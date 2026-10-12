/*
 * range_fsm.h - range-trim state machine and TIA overload guard, pure C.
 *
 * Implements firmware/esp32/README.md s.6.3 (state table and guard table).
 * No ESP-IDF includes: host-tested in firmware/esp32/test_host.
 * Every number is a first guess, PROPOSED, to be tuned at G2/G3
 * (docs/bringup/gates.md). Nothing here is measured.
 *
 * Call range_fsm_step() every 100 ms (README s.3 task table). All times are
 * milliseconds from in->now_ms (wraps handled with unsigned subtraction).
 *
 * Deviations from the coordinator's contract struct (added fields, all
 * zero-initialisable): range_in_t.fault, .rssi_rail, .tia_auto;
 * range_out_t.los_report.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Numeric values equal the protocol s.1.4 loop_state enumeration. */
typedef enum {
    RANGE_OFF = 0,
    RANGE_RAMP = 1,
    RANGE_SEARCH = 2,
    RANGE_TRACK = 3,
    RANGE_LOS = 4,
    RANGE_MANUAL = 5,
    RANGE_FAULT = 6,
} range_state_t;

/* ---- SEARCH (README s.6.3) ---- */
#define RFSM_SEARCH_STEP_V        2.0f     /* +2 V ...                        README s.6.3, PROPOSED */
#define RFSM_SEARCH_STEP_MS       400u     /* ... per 400 ms                  README s.6.3, PROPOSED */
#define RFSM_SEARCH_CLEAN_MS      1000u    /* valid + class 0 for 1 s         README s.6.3, PROPOSED */
#define RFSM_LOCK_MARGIN_V        8.0f     /* +8 V margin after lock          README s.6.3, PROPOSED */
#define RFSM_SEARCH_RETRY_MS      30000u   /* at hv_max, retry from hv_min    README s.6.3, PROPOSED */
/* ---- TRACK ---- */
#define RFSM_TRACK_AVG_MS         2000u    /* class average window            README s.6.3, PROPOSED */
#define RFSM_TRACK_CLASS_THRESH   2.0f     /* class >= 2                      README s.6.3, PROPOSED */
#define RFSM_TRACK_BUMP_V         2.0f     /* +2 V                            README s.6.3, PROPOSED */
#define RFSM_TRACK_BUMP_WAIT_MS   1000u    /* wait 1 s, repeat                README s.6.3, PROPOSED */
#define RFSM_TRACK_BUMP_MAX_V     6.0f     /* max +6 V ...                    README s.6.3, PROPOSED */
#define RFSM_TRACK_BUMP_WIN_MS    5000u    /* ... per 5 s                     README s.6.3, PROPOSED */
#define RFSM_TRIAL_STEP_V         4.0f     /* down-trial -4 V                 README s.6.3, PROPOSED */
#define RFSM_TRIAL_HOLD_MS        5000u    /* for 5 s                         README s.6.3, PROPOSED */
#define RFSM_TRIAL_INTERVAL_MS    60000u   /* first interval 60 s             README s.6.3, PROPOSED */
#define RFSM_TRIAL_INTERVAL_MAX   600000u  /* doubling up to 10 min           README s.6.3, PROPOSED */
#define RFSM_LOS_ENTER_MS         1000u    /* valid=0 or class 7 for 1 s      README s.6.3, PROPOSED */
/* ---- LOS ---- */
#define RFSM_LOS_HOLD_MS          5000u    /* hold bias and TIA for 5 s       README s.6.3, PROPOSED */
#define RFSM_LOS_RESTART_BACK_V   8.0f     /* SEARCH from V_lock - 8 V        README s.6.3, PROPOSED */
#define RFSM_CLASS_LOS            7u       /* protocol s.1.5 class 7 = LOS */
/* ---- RAMP ---- */
#define RFSM_RAMP_ARRIVE_V        2.0f     /* within 2 V of target ...        README s.4 step 9d, PROPOSED */
#define RFSM_RAMP_ARRIVE_MS       1000u    /* ... for 1 s                     README s.4 step 9d, PROPOSED */
/* ---- TIA guard ---- */
#define RFSM_GUARD_HI_MV          800      /* rssi_drop > 0.80 V              README s.6.3 guard, PROPOSED */
#define RFSM_GUARD_HI_MS          100u     /* for 100 ms                      README s.6.3 guard, PROPOSED */
#define RFSM_GUARD_LOWER_V        2.0f     /* lower bias 2 V ...              README s.6.3 guard, PROPOSED */
#define RFSM_GUARD_LOWER_MS       200u     /* ... per 200 ms                  README s.6.3 guard, PROPOSED */
#define RFSM_GUARD_LO_MV          100      /* at 5k, rssi_drop < 0.10 V       README s.6.3 guard, PROPOSED */
#define RFSM_GUARD_LO_MS          10000u   /* for 10 s -> back to 20k         README s.6.3 guard, PROPOSED */
#define RFSM_SWITCH_MIN_MS        10000u   /* >= 10 s between switches        README s.6.3 guard, PROPOSED */
#define RFSM_BLANK_MS             300u     /* ignore link metrics 300 ms      README s.6.3 guard, PROPOSED */

typedef struct {
    bool hv_on;               /* HV enabled and supply running (app_safety) */
    float bias_v;             /* measured APD bias, HV_MON x 101 */
    int32_t rssi_drop_mv;     /* idle level minus present RSSI (positive with light) */
    bool tia_20k;             /* actual OPA857 gain, true = 20k */
    bool link_valid;          /* LINK_ALL nibble bit3 */
    uint8_t err_class;        /* LINK_ALL nibble bits 2:0, 0..7 (7 = LOS) */
    bool automatic;           /* `loop auto` */
    bool bus_mode;            /* LINK_ALL heard (no link metric exists standalone) */
    float hv_min_v, hv_max_v, hv_set_v;
    uint32_t now_ms;
    /* additions */
    bool fault;               /* latched fault that turned HV off -> FAULT */
    bool rssi_rail;           /* RSSI below 0.3 V (README s.6.3 guard) */
    bool tia_auto;            /* `tia auto`: guard may switch TIA even with loop manual */
} range_in_t;

typedef struct {
    float bias_target_v;      /* closed-loop target for the DAC_HV trim */
    bool tia_20k;             /* requested TIA gain */
    bool tia_changed;         /* true on the step that requests a switch */
    range_state_t state;
    bool los_report;          /* SEARCH reached hv_max without lock (README s.6.3) */
} range_out_t;

#define RFSM_CLASS_WIN 40  /* ring capacity of the 2 s class window at 100 ms steps (+margin) */

typedef struct {
    range_state_t state;
    uint32_t state_since_ms;
    float target;             /* commanded bias, V */
    float v_lock;             /* pre-margin clean bias, V */
    bool have_lock;
    bool down_trial_enable;   /* PROPOSED default true; README s.12 item 2 says Daniel decides */
    /* RAMP */
    float ramp_target;
    bool arrive_set;
    uint32_t arrive_since;
    /* SEARCH */
    uint32_t search_last_step;
    bool clean_set;
    uint32_t clean_since;
    bool max_set;
    uint32_t max_since;
    bool los_report;
    /* TRACK */
    uint32_t win_t[RFSM_CLASS_WIN];
    uint8_t win_c[RFSM_CLASS_WIN];
    uint8_t win_n, win_head;
    uint32_t bump_t[3];
    uint8_t bump_n;
    uint32_t bump_hold_until;
    bool bump_hold;
    bool bad_set;
    uint32_t bad_since;
    bool trial_active;
    uint32_t trial_start;
    float trial_prev;
    uint32_t trial_interval;
    /* LOS */
    uint32_t los_since;
    /* MANUAL */
    /* guard */
    bool over_set;
    uint32_t over_since;
    bool lo_set;
    uint32_t lo_since;
    bool have_switched;
    uint32_t last_switch;
    uint32_t last_lower;
    bool lower_valid;
} range_fsm_t;

/** Initialise to OFF with the default 60 s down-trial interval. */
void range_fsm_init(range_fsm_t *f);
/** Restore a saved lock (NVS `state` namespace, README s.6.6): RAMP then starts at hv_set. */
void range_fsm_set_last_lock(range_fsm_t *f, float v_lock);
/** One 100 ms step. */
void range_fsm_step(range_fsm_t *f, const range_in_t *in, range_out_t *out);
/** Short upper-case name of a state ("OFF", "RAMP", ...). */
const char *range_state_str(range_state_t s);

#ifdef __cplusplus
}
#endif
