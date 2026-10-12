/*
 * app_selftest.c - README s.8 self-test. Every window is PROPOSED (README s.8
 * "first guesses"); the source column cites README s.8 unless noted.
 * Compiled but not run on hardware.
 */
#include "app_selftest.h"
#include <inttypes.h>
#include <math.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include "app_range.h"
#include "app_safety.h"
#include "board_i2c.h"
#include "board_pins.h"
#include "board_time.h"
#include "can_codec.h"
#include "can_link.h"
#include "drv_ads1115.h"
#include "drv_gpio.h"
#include "drv_mcp4728.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "fault.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "params.h"
#include "sense.h"

static const char *TAG = "selftest";

/* ---- windows (README s.8, all PROPOSED) ---- */
#define AIN3_ABS_MAX_MV        5        /* step 5: AIN3 = 0 +- 5 mV */
#define RSSI_MIN_MV            1500     /* step 5: RSSI idle 1.5-2.3 V */
#define RSSI_MAX_MV            2300
#define VTH_CENTER_MV          1650     /* step 5: VCM_REF 1.65 V +- 0.10 V (slicer.md) */
#define VTH_TOL_MV             100
#define HVMON_MAX_MV           100      /* step 5: HV_MON under 0.1 V (bias under ~10 V) */
#define TH_STEP_V              0.5f     /* step 4: DAC_TH +-0.5 V */
#define TH_CODE_PER_V          (4096.0f / 3.3f)   /* 3.3 V reference, 12 bit (README s.1 DAC_TH row) */
#define TH_EXPECT_MV           4.95     /* step 4: 0.5 V x 1/101 */
#define TH_TOL_FRAC            0.30     /* step 4: +-30 % */
#define TH_SETTLE_MS           50       /* PROPOSED: settle before reading VTH_MON */
#define TEMP_MIN_DC            (-100)   /* step 8: -10 C */
#define TEMP_MAX_DC            600      /* step 8: 60 C */
#define CAN_FRAMES             8        /* step 7 */
#define HV_ABS_CAP_V           120.0f   /* step 9 (finding 5): per-request cap, enforced in hv_gate (hvg), PROPOSED */
#define HV_FLOOR_MIN_V         95.0f    /* step 9: floor window 95-115 V, PROPOSED, UNRESOLVED until measured */
#define HV_FLOOR_MAX_V         115.0f   /* (README s.1: about 104-110 V at code 0xFFF, calculated) */
#define HV_SETTLE_STABLE_MS    2000     /* step 9: bias stable for 2 s ... */
#define HV_SETTLE_TOL_V        1.0f     /* ... within 1 V */
#define HV_SETTLE_TIMEOUT_S    12       /* PROPOSED: overall wait for ON + settle (hv_gate arrival takes 1 s) */
#define HV_SLOPE_MIN           10.0f    /* step 9: 10..30 V per V (nominal 18.5, calculated) */
#define HV_SLOPE_MAX           30.0f
#define HV_SLOPE_CODES         60       /* step 9 (finding 5): DAC step of at most 60 codes (about 0.9 V of bias) */
#define HV_SLOPE_SETTLE_MS     600      /* PROPOSED */
#define HV_DECAY_V             30.0f    /* step 9: wait until bias below 30 V ... */
#define HV_DECAY_TIMEOUT_S     30       /* ... or 30 s */
#define DAC_V_PER_CODE         (3.3f / 4096.0f)
#define POLL_MS                100      /* sense round is about 100 ms (sense.h) */

#define MAX_STEPS              9
#define LED_TICK_MS            50
#define LED_PASS_MS            6000     /* 3 x (1 s on, 1 s off), README s.8 */
#define LED_SHOW_MAX_MS        8000

typedef enum { R_PASS, R_FAIL, R_SKIP, R_INFO } res_t;

typedef struct {
    const char *id;
    res_t r;
    char d[48];
} step_t;

static step_t s_steps[MAX_STEPS];
static int s_nsteps;
static char s_json[1200];
static _Atomic bool s_running;     /* set with atomic_exchange: one run at a time (finding 13) */
static volatile int64_t s_show_until_us;
static volatile uint8_t s_last_status;
static volatile int s_led_mode;       /* 0 idle, 1 running, 2 pass, 3 fail */
static volatile int s_led_fail_step;
static volatile int64_t s_led_t0_us;
static TaskHandle_t s_led_task;
static float s_hv_peak_v, s_hv_floor_v;

bool app_selftest_within(double value, double expected, double tol_frac)
{
    return fabs(value - expected) <= fabs(expected) * tol_frac;
}

bool app_selftest_running(void)
{
    return s_running || esp_timer_get_time() < s_show_until_us;
}

const char *app_selftest_last_json(void) { return s_json; }
uint8_t app_selftest_last_status(void) { return s_last_status; }

/* ---- LED (README s.8 patterns, PROPOSED) ---- */
static bool led_level(int64_t t_ms)
{
    switch (s_led_mode) {
    case 1:  return (t_ms / 100) % 2 == 0;                     /* running: 5 Hz blink */
    case 2:  return t_ms < LED_PASS_MS && (t_ms / 1000) % 2 == 0;   /* pass: 3 x 1 s on / 1 s off */
    case 3: {                                                  /* fail: N flashes, 2 s pause */
        int n = s_led_fail_step;
        int64_t flash_ms = (int64_t)n * 400;                   /* 200 on / 200 off each */
        int64_t p = t_ms % (flash_ms + 2000);
        return p < flash_ms && (p / 200) % 2 == 0;
    }
    default: return false;
    }
}

static void led_task(void *arg)
{
    (void)arg;
    for (;;) {
        vTaskDelay(ticks_at_least_1(LED_TICK_MS));
        if (s_led_mode == 0) {
            continue;
        }
        int64_t t_ms = (esp_timer_get_time() - s_led_t0_us) / 1000;
        if (s_led_mode >= 2 && !s_running && esp_timer_get_time() >= s_show_until_us) {
            drv_gpio_led_set(false);
            s_led_mode = 0;
            continue;
        }
        drv_gpio_led_set(led_level(t_ms));
    }
}

static void led_set_mode(int mode, int fail_step, int show_ms)
{
    s_led_t0_us = esp_timer_get_time();
    s_led_fail_step = fail_step;
    s_led_mode = mode;
    if (show_ms > 0) {
        s_show_until_us = esp_timer_get_time() + (int64_t)show_ms * 1000;
    }
}

/* ---- step bookkeeping ---- */
static void step(const char *id, res_t r, const char *fmt, ...) __attribute__((format(printf, 3, 4)));
static void step(const char *id, res_t r, const char *fmt, ...)
{
    if (s_nsteps >= MAX_STEPS) {
        return;
    }
    step_t *s = &s_steps[s_nsteps++];
    s->id = id;
    s->r = r;
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(s->d, sizeof(s->d), fmt, ap);
    va_end(ap);
    static const char *const nm[] = {"pass", "fail", "skip", "info"};
    ESP_LOGW(TAG, "step %d %-10s %s %s", s_nsteps, id, nm[r], s->d);
}

static res_t step_result(const char *id)
{
    for (int i = 0; i < s_nsteps; i++) {
        if (strcmp(s_steps[i].id, id) == 0) {
            return s_steps[i].r;
        }
    }
    return R_SKIP;
}

static bool read_mv(uint8_t ain, int32_t *v) { return ads1115_read_mv(ain, v) == ESP_OK; }

/* ---- steps 1-8 ---- */
static void st_identity(void)
{
    int32_t ver = 0, sn = 0, rev = 0;
    uint8_t mac[6] = {0};
    bool ok = params_get_i32(PARAM_FW_VER, &ver) == ESP_OK && ver != 0;
    params_get_i32(PARAM_SERIAL, &sn);
    params_get_i32(PARAM_BOARD_REV, &rev);
    ok = ok && esp_read_mac(mac, ESP_MAC_EFUSE_FACTORY) == ESP_OK;
    bool mac_nz = (mac[0] | mac[1] | mac[2] | mac[3] | mac[4] | mac[5]) != 0;
    if (!ok || !mac_nz) {
        step("identity", R_FAIL, "ver/mac missing");
    } else if (sn == 0) {
        step("identity", R_INFO, "serial unset");         /* README s.8 step 1: missing serial is a warning */
    } else {
        step("identity", R_PASS, "sn %" PRId32 " rev %" PRId32, sn, rev);
    }
}

static void st_i2c(void)
{
    /* SDA/SCL idle high (step 2): read the pads (inputs stay enabled under the I2C driver; UNRESOLVED on hardware) */
    bool lines = gpio_get_level(BOARD_PIN_I2C_SDA) && gpio_get_level(BOARD_PIN_I2C_SCL);
    bool dac = board_i2c_probe(BOARD_I2C_ADDR_MCP4728);
    bool adc = board_i2c_probe(BOARD_I2C_ADDR_ADS1115);
    char extra[24] = "";
    int ne = 0;
    for (uint8_t a = 0x08; a < 0x78; a++) {
        if (a == BOARD_I2C_ADDR_MCP4728 || a == BOARD_I2C_ADDR_ADS1115) {
            continue;
        }
        if (board_i2c_probe(a) && ne < 3) {
            size_t l = strlen(extra);
            snprintf(extra + l, sizeof(extra) - l, " %02x", a);
            ne++;
        }
    }
    if (!lines || !dac || !adc) {
        step("i2c", R_FAIL, "lines%d dac%d adc%d", lines, dac, adc);
    } else if (ne) {
        step("i2c", R_PASS, "other:%s", extra);          /* README: other addresses are reported */
    } else {
        step("i2c", R_PASS, "ok");
    }
}

static void st_dac_eeprom(void)
{
    mcp4728_regs_t r;
    if (mcp4728_read_all(&r) != ESP_OK) {
        step("dac_eeprom", R_FAIL, "read failed");
    } else if (!mcp4728_eeprom_defaults_ok(&r)) {
        step("dac_eeprom", R_FAIL, "C %03x B %03x", (unsigned)r.eeprom[2].code, (unsigned)r.eeprom[1].code);
    } else {
        step("dac_eeprom", R_PASS, "ok");
    }
}

static int32_t th_mv_avg(void)
{
    vTaskDelay(ticks_at_least_1(TH_SETTLE_MS));
    int32_t v = 0;
    return read_mv(BOARD_ADC_AIN_VTH_MON, &v) ? v : INT32_MIN;
}

static void st_dac_rw(void)
{
    bool ok = mcp4728_write_volatile(BOARD_DAC_CH_HV, BOARD_DAC_HV_SAFE_CODE) == ESP_OK &&
              mcp4728_readback_verify(BOARD_DAC_CH_HV, BOARD_DAC_HV_SAFE_CODE) == ESP_OK;
    if (!ok) {
        step("dac_rw", R_FAIL, "DAC_HV rb");
        return;
    }
    const int dcode = (int)lroundf(TH_STEP_V * TH_CODE_PER_V);
    const uint16_t base = BOARD_DAC_TH_ZERO_CODE;
    int32_t v0, vp, vm;
    ok = mcp4728_write_volatile(BOARD_DAC_CH_TH, base) == ESP_OK && mcp4728_readback_verify(BOARD_DAC_CH_TH, base) == ESP_OK;
    v0 = ok ? th_mv_avg() : INT32_MIN;
    ok = ok && mcp4728_write_volatile(BOARD_DAC_CH_TH, (uint16_t)(base + dcode)) == ESP_OK &&
         mcp4728_readback_verify(BOARD_DAC_CH_TH, (uint16_t)(base + dcode)) == ESP_OK;
    vp = ok ? th_mv_avg() : INT32_MIN;
    ok = ok && mcp4728_write_volatile(BOARD_DAC_CH_TH, (uint16_t)(base - dcode)) == ESP_OK &&
         mcp4728_readback_verify(BOARD_DAC_CH_TH, (uint16_t)(base - dcode)) == ESP_OK;
    vm = ok ? th_mv_avg() : INT32_MIN;
    /* restore DAC_TH to the user's `th` value through the parameter action (main/params_bind.c) */
    int32_t th = 0;
    params_get_i32(PARAM_TH, &th);
    if (params_set_i32(PARAM_TH, th) != ESP_OK) {
        mcp4728_write_volatile(BOARD_DAC_CH_TH, base);
    }
    if (!ok || v0 == INT32_MIN || vp == INT32_MIN || vm == INT32_MIN) {
        step("dac_rw", R_FAIL, "DAC_TH rb/adc");
        return;
    }
    double up = vp - v0, dn = v0 - vm;       /* each should be 4.95 mV +-30 % */
    bool pass = app_selftest_within(up, TH_EXPECT_MV, TH_TOL_FRAC) && app_selftest_within(dn, TH_EXPECT_MV, TH_TOL_FRAC);
    step("dac_rw", pass ? R_PASS : R_FAIL, "up %.1f dn %.1f mV", up, dn);
}

static void st_adc(void)
{
    int32_t g, rs, vt, hv;
    if (!read_mv(BOARD_ADC_AIN_GND, &g) || !read_mv(BOARD_ADC_AIN_RSSI, &rs) ||
        !read_mv(BOARD_ADC_AIN_VTH_MON, &vt) || !read_mv(BOARD_ADC_AIN_HV_MON, &hv)) {
        step("adc", R_FAIL, "read failed");
        return;
    }
    bool pass = abs(g) <= AIN3_ABS_MAX_MV && rs >= RSSI_MIN_MV && rs <= RSSI_MAX_MV &&
                abs(vt - VTH_CENTER_MV) <= VTH_TOL_MV && hv < HVMON_MAX_MV;
    step("adc", pass ? R_PASS : R_FAIL, "g%d r%d t%d h%d", (int)g, (int)rs, (int)vt, (int)hv);
}

static void st_gpio(void)
{
    bool ok = true;
    char d[48] = "";
    ok = ok && drv_gpio_hv_dis_read();                      /* HV_DIS reads high (HV off) */
    bool live = can_link_link_valid();
    if (live) {
        snprintf(d, sizeof(d), "comp skipped: link live");  /* do not shut down a running comparator */
    } else {
        bool was = drv_gpio_comp_enabled();
        drv_gpio_comp_enable(false);
        ok = ok && !drv_gpio_comp_enabled();
        drv_gpio_comp_enable(true);
        ok = ok && drv_gpio_comp_enabled();
        drv_gpio_comp_enable(was);
    }
    bool tia = drv_gpio_tia_get();
    drv_gpio_tia_set(!tia);
    ok = ok && drv_gpio_tia_get() == !tia;
    drv_gpio_tia_set(tia);
    ok = ok && drv_gpio_tia_get() == tia;
    if (!d[0]) {
        snprintf(d, sizeof(d), "pins only; effect not observable");   /* README s.8 step 6 UNRESOLVED note */
    }
    step("gpio", ok ? R_PASS : R_FAIL, "%s", d);
}

static void st_can(void)
{
    int n = 0;
    if (can_link_mode() == CAN_MODE_BUS) {
        step("can", R_SKIP, "bus active rx %" PRIu32, can_link_rx_count());
        return;
    }
    esp_err_t e = can_link_selftest_loopback(&n);
    if (e == ESP_ERR_INVALID_STATE) {
        step("can", R_SKIP, "bus not quiet rx %" PRIu32, can_link_rx_count());
    } else {
        step("can", e == ESP_OK ? R_PASS : R_FAIL, "%d/%d frames", n, CAN_FRAMES);
    }
}

static void st_temp(void)
{
    int32_t t = 0;
    if (params_get_i32(PARAM_TEMP, &t) != ESP_OK) {
        step("temp", R_FAIL, "no sensor");
        return;
    }
    step("temp", (t >= TEMP_MIN_DC && t <= TEMP_MAX_DC) ? R_PASS : R_FAIL, "%.1f C", (double)t / 10.0);
}

/* ---- step 9: HV supply ---- */
static bool fresh_bias(int64_t after_us, float *bias)
{
    for (int i = 0; i < 30; i++) {
        sense_snapshot_t s;
        if (sense_get(&s) && s.valid && s.t_us > after_us) {
            *bias = sense_bias_v(&s);
            if (*bias > s_hv_peak_v) {
                s_hv_peak_v = *bias;
            }
            /* The absolute cap is enforced by the hv_gate machine (per-request cap), not here. */
            return true;
        }
        vTaskDelay(ticks_at_least_1(POLL_MS / 2));
    }
    return false;
}

static bool read_bias(float *bias) { return fresh_bias(esp_timer_get_time(), bias); }

static void hv_finish(void)
{
    app_safety_hv_request(false);
    for (int i = 0; i < 150 && app_safety_hv_state() != HV_OFF; i++) {
        vTaskDelay(ticks_at_least_1(100));
    }
    for (int i = 0; i < HV_DECAY_TIMEOUT_S * 10; i++) {
        float b;
        if (read_bias(&b) && b < HV_DECAY_V) {
            return;
        }
        vTaskDelay(ticks_at_least_1(100));
    }
}

/* Step 9 (finding 5): enable at 0xFFF (the ramp target is hv_min, below the
 * hardware floor, so the code stays pinned at 0xFFF), wait for the bias to
 * settle, record it as hv_floor_v and require 95-115 V; then a slope step of
 * 60 codes. The absolute cap (120 V) is a per-request input of the hv_gate
 * machine, which raises HV_DIS and HV_OVER itself. */
static void st_hv(void)
{
    int32_t hv_min_dv = 1000;
    params_get_i32(PARAM_HV_MIN, &hv_min_dv);
    const float hv_min = hv_min_dv / 10.0f;
    if (hv_min > HV_FLOOR_MAX_V) {
        step("hv", R_SKIP, "hv_min %.0f V too high", (double)hv_min);
        return;
    }
    if (step_result("dac_eeprom") != R_PASS || step_result("dac_rw") != R_PASS || step_result("adc") != R_PASS) {
        step("hv", R_SKIP, "precondition failed");
        return;
    }
    s_hv_peak_v = 0;
    s_hv_floor_v = 0;
    int64_t t_req = esp_timer_get_time();
    esp_err_t e = app_safety_hv_request_ex(true, HV_ABS_CAP_V, hv_min);
    if (e != ESP_OK) {
        step("hv", R_FAIL, "enable refused %s", esp_err_to_name(e));
        return;
    }
    res_t res = R_PASS;
    char d[48];
    snprintf(d, sizeof(d), "ok");
    /* wait for the gate to report ON (arrival), then for 2 s of stable bias */
    float lo = 1e9f, hi = -1e9f, b = 0;
    int64_t t_stable = 0;
    bool settled = false, tripped = false;
    while ((esp_timer_get_time() - t_req) < (int64_t)HV_SETTLE_TIMEOUT_S * 1000000) {
        hv_state_t st = app_safety_hv_state();
        if (st == HV_FAULT || st == HV_OFF) {
            tripped = true;
            break;
        }
        if (read_bias(&b) && st == HV_ON) {
            if (!t_stable) {
                lo = hi = b;
                t_stable = esp_timer_get_time();
            } else if ((fmaxf(hi, b) - fminf(lo, b)) > 2.0f * HV_SETTLE_TOL_V) {
                lo = hi = b;                               /* moved: restart the 2 s window */
                t_stable = esp_timer_get_time();
            } else {
                lo = fminf(lo, b);
                hi = fmaxf(hi, b);
            }
            if ((esp_timer_get_time() - t_stable) >= (int64_t)HV_SETTLE_STABLE_MS * 1000) {
                settled = true;
                break;
            }
        }
    }
    if (tripped) {
        res = R_FAIL;
        snprintf(d, sizeof(d), "tripped f=0x%04x peak %.0f V", (unsigned)fault_get(), (double)s_hv_peak_v);
    } else if (!settled) {
        res = R_FAIL;
        snprintf(d, sizeof(d), "no settle peak %.0f V", (double)s_hv_peak_v);
    } else {
        s_hv_floor_v = 0.5f * (lo + hi);
        if (s_hv_floor_v < HV_FLOOR_MIN_V || s_hv_floor_v > HV_FLOOR_MAX_V) {
            res = R_FAIL;
            snprintf(d, sizeof(d), "floor %.1f V off 95-115", (double)s_hv_floor_v);
        } else {
            /* slope: bias change per DAC volt for a small code step, then back to the floor code */
            float v0 = 0, v1 = 0;
            int c0 = mcp4728_last_code(BOARD_DAC_CH_HV);
            if (c0 >= HV_SLOPE_CODES && read_bias(&v0) &&
                app_range_manual_set_code((uint16_t)(c0 - HV_SLOPE_CODES)) == ESP_OK) {   /* lower code = higher bias */
                vTaskDelay(ticks_at_least_1(HV_SLOPE_SETTLE_MS));
                bool got = read_bias(&v1);
                app_range_manual_set_code((uint16_t)c0);
                vTaskDelay(ticks_at_least_1(HV_SLOPE_SETTLE_MS));
                if (got) {
                    float slope = (v1 - v0) / ((float)HV_SLOPE_CODES * DAC_V_PER_CODE);
                    if (slope < HV_SLOPE_MIN || slope > HV_SLOPE_MAX) {
                        res = R_FAIL;
                    }
                    snprintf(d, sizeof(d), "floor %.1f V slope %.1f V/V", (double)s_hv_floor_v, (double)slope);
                } else {
                    res = R_FAIL;
                    snprintf(d, sizeof(d), "slope read failed");
                }
            } else {
                res = R_FAIL;
                snprintf(d, sizeof(d), "slope setup failed");
            }
            /* VTH_MON window re-read (RSSI window is informational, README: may fall with room light) */
            int32_t vt = 0;
            if (!read_mv(BOARD_ADC_AIN_VTH_MON, &vt) || abs(vt - VTH_CENTER_MV) > VTH_TOL_MV) {
                res = R_FAIL;
                snprintf(d, sizeof(d), "vth %d mV", (int)vt);
            }
        }
    }
    hv_finish();
    step("hv", res, "%s", d);
}

/* ---- JSON ---- */
static void build_json(bool full, bool pass)
{
    int32_t ver = 0, sn = 0;
    params_get_i32(PARAM_FW_VER, &ver);
    params_get_i32(PARAM_SERIAL, &sn);
    static const char *const nm[] = {"pass", "fail", "skip", "info"};
    int n = snprintf(s_json, sizeof(s_json),
                     "{\"selftest\":{\"mode\":\"%s\",\"sn\":%" PRId32 ",\"ver\":\"%d.%d.%d\",\"pass\":%s,\"steps\":[",
                     full ? "full" : "quick", sn, (int)(ver >> 16) & 0xFF, (int)(ver >> 8) & 0xFF, (int)ver & 0xFF,
                     pass ? "true" : "false");
    for (int i = 0; i < s_nsteps && n < (int)sizeof(s_json); i++) {
        n += snprintf(s_json + n, sizeof(s_json) - n, "%s{\"id\":\"%s\",\"r\":\"%s\",\"d\":\"%s\"}", i ? "," : "",
                      s_steps[i].id, nm[s_steps[i].r], s_steps[i].d);
    }
    if (n < (int)sizeof(s_json)) {
        snprintf(s_json + n, sizeof(s_json) - n, "],\"hv_peak_v\":%.1f,\"hv_floor_v\":%.1f,\"usb_ma_est\":null}}",
                 (double)s_hv_peak_v, (double)s_hv_floor_v);
    }
}

esp_err_t app_selftest_run(bool full)
{
    if (atomic_exchange(&s_running, true)) {
        return ESP_ERR_INVALID_STATE;     /* one run at a time (finding 13) */
    }
    if (app_safety_hv_state() != HV_OFF) {
        s_running = false;
        return ESP_ERR_INVALID_STATE;     /* steps 5 and 9 need HV off at the start */
    }
    app_safety_set_auto_inhibit(true);    /* hv_auto must not enable HV during the run */
    if (!s_led_task) {
        xTaskCreate(led_task, "st_led", 2048, NULL, 2, &s_led_task);
    }
    s_nsteps = 0;
    s_hv_peak_v = 0;
    s_hv_floor_v = 0;
    s_json[0] = '\0';
    led_set_mode(1, 0, 0);
    const bool was_auto = app_range_is_auto();
    app_range_set_mode(false);            /* keep the loop from trimming DAC_HV during step 9 */

    st_identity();
    st_i2c();
    st_dac_eeprom();
    st_dac_rw();
    st_adc();
    st_gpio();
    st_can();
    st_temp();
    if (full) {
        st_hv();
    }

    app_range_set_mode(was_auto);
    bool pass = true;
    int first_fail = 0;
    uint16_t fail_mask = 0;
    for (int i = 0; i < s_nsteps; i++) {
        if (s_steps[i].r == R_FAIL) {
            pass = false;
            fail_mask |= (uint16_t)(1u << i);
            if (!first_fail) {
                first_fail = i + 1;
            }
        }
    }
    build_json(full, pass);
    s_last_status = pass ? 1 : 2;
    if (pass) {
        fault_clear(FAULT_SELFTEST);
    } else {
        fault_set(FAULT_SELFTEST);
    }
    {
        uint8_t d[8] = {pass ? 1 : 0, (uint8_t)s_nsteps, (uint8_t)fail_mask, (uint8_t)(fail_mask >> 8),
                        0, 0, 0, 0};
        uint16_t pk = (uint16_t)lroundf(s_hv_peak_v * 10.0f);
        d[4] = (uint8_t)pk;
        d[5] = (uint8_t)(pk >> 8);
        can_link_send_frame(CAN_CLS_RESP, CAN_FN_SELFTEST, d, 8);   /* protocol s.1.6 */
    }
    led_set_mode(pass ? 2 : 3, first_fail, pass ? LED_PASS_MS : (first_fail * 400 + 2000 + 200));
    app_safety_set_auto_inhibit(false);
    s_running = false;
    (void)LED_SHOW_MAX_MS;
    return ESP_OK;
}
