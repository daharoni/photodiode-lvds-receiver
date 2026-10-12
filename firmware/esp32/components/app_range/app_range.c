/* app_range.c - see app_range.h. README s.6, PROPOSED; not run on hardware. */
#include "app_range.h"
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include "app_safety.h"
#include "app_telemetry.h"
#include "board_pins.h"
#include "board_time.h"
#include "can_link.h"
#include "drv_gpio.h"
#include "drv_mcp4728.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "fault.h"
#include "hv_gate.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "params.h"
#include "sense.h"

static const char *TAG = "range";

#define RANGE_TASK_PRIO         8        /* README s.3 task table */
#define RANGE_TASK_STACK        4096     /* PROPOSED */
#define RANGE_PERIOD_MS         100      /* README s.3 task table */
#define DAC_STEP_MAX_CODES      134      /* 20 V/s x 0.1 s / 14.95 mV per code (README s.4 step 9c slew), under the 150-code cap */
#define DAC_DEADBAND_V          0.3f     /* PROPOSED: no write inside +-0.3 V (20 codes) */
#define MANUAL_TRIM_DONE_V      0.5f     /* PROPOSED */
#define MANUAL_SET_CHANGE_V     0.05f    /* PROPOSED: hv_set change that restarts the one-shot trim */
#define DAC_RESYNC_CYCLES       20       /* re-read the MCP4728 every 2 s, PROPOSED */
#define RSSI_RAIL_MV            300      /* README s.6.3 guard: RSSI below 0.3 V */
#define PIN_LIMIT_MS            10000u   /* protocol s.5 bit 13: bias pinned more than 10 s */
#define RAIL_FAULT_MS           1000u    /* PROPOSED persistence before FAULT_RSSI_RAIL / TIA_5K_SAT */
#define HV_UNITS_PER_V          10.0f    /* params hv_* are in 0.1 V (protocol s.2) */

static volatile range_state_t s_state = RANGE_OFF;
static volatile bool s_auto = true;
static volatile uint16_t s_code = BOARD_DAC_HV_SAFE_CODE;
static volatile int32_t s_man_code = -1;     /* manual code target, -1 = none */
static volatile int32_t s_m_x10 = RANGE_M_UNKNOWN_X10;
static range_fsm_t s_fsm;
static range_m_est_cfg_t s_cal;
static portMUX_TYPE s_cal_lock = portMUX_INITIALIZER_UNLOCKED;
static volatile bool s_last_lock_pending;
static float s_last_lock_v;

const char *app_range_state_name(void) { return range_state_str(s_state); }
int app_range_state(void) { return (int)s_state; }
void app_range_set_mode(bool automatic) { s_auto = automatic; }
bool app_range_is_auto(void) { return s_auto; }
int32_t app_range_m_est_x10(void) { return s_m_x10; }
uint16_t app_range_dac_code(void) { return s_code; }

void app_range_cal_set_v100(float v100)
{
    taskENTER_CRITICAL(&s_cal_lock);
    range_m_est_set_v100(&s_cal, v100);
    taskEXIT_CRITICAL(&s_cal_lock);
}

void app_range_cal_set_code(uint16_t code, float bias_v)
{
    taskENTER_CRITICAL(&s_cal_lock);
    range_m_est_set_code_cal(&s_cal, code, bias_v);
    taskEXIT_CRITICAL(&s_cal_lock);
}

esp_err_t app_range_manual_set_code(uint16_t code)
{
    if (code > 0xFFF) {
        return ESP_ERR_INVALID_ARG;
    }
    if (s_auto || app_safety_hv_state() != HV_ON) {
        return ESP_ERR_INVALID_STATE;
    }
    s_man_code = code;
    return ESP_OK;
}

void app_range_set_last_lock(float v_lock)
{
    s_last_lock_v = v_lock;
    s_last_lock_pending = true;
}

static int32_t g_m_est(void) { return s_m_x10; }

static float param_v(uint16_t id, float fallback)
{
    int32_t v = 0;
    return params_get_i32(id, &v) == ESP_OK ? (float)v / HV_UNITS_PER_V : fallback;
}

static bool param_node0(void)
{
    int32_t n = 0;
    return params_get_i32(PARAM_NODE, &n) == ESP_OK && n == 0;
}

static bool param_flag(uint16_t id, bool fallback)
{
    int32_t v = 0;
    return params_get_i32(id, &v) == ESP_OK ? v != 0 : fallback;
}

static void event(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void event(const char *fmt, ...)
{
    char line[160];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(line, sizeof(line), fmt, ap);
    va_end(ap);
    app_telemetry_event(line);      /* README s.6.6 JSON event line */
}

/* One closed-loop step of DAC_HV toward target_v. Higher code = lower bias. */
static void dac_step(float target_v, float bias_v, float hv_max_v)
{
    float err = target_v - bias_v;
    if (fabsf(err) < DAC_DEADBAND_V) {
        return;
    }
    if (app_safety_hv_state() != HV_ON) {
        return;                         /* the gate owns the DAC during ramps (review finding 2) */
    }
    int32_t d = (int32_t)lroundf(err / BOARD_HV_V_PER_CODE);
    if (d > DAC_STEP_MAX_CODES) d = DAC_STEP_MAX_CODES;
    if (d < -DAC_STEP_MAX_CODES) d = -DAC_STEP_MAX_CODES;
    int32_t code = (int32_t)s_code - d;
    const int32_t cmin = hvg_code_min(hv_max_v);       /* open-loop bound, review finding 4 */
    if (code < cmin) code = cmin;
    if (code > 0xFFF) code = 0xFFF;
    if (mcp4728_write_volatile(BOARD_DAC_CH_HV, (uint16_t)code) == ESP_OK) {
        s_code = (uint16_t)code;
    }
}

static void range_task(void *arg)
{
    (void)arg;
    range_fsm_init(&s_fsm);
    range_state_t prev_state = RANGE_OFF;
    bool controlled_prev = false;
    int resync = 0;
    float last_hv_set = -1000.0f;
    bool manual_trim = false;
    bool node0_warned = false;
    uint32_t pin_since = 0, rail_since = 0, sat_since = 0;
    bool pin_set = false, rail_set = false, sat_set = false;
    TickType_t wake = xTaskGetTickCount();

    for (;;) {
        vTaskDelayUntil(&wake, ticks_at_least_1(RANGE_PERIOD_MS));
        app_safety_task_checkin(APP_TASK_RANGE);
        if (s_last_lock_pending) {
            range_fsm_set_last_lock(&s_fsm, s_last_lock_v);
            s_last_lock_pending = false;
        }
        {
            /* The ramp target is owned here (review finding 16): the soft start walks to
             * hv_set only if the FSM would (a saved lock exists), otherwise to hv_min.
             * Same rule as the FSM's RANGE_OFF branch. */
            const float lo = param_v(PARAM_HV_MIN, 100.0f);
            float hi = param_v(PARAM_HV_MAX, 200.0f);
            if (hi < lo) hi = lo;
            float t = lo;
            if (s_fsm.have_lock) {
                t = param_v(PARAM_HV_SET, 100.0f);
                t = t < lo ? lo : (t > hi ? hi : t);
            }
            app_safety_set_ramp_target_dv((int32_t)lroundf(t * HV_UNITS_PER_V));
        }

        sense_snapshot_t s;
        if (!sense_get(&s) || !s.valid) {
            continue;                       /* no fresh measurement: hold everything */
        }
        const uint32_t now_ms = (uint32_t)(esp_timer_get_time() / 1000);
        const hv_state_t hs = app_safety_hv_state();
        const float bias = sense_bias_v(&s);

        /* Node 0 (unassigned) in bus mode has no LINK_ALL nibble, so the metrics are meaningless:
         * force MANUAL (review finding 17). Warn once per episode. */
        const bool node0_bus = param_node0() && can_link_mode() == CAN_MODE_BUS;
        if (node0_bus && s_auto && !node0_warned) {
            node0_warned = true;
            ESP_LOGW(TAG, "node id 0 in bus mode: loop forced to MANUAL until a node id is assigned");
            event("{\"ev\":\"warn\",\"msg\":\"node0 bus: loop manual\"}");
        } else if (!node0_bus) {
            node0_warned = false;
        }

        range_in_t in = {
            .hv_on = hs == HV_RAMP || hs == HV_ON || hs == HV_HOLD,
            .bias_v = bias,
            .rssi_drop_mv = sense_rssi_drop_mv(),
            .tia_20k = drv_gpio_tia_get(),
            .link_valid = can_link_link_valid(),
            .err_class = can_link_err_class(),
            .automatic = s_auto && !node0_bus,
            .bus_mode = can_link_mode() == CAN_MODE_BUS && can_link_master_seen(),
            .hv_min_v = param_v(PARAM_HV_MIN, 100.0f),
            .hv_max_v = param_v(PARAM_HV_MAX, 200.0f),
            .hv_set_v = param_v(PARAM_HV_SET, 100.0f),
            .now_ms = now_ms,
            .fault = (fault_get() & FAULT_HV_BLOCKING_MASK) != 0,
            .rssi_rail = s.rssi_mv < RSSI_RAIL_MV,
            .tia_auto = param_flag(PARAM_TIA_AUTO, false),
        };
        range_out_t out;
        range_fsm_step(&s_fsm, &in, &out);
        s_state = out.state;

        if (out.tia_changed) {
            drv_gpio_tia_set(out.tia_20k);
            event("{\"ev\":\"tia\",\"to\":\"%s\",\"drop\":%.2f,\"bias\":%.1f}", out.tia_20k ? "20k" : "5k",
                  (double)in.rssi_drop_mv / 1000.0, (double)bias);
        }
        if (out.state != prev_state) {
            event("{\"ev\":\"loop\",\"from\":\"%s\",\"to\":\"%s\",\"bias\":%.1f,\"target\":%.1f}",
                  range_state_str(prev_state), range_state_str(out.state), (double)bias, (double)out.bias_target_v);
            prev_state = out.state;
        }

        /* ---- DAC_HV: only while safety reports HV_ON and the loop is in a controlling state ---- */
        const bool controlling = hs == HV_ON && (out.state == RANGE_SEARCH || out.state == RANGE_TRACK ||
                                                 out.state == RANGE_LOS || out.state == RANGE_MANUAL);
        if (!controlling || !controlled_prev || ++resync >= DAC_RESYNC_CYCLES) {
            resync = 0;
            if (hs == HV_ON || hs == HV_RAMP) {
                mcp4728_regs_t r;
                if (mcp4728_read_all(&r) == ESP_OK) {
                    s_code = r.input[BOARD_DAC_CH_HV].code;     /* adopt what safety wrote */
                }
            }
        }
        /* Explicit manual code target (console / CAN / self-test), loop manual only. */
        const bool code_target = s_man_code >= 0;
        if (code_target && (s_auto || hs != HV_ON)) {
            s_man_code = -1;                                   /* stale: loop went auto or HV left ON */
        } else if (code_target) {
            int32_t next = range_manual_code_step(s_code, s_man_code, bias, in.hv_min_v, in.hv_max_v,
                                                  BOARD_HV_V_PER_CODE, DAC_STEP_MAX_CODES,
                                                  hvg_code_min(in.hv_max_v));
            if (next != s_code && mcp4728_write_volatile(BOARD_DAC_CH_HV, (uint16_t)next) == ESP_OK) {
                s_code = (uint16_t)next;
            }
        }
        if (s_man_code >= 0) {
            manual_trim = false;                               /* the explicit target wins over the one-shot trim */
        } else if (controlling) {
            if (out.state == RANGE_MANUAL) {
                /* README s.6.5: hold the code; a changed hv_set triggers one closed-loop trim */
                if (fabsf(in.hv_set_v - last_hv_set) > MANUAL_SET_CHANGE_V) {
                    manual_trim = last_hv_set > -999.0f;       /* the first value is the arrival bias, no trim */
                    last_hv_set = in.hv_set_v;
                }
                if (manual_trim) {
                    if (fabsf(out.bias_target_v - bias) <= MANUAL_TRIM_DONE_V) {
                        manual_trim = false;
                    } else {
                        dac_step(out.bias_target_v, bias, in.hv_max_v);
                    }
                }
            } else {
                manual_trim = false;
                last_hv_set = in.hv_set_v;
                dac_step(out.bias_target_v, bias, in.hv_max_v);
            }
        } else {
            manual_trim = false;
            last_hv_set = -1000.0f;
        }
        controlled_prev = controlling;

        /* ---- M estimate (README s.6.4) ---- */
        {
            range_m_est_cfg_t c;
            taskENTER_CRITICAL(&s_cal_lock);
            c = s_cal;
            taskEXIT_CRITICAL(&s_cal_lock);
            int32_t vbr_dv = 0;
            if (!c.have_v100 && params_get_i32(PARAM_VBR, &vbr_dv) == ESP_OK && vbr_dv > 0) {
                range_m_est_set_vbr(&c, (float)vbr_dv / HV_UNITS_PER_V);
            }
            s_m_x10 = (hs == HV_ON) ? range_m_est_x10(&c, s_code, bias) : RANGE_M_UNKNOWN_X10;
        }

        /* ---- telemetry faults (protocol s.5 bits 10, 11, 13; not HV-blocking) ---- */
        const bool auto_states = out.state == RANGE_SEARCH || out.state == RANGE_TRACK;
        bool pinned = auto_states && out.bias_target_v >= in.hv_max_v - 0.05f;   /* hv_max only: see README.md */
        if (pinned) {
            if (!pin_set) { pin_set = true; pin_since = now_ms; }
            else if (now_ms - pin_since >= PIN_LIMIT_MS) fault_set(FAULT_LOOP_LIMIT);
        } else {
            pin_set = false;
        }
        bool rail5 = in.rssi_rail && !in.tia_20k && hs == HV_ON;
        if (rail5) {
            if (!rail_set) { rail_set = true; rail_since = now_ms; }
            else if (now_ms - rail_since >= RAIL_FAULT_MS) fault_set(FAULT_RSSI_RAIL);
        } else {
            rail_set = false;
        }
        bool sat5 = rail5 && bias <= in.hv_min_v + 1.0f;
        if (sat5) {
            if (!sat_set) { sat_set = true; sat_since = now_ms; }
            else if (now_ms - sat_since >= RAIL_FAULT_MS) fault_set(FAULT_TIA_5K_SAT);
        } else {
            sat_set = false;
        }
    }
}

void app_range_start(void)
{
    range_m_est_init(&s_cal);
    params_register_live(PARAM_M_EST, g_m_est);
    int32_t loop = 1;
    if (params_get_i32(PARAM_LOOP, &loop) == ESP_OK) {
        s_auto = loop != 0;
    }
    if (xTaskCreate(range_task, "range", RANGE_TASK_STACK, NULL, RANGE_TASK_PRIO, NULL) != pdPASS) {
        ESP_LOGE(TAG, "task create failed");
    }
}
