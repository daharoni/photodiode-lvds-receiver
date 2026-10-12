#include "test_harness.h"
#include "range_fsm.h"

typedef struct { range_fsm_t f; range_in_t in; range_out_t out; } sim_t;

static void sim_init(sim_t *s)
{
    range_fsm_init(&s->f);
    memset(&s->in, 0, sizeof(s->in));
    s->in.hv_on = true;
    s->in.bias_v = 100.0f;
    s->in.tia_20k = true;
    s->in.automatic = true;
    s->in.bus_mode = true;
    s->in.hv_min_v = 100.0f;
    s->in.hv_max_v = 200.0f;
    s->in.hv_set_v = 100.0f;
    s->in.now_ms = 1000;
}

/* advance by ms in 100 ms steps; the measured bias follows the target at once
 * unless follow == false; applies tia changes requested by the FSM */
static void run(sim_t *s, uint32_t ms, bool follow)
{
    for (uint32_t t = 0; t < ms; t += 100) {
        s->in.now_ms += 100;
        range_fsm_step(&s->f, &s->in, &s->out);
        s->in.tia_20k = s->out.tia_20k;
        if (follow && s->f.state != RANGE_OFF && s->f.state != RANGE_FAULT) {
            s->in.bias_v = s->out.bias_target_v;
        }
    }
}

static void to_search(sim_t *s)
{
    range_fsm_step(&s->f, &s->in, &s->out);
    ASSERT_EQ(s->out.state, RANGE_RAMP);
    run(s, 1200, false);
    ASSERT_EQ(s->out.state, RANGE_SEARCH);
}

TEST(off_ramp_search_track_walk)
{
    sim_t s;
    sim_init(&s);
    s.in.hv_on = false;
    run(&s, 300, false);
    ASSERT_EQ(s.out.state, RANGE_OFF);
    ASSERT_NEAR(s.out.bias_target_v, 100.0, 1e-3);
    s.in.hv_on = true;
    to_search(&s);
    ASSERT_NEAR(s.out.bias_target_v, 100.0, 2.01);
    /* no link: +2 V per 400 ms -> after 4 s about +20 V */
    s.in.link_valid = false;
    run(&s, 4000, true);
    ASSERT_EQ(s.out.state, RANGE_SEARCH);
    ASSERT_NEAR(s.out.bias_target_v, 120.0, 2.01);
    float before = s.out.bias_target_v;
    /* link goes clean: bias holds, and after 1 s locks with +8 V margin */
    s.in.link_valid = true;
    s.in.err_class = 0;
    run(&s, 1200, true);
    ASSERT_EQ(s.out.state, RANGE_TRACK);
    ASSERT_NEAR(s.f.v_lock, before, 2.01);
    ASSERT_NEAR(s.out.bias_target_v, s.f.v_lock + 8.0, 1e-3);
}

TEST(search_margin_limited_to_hv_max)
{
    sim_t s;
    sim_init(&s);
    s.in.hv_max_v = 130.0f;
    to_search(&s);
    s.in.link_valid = false;
    run(&s, 20000, true);
    ASSERT_NEAR(s.out.bias_target_v, 130.0, 1e-3);
    ASSERT_TRUE(s.out.los_report);
    s.in.link_valid = true;
    run(&s, 1200, true);
    ASSERT_EQ(s.out.state, RANGE_TRACK);
    ASSERT_NEAR(s.out.bias_target_v, 130.0, 1e-3);   /* +8 clamped */
}

TEST(search_at_max_retries_from_hv_min_every_30s)
{
    sim_t s;
    sim_init(&s);
    s.in.hv_max_v = 110.0f;
    to_search(&s);
    s.in.link_valid = false;
    run(&s, 5000, true);
    ASSERT_NEAR(s.out.bias_target_v, 110.0, 1e-3);
    run(&s, 30000, true);
    ASSERT_TRUE(s.out.bias_target_v < 110.0f || s.out.state == RANGE_SEARCH);
    /* within the 35 s the retry must have fired at least once */
    bool saw_min = false;
    for (int i = 0; i < 400; i++) {
        run(&s, 100, true);
        if (s.out.bias_target_v < 105.0f) saw_min = true;
    }
    ASSERT_TRUE(saw_min);
}

static void to_track(sim_t *s)
{
    to_search(s);
    s->in.link_valid = true;
    s->in.err_class = 0;
    run(s, 1300, true);
    ASSERT_EQ(s->out.state, RANGE_TRACK);
}

TEST(track_class2_bump_limited_6v_per_5s)
{
    sim_t s;
    sim_init(&s);
    to_track(&s);
    float t0 = s.out.bias_target_v;
    s.in.err_class = 3;
    s.in.hv_max_v = 200.0f;
    /* sustained class 3: observe over 30 s; check every sliding 5 s window <= 6 V */
    float hist[400];
    int n = 0;
    for (int i = 0; i < 300; i++) {
        run(&s, 100, true);
        hist[n++] = s.out.bias_target_v;
    }
    ASSERT_TRUE(s.out.bias_target_v > t0 + 2.0f);       /* it did correct */
    float worst = 0;
    for (int i = 50; i < n; i++) {
        float d = hist[i] - hist[i - 50];
        if (d > worst) worst = d;
    }
    ASSERT_TRUE(worst <= 6.001f);
    ASSERT_TRUE(worst >= 2.0f);
    /* the 2 s rolling average needs time to rise above class 2: no bump in the first 1 s */
    sim_t q;
    sim_init(&q);
    to_track(&q);
    float b0 = q.out.bias_target_v;
    q.in.err_class = 3;
    run(&q, 1000, true);
    ASSERT_NEAR(q.out.bias_target_v, b0, 1e-3);
    run(&q, 1600, true);
    ASSERT_NEAR(q.out.bias_target_v, b0 + 2.0, 1e-3);
}

TEST(track_class1_does_not_bump)
{
    sim_t s;
    sim_init(&s);
    to_track(&s);
    float t0 = s.out.bias_target_v;
    s.in.err_class = 1;
    s.f.down_trial_enable = false;
    run(&s, 10000, true);
    ASSERT_NEAR(s.out.bias_target_v, t0, 1e-3);
}

TEST(los_hold_then_search_from_vlock_minus_8)
{
    sim_t s;
    sim_init(&s);
    s.in.hv_max_v = 200.0f;
    to_search(&s);
    s.in.link_valid = false;
    run(&s, 2000, true);
    s.in.link_valid = true;
    s.in.err_class = 0;
    run(&s, 1300, true);
    ASSERT_EQ(s.out.state, RANGE_TRACK);
    float vlock = s.f.v_lock;
    float held = s.out.bias_target_v;
    /* link lost */
    s.in.link_valid = false;
    run(&s, 1200, true);
    ASSERT_EQ(s.out.state, RANGE_LOS);
    run(&s, 4000, true);
    ASSERT_EQ(s.out.state, RANGE_LOS);
    ASSERT_NEAR(s.out.bias_target_v, held, 1e-3);   /* held for 5 s */
    run(&s, 1500, true);
    ASSERT_EQ(s.out.state, RANGE_SEARCH);
    ASSERT_TRUE(s.out.bias_target_v <= vlock - 8.0f + 2.01f);
    ASSERT_TRUE(s.out.bias_target_v >= vlock - 8.0f - 0.01f || vlock - 8.0f < 100.0f);
}

TEST(los_class7_and_recovery_to_track)
{
    sim_t s;
    sim_init(&s);
    to_track(&s);
    s.in.err_class = 7;
    run(&s, 1200, true);
    ASSERT_EQ(s.out.state, RANGE_LOS);
    s.in.err_class = 0;
    run(&s, 300, true);
    ASSERT_EQ(s.out.state, RANGE_TRACK);
}

TEST(down_trial_and_doubling)
{
    sim_t s;
    sim_init(&s);
    to_search(&s);
    s.in.link_valid = false;
    run(&s, 4000, true);
    s.in.link_valid = true;
    run(&s, 1300, true);
    ASSERT_EQ(s.out.state, RANGE_TRACK);
    float top = s.out.bias_target_v;
    run(&s, 61000, true);                     /* 60 s clean -> down trial -4 V */
    ASSERT_NEAR(s.out.bias_target_v, top - 4.0, 1e-3);
    s.in.err_class = 1;                       /* trial fails */
    run(&s, 200, true);
    ASSERT_NEAR(s.out.bias_target_v, top, 1e-3);
    ASSERT_EQ(s.f.trial_interval, 120000u);
    s.in.err_class = 0;
    run(&s, 61000, true);                     /* 120 s needed now */
    ASSERT_NEAR(s.out.bias_target_v, top, 1e-3);
}

TEST(tia_guard_5k_at_hv_min_and_back_after_10s)
{
    sim_t s;
    sim_init(&s);
    to_search(&s);
    s.in.link_valid = false;
    s.in.rssi_drop_mv = 900;
    run(&s, 50, true);
    ASSERT_TRUE(!s.out.tia_changed);                 /* not yet 100 ms */
    uint32_t t_switch = 0;
    for (int i = 0; i < 30 && s.in.tia_20k; i++) {
        run(&s, 100, true);
        if (s.out.tia_changed) t_switch = s.in.now_ms;
    }
    ASSERT_TRUE(!s.in.tia_20k);                      /* switched to 5k at hv_min */
    ASSERT_TRUE(t_switch != 0);
    /* light drops: rssi_drop < 0.10 V for 10 s returns to 20k, not before */
    s.in.rssi_drop_mv = 50;
    run(&s, 9000, true);
    ASSERT_TRUE(!s.in.tia_20k);
    run(&s, 2500, true);
    ASSERT_TRUE(s.in.tia_20k);
    ASSERT_TRUE(s.in.now_ms - t_switch >= 10000u);
}

TEST(tia_guard_no_switch_within_10s)
{
    sim_t s;
    sim_init(&s);
    to_search(&s);
    s.in.rssi_drop_mv = 900;
    run(&s, 400, true);
    ASSERT_TRUE(!s.in.tia_20k);                      /* first switch to 5k */
    uint32_t t_sw = s.f.last_switch;
    s.in.rssi_drop_mv = 20;
    s.in.tia_20k = true;                             /* user forces 20k right away (tia 20k) */
    s.in.rssi_drop_mv = 900;
    run(&s, 5000, true);
    ASSERT_TRUE(s.in.tia_20k);                       /* guard must wait: <10 s since switch */
    run(&s, 6000, true);
    ASSERT_TRUE(!s.in.tia_20k);
    ASSERT_TRUE(s.f.last_switch - t_sw >= 10000u);
}

TEST(tia_guard_lowers_bias_first)
{
    sim_t s;
    sim_init(&s);
    to_track(&s);
    float top = s.out.bias_target_v;
    ASSERT_TRUE(top > 105.0f);
    s.in.rssi_drop_mv = 900;
    run(&s, 300, true);
    ASSERT_TRUE(s.out.bias_target_v < top);
    ASSERT_TRUE(s.in.tia_20k);                       /* still 20k while above hv_min */
}

TEST(tia_guard_not_during_ramp)
{
    sim_t s;
    sim_init(&s);
    s.in.rssi_drop_mv = 900;
    s.in.bias_v = 30.0f;                             /* still ramping */
    run(&s, 3000, false);
    ASSERT_EQ(s.out.state, RANGE_RAMP);
    ASSERT_TRUE(s.in.tia_20k);
    ASSERT_TRUE(!s.out.tia_changed);
}

TEST(manual_holds_and_standalone_is_manual)
{
    sim_t s;
    sim_init(&s);
    s.in.bus_mode = false;                           /* standalone USB */
    s.in.hv_set_v = 150.0f;
    s.in.bias_v = 150.0f;
    range_fsm_step(&s.f, &s.in, &s.out);
    run(&s, 1500, false);
    ASSERT_EQ(s.out.state, RANGE_MANUAL);
    ASSERT_NEAR(s.out.bias_target_v, 150.0, 1e-3);
    s.in.link_valid = false;
    run(&s, 20000, false);
    ASSERT_EQ(s.out.state, RANGE_MANUAL);
    ASSERT_NEAR(s.out.bias_target_v, 150.0, 1e-3);
    ASSERT_TRUE(s.in.tia_20k);
    /* manual loop with tia_auto: guard may still switch the TIA, bias stays */
    s.in.tia_auto = true;
    s.in.automatic = false;
    s.in.rssi_drop_mv = 900;
    run(&s, 500, false);
    ASSERT_TRUE(!s.in.tia_20k);
    ASSERT_NEAR(s.out.bias_target_v, 150.0, 1e-3);
    /* back to auto with a master: leaves MANUAL */
    s.in.automatic = true;
    s.in.bus_mode = true;
    s.in.rssi_drop_mv = 300;
    run(&s, 200, false);
    ASSERT_EQ(s.out.state, RANGE_SEARCH);
}

TEST(manual_ignores_guard_when_neither_auto)
{
    sim_t s;
    sim_init(&s);
    s.in.automatic = false;
    s.in.hv_set_v = 120.0f;
    s.in.bias_v = 120.0f;
    s.in.rssi_drop_mv = 900;
    range_fsm_step(&s.f, &s.in, &s.out);
    run(&s, 3000, false);
    ASSERT_EQ(s.out.state, RANGE_MANUAL);
    ASSERT_TRUE(s.in.tia_20k);
}

TEST(fault_and_hv_off)
{
    sim_t s;
    sim_init(&s);
    to_track(&s);
    s.in.fault = true;
    run(&s, 100, false);
    ASSERT_EQ(s.out.state, RANGE_FAULT);
    ASSERT_NEAR(s.out.bias_target_v, 100.0, 1e-3);
    s.in.fault = false;
    s.in.hv_on = false;
    run(&s, 100, false);
    ASSERT_EQ(s.out.state, RANGE_OFF);
}

TEST(ramp_starts_at_saved_lock_when_present)
{
    sim_t s;
    sim_init(&s);
    range_fsm_set_last_lock(&s.f, 140.0f);
    s.in.hv_set_v = 140.0f;
    range_fsm_step(&s.f, &s.in, &s.out);
    ASSERT_EQ(s.out.state, RANGE_RAMP);
    ASSERT_NEAR(s.out.bias_target_v, 140.0, 1e-3);
}

/* ---- manual DAC_HV code target (review finding 3) ---- */
#define VPC 0.01495f

TEST(manual_code_slew_limited)
{
    /* far target: at most max_step codes per call */
    int32_t c = 4095;
    c = range_manual_code_step(c, 0, 107.0f, 100.0f, 200.0f, VPC, 134, 0);
    ASSERT_EQ(c, 4095 - 134);
    c = range_manual_code_step(c, 0, 109.0f, 100.0f, 200.0f, VPC, 134, 0);
    ASSERT_EQ(c, 4095 - 268);
    /* reaching a near target exactly */
    ASSERT_EQ(range_manual_code_step(3000, 2990, 150.0f, 100.0f, 200.0f, VPC, 134, 0), 2990);
    /* no move when already there */
    ASSERT_EQ(range_manual_code_step(3000, 3000, 150.0f, 100.0f, 200.0f, VPC, 134, 0), 3000);
    /* upward (lower bias) is slew limited too */
    ASSERT_EQ(range_manual_code_step(2000, 4095, 150.0f, 100.0f, 200.0f, VPC, 134, 0), 2134);
}

TEST(manual_code_clamped_to_hv_max)
{
    /* bias 148 V, hv_max 150 V: at most 2 V / 14.95 mV = 133 codes down */
    int32_t n = range_manual_code_step(3000, 0, 148.0f, 100.0f, 150.0f, VPC, 500, 0);
    ASSERT_TRUE(n >= 3000 - 134 && n <= 3000 - 133 + 1);
    /* at the limit: no further move */
    ASSERT_EQ(range_manual_code_step(3000, 0, 150.0f, 100.0f, 150.0f, VPC, 500, 0), 3000);
    /* above the limit already: pulled back (code goes up) even though the target asks for lower */
    ASSERT_TRUE(range_manual_code_step(3000, 0, 152.0f, 100.0f, 150.0f, VPC, 500, 0) > 3000);
}

TEST(manual_code_clamped_to_hv_min)
{
    /* bias 102 V, hv_min 100 V: at most 133 codes up */
    int32_t n = range_manual_code_step(2000, 4095, 102.0f, 100.0f, 200.0f, VPC, 500, 0);
    ASSERT_TRUE(n >= 2000 + 133 && n <= 2000 + 134);
    ASSERT_EQ(range_manual_code_step(2000, 4095, 100.0f, 100.0f, 200.0f, VPC, 500, 0), 2000);
}

TEST(manual_code_open_loop_bound)
{
    /* code_min 3360 (hv_max 110 V): never below it whatever the bias reading says */
    ASSERT_EQ(range_manual_code_step(3400, 0, 60.0f, 50.0f, 110.0f, VPC, 500, 3360), 3360);
    ASSERT_EQ(range_manual_code_step(3360, 0, 60.0f, 50.0f, 110.0f, VPC, 500, 3360), 3360);
    /* never above 0xFFF */
    ASSERT_EQ(range_manual_code_step(4090, 4095, 130.0f, 100.0f, 200.0f, VPC, 500, 0), 4095);
}

TEST(state_names)
{
    ASSERT_TRUE(strcmp(range_state_str(RANGE_TRACK), "TRACK") == 0);
    ASSERT_TRUE(strcmp(range_state_str((range_state_t)9), "?") == 0);
}

TH_MAIN
