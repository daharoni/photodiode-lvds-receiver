/* HV gate. PROPOSED; compiled status in README.md of this component.
 *
 * Ownership of HV_DIS: every write is in hv_dis_apply(), under one spinlock,
 * and it always computes the level from the same three flags
 * (s_hv_req, s_force_off, blocking faults). Only the safety task lowers the
 * pin; hv_off_now() only raises it. */
#include "app_safety.h"
#include <math.h>
#include "board_pins.h"
#include "drv_gpio.h"
#include "drv_mcp4728.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "params.h"
#include "sense.h"
#include "can_link.h"

static const char *TAG = "safety";

/* ---- constants (source in each comment) -------------------------------- */
#define SAFETY_PERIOD_MS        10      /* README s.3 task table: safety 10 ms */
#define SAFETY_TASK_PRIO        20      /* README s.3 */
#define RAMP_TASK_PRIO          8       /* PROPOSED: same as range (README s.3), not in the plan for a separate task */
#define HV_OVER_MARGIN_DV       50      /* README s.5: hv_max + 5 V (0.1 V units) */
#define HV_UNDER_PERCENT        70      /* README s.5: collapse below 70 % of set */
#define HV_STUCK_THRESHOLD_V    20.0f   /* protocol s.5 bit 5: above 20 V */
#define HV_STUCK_AFTER_MS       30000   /* protocol s.5 bit 5: 30 s after HV_DIS high */
#define RAMP_STEP_MS            100     /* README s.4 step 9(c): each 100 ms */
#define RAMP_SLEW_V_PER_S       20.0f   /* README s.4 step 9(c), PROPOSED */
#define RAMP_MAX_STEP_CODES     150     /* README s.4 step 9(c) */
#define RAMP_ARRIVE_BAND_V      2.0f    /* README s.4 step 9(d) */
#define RAMP_ARRIVE_HOLD_MS     1000    /* README s.4 step 9(d) */
#define RAMP_TIMEOUT_MS         10000   /* README s.4 step 9(d) */
#define RAMP_DOWN_V_PER_S       50.0f   /* README s.4 step 10 */
#define SENSE_STALE_MS          500     /* UNRESOLVED: first guess (sense round is about 30 ms, README s.3) */
#define UNDER_DEBOUNCE_SAMPLES  2       /* UNRESOLVED: distinct snapshots required below 70 % */
#define TASK_SILENT_MS          2000    /* UNRESOLVED: monitored task check-in timeout */
#define DAC_SAFE_RETRY_MS       500     /* UNRESOLVED: retry period for DAC_HV safe write after a fault */

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static volatile bool s_hv_req;          /* want the supply enabled (under s_lock) */
static volatile bool s_force_off;       /* latched by hv_off_now until next request (s_lock) */
static volatile hv_state_t s_state = HV_OFF;
static volatile bool s_ramp_down;       /* RAMP state is a commanded turn-off */
static volatile bool s_dac_verified, s_adc_ok;
static volatile bool s_dac_needs_safe;  /* DAC_HV must be returned to 0xFFF */
static volatile int64_t s_dis_since_us; /* when HV_DIS last went high */
static uint8_t s_reset_reason;
static const char *s_reset_name = "other";
static volatile int64_t s_checkin_us[APP_TASK_COUNT];
static TaskHandle_t s_ramp_task;

/* ---- the one HV_DIS writer --------------------------------------------- */
/* Caller holds s_lock. */
static void hv_dis_apply_locked(void)
{
    bool blocked = (fault_get() & FAULT_HV_BLOCKING_MASK) != 0;
    bool want = s_hv_req && !s_force_off && !blocked;
    bool was_enabled = !drv_gpio_hv_dis_read();
    drv_gpio_hv_dis_write(!want);
    if (!want && was_enabled) {
        s_dis_since_us = esp_timer_get_time();
    }
}

void app_safety_init(void)
{
    /* README s.4 step 1: level first, then direction (no glitch). */
    drv_gpio_hv_dis_write(true);
    s_dis_since_us = esp_timer_get_time();

    switch (esp_reset_reason()) {
    case ESP_RST_POWERON: s_reset_reason = 1; s_reset_name = "poweron"; break;
    case ESP_RST_SW:      s_reset_reason = 2; s_reset_name = "sw"; break;
    case ESP_RST_BROWNOUT:
        s_reset_reason = 3; s_reset_name = "brownout"; fault_set(FAULT_BROWNOUT); break;
    case ESP_RST_TASK_WDT:
        s_reset_reason = 4; s_reset_name = "task_wdt"; fault_set(FAULT_WDT); break;
    case ESP_RST_INT_WDT:
        s_reset_reason = 5; s_reset_name = "int_wdt"; fault_set(FAULT_WDT); break;
    case ESP_RST_WDT:
        s_reset_reason = 6; s_reset_name = "wdt"; fault_set(FAULT_WDT); break;
    default: s_reset_reason = 6; s_reset_name = "other"; break;
    }
}

uint8_t app_safety_reset_reason(void) { return s_reset_reason; }
const char *app_safety_reset_reason_name(void) { return s_reset_name; }

void app_safety_set_dac_verified(bool ok) { s_dac_verified = ok; }
void app_safety_set_adc_ok(bool ok) { s_adc_ok = ok; }

hv_state_t app_safety_hv_state(void) { return s_state; }
bool app_safety_hv_enabled(void) { return !drv_gpio_hv_dis_read(); }

const char *app_safety_hv_state_name(hv_state_t s)
{
    static const char *const n[] = {"off", "ramp", "on", "hold", "fault"};
    return ((unsigned)s <= HV_FAULT) ? n[s] : "?";
}

void app_safety_task_checkin(uint8_t task_id)
{
    if (task_id < APP_TASK_COUNT) {
        s_checkin_us[task_id] = esp_timer_get_time();
    }
}

void app_safety_hv_off_now(void)
{
    taskENTER_CRITICAL(&s_lock);
    s_force_off = true;
    s_hv_req = false;
    hv_dis_apply_locked();
    s_state = (fault_get() & FAULT_HV_BLOCKING_MASK) ? HV_FAULT : HV_OFF;
    s_dac_needs_safe = true;
    taskEXIT_CRITICAL(&s_lock);
}

esp_err_t app_safety_hv_request(bool on)
{
    esp_err_t res = ESP_OK;
    if (on) {
        taskENTER_CRITICAL(&s_lock);
        if ((fault_get() & FAULT_HV_BLOCKING_MASK) || !s_dac_verified || !s_adc_ok) {
            res = ESP_ERR_INVALID_STATE;
        } else if (s_state == HV_RAMP && s_ramp_down) {
            res = ESP_ERR_INVALID_STATE;
        } else if (s_state == HV_OFF) {
            s_force_off = false;
            s_hv_req = true;
            s_ramp_down = false;
            s_state = HV_RAMP;
        } else if (s_state == HV_FAULT) {
            res = ESP_ERR_INVALID_STATE;
        }
        bool start = (res == ESP_OK && s_state == HV_RAMP && !s_ramp_down);
        taskEXIT_CRITICAL(&s_lock);
        if (start && s_ramp_task) {
            xTaskNotify(s_ramp_task, 1, eSetValueWithOverwrite);
        }
    } else {
        taskENTER_CRITICAL(&s_lock);
        bool start = (s_state == HV_RAMP || s_state == HV_ON || s_state == HV_HOLD);
        if (start) {
            s_state = HV_RAMP;
            s_ramp_down = true;
        }
        taskEXIT_CRITICAL(&s_lock);
        if (start && s_ramp_task) {
            xTaskNotify(s_ramp_task, 2, eSetValueWithOverwrite);
        }
    }
    return res;
}

void app_safety_faults_clear(void)
{
    /* Conditions that are still true re-latch on the next safety tick; the
     * verified flags (set false by faults at boot) keep HV refused. */
    fault_word_t keep = 0;
    sense_snapshot_t s;
    if (sense_get(&s) && s.valid && sense_bias_v(&s) > HV_STUCK_THRESHOLD_V && !app_safety_hv_enabled()) {
        keep |= FAULT_HV_STUCK;
    }
    if (!s_dac_verified) {
        keep |= FAULT_I2C_DAC | FAULT_DAC_EEPROM;
    }
    if (!s_adc_ok) {
        keep |= FAULT_I2C_ADC;
    }
    fault_clear((fault_word_t)~keep);
}

/* ---- ramp task: DAC walks (README s.4 steps 9 and 10) ------------------- */
static int32_t get_p(uint16_t id)
{
    int32_t v = 0;
    params_get_i32(id, &v);
    return v;
}

static bool dac_write(uint16_t code)
{
    esp_err_t e = mcp4728_write_volatile(BOARD_DAC_CH_HV, code);
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "DAC_HV write failed: %s", esp_err_to_name(e));
        fault_set(FAULT_I2C_DAC);
        return false;
    }
    return true;
}

static void ramp_up(void)
{
    /* Wait for the safety task to drive HV_DIS low (README s.4 step 9(b)). */
    int64_t t0 = esp_timer_get_time();
    while (!app_safety_hv_enabled()) {
        if (s_state != HV_RAMP || s_ramp_down) {
            return;
        }
        if ((esp_timer_get_time() - t0) > 200000) {
            return; /* never enabled; state will be resolved by the safety task */
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
    int64_t t_start = esp_timer_get_time();
    int64_t in_band_since = 0;
    int32_t code = BOARD_DAC_HV_SAFE_CODE;
    const float slew_codes = RAMP_SLEW_V_PER_S * (RAMP_STEP_MS / 1000.0f) / BOARD_HV_V_PER_CODE;
    int max_step = (int)fminf((float)RAMP_MAX_STEP_CODES, slew_codes);

    while (s_state == HV_RAMP && !s_ramp_down) {
        vTaskDelay(pdMS_TO_TICKS(RAMP_STEP_MS));
        sense_snapshot_t s;
        if (!sense_get(&s) || !s.valid) {
            if ((esp_timer_get_time() - t_start) > RAMP_TIMEOUT_MS * 1000LL) {
                break;
            }
            continue;
        }
        float target = get_p(PARAM_HV_SET) * 0.1f;
        float err = target - sense_bias_v(&s);
        int step = (int)lroundf(err / BOARD_HV_V_PER_CODE);
        if (step > max_step) step = max_step;
        if (step < -max_step) step = -max_step;
        code -= step;   /* lower code = higher bias */
        if (code < 0) code = 0;
        if (code > BOARD_DAC_HV_SAFE_CODE) code = BOARD_DAC_HV_SAFE_CODE;
        if (!dac_write((uint16_t)code)) {
            return;
        }
        /* Arrival: within 2 V for 1 s. Also accepted when the code is pinned
         * at the minimum-bias end and the bias is above target (the supply
         * cannot go lower). PROPOSED. */
        bool in_band = fabsf(err) < RAMP_ARRIVE_BAND_V ||
                       (code == BOARD_DAC_HV_SAFE_CODE && err < 0);
        int64_t now = esp_timer_get_time();
        if (!in_band) {
            in_band_since = 0;
        } else if (in_band_since == 0) {
            in_band_since = now;
        } else if ((now - in_band_since) >= RAMP_ARRIVE_HOLD_MS * 1000LL) {
            taskENTER_CRITICAL(&s_lock);
            if (s_state == HV_RAMP && !s_ramp_down) {
                s_state = HV_ON;
            }
            taskEXIT_CRITICAL(&s_lock);
            return;
        }
        if ((now - t_start) > RAMP_TIMEOUT_MS * 1000LL) {
            break;
        }
    }
    if (s_state == HV_RAMP && !s_ramp_down) {
        ESP_LOGW(TAG, "ramp timeout");
        fault_set(FAULT_HV_UNDER);   /* safety task turns HV off */
    }
}

static void ramp_down(void)
{
    /* README s.4 step 10: DAC_HV back to 0xFFF at 50 V/s, then HV_DIS high. */
    int32_t codes_per_step = (int32_t)ceilf(RAMP_DOWN_V_PER_S * (RAMP_STEP_MS / 1000.0f) / BOARD_HV_V_PER_CODE);
    /* The present code is not read back (the contract has no getter); walk
     * from 0 would waste time, so use the measured bias to estimate it. */
    sense_snapshot_t s;
    int32_t code = BOARD_DAC_HV_SAFE_CODE;
    if (sense_get(&s) && s.valid) {
        float over = sense_bias_v(&s) - get_p(PARAM_HV_MIN) * 0.1f;
        if (over > 0) {
            code = BOARD_DAC_HV_SAFE_CODE - (int32_t)(over / BOARD_HV_V_PER_CODE);
        }
        if (code < 0) code = 0;
    }
    while (code < BOARD_DAC_HV_SAFE_CODE && s_state == HV_RAMP && s_ramp_down) {
        code += codes_per_step;
        if (code > BOARD_DAC_HV_SAFE_CODE) code = BOARD_DAC_HV_SAFE_CODE;
        if (!dac_write((uint16_t)code)) {
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(RAMP_STEP_MS));
    }
    dac_write(BOARD_DAC_HV_SAFE_CODE);
    taskENTER_CRITICAL(&s_lock);
    if (s_state == HV_RAMP && s_ramp_down) {
        s_hv_req = false;
        s_ramp_down = false;
        s_state = HV_OFF;
        hv_dis_apply_locked();
    }
    taskEXIT_CRITICAL(&s_lock);
}

static void ramp_task(void *arg)
{
    (void)arg;
    for (;;) {
        uint32_t cmd = 0;
        if (xTaskNotifyWait(0, UINT32_MAX, &cmd, pdMS_TO_TICKS(DAC_SAFE_RETRY_MS)) == pdTRUE) {
            if (cmd == 1) {
                ramp_up();
            } else if (cmd == 2) {
                ramp_down();
            }
        }
        /* After a fault trip, return DAC_HV to the minimum-bias code
         * (README s.4 step 10, "afterwards"). */
        if (s_dac_needs_safe && !app_safety_hv_enabled()) {
            if (dac_write(BOARD_DAC_HV_SAFE_CODE)) {
                s_dac_needs_safe = false;
            }
        }
    }
}

/* ---- safety task -------------------------------------------------------- */
static void safety_task(void *arg)
{
    (void)arg;
    esp_task_wdt_add(NULL);
    TickType_t last = xTaskGetTickCount();
    int64_t last_sample_us = 0;
    int under_count = 0;

    for (;;) {
        vTaskDelayUntil(&last, pdMS_TO_TICKS(SAFETY_PERIOD_MS));
        int64_t now = esp_timer_get_time();

        /* Watchdog: feed only if every monitored task checked in recently. */
        bool all_alive = true;
        for (int i = 0; i < APP_TASK_COUNT; i++) {
            int64_t t = s_checkin_us[i];
            if (t != 0 && (now - t) > TASK_SILENT_MS * 1000LL) {
                all_alive = false;
            }
        }
        if (all_alive) {
            esp_task_wdt_reset();
        }

        sense_snapshot_t s;
        bool have = sense_get(&s) && s.valid;
        bool enabled = app_safety_hv_enabled();
        hv_state_t st = s_state;

        if (enabled) {
            if (!have || (now - s.t_us) > SENSE_STALE_MS * 1000LL) {
                fault_set(FAULT_I2C_ADC);
                s_adc_ok = false;
            } else {
                int32_t bias_dv = (int32_t)lroundf(sense_bias_v(&s) * 10.0f);
                if (bias_dv > get_p(PARAM_HV_MAX) + HV_OVER_MARGIN_DV) {
                    fault_set(FAULT_HV_OVER);
                }
                if (st == HV_ON && s.t_us != last_sample_us) {
                    last_sample_us = s.t_us;
                    if (bias_dv * 100 < get_p(PARAM_HV_SET) * HV_UNDER_PERCENT) {
                        if (++under_count >= UNDER_DEBOUNCE_SAMPLES) {
                            fault_set(FAULT_HV_UNDER);
                        }
                    } else {
                        under_count = 0;
                    }
                }
            }
            if (can_link_mode() == CAN_MODE_BUS &&
                can_link_heartbeat_age_ms() > (uint32_t)get_p(PARAM_BUS_TIMEOUT)) {
                fault_set(FAULT_CAN_TIMEOUT);
            }
        } else {
            under_count = 0;
            if (have && sense_bias_v(&s) > HV_STUCK_THRESHOLD_V &&
                (now - s_dis_since_us) > HV_STUCK_AFTER_MS * 1000LL) {
                fault_set(FAULT_HV_STUCK);
            }
        }

        /* Apply: one place, under the lock. A newly latched blocking fault
         * lowers `want` inside hv_dis_apply_locked(), so HV_DIS goes high
         * within this tick (README s.5: within 10 ms of detection). */
        taskENTER_CRITICAL(&s_lock);
        hv_dis_apply_locked();
        if ((fault_get() & FAULT_HV_BLOCKING_MASK) && s_state != HV_FAULT && s_state != HV_OFF) {
            s_hv_req = false;
            s_ramp_down = false;
            s_state = HV_FAULT;
            s_dac_needs_safe = true;
        } else if (s_state == HV_FAULT && !(fault_get() & FAULT_HV_BLOCKING_MASK)) {
            s_state = HV_OFF;
        } else if ((fault_get() & FAULT_HV_BLOCKING_MASK) && s_state == HV_OFF) {
            /* faults latched while off: reflect them in the state */
            s_state = HV_FAULT;
        }
        taskEXIT_CRITICAL(&s_lock);
    }
}

void app_safety_start(void)
{
    xTaskCreate(ramp_task, "hv_ramp", 3072, NULL, RAMP_TASK_PRIO, &s_ramp_task);
    xTaskCreate(safety_task, "safety", 3072, NULL, SAFETY_TASK_PRIO, NULL);
}
