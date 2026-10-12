/* test_hv_gate.c - host tests of the HV gate state machine (hv_gate.c).
 * Plant model: bias = 104 V + (0xFFF - code) x 14.95 mV while HV_DIS is low
 * (PROPOSED numbers from README s.1; not measured), 5 V while it is high.
 * These tests exercise the logic only; nothing here says anything about the
 * real supply. */
#include "test_harness.h"
#include "hv_gate.h"
#include "board_pins.h"

typedef struct {
    hvg_t g;
    hvg_in_t in;
    hvg_out_t out;
    uint32_t now;
    int code;                 /* DAC_HV code as the plant sees it */
    int fail_next_writes;     /* executor failures to inject */
    bool hold_executor;       /* executor does nothing */
    bool stuck_bias;          /* HV_MON ignores the DAC */
    float stuck_v;
    float plant_gain;         /* fraction of the nominal bias change the plant delivers */
    float plant_max_v;
    fault_word_t faults;      /* latched fault word, as app_safety would hold it */
    int min_code_written;
    int n_writes;
    bool dis_low_seen_without_arm;
    bool arm_ok_seen;
} ctx_t;

static void ctx_init(ctx_t *c)
{
    memset(c, 0, sizeof(*c));
    hvg_init(&c->g);
    c->code = 0xFFF;
    c->plant_gain = 1.0f;
    c->plant_max_v = 1000.0f;
    c->min_code_written = 0xFFF;
    c->in.dac_verified = true;
    c->in.adc_ok = true;
    c->in.sense_ok = true;
    c->in.hv_min_v = 100.0f;
    c->in.hv_max_v = 200.0f;
    c->in.hv_set_v = 150.0f;
    c->in.ramp_target_v = 150.0f;
    c->now = 1000;
}

static float plant_bias(const ctx_t *c)
{
    if (c->stuck_bias) return c->stuck_v;
    if (hvg_hv_dis(&c->g)) return 5.0f;
    float v = BOARD_HV_V_AT_SAFE_CODE + c->plant_gain * (0xFFF - c->code) * BOARD_HV_V_PER_CODE;
    return v > c->plant_max_v ? c->plant_max_v : v;
}

static void tick(ctx_t *c)
{
    c->now += 10;
    c->in.now_ms = c->now;
    c->in.bias_v = plant_bias(c);
    c->in.sample_seq = c->now / 100;
    c->in.dac_code = c->code;
    c->in.blocking_fault = (c->faults & FAULT_HV_BLOCKING_MASK) != 0;
    hvg_step(&c->g, &c->in, &c->out);
    c->faults |= c->out.fault_bits;
    if (c->out.adc_bad) c->in.adc_ok = false;
    /* executor */
    hvg_cmd_t cmd;
    if (!c->hold_executor && hvg_take_cmd(&c->g, &cmd)) {
        bool ok = true;
        if (c->fail_next_writes > 0) { c->fail_next_writes--; ok = false; }
        if (ok) {
            c->code = cmd.code;
            c->n_writes++;
            if (cmd.kind != HVG_CMD_ARM && cmd.kind != HVG_CMD_SAFE && cmd.code < c->min_code_written)
                c->min_code_written = cmd.code;
        }
        hvg_report(&c->g, cmd.gen, ok);
    }
}

static void run_ms(ctx_t *c, uint32_t ms)
{
    for (uint32_t t = 0; t < ms; t += 10) tick(c);
}

static void run_until_state(ctx_t *c, hvg_state_t s, uint32_t max_ms)
{
    for (uint32_t t = 0; t < max_ms && hvg_state(&c->g) != s; t += 10) tick(c);
}

static bool request(ctx_t *c, bool on, float cap, float target)
{
    c->in.now_ms = c->now;
    c->in.bias_v = plant_bias(c);
    c->in.blocking_fault = (c->faults & FAULT_HV_BLOCKING_MASK) != 0;
    return hvg_request(&c->g, on, &c->in, cap, target);
}

TEST(hv_dis_stays_high_until_arm_readback)
{
    ctx_t c; ctx_init(&c);
    ASSERT_TRUE(request(&c, true, 0, 0));
    ASSERT_EQ(hvg_state(&c.g), HVG_ARMING);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    c.hold_executor = true;                      /* readback never arrives */
    run_ms(&c, 1500);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_EQ(hvg_state(&c.g), HVG_ARMING);
    run_ms(&c, 1000);                            /* ARM timeout 2 s: trips, HV_DIS still high */
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_EQ(hvg_state(&c.g), HVG_FAULT);
    ASSERT_TRUE((c.faults & FAULT_I2C_DAC) != 0);
}

TEST(arm_failure_never_lowers_hv_dis)
{
    ctx_t c; ctx_init(&c);
    c.fail_next_writes = 1;
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 100);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_EQ(hvg_state(&c.g), HVG_FAULT);
    ASSERT_TRUE((c.faults & FAULT_I2C_DAC) != 0);
    /* with the fault latched a new request is refused */
    ASSERT_TRUE(!request(&c, true, 0, 0));
}

TEST(hv_dis_low_only_after_successful_arm)
{
    ctx_t c; ctx_init(&c);
    ASSERT_TRUE(request(&c, true, 0, 0));
    bool low_before_report = false;
    /* step once with the executor held: still high */
    c.hold_executor = true;
    tick(&c);
    low_before_report = !hvg_hv_dis(&c.g);
    ASSERT_TRUE(!low_before_report);
    c.hold_executor = false;
    run_ms(&c, 30);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    ASSERT_EQ(hvg_state(&c.g), HVG_RAMP_UP);
}

TEST(stale_arm_report_from_older_request_is_ignored)
{
    ctx_t c; ctx_init(&c);
    ASSERT_TRUE(request(&c, true, 0, 0));
    hvg_cmd_t old;
    ASSERT_TRUE(hvg_take_cmd(&c.g, &old));       /* executor is busy with request 1 */
    ASSERT_TRUE(request(&c, true, 0, 0));        /* restart: new generation */
    hvg_report(&c.g, old.gen, true);             /* late report of the old request */
    c.hold_executor = true;
    run_ms(&c, 100);
    ASSERT_TRUE(hvg_hv_dis(&c.g));               /* must not count for the new request */
    ASSERT_EQ(hvg_state(&c.g), HVG_ARMING);
    c.hold_executor = false;
    run_ms(&c, 50);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
}

TEST(fault_raises_hv_dis_in_the_same_step)
{
    ctx_t c; ctx_init(&c);
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 200);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    c.faults |= FAULT_CAN_TIMEOUT;               /* latched by another task */
    c.now += 10;
    c.in.now_ms = c.now;
    c.in.bias_v = plant_bias(&c);
    c.in.blocking_fault = true;
    hvg_step(&c.g, &c.in, &c.out);
    ASSERT_TRUE(c.out.hv_dis);
    ASSERT_EQ(c.out.state, HVG_FAULT);
}

TEST(over_limit_trips_in_same_step)
{
    ctx_t c; ctx_init(&c);
    c.in.hv_max_v = 150.0f;
    c.in.ramp_target_v = 150.0f;
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 100);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    c.stuck_bias = true; c.stuck_v = 156.0f;     /* above hv_max + 5 V */
    tick(&c);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_TRUE((c.faults & FAULT_HV_OVER) != 0);
}

TEST(force_off_raises_hv_dis_immediately_and_queues_safe_write)
{
    ctx_t c; ctx_init(&c);
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 3000);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    c.in.now_ms = c.now;
    hvg_force_off(&c.g, &c.in);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_TRUE(!request(&c, true, 0, 0));       /* safe write pending: refused */
    run_ms(&c, 100);
    ASSERT_EQ(c.code, 0xFFF);
    ASSERT_TRUE(request(&c, true, 0, 0));        /* after the safe write: accepted */
}

TEST(rerequest_mid_ramp_restarts_from_arming)
{
    ctx_t c; ctx_init(&c);
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 600);
    ASSERT_EQ(hvg_state(&c.g), HVG_RAMP_UP);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    ASSERT_TRUE(c.code < 0xFFF);
    ASSERT_TRUE(request(&c, true, 0, 0));
    ASSERT_EQ(hvg_state(&c.g), HVG_ARMING);
    ASSERT_TRUE(hvg_hv_dis(&c.g));               /* high again in the same call */
    c.hold_executor = true;
    run_ms(&c, 200);
    ASSERT_TRUE(hvg_hv_dis(&c.g));               /* stays high until the new readback */
    c.hold_executor = false;
    run_ms(&c, 100);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    ASSERT_EQ(c.code, 0xFFF);                    /* the new ramp started from the safe code */
}

TEST(request_refused_when_unverified_or_faulted)
{
    ctx_t c; ctx_init(&c);
    c.in.dac_verified = false;
    ASSERT_TRUE(!request(&c, true, 0, 0));
    c.in.dac_verified = true;
    c.in.adc_ok = false;
    ASSERT_TRUE(!request(&c, true, 0, 0));
    c.in.adc_ok = true;
    c.faults = FAULT_I2C_DAC;
    ASSERT_TRUE(!request(&c, true, 0, 0));
    c.faults = 0;
    ASSERT_TRUE(request(&c, true, 0, 0));
}

TEST(ramp_reaches_target_and_obeys_slew)
{
    ctx_t c; ctx_init(&c);
    c.in.ramp_target_v = 150.0f;
    ASSERT_TRUE(request(&c, true, 0, 0));
    int last = 0xFFF, max_step = 0;
    for (int i = 0; i < 1500 && hvg_state(&c.g) != HVG_ON; i++) {
        tick(&c);
        if (c.code != last) {
            int d = last - c.code;
            if (d < 0) d = -d;
            if (d > max_step) max_step = d;
            last = c.code;
        }
    }
    ASSERT_EQ(hvg_state(&c.g), HVG_ON);
    ASSERT_TRUE(max_step <= 150);
    ASSERT_TRUE(max_step <= 134);                /* 20 V/s x 100 ms / 14.95 mV */
    ASSERT_NEAR(plant_bias(&c), 150.0, 2.0);
}

TEST(ramp_timeout_raises_hv_under)
{
    ctx_t c; ctx_init(&c);
    c.plant_max_v = 110.0f;                      /* supply saturates: bias follows, target unreachable */
    c.in.ramp_target_v = 150.0f;
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 9500);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    ASSERT_EQ(hvg_state(&c.g), HVG_RAMP_UP);
    run_ms(&c, 1200);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_EQ(hvg_state(&c.g), HVG_FAULT);
    ASSERT_TRUE((c.faults & FAULT_HV_UNDER) != 0);
    ASSERT_EQ(c.g.last_reason, HVG_R_RAMP_TIMEOUT);
}

TEST(code_min_formula_and_open_loop_bound)
{
    /* 0xFFF - (hv_max + 5 - 104) / 0.01495 */
    ASSERT_EQ(hvg_code_min(110.0f), 4095 - (int)((115.0f - 104.0f) / BOARD_HV_V_PER_CODE));
    ASSERT_EQ(hvg_code_min(150.0f), 4095 - (int)((155.0f - 104.0f) / BOARD_HV_V_PER_CODE));
    ASSERT_EQ(hvg_code_min(200.0f), 0);          /* bound inactive with the nominal 61 V DAC span */
    ASSERT_EQ(hvg_code_min(50.0f), 0xFFF);
    /* The ramp never writes below the bound even if the bias lags (half gain). */
    ctx_t c; ctx_init(&c);
    c.in.hv_max_v = 110.0f;
    c.in.ramp_target_v = 110.0f;
    c.plant_gain = 0.5f;
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 5000);
    ASSERT_TRUE(c.min_code_written >= hvg_code_min(110.0f));
    ASSERT_TRUE(c.min_code_written <= hvg_code_min(110.0f) + 140);   /* and it did walk to it */
}

TEST(bias_not_following_trips_hv_under)
{
    ctx_t c; ctx_init(&c);
    c.stuck_bias = true; c.stuck_v = 107.0f;     /* HV_MON stuck low: bias reading ignores the DAC */
    c.in.ramp_target_v = 150.0f;
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 3000);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_TRUE((c.faults & FAULT_HV_UNDER) != 0);
    ASSERT_EQ(c.g.last_reason, HVG_R_NOT_FOLLOWING);
    ASSERT_TRUE(0xFFF - c.min_code_written > HVG_NF_CODES);
    ASSERT_TRUE(0xFFF - c.min_code_written < HVG_NF_CODES + 2 * HVG_MAX_STEP_CODES);   /* walk stopped soon after 400 */
}

TEST(per_request_cap_is_enforced_by_the_machine)
{
    ctx_t c; ctx_init(&c);
    c.in.hv_max_v = 200.0f;
    ASSERT_TRUE(request(&c, true, 120.0f, 100.0f));   /* self-test: cap 120 V, stay at the floor */
    run_ms(&c, 2500);
    ASSERT_EQ(hvg_state(&c.g), HVG_ON);               /* pinned at 0xFFF counts as arrival */
    ASSERT_EQ(c.code, 0xFFF);
    c.stuck_bias = true; c.stuck_v = 121.0f;
    tick(&c);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_TRUE((c.faults & FAULT_HV_OVER) != 0);
    /* without a cap the limit is hv_max + 5 V */
    ctx_t d; ctx_init(&d);
    ASSERT_TRUE(request(&d, true, 0, 0));
    run_ms(&d, 200);
    d.stuck_bias = true; d.stuck_v = 121.0f;
    tick(&d);
    ASSERT_TRUE(!hvg_hv_dis(&d.g));
}

TEST(ramp_down_slew_and_hv_dis_high_only_at_safe_code)
{
    ctx_t c; ctx_init(&c);
    c.in.ramp_target_v = 150.0f;
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_until_state(&c, HVG_ON, 15000);
    ASSERT_EQ(hvg_state(&c.g), HVG_ON);
    int start = c.code;
    ASSERT_TRUE(start < 0xFFF - 2000);
    ASSERT_TRUE(request(&c, false, 0, 0));
    ASSERT_EQ(hvg_state(&c.g), HVG_RAMP_DOWN);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    int last = start, max_step = 0, steps = 0;
    bool dis_before_safe = false;
    for (int i = 0; i < 1500 && hvg_state(&c.g) == HVG_RAMP_DOWN; i++) {
        tick(&c);
        if (c.code != last) {
            if (c.code - last > max_step) max_step = c.code - last;
            last = c.code;
            steps++;
        }
        if (hvg_hv_dis(&c.g) && c.code != 0xFFF) dis_before_safe = true;
    }
    ASSERT_EQ(hvg_state(&c.g), HVG_OFF);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_TRUE(!dis_before_safe);
    ASSERT_EQ(c.code, 0xFFF);
    ASSERT_TRUE(max_step <= 335);                     /* ceil(50 V/s x 0.1 s / 14.95 mV) */
    ASSERT_TRUE(steps >= (0xFFF - start) / 335);
    /* off then on again is accepted (no safe write pending) */
    ASSERT_TRUE(request(&c, true, 0, 0));
}

TEST(off_request_while_arming_aborts_with_hv_dis_high)
{
    ctx_t c; ctx_init(&c);
    ASSERT_TRUE(request(&c, true, 0, 0));
    c.hold_executor = true;
    run_ms(&c, 50);
    ASSERT_TRUE(request(&c, false, 0, 0));
    ASSERT_EQ(hvg_state(&c.g), HVG_OFF);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    c.hold_executor = false;
    run_ms(&c, 100);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
}

TEST(stale_sense_trips_i2c_adc)
{
    ctx_t c; ctx_init(&c);
    ASSERT_TRUE(request(&c, true, 0, 0));
    run_ms(&c, 200);
    ASSERT_TRUE(!hvg_hv_dis(&c.g));
    c.in.sense_ok = false;
    tick(&c);
    ASSERT_TRUE(hvg_hv_dis(&c.g));
    ASSERT_TRUE((c.faults & FAULT_I2C_ADC) != 0);
    ASSERT_TRUE(!c.in.adc_ok);
}

TEST(stuck_bias_reported_after_30_s)
{
    ctx_t c; ctx_init(&c);
    c.stuck_bias = true; c.stuck_v = 40.0f;
    run_ms(&c, 29000);
    ASSERT_TRUE((c.faults & FAULT_HV_STUCK) == 0);
    run_ms(&c, 3000);
    ASSERT_TRUE((c.faults & FAULT_HV_STUCK) != 0);
}

TH_MAIN
