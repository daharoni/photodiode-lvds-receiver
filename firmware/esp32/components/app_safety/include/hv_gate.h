/*
 * hv_gate.h - HV enable / ramp state machine, pure C (no ESP-IDF includes).
 * Host-tested in firmware/esp32/test_host/test_hv_gate.c. PROPOSED; nothing
 * here has run on hardware. Review findings 2, 4, 5, 9, 16 (2026-10-12).
 *
 * States: OFF, ARMING (write DAC_HV = 0xFFF and read it back; HV_DIS still
 * high), RAMP_UP, ON, RAMP_DOWN, FAULT. Rules (README s.4 steps 9 and 10, s.5):
 *  - HV_DIS may go low only from ARMING, after the 0xFFF write + readback
 *    reported OK for THIS request (generation counter; stale reports ignored).
 *  - Any fault, any trip, or hvg_force_off() raises HV_DIS in the same call.
 *  - A new on-request while ARMING or RAMP_UP restarts from ARMING.
 *  - A request is refused while a safe-write is pending, the DAC or ADC is not
 *    verified, a blocking fault is latched, or a turn-off ramp is running.
 *
 * The machine does no I/O. The caller (app_safety.c) holds one lock around
 * every call, applies hvg_hv_dis() to the pin, and runs the I2C work the
 * machine asks for: hvg_take_cmd() hands out one DAC command; the executor
 * reports the result with hvg_report(gen, ok).
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "fault.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- constants (source in each comment; all PROPOSED first guesses) ------ */
#define HVG_SAFE_CODE          0xFFF   /* README s.4 step 5: minimum bias */
#define HVG_STEP_MS            100     /* README s.4 step 9(c): each 100 ms */
#define HVG_RAMP_UP_V_PER_S    20.0f   /* README s.4 step 9(c), PROPOSED */
#define HVG_MAX_STEP_CODES     150     /* README s.4 step 9(c) */
#define HVG_ARRIVE_BAND_V      2.0f    /* README s.4 step 9(d) */
#define HVG_ARRIVE_HOLD_MS     1000    /* README s.4 step 9(d) */
#define HVG_RAMP_TIMEOUT_MS    10000   /* README s.4 step 9(d) */
#define HVG_RAMP_DOWN_V_PER_S  50.0f   /* README s.4 step 10 */
#define HVG_ARM_TIMEOUT_MS     2000    /* UNRESOLVED: 0xFFF write+readback not done in time */
#define HVG_DOWN_TIMEOUT_MS    10000   /* UNRESOLVED: turn-off walk not finished: HV_DIS goes high anyway */
#define HVG_SAFE_RETRY_MS      500     /* UNRESOLVED: retry of the post-fault 0xFFF write */
#define HVG_OVER_MARGIN_V      5.0f    /* README s.5: hv_max + 5 V (default over limit) */
#define HVG_UNDER_PERCENT      70      /* README s.5: collapse below 70 % of the ramp target */
#define HVG_UNDER_SAMPLES      2       /* UNRESOLVED: distinct samples required below 70 % */
#define HVG_SENSE_STALE_MS     500     /* UNRESOLVED: first guess (sense round about 100 ms) */
#define HVG_STUCK_V            20.0f   /* protocol s.5 bit 5 */
#define HVG_STUCK_AFTER_MS     30000   /* protocol s.5 bit 5 */
/* "Bias not following" (finding 4, PROPOSED): code moved more than 400 codes
 * (about 6 V at 14.95 mV per code) below 0xFFF while the measured bias has
 * not risen 2 V above the bias seen when the code left the floor. */
#define HVG_NF_CODES           400
#define HVG_NF_RISE_V          2.0f
#define HVG_FLOOR_REFRESH_CODES 20     /* baseline is refreshed while the code is within 20 of 0xFFF */

typedef enum { HVG_OFF = 0, HVG_ARMING, HVG_RAMP_UP, HVG_ON, HVG_RAMP_DOWN, HVG_FAULT } hvg_state_t;

typedef enum {
    HVG_R_NONE = 0, HVG_R_RAMP_TIMEOUT, HVG_R_OVER, HVG_R_UNDER, HVG_R_NOT_FOLLOWING,
    HVG_R_ARM_FAILED, HVG_R_DAC_WRITE, HVG_R_SENSE_STALE, HVG_R_STUCK, HVG_R_PRECONDITION,
} hvg_reason_t;

typedef enum { HVG_CMD_NONE = 0, HVG_CMD_ARM, HVG_CMD_WRITE, HVG_CMD_SAFE } hvg_cmd_kind_t;

typedef struct {
    hvg_cmd_kind_t kind;   /* ARM: write code then read it back (code = 0xFFF); WRITE/SAFE: write only */
    uint16_t code;
    uint32_t gen;
} hvg_cmd_t;

typedef struct {
    uint32_t now_ms;
    bool blocking_fault;       /* (fault word & FAULT_HV_BLOCKING_MASK) != 0 */
    bool dac_verified, adc_ok;
    bool sense_ok;             /* a valid snapshot younger than HVG_SENSE_STALE_MS exists */
    uint32_t sample_seq;       /* changes with every new sense round (debounce) */
    float bias_v;              /* measured APD bias */
    int dac_code;              /* last code written to DAC_HV, -1 if unknown */
    float hv_set_v, hv_min_v, hv_max_v;
    float ramp_target_v;       /* from app_range (finding 16); <= 0: use hv_min */
} hvg_in_t;

typedef struct {
    bool hv_dis;               /* true = HV disabled (pin high) */
    hvg_state_t state;
    fault_word_t fault_bits;   /* to latch this step (HV_UNDER, HV_OVER, I2C_*, HV_STUCK) */
    hvg_reason_t reason;       /* why fault_bits / a trip happened, HVG_R_NONE otherwise */
    bool adc_bad;              /* caller clears its adc_ok flag */
    bool cmd_ready;            /* a DAC command is waiting for hvg_take_cmd() */
} hvg_out_t;

typedef struct {
    hvg_state_t state;
    bool hv_dis;
    uint32_t gen;
    /* request context */
    float cap_v;               /* per-request absolute cap, 0 = hv_max + margin */
    float target_override_v;   /* per-request ramp target, <= 0 = follow in->ramp_target_v */
    float under_ref_v;         /* 70 % reference, the clamped ramp target of this request */
    /* DAC command slot */
    hvg_cmd_t cmd, inflight;
    bool cmd_pending, cmd_inflight;
    bool rep_valid, rep_ok;
    uint32_t rep_gen;
    hvg_cmd_kind_t rep_kind;
    int code;                  /* machine's commanded code while ramping */
    int code_done;             /* last code confirmed by a report */
    bool needs_safe;
    uint32_t next_safe_ms;
    /* timing */
    uint32_t arm_t0, ramp_t0, down_t0, last_step_ms, dis_since_ms, in_band_since;
    bool in_band_set, down_code_valid, dis_since_set;
    /* monitors */
    bool floor_set;
    float floor_v;
    uint32_t last_seq;
    int under_count;
    hvg_reason_t last_reason;
} hvg_t;

void hvg_init(hvg_t *g);

/** Lowest DAC code allowed for a given hv_max (open-loop bound, finding 4):
 *  0xFFF - (hv_max + 5 - BOARD_HV_V_AT_SAFE_CODE) / BOARD_HV_V_PER_CODE,
 *  clamped to 0..0xFFF. Note: with the nominal 14.95 mV per code the DAC spans
 *  only about 61 V, so for hv_max above about 160 V the bound is 0 (inactive)
 *  and the not-following trip is the only protection. */
int hvg_code_min(float hv_max_v);

/** One on or off request. on: returns true if accepted (also when already ON:
 *  idempotent, nothing restarts). false: refused. cap_v: per-request absolute
 *  bias cap (0 = hv_max + 5 V), target_v: per-request ramp target (<= 0 =
 *  follow in->ramp_target_v). off: always true; starts the commanded ramp
 *  down from ON or RAMP_UP, aborts ARMING. */
bool hvg_request(hvg_t *g, bool on, const hvg_in_t *in, float cap_v, float target_v);

/** Fault path callable from anywhere: HV_DIS high now, FAULT or OFF, safe
 *  write queued. */
void hvg_force_off(hvg_t *g, const hvg_in_t *in);

/** Executor side: take the pending command (marks it in flight). */
bool hvg_take_cmd(hvg_t *g, hvg_cmd_t *out);
/** Executor side: result of the command with generation gen. Stale
 *  generations are ignored. */
void hvg_report(hvg_t *g, uint32_t gen, bool ok);

/** Evaluate everything; call every 10 ms. */
void hvg_step(hvg_t *g, const hvg_in_t *in, hvg_out_t *out);

bool hvg_hv_dis(const hvg_t *g);
hvg_state_t hvg_state(const hvg_t *g);
const char *hvg_state_name(hvg_state_t s);
const char *hvg_reason_name(hvg_reason_t r);

#ifdef __cplusplus
}
#endif
