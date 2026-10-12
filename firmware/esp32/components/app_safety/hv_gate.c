/* hv_gate.c - see hv_gate.h. Pure C; PROPOSED, host-tested only. */
#include "hv_gate.h"
#include <math.h>
#include <string.h>
#include "board_pins.h"

static uint32_t el(uint32_t now, uint32_t since) { return now - since; }

static float clampf(float v, float lo, float hi)
{
    if (hi < lo) {
        hi = lo;
    }
    return v < lo ? lo : (v > hi ? hi : v);
}

void hvg_init(hvg_t *g)
{
    memset(g, 0, sizeof(*g));
    g->state = HVG_OFF;
    g->hv_dis = true;
    g->code = HVG_SAFE_CODE;
    g->code_done = HVG_SAFE_CODE;
    g->gen = 1;
}

int hvg_code_min(float hv_max_v)
{
    int c = HVG_SAFE_CODE - (int)((hv_max_v + HVG_OVER_MARGIN_V - BOARD_HV_V_AT_SAFE_CODE) / BOARD_HV_V_PER_CODE);
    return c < 0 ? 0 : (c > HVG_SAFE_CODE ? HVG_SAFE_CODE : c);
}

bool hvg_hv_dis(const hvg_t *g) { return g->hv_dis; }
hvg_state_t hvg_state(const hvg_t *g) { return g->state; }

const char *hvg_state_name(hvg_state_t s)
{
    static const char *const n[] = {"off", "arming", "ramp_up", "on", "ramp_down", "fault"};
    return (unsigned)s <= HVG_FAULT ? n[s] : "?";
}

const char *hvg_reason_name(hvg_reason_t r)
{
    static const char *const n[] = {"none", "ramp timeout", "bias over limit", "bias collapsed",
                                    "bias not following", "arm failed", "dac write failed",
                                    "sense stale", "hv stuck", "precondition"};
    return (unsigned)r <= HVG_R_PRECONDITION ? n[r] : "?";
}

/* ---- internal helpers ----------------------------------------------------- */
static void dis_high(hvg_t *g, uint32_t now)
{
    if (!g->hv_dis) {
        g->hv_dis = true;
        g->dis_since_ms = now;
        g->dis_since_set = true;
    }
}

/* New generation: every older report and pending command is void. */
static void new_gen(hvg_t *g)
{
    g->gen++;
    g->cmd_pending = false;
    g->rep_valid = false;
}

static void queue_cmd(hvg_t *g, hvg_cmd_kind_t kind, uint16_t code)
{
    g->cmd.kind = kind;
    g->cmd.code = code;
    g->cmd.gen = g->gen;
    g->cmd_pending = true;
}

/* Trip: HV_DIS high now, FAULT (a blocking fault is or becomes latched) or OFF,
 * DAC_HV back to 0xFFF afterwards (README s.4 step 10, fault path). */
static void trip(hvg_t *g, const hvg_in_t *in, hvg_out_t *out, fault_word_t bits, hvg_reason_t why)
{
    dis_high(g, in->now_ms);
    new_gen(g);
    g->needs_safe = true;
    g->next_safe_ms = in->now_ms;
    g->in_band_set = false;
    g->state = (in->blocking_fault || (bits & FAULT_HV_BLOCKING_MASK)) ? HVG_FAULT : HVG_OFF;
    out->fault_bits |= bits;
    if (out->reason == HVG_R_NONE) {
        out->reason = why;
    }
    g->last_reason = out->reason;
}

static float ramp_target(const hvg_t *g, const hvg_in_t *in)
{
    float lo = in->hv_min_v, hi = in->hv_max_v < in->hv_min_v ? in->hv_min_v : in->hv_max_v;
    float t = g->target_override_v > 0 ? g->target_override_v : in->ramp_target_v;
    if (t <= 0) {
        t = lo;
    }
    if (g->cap_v > 0 && hi > g->cap_v - 1.0f) {
        hi = g->cap_v - 1.0f;
    }
    return clampf(t, lo, hi);
}

static float over_limit(const hvg_t *g, const hvg_in_t *in)
{
    return g->cap_v > 0 ? g->cap_v : in->hv_max_v + HVG_OVER_MARGIN_V;
}

/* ---- requests ------------------------------------------------------------- */
bool hvg_request(hvg_t *g, bool on, const hvg_in_t *in, float cap_v, float target_v)
{
    const uint32_t now = in->now_ms;
    if (on) {
        if (in->blocking_fault || !in->dac_verified || !in->adc_ok || g->needs_safe) {
            return false;
        }
        switch (g->state) {
        case HVG_ON:
            return true;                    /* idempotent, nothing restarts */
        case HVG_RAMP_DOWN:
        case HVG_FAULT:
            return false;
        case HVG_OFF:
        case HVG_ARMING:
        case HVG_RAMP_UP:
        default:
            break;
        }
        /* Fresh request, or restart of one in flight: always through ARMING. */
        dis_high(g, now);
        new_gen(g);
        g->state = HVG_ARMING;
        g->cap_v = cap_v > 0 ? cap_v : 0;
        g->target_override_v = target_v > 0 ? target_v : 0;
        g->arm_t0 = now;
        g->code = HVG_SAFE_CODE;
        g->floor_set = false;
        g->under_count = 0;
        g->in_band_set = false;
        g->down_code_valid = false;
        queue_cmd(g, HVG_CMD_ARM, HVG_SAFE_CODE);
        return true;
    }
    switch (g->state) {
    case HVG_ARMING:
        dis_high(g, now);                   /* already high; abort the request */
        new_gen(g);
        g->state = HVG_OFF;
        g->needs_safe = true;
        g->next_safe_ms = now;
        break;
    case HVG_RAMP_UP:
    case HVG_ON:
        new_gen(g);
        g->state = HVG_RAMP_DOWN;
        g->down_t0 = now;
        g->down_code_valid = false;
        g->in_band_set = false;
        break;
    default:
        break;
    }
    return true;
}

void hvg_force_off(hvg_t *g, const hvg_in_t *in)
{
    dis_high(g, in->now_ms);
    new_gen(g);
    g->needs_safe = true;
    g->next_safe_ms = in->now_ms;
    g->in_band_set = false;
    g->state = in->blocking_fault ? HVG_FAULT : HVG_OFF;
}

bool hvg_take_cmd(hvg_t *g, hvg_cmd_t *out)
{
    if (!g->cmd_pending || g->cmd_inflight) {
        return false;
    }
    *out = g->cmd;
    g->inflight = g->cmd;
    g->cmd_inflight = true;
    g->cmd_pending = false;
    return true;
}

void hvg_report(hvg_t *g, uint32_t gen, bool ok)
{
    g->cmd_inflight = false;
    if (gen != g->gen) {
        return;                             /* stale: belongs to an older request */
    }
    g->rep_valid = true;
    g->rep_ok = ok;
    g->rep_gen = gen;
    g->rep_kind = g->inflight.kind;
    g->code_done = ok ? g->inflight.code : g->code_done;
}

/* ---- the step ---------------------------------------------------------------- */
static bool not_following(const hvg_t *g, const hvg_in_t *in)
{
    int code = in->dac_code >= 0 ? in->dac_code : g->code_done;
    return g->floor_set && (HVG_SAFE_CODE - code) > HVG_NF_CODES && (in->bias_v - g->floor_v) < HVG_NF_RISE_V;
}

void hvg_step(hvg_t *g, const hvg_in_t *in, hvg_out_t *out)
{
    const uint32_t now = in->now_ms;
    memset(out, 0, sizeof(*out));
    if (!g->dis_since_set) {
        g->dis_since_ms = now;
        g->dis_since_set = true;
    }

    /* Result of the executor's last command, if it belongs to this generation. */
    bool rep = false, rep_ok = false;
    hvg_cmd_kind_t rk = HVG_CMD_NONE;
    if (g->rep_valid) {
        g->rep_valid = false;
        if (g->rep_gen == g->gen) {
            rep = true;
            rep_ok = g->rep_ok;
            rk = g->rep_kind;
        }
    }

    /* ---- checks that apply while HV_DIS is low or about to go low ---- */
    bool tripped = false;
    if (!g->hv_dis || g->state == HVG_ARMING) {
        if (in->blocking_fault || !in->dac_verified || !in->adc_ok) {
            trip(g, in, out, 0, HVG_R_PRECONDITION);
            tripped = true;
        }
    }
    if (!tripped && !g->hv_dis && in->sense_ok) {
        /* Keep the "floor" baseline of the not-following check fresh while the code sits at the
         * minimum-bias end (the supply floor may drift with temperature: UNRESOLVED). */
        const int code = in->dac_code >= 0 ? in->dac_code : g->code_done;
        if (code >= HVG_SAFE_CODE - HVG_FLOOR_REFRESH_CODES) {
            g->floor_v = in->bias_v;
            g->floor_set = true;
        }
    }
    if (!tripped && !g->hv_dis) {
        if (!in->sense_ok) {
            trip(g, in, out, FAULT_I2C_ADC, HVG_R_SENSE_STALE);
            out->adc_bad = true;
            tripped = true;
        } else if (in->bias_v > over_limit(g, in)) {
            trip(g, in, out, FAULT_HV_OVER, HVG_R_OVER);
            tripped = true;
        } else if ((g->state == HVG_RAMP_UP || g->state == HVG_ON) && not_following(g, in)) {
            trip(g, in, out, FAULT_HV_UNDER, HVG_R_NOT_FOLLOWING);
            tripped = true;
        }
    }

    /* ---- state machine (skipped on the step that tripped) ---- */
    switch (tripped ? -1 : (int)g->state) {
    default:
        break;
    case (int)HVG_OFF:
        if (in->blocking_fault) {
            g->state = HVG_FAULT;           /* faults latched while off are reflected */
        }
        break;

    case (int)HVG_FAULT:
        if (!in->blocking_fault) {
            g->state = HVG_OFF;             /* cleared: wait for a deliberate enable */
        }
        break;

    case (int)HVG_ARMING:
        if (rep && rk == HVG_CMD_ARM) {
            if (rep_ok) {
                /* The only place HV_DIS goes low: 0xFFF written and read back in this request. */
                g->hv_dis = false;
                g->state = HVG_RAMP_UP;
                g->ramp_t0 = now;
                g->last_step_ms = now;
                g->code = HVG_SAFE_CODE;
                g->under_ref_v = ramp_target(g, in);
                g->in_band_set = false;
            } else {
                trip(g, in, out, FAULT_I2C_DAC, HVG_R_ARM_FAILED);
            }
        } else if (el(now, g->arm_t0) > HVG_ARM_TIMEOUT_MS) {
            trip(g, in, out, FAULT_I2C_DAC, HVG_R_ARM_FAILED);
        }
        break;

    case (int)HVG_RAMP_UP: {
        if (rep && rk == HVG_CMD_WRITE && !rep_ok) {
            trip(g, in, out, FAULT_I2C_DAC, HVG_R_DAC_WRITE);
            break;
        }
        const bool busy = g->cmd_pending || g->cmd_inflight;
        const float tgt = ramp_target(g, in);
        const float err = tgt - in->bias_v;
        if (!busy && in->sense_ok && el(now, g->last_step_ms) >= HVG_STEP_MS) {
            const int max_step = (int)fminf((float)HVG_MAX_STEP_CODES,
                                            HVG_RAMP_UP_V_PER_S * (HVG_STEP_MS / 1000.0f) / BOARD_HV_V_PER_CODE);
            int step = (int)lroundf(err / BOARD_HV_V_PER_CODE);
            step = step > max_step ? max_step : (step < -max_step ? -max_step : step);
            int code = g->code - step;      /* lower code = higher bias */
            const int cmin = hvg_code_min(in->hv_max_v);
            code = code < cmin ? cmin : (code > HVG_SAFE_CODE ? HVG_SAFE_CODE : code);
            g->last_step_ms = now;
            if (code != g->code) {
                if (!g->floor_set && g->code == HVG_SAFE_CODE) {
                    g->floor_v = in->bias_v;    /* bias where the code leaves the floor */
                    g->floor_set = true;
                }
                g->code = code;
                queue_cmd(g, HVG_CMD_WRITE, (uint16_t)code);
            }
        }
        /* Arrival: within 2 V for 1 s, or pinned at the minimum-bias end with the
         * bias above target (the supply cannot go lower). README s.4 step 9(d). */
        const bool in_band = fabsf(err) < HVG_ARRIVE_BAND_V ||
                             (g->code_done == HVG_SAFE_CODE && g->code == HVG_SAFE_CODE && err < 0);
        if (!in_band) {
            g->in_band_set = false;
        } else if (!g->in_band_set) {
            g->in_band_set = true;
            g->in_band_since = now;
        } else if (el(now, g->in_band_since) >= HVG_ARRIVE_HOLD_MS && !busy && g->code_done == g->code) {
            g->state = HVG_ON;
            if (!g->floor_set) {
                g->floor_v = in->bias_v;
                g->floor_set = true;
            }
            g->last_seq = in->sample_seq;
            g->under_count = 0;
            break;
        }
        if (el(now, g->ramp_t0) > HVG_RAMP_TIMEOUT_MS) {
            trip(g, in, out, FAULT_HV_UNDER, HVG_R_RAMP_TIMEOUT);
        }
        break;
    }

    case (int)HVG_ON:
        if (in->sample_seq != g->last_seq) {
            g->last_seq = in->sample_seq;
            if (in->bias_v * 100.0f < g->under_ref_v * (float)HVG_UNDER_PERCENT) {
                if (++g->under_count >= HVG_UNDER_SAMPLES) {
                    trip(g, in, out, FAULT_HV_UNDER, HVG_R_UNDER);
                }
            } else {
                g->under_count = 0;
            }
        }
        break;

    case (int)HVG_RAMP_DOWN: {
        if (rep && rk == HVG_CMD_WRITE) {
            if (!rep_ok) {
                trip(g, in, out, FAULT_I2C_DAC, HVG_R_DAC_WRITE);
                break;
            }
            if (g->code_done >= HVG_SAFE_CODE) {
                /* Safe code reached and acknowledged: now HV_DIS goes high. */
                dis_high(g, now);
                new_gen(g);
                g->state = HVG_OFF;
                g->needs_safe = false;
                break;
            }
        }
        const bool busy = g->cmd_pending || g->cmd_inflight;
        if (!busy) {
            if (!g->down_code_valid) {
                int c = in->dac_code >= 0 ? in->dac_code : 0;   /* unknown: assume the longest walk */
                g->code = c > HVG_SAFE_CODE ? HVG_SAFE_CODE : c;
                g->down_code_valid = true;
                g->last_step_ms = now - HVG_STEP_MS;
            }
            if (el(now, g->last_step_ms) >= HVG_STEP_MS && g->code < HVG_SAFE_CODE) {
                const int cps = (int)ceilf(HVG_RAMP_DOWN_V_PER_S * (HVG_STEP_MS / 1000.0f) / BOARD_HV_V_PER_CODE);
                int code = g->code + cps;
                g->code = code > HVG_SAFE_CODE ? HVG_SAFE_CODE : code;
                g->last_step_ms = now;
                queue_cmd(g, HVG_CMD_WRITE, (uint16_t)g->code);
            } else if (g->code >= HVG_SAFE_CODE && g->down_code_valid && g->code_done < HVG_SAFE_CODE) {
                queue_cmd(g, HVG_CMD_WRITE, HVG_SAFE_CODE);
            } else if (g->code >= HVG_SAFE_CODE && g->down_code_valid && g->code_done >= HVG_SAFE_CODE) {
                /* the DAC was already at the safe code when the turn-off began */
                dis_high(g, now);
                new_gen(g);
                g->state = HVG_OFF;
                g->needs_safe = false;
                break;
            }
        }
        if (el(now, g->down_t0) > HVG_DOWN_TIMEOUT_MS) {
            /* Safe direction regardless: HV_DIS high, safe write retried. */
            dis_high(g, now);
            new_gen(g);
            g->state = HVG_OFF;
            g->needs_safe = true;
            g->next_safe_ms = now;
            out->reason = HVG_R_DAC_WRITE;
        }
        break;
    }
    }

    /* ---- stuck bias while disabled (protocol s.5 bit 5): report only ---- */
    if (g->hv_dis && in->sense_ok && in->bias_v > HVG_STUCK_V && el(now, g->dis_since_ms) > HVG_STUCK_AFTER_MS) {
        out->fault_bits |= FAULT_HV_STUCK;
        if (out->reason == HVG_R_NONE) {
            out->reason = HVG_R_STUCK;
        }
    }

    /* ---- post-fault safe write (README s.4 step 10, "afterwards") ---- */
    if (g->hv_dis && (g->state == HVG_OFF || g->state == HVG_FAULT)) {
        if (rep && rk == HVG_CMD_SAFE) {
            if (rep_ok) {
                g->needs_safe = false;
                g->code = g->code_done = HVG_SAFE_CODE;
            } else {
                g->next_safe_ms = now + HVG_SAFE_RETRY_MS;
            }
        }
        if (g->needs_safe && !g->cmd_pending && !g->cmd_inflight && (int32_t)(now - g->next_safe_ms) >= 0) {
            g->next_safe_ms = now + HVG_SAFE_RETRY_MS;   /* retry period if this one is lost or fails */
            queue_cmd(g, HVG_CMD_SAFE, HVG_SAFE_CODE);
        }
    }

    out->hv_dis = g->hv_dis;
    out->state = g->state;
    out->cmd_ready = g->cmd_pending;
}
