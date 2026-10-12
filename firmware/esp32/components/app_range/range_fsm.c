/* range_fsm.c - see range_fsm.h. README s.6.3, PROPOSED. */
#include "range_fsm.h"
#include <math.h>
#include <string.h>

static uint32_t el(uint32_t now, uint32_t since) { return now - since; }

static float clampf(float v, float lo, float hi)
{
    if (hi < lo) {
        hi = lo;
    }
    return v < lo ? lo : (v > hi ? hi : v);
}

const char *range_state_str(range_state_t s)
{
    static const char *const n[] = {"OFF", "RAMP", "SEARCH", "TRACK", "LOS", "MANUAL", "FAULT"};
    return (unsigned)s < 7u ? n[s] : "?";
}

int32_t range_manual_code_step(int32_t cur, int32_t target, float bias_v, float hv_min_v, float hv_max_v,
                               float v_per_code, int32_t max_step, int32_t code_min)
{
    if (hv_max_v < hv_min_v) {
        hv_max_v = hv_min_v;
    }
    /* code that would give hv_max / hv_min at the present bias (linear model) */
    int32_t lo = (int32_t)ceilf((float)cur - (hv_max_v - bias_v) / v_per_code);
    int32_t hi = (int32_t)floorf((float)cur + (bias_v - hv_min_v) / v_per_code);
    if (lo < code_min) lo = code_min;
    if (hi > 0xFFF) hi = 0xFFF;
    if (hi < lo) hi = lo;
    int32_t want = target < lo ? lo : (target > hi ? hi : target);
    int32_t d = want - cur;
    if (d > max_step) d = max_step;
    if (d < -max_step) d = -max_step;
    return cur + d;
}

void range_fsm_init(range_fsm_t *f)
{
    memset(f, 0, sizeof(*f));
    f->state = RANGE_OFF;
    f->down_trial_enable = true;
    f->trial_interval = RFSM_TRIAL_INTERVAL_MS;   /* README s.6.3, PROPOSED */
}

void range_fsm_set_last_lock(range_fsm_t *f, float v_lock)
{
    f->v_lock = v_lock;
    f->have_lock = true;
}

static void win_clear(range_fsm_t *f) { f->win_n = 0; f->win_head = 0; }

static void win_push(range_fsm_t *f, uint32_t now, uint8_t c)
{
    f->win_t[f->win_head] = now;
    f->win_c[f->win_head] = c;
    f->win_head = (uint8_t)((f->win_head + 1) % RFSM_CLASS_WIN);
    if (f->win_n < RFSM_CLASS_WIN) {
        f->win_n++;
    }
}

/* Average class over the last RFSM_TRACK_AVG_MS; returns false until the
 * window spans at least 95 % of the averaging time (avoids acting on 1 sample). */
static bool win_avg(const range_fsm_t *f, uint32_t now, float *avg)
{
    uint32_t sum = 0, n = 0, oldest = 0;
    for (uint8_t i = 0; i < f->win_n; i++) {
        uint8_t idx = (uint8_t)((f->win_head + RFSM_CLASS_WIN - 1 - i) % RFSM_CLASS_WIN);
        uint32_t age = el(now, f->win_t[idx]);
        if (age > RFSM_TRACK_AVG_MS) {
            break;
        }
        sum += f->win_c[idx];
        n++;
        oldest = age;
    }
    if (n == 0 || oldest < (RFSM_TRACK_AVG_MS * 95u) / 100u) {
        return false;
    }
    *avg = (float)sum / (float)n;
    return true;
}

static void enter(range_fsm_t *f, range_state_t s, uint32_t now)
{
    f->state = s;
    f->state_since_ms = now;
    f->clean_set = false;
    f->bad_set = false;
    f->trial_active = false;
    win_clear(f);
    f->bump_hold = false;
    f->bump_n = 0;
}

static void enter_search(range_fsm_t *f, float start, uint32_t now)
{
    enter(f, RANGE_SEARCH, now);
    f->target = start;
    f->search_last_step = now;
    f->max_set = false;
}

static void enter_track(range_fsm_t *f, uint32_t now)
{
    enter(f, RANGE_TRACK, now);
    f->los_report = false;
}

void range_fsm_step(range_fsm_t *f, const range_in_t *in, range_out_t *out)
{
    const uint32_t now = in->now_ms;
    const bool mode_auto = in->automatic && in->bus_mode;
    const float hv_min = in->hv_min_v;
    const float hv_max = in->hv_max_v < in->hv_min_v ? in->hv_min_v : in->hv_max_v;
    bool tia_20k = in->tia_20k;
    bool tia_changed = false;

    const bool blanking = f->have_switched && el(now, f->last_switch) < RFSM_BLANK_MS;
    const bool link_ok = in->link_valid && !blanking;

    /* ---- global transitions ---- */
    if (in->fault) {
        if (f->state != RANGE_FAULT) {
            enter(f, RANGE_FAULT, now);
        }
    } else if (f->state == RANGE_FAULT) {
        enter(f, RANGE_OFF, now);       /* cleared: wait for a deliberate enable */
    }
    if (f->state != RANGE_FAULT && !in->hv_on && f->state != RANGE_OFF) {
        enter(f, RANGE_OFF, now);
    }

    /* ---- guard condition (evaluated first so states do not raise bias while over) ---- */
    const bool guard_states = f->state == RANGE_SEARCH || f->state == RANGE_TRACK ||
                              f->state == RANGE_LOS || f->state == RANGE_MANUAL;
    const bool guard_on = guard_states && (in->automatic || in->tia_auto);
    bool over_active = false;
    if (guard_on) {
        bool over = in->rssi_drop_mv > RFSM_GUARD_HI_MV || in->rssi_rail;
        if (over) {
            if (!f->over_set) {
                f->over_set = true;
                f->over_since = now;
            }
        } else {
            f->over_set = false;
        }
        over_active = f->over_set && el(now, f->over_since) >= RFSM_GUARD_HI_MS;
    } else {
        f->over_set = false;
        f->lo_set = false;
    }

    /* ---- state machine ---- */
    switch (f->state) {
    case RANGE_OFF:
        if (in->hv_on && !in->fault) {
            enter(f, RANGE_RAMP, now);
            f->ramp_target = f->have_lock ? clampf(in->hv_set_v, hv_min, hv_max) : hv_min;
            f->target = f->ramp_target;
            f->arrive_set = false;
        } else {
            f->target = hv_min;
        }
        break;

    case RANGE_RAMP: {
        bool near = (in->bias_v >= f->ramp_target - RFSM_RAMP_ARRIVE_V &&
                     in->bias_v <= f->ramp_target + RFSM_RAMP_ARRIVE_V) ||
                    (in->bias_v >= in->hv_set_v - RFSM_RAMP_ARRIVE_V &&
                     in->bias_v <= in->hv_set_v + RFSM_RAMP_ARRIVE_V);
        if (near) {
            if (!f->arrive_set) {
                f->arrive_set = true;
                f->arrive_since = now;
            } else if (el(now, f->arrive_since) >= RFSM_RAMP_ARRIVE_MS) {
                if (mode_auto) {
                    enter_search(f, f->ramp_target, now);
                } else {
                    enter(f, RANGE_MANUAL, now);
                    f->target = clampf(in->hv_set_v, hv_min, hv_max);
                }
            }
        } else {
            f->arrive_set = false;
        }
        break;
    }

    case RANGE_SEARCH: {
        if (!mode_auto) {
            enter(f, RANGE_MANUAL, now);
            f->target = clampf(in->hv_set_v, hv_min, hv_max);
            break;
        }
        const bool clean = link_ok && in->err_class == 0;
        if (blanking) {
            /* metrics ignored: neither start nor reset the clean timer */
        } else if (clean) {
            if (!f->clean_set) {
                f->clean_set = true;
                f->clean_since = now;
            } else if (el(now, f->clean_since) >= RFSM_SEARCH_CLEAN_MS) {
                f->v_lock = f->target;                       /* record V_lock (pre-margin) */
                f->have_lock = true;
                f->target = clampf(f->target + RFSM_LOCK_MARGIN_V, hv_min, hv_max);
                enter_track(f, now);
                f->clean_set = true;
                f->clean_since = now;
                f->trial_interval = RFSM_TRIAL_INTERVAL_MS;
                break;
            }
        } else {
            f->clean_set = false;
        }
        /* raise while no clean run is in progress */
        if (!f->clean_set && !over_active && el(now, f->search_last_step) >= RFSM_SEARCH_STEP_MS) {
            f->search_last_step = now;
            if (f->target < hv_max) {
                f->target = clampf(f->target + RFSM_SEARCH_STEP_V, hv_min, hv_max);
            }
        }
        /* hv_max reached with no lock: report, retry from hv_min every 30 s */
        if (f->target >= hv_max - 0.001f) {
            if (!f->max_set) {
                f->max_set = true;
                f->max_since = now;
            }
            f->los_report = true;
            if (el(now, f->max_since) >= RFSM_SEARCH_RETRY_MS) {
                f->target = hv_min;
                f->max_set = false;
                f->search_last_step = now;
            }
        } else {
            f->max_set = false;
        }
        break;
    }

    case RANGE_TRACK: {
        if (!mode_auto) {
            enter(f, RANGE_MANUAL, now);
            f->target = clampf(in->hv_set_v, hv_min, hv_max);
            break;
        }
        const bool bad = !in->link_valid || in->err_class == RFSM_CLASS_LOS;
        const bool clean = in->link_valid && in->err_class == 0;
        if (!blanking) {
            win_push(f, now, bad ? (uint8_t)RFSM_CLASS_LOS : in->err_class);
            if (bad) {
                if (!f->bad_set) {
                    f->bad_set = true;
                    f->bad_since = now;
                } else if (el(now, f->bad_since) >= RFSM_LOS_ENTER_MS) {
                    enter(f, RANGE_LOS, now);
                    f->los_since = now;
                    break;
                }
            } else {
                f->bad_set = false;
            }
            if (clean) {
                if (!f->clean_set) {
                    f->clean_set = true;
                    f->clean_since = now;
                }
            } else {
                f->clean_set = false;
            }
        }
        bool acted = false;
        if (f->trial_active && !blanking) {
            if (!clean) {                                   /* any class >= 1 (or invalid) */
                f->target = clampf(f->trial_prev, hv_min, hv_max);   /* restore +4 V */
                f->trial_active = false;
                f->trial_interval *= 2u;                    /* double the interval */
                if (f->trial_interval > RFSM_TRIAL_INTERVAL_MAX) {
                    f->trial_interval = RFSM_TRIAL_INTERVAL_MAX;
                }
                f->clean_set = false;
                acted = true;
            } else if (el(now, f->trial_start) >= RFSM_TRIAL_HOLD_MS) {
                f->trial_active = false;                    /* trial accepted */
                f->clean_set = true;
                f->clean_since = now;
            }
        }
        /* upward correction on class >= 2 over 2 s, max +6 V per 5 s */
        if (!acted && !blanking && !over_active && !f->trial_active) {
            float avg;
            bool hold = f->bump_hold && (int32_t)(now - f->bump_hold_until) < 0;
            if (!hold && win_avg(f, now, &avg) && avg >= RFSM_TRACK_CLASS_THRESH && f->target < hv_max) {
                /* count bumps inside the last 5 s */
                uint8_t k = 0;
                uint32_t keep[3];
                for (uint8_t i = 0; i < f->bump_n; i++) {
                    if (el(now, f->bump_t[i]) < RFSM_TRACK_BUMP_WIN_MS) {
                        keep[k++] = f->bump_t[i];
                    }
                }
                memcpy(f->bump_t, keep, sizeof(uint32_t) * k);
                f->bump_n = k;
                if ((float)(k + 1u) * RFSM_TRACK_BUMP_V <= RFSM_TRACK_BUMP_MAX_V + 0.001f) {
                    f->target = clampf(f->target + RFSM_TRACK_BUMP_V, hv_min, hv_max);
                    f->bump_t[f->bump_n++] = now;
                    f->bump_hold = true;
                    f->bump_hold_until = now + RFSM_TRACK_BUMP_WAIT_MS;
                    acted = true;
                }
            }
        }
        /* down-trial */
        if (!acted && f->down_trial_enable && !blanking && !over_active && !f->trial_active &&
            f->clean_set && el(now, f->clean_since) >= f->trial_interval &&
            f->target > f->v_lock + 0.01f && f->target - RFSM_TRIAL_STEP_V >= hv_min) {
            f->trial_prev = f->target;
            f->target -= RFSM_TRIAL_STEP_V;
            f->trial_active = true;
            f->trial_start = now;
        }
        break;
    }

    case RANGE_LOS:
        if (!mode_auto) {
            enter(f, RANGE_MANUAL, now);
            f->target = clampf(in->hv_set_v, hv_min, hv_max);
            break;
        }
        if (link_ok && in->err_class != RFSM_CLASS_LOS) {
            enter_track(f, now);
        } else if (el(now, f->los_since) >= RFSM_LOS_HOLD_MS) {
            enter_search(f, clampf(f->v_lock - RFSM_LOS_RESTART_BACK_V, hv_min, hv_max), now);
        }
        break;

    case RANGE_MANUAL:
        f->target = clampf(in->hv_set_v, hv_min, hv_max);
        if (mode_auto) {
            enter_search(f, clampf(in->bias_v, hv_min, hv_max), now);
        }
        break;

    case RANGE_FAULT:
        f->target = hv_min;
        break;
    }

    /* ---- TIA guard actions ---- */
    if (guard_on && (f->state == RANGE_SEARCH || f->state == RANGE_TRACK ||
                     f->state == RANGE_LOS || f->state == RANGE_MANUAL)) {
        const bool switch_ok = !f->have_switched || el(now, f->last_switch) >= RFSM_SWITCH_MIN_MS;
        bool do_switch = false;
        if (over_active) {
            f->lo_set = false;
            bool auto_states = f->state != RANGE_MANUAL;
            if (auto_states && f->target > hv_min + 0.05f) {
                if (!f->lower_valid || el(now, f->last_lower) >= RFSM_GUARD_LOWER_MS) {
                    f->target = clampf(f->target - RFSM_GUARD_LOWER_V, hv_min, hv_max);
                    f->last_lower = now;
                    f->lower_valid = true;
                    f->trial_active = false;
                }
            } else if (tia_20k && switch_ok) {
                tia_20k = false;                            /* 20k -> 5k */
                do_switch = true;
            }
        } else if (!tia_20k && in->rssi_drop_mv < RFSM_GUARD_LO_MV && !in->rssi_rail) {
            if (!f->lo_set) {
                f->lo_set = true;
                f->lo_since = now;
            }
            if (el(now, f->lo_since) >= RFSM_GUARD_LO_MS && switch_ok) {
                tia_20k = true;                             /* 5k -> 20k */
                do_switch = true;
            }
        } else {
            f->lo_set = false;
        }
        if (do_switch) {
            tia_changed = true;
            f->have_switched = true;
            f->last_switch = now;
            f->over_set = false;
            f->lo_set = false;
            f->clean_set = false;
            f->bad_set = false;
            win_clear(f);
            f->trial_active = false;
        }
    }

    out->state = f->state;
    out->tia_20k = tia_20k;
    out->tia_changed = tia_changed;
    out->los_report = f->los_report && f->state == RANGE_SEARCH;
    out->bias_target_v = (f->state == RANGE_OFF || f->state == RANGE_FAULT) ? hv_min : f->target;
}
