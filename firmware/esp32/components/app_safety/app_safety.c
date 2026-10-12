/* HV gate wrapper. PROPOSED; compiled status in README.md of this component.
 * Logic: hv_gate.c (pure, host-tested). This file does the I/O: reads the
 * inputs, holds the lock, writes HV_DIS, runs the DAC commands the machine
 * issues, and owns the watchdog and the fault-clear policy.
 *
 * Locking: s_lock (spinlock) guards s_gate and every HV_DIS write. Nothing that
 * can block (sense_get, params, I2C) runs under it: inputs are built first. */
#include "app_safety.h"
#include <math.h>
#include <string.h>
#include "board_pins.h"
#include "board_time.h"
#include "can_link.h"
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

static const char *TAG = "safety";

/* ---- constants (source in each comment) -------------------------------- */
#define SAFETY_PERIOD_MS        10      /* README s.3 task table: safety 10 ms */
#define SAFETY_TASK_PRIO        20      /* README s.3 */
#define EXEC_TASK_PRIO          8       /* PROPOSED: same as range (README s.3); it only does I2C for the gate */
#define EXEC_TASK_STACK         3072
#define EXEC_WAIT_MS            20      /* PROPOSED: poll period of the executor when not notified */
#define AUTO_POLL_MS            500     /* PROPOSED: hv_auto re-arm check (finding 7) */
#define HV_STUCK_THRESHOLD_V    HVG_STUCK_V
#define TASK_SILENT_MS          2000    /* UNRESOLVED: monitored task check-in timeout */

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static hvg_t s_gate;                    /* under s_lock */
static volatile bool s_dac_verified, s_adc_ok;
static volatile bool s_manual_busy;     /* a manual DAC_HV write is in progress (under s_lock) */
static volatile bool s_auto_inhibit;    /* self-test running */
static volatile bool s_auto_off_latch;  /* operator turned HV off: no hv_auto until the next on */
static volatile int32_t s_ramp_target_dv;
static uint8_t s_reset_reason;
static const char *s_reset_name = "other";
static volatile int64_t s_checkin_us[APP_TASK_COUNT];
static TaskHandle_t s_exec_task;

static int32_t get_p(uint16_t id)
{
    int32_t v = 0;
    params_get_i32(id, &v);
    return v;
}

/* ---- inputs --------------------------------------------------------------- */
static void build_in(hvg_in_t *in)
{
    memset(in, 0, sizeof(*in));
    sense_snapshot_t s;
    const bool have = sense_get(&s) && s.valid;
    const int64_t now_us = esp_timer_get_time();
    in->now_ms = (uint32_t)(now_us / 1000);
    in->blocking_fault = (fault_get() & FAULT_HV_BLOCKING_MASK) != 0;
    in->dac_verified = s_dac_verified;
    in->adc_ok = s_adc_ok;
    in->sense_ok = have && (now_us - s.t_us) <= (int64_t)HVG_SENSE_STALE_MS * 1000;
    in->sample_seq = have ? (uint32_t)(s.t_us / 1000) : 0;
    in->bias_v = have ? sense_bias_v(&s) : 0.0f;
    in->dac_code = mcp4728_last_code(BOARD_DAC_CH_HV);
    in->hv_set_v = get_p(PARAM_HV_SET) * 0.1f;
    in->hv_min_v = get_p(PARAM_HV_MIN) * 0.1f;
    in->hv_max_v = get_p(PARAM_HV_MAX) * 0.1f;
    in->ramp_target_v = s_ramp_target_dv > 0 ? s_ramp_target_dv * 0.1f : 0.0f;
}

/* ---- the one HV_DIS writer: copies the machine's level (caller holds s_lock) ---- */
static void pin_apply_locked(void)
{
    drv_gpio_hv_dis_write(hvg_hv_dis(&s_gate));
}

static void kick_exec(bool pending)
{
    if (pending && s_exec_task) {
        xTaskNotifyGive(s_exec_task);
    }
}

void app_safety_init(void)
{
    /* README s.4 step 1: level first, then direction (no glitch). */
    drv_gpio_hv_dis_write(true);
    hvg_init(&s_gate);

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
bool app_safety_dac_verified(void) { return s_dac_verified; }
void app_safety_set_ramp_target_dv(int32_t dv) { s_ramp_target_dv = dv; }
void app_safety_set_auto_inhibit(bool inhibit) { s_auto_inhibit = inhibit; }

hv_state_t app_safety_hv_state(void)
{
    hvg_state_t g;
    taskENTER_CRITICAL(&s_lock);
    g = hvg_state(&s_gate);
    taskEXIT_CRITICAL(&s_lock);
    switch (g) {
    case HVG_ARMING:
    case HVG_RAMP_UP:
    case HVG_RAMP_DOWN: return HV_RAMP;
    case HVG_ON:        return HV_ON;
    case HVG_FAULT:     return HV_FAULT;
    default:            return HV_OFF;
    }
}

const char *app_safety_gate_state_name(void)
{
    hvg_state_t g;
    taskENTER_CRITICAL(&s_lock);
    g = hvg_state(&s_gate);
    taskEXIT_CRITICAL(&s_lock);
    return hvg_state_name(g);
}

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
    hvg_in_t in;
    build_in(&in);
    taskENTER_CRITICAL(&s_lock);
    hvg_force_off(&s_gate, &in);
    pin_apply_locked();
    bool pending = s_gate.cmd_pending;
    taskEXIT_CRITICAL(&s_lock);
    kick_exec(pending);
}

esp_err_t app_safety_hv_request_ex(bool on, float cap_v, float target_v)
{
    hvg_in_t in;
    build_in(&in);
    taskENTER_CRITICAL(&s_lock);
    bool ok = !(on && s_manual_busy) && hvg_request(&s_gate, on, &in, cap_v, target_v);
    pin_apply_locked();     /* a restart raises HV_DIS in the same call */
    bool pending = s_gate.cmd_pending;
    taskEXIT_CRITICAL(&s_lock);
    if (ok) {
        s_auto_off_latch = !on;
    }
    kick_exec(pending);
    return ok ? ESP_OK : ESP_ERR_INVALID_STATE;
}

esp_err_t app_safety_hv_request(bool on) { return app_safety_hv_request_ex(on, 0.0f, 0.0f); }

esp_err_t app_safety_manual_dac_hv(uint16_t code)
{
    esp_err_t res = ESP_ERR_INVALID_STATE;
    taskENTER_CRITICAL(&s_lock);
    if (hvg_hv_dis(&s_gate) && hvg_state(&s_gate) == HVG_OFF && !s_manual_busy && !s_gate.cmd_pending &&
        !s_gate.cmd_inflight) {
        s_manual_busy = true;       /* an enable request is refused until the write is done */
        res = ESP_OK;
    }
    taskEXIT_CRITICAL(&s_lock);
    if (res != ESP_OK) {
        return res;
    }
    res = mcp4728_write_volatile(BOARD_DAC_CH_HV, code);
    taskENTER_CRITICAL(&s_lock);
    s_manual_busy = false;
    taskEXIT_CRITICAL(&s_lock);
    return res;
}

esp_err_t app_safety_reverify_dac(void)
{
    if (app_safety_hv_enabled() || app_safety_hv_state() == HV_RAMP || app_safety_hv_state() == HV_ON) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t e = mcp4728_init();       /* idempotent; also covers a DAC that was absent at boot */
    if (e != ESP_OK) {
        return e;
    }
    mcp4728_regs_t r;
    e = mcp4728_read_all(&r);
    if (e != ESP_OK) {
        return e;
    }
    if (!mcp4728_eeprom_defaults_ok(&r)) {
        return ESP_FAIL;                /* FAULT_DAC_EEPROM stays: `dac provision confirm` */
    }
    e = mcp4728_write_volatile(BOARD_DAC_CH_HV, BOARD_DAC_HV_SAFE_CODE);
    if (e == ESP_OK) {
        e = mcp4728_readback_verify(BOARD_DAC_CH_HV, BOARD_DAC_HV_SAFE_CODE);
    }
    if (e != ESP_OK) {
        return e;
    }
    fault_clear(FAULT_I2C_DAC | FAULT_DAC_EEPROM);   /* before the flag, so the safety task cannot undo it */
    s_dac_verified = true;
    return ESP_OK;
}

esp_err_t app_safety_faults_clear(void)
{
    /* Conditions that are still true re-latch on the next safety tick. */
    fault_word_t keep = 0;
    esp_err_t res = ESP_OK;
    if (fault_get() & (FAULT_I2C_DAC | FAULT_DAC_EEPROM)) {
        res = app_safety_reverify_dac();
        if (res != ESP_OK) {
            keep |= FAULT_I2C_DAC | FAULT_DAC_EEPROM;
        }
    }
    sense_snapshot_t s;
    if (sense_get(&s) && s.valid && sense_bias_v(&s) > HV_STUCK_THRESHOLD_V && !app_safety_hv_enabled()) {
        keep |= FAULT_HV_STUCK;
    }
    if (!s_adc_ok) {
        keep |= FAULT_I2C_ADC;
    }
    fault_clear((fault_word_t)~keep);
    return res;
}

/* ---- executor: the DAC writes the gate asks for ------------------------- */
static bool exec_cmd(const hvg_cmd_t *c)
{
    esp_err_t e = mcp4728_write_volatile(BOARD_DAC_CH_HV, c->code);
    if (e == ESP_OK && c->kind == HVG_CMD_ARM) {
        e = mcp4728_readback_verify(BOARD_DAC_CH_HV, c->code);   /* Read command: 0xFFF really is in the register */
    }
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "DAC_HV %s 0x%03x failed: %s", c->kind == HVG_CMD_ARM ? "arm" : "write",
                 (unsigned)c->code, esp_err_to_name(e));
        fault_set(FAULT_I2C_DAC);
        return false;
    }
    return true;
}

static void exec_task(void *arg)
{
    (void)arg;
    for (;;) {
        ulTaskNotifyTake(pdTRUE, ticks_at_least_1(EXEC_WAIT_MS));
        for (int i = 0; i < 4; i++) {
            hvg_cmd_t cmd;
            taskENTER_CRITICAL(&s_lock);
            bool got = hvg_take_cmd(&s_gate, &cmd);
            taskEXIT_CRITICAL(&s_lock);
            if (!got) {
                break;
            }
            bool ok = exec_cmd(&cmd);
            taskENTER_CRITICAL(&s_lock);
            hvg_report(&s_gate, cmd.gen, ok);
            taskEXIT_CRITICAL(&s_lock);
        }
    }
}

/* ---- safety task -------------------------------------------------------- */
/* hv_auto (README s.4 step 8c, s.5): HV off, master heard, no blocking fault,
 * and the operator did not turn it off. Faults BROWNOUT and WDT also block
 * (README s.4 step 1: HV stays off until a deliberate command). */
static void auto_poll(void)
{
    if (s_auto_inhibit || s_auto_off_latch || get_p(PARAM_HV_AUTO) == 0) {
        return;
    }
    if (can_link_mode() != CAN_MODE_BUS || !can_link_master_seen() ||
        can_link_heartbeat_age_ms() > (uint32_t)get_p(PARAM_BUS_TIMEOUT)) {
        return;
    }
    if (fault_get() & (FAULT_HV_BLOCKING_MASK | FAULT_BROWNOUT | FAULT_WDT)) {
        return;
    }
    if (app_safety_hv_state() != HV_OFF) {
        return;
    }
    if (app_safety_hv_request(true) == ESP_OK) {
        ESP_LOGW(TAG, "hv_auto: master heard, HV requested");
    }
}

static void safety_task(void *arg)
{
    (void)arg;
    esp_task_wdt_add(NULL);
    TickType_t last = xTaskGetTickCount();
    int64_t last_auto_us = 0;

    for (;;) {
        vTaskDelayUntil(&last, ticks_at_least_1(SAFETY_PERIOD_MS));
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

        /* A DAC failure at run time voids the boot-time proof (review finding 6). */
        if (fault_get() & (FAULT_I2C_DAC | FAULT_DAC_EEPROM)) {
            s_dac_verified = false;
        }
        /* CAN heartbeat loss while HV is enabled (README s.5). */
        if (app_safety_hv_enabled() && can_link_mode() == CAN_MODE_BUS &&
            can_link_heartbeat_age_ms() > (uint32_t)get_p(PARAM_BUS_TIMEOUT)) {
            fault_set(FAULT_CAN_TIMEOUT);
        }

        hvg_in_t in;
        build_in(&in);
        hvg_out_t out;
        taskENTER_CRITICAL(&s_lock);
        hvg_step(&s_gate, &in, &out);
        pin_apply_locked();       /* a newly latched fault lowers `want` inside the step: HV_DIS high this tick */
        taskEXIT_CRITICAL(&s_lock);
        if (out.fault_bits) {
            if (out.fault_bits & ~fault_get()) {
                ESP_LOGW(TAG, "HV trip: %s (faults 0x%04x)", hvg_reason_name(out.reason), (unsigned)out.fault_bits);
            }
            fault_set(out.fault_bits);
        }
        if (out.adc_bad) {
            s_adc_ok = false;
        }
        kick_exec(out.cmd_ready);

        if ((now - last_auto_us) >= (int64_t)AUTO_POLL_MS * 1000) {
            last_auto_us = now;
            auto_poll();
        }
    }
}

void app_safety_start(void)
{
    xTaskCreate(exec_task, "hv_exec", EXEC_TASK_STACK, NULL, EXEC_TASK_PRIO, &s_exec_task);
    xTaskCreate(safety_task, "safety", 3072, NULL, SAFETY_TASK_PRIO, NULL);
}
