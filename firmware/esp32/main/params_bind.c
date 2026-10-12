#include "params_bind.h"
#include <math.h>
#include <string.h>
#include "app_range.h"
#include "app_safety.h"
#include "app_selftest.h"
#include "board_pins.h"
#include "can_link.h"
#include "drv_gpio.h"
#include "drv_mcp4728.h"
#include "driver/temperature_sensor.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "params.h"
#include "sense.h"

static const char *TAG = "bind";

#define SELFTEST_TASK_PRIO   4      /* PROPOSED: below range (8), above console (3) */
#define SELFTEST_TASK_STACK  6144   /* UNRESOLVED: first guess */
#define TSENSE_MIN_C         (-10)  /* README s.8 step 8 window starts at -10 C */
#define TSENSE_MAX_C         80     /* PROPOSED sensor range choice */
#define VCM_REF_DAC_MV_PER_CODE 0.80566f   /* 3.3 V / 4096 */
#define TH_DIV 101.0f               /* README s.1 DAC_TH */

static temperature_sensor_handle_t s_tsens;
static TaskHandle_t s_st_task;

uint16_t params_th_to_code(int32_t th_dmv)
{
    float code = BOARD_DAC_TH_ZERO_CODE + (th_dmv * 0.1f) * TH_DIV / VCM_REF_DAC_MV_PER_CODE;
    long c = lroundf(code);
    return (uint16_t)(c < 0 ? 0 : (c > 4095 ? 4095 : c));
}

/* ---- live getters ------------------------------------------------------ */
static int32_t g_hv_state(void) { return (int32_t)app_safety_hv_state(); }
static int32_t g_hv_cmd(void)
{
    hv_state_t s = app_safety_hv_state();
    return (s == HV_RAMP || s == HV_ON || s == HV_HOLD) ? 1 : 0;
}
static int32_t g_hv_mon(void)
{
    sense_snapshot_t s;
    return (sense_get(&s) && s.valid) ? (int32_t)lroundf(sense_bias_v(&s) * 10.0f) : 0;
}
static int32_t g_rssi(void) { sense_snapshot_t s; return (sense_get(&s) && s.valid) ? s.rssi_mv : 0; }
static int32_t g_vth(void) { sense_snapshot_t s; return (sense_get(&s) && s.valid) ? s.vth_mv : 0; }
static int32_t g_tia(void) { return drv_gpio_tia_get() ? 1 : 0; }
static int32_t g_comp(void) { return drv_gpio_comp_enabled() ? 1 : 0; }
static int32_t g_link_valid(void) { return can_link_link_valid() ? 1 : 0; }
static int32_t g_link_err(void) { return can_link_err_class(); }
static int32_t g_temp(void)
{
    float c = 0;
    if (s_tsens && temperature_sensor_get_celsius(s_tsens, &c) == ESP_OK) {
        return (int32_t)lroundf(c * 10.0f);
    }
    return 0;
}
static int32_t g_loop_state(void)
{
    /* Enumeration of protocol s.1.4 `loop_state`, derived from the state name. */
    static const char *const n[] = {"OFF", "RAMP", "SEARCH", "TRACK", "LOS", "MANUAL", "FAULT"};
    const char *s = app_range_state_name();
    for (int i = 0; i < 7; i++) {
        if (s && strcmp(s, n[i]) == 0) return i;
    }
    return 0;
}

/* ---- actions ----------------------------------------------------------- */
static esp_err_t a_hv_cmd(int32_t v)
{
    if (v && app_selftest_running()) return PARAMS_ERR_BUSY;
    return app_safety_hv_request(v != 0);
}
static esp_err_t a_dac_hv(int32_t code)
{
    int32_t loop = 1;
    params_get_i32(PARAM_LOOP, &loop);
    if (loop != 0) return ESP_ERR_INVALID_STATE;   /* only with `loop manual` (protocol s.2) */
    return mcp4728_write_volatile(BOARD_DAC_CH_HV, (uint16_t)code) == ESP_OK ? ESP_OK : ESP_FAIL;
}
static esp_err_t a_th(int32_t th_dmv)
{
    return mcp4728_write_volatile(BOARD_DAC_CH_TH, params_th_to_code(th_dmv)) == ESP_OK ? ESP_OK : ESP_FAIL;
}
static esp_err_t a_tia(int32_t v) { drv_gpio_tia_set(v != 0); return ESP_OK; }
static esp_err_t a_comp(int32_t v) { drv_gpio_comp_enable(v != 0); return ESP_OK; }
static esp_err_t a_loop(int32_t v) { app_range_set_mode(v != 0); return ESP_OK; }
static esp_err_t a_faults_clear(int32_t v) { (void)v; app_safety_faults_clear(); return ESP_OK; }
static esp_err_t a_save(int32_t v) { (void)v; return params_save(); }
static esp_err_t a_defaults(int32_t v) { return params_defaults(v == 2); }
static esp_err_t a_reboot(int32_t v)
{
    (void)v;
    app_safety_hv_off_now();
    vTaskDelay(pdMS_TO_TICKS(50));
    esp_restart();
    return ESP_OK;
}
static esp_err_t a_selftest(int32_t v)
{
    if (app_selftest_running()) return PARAMS_ERR_BUSY;
    xTaskNotify(s_st_task, (uint32_t)v, eSetValueWithOverwrite);
    return ESP_OK;
}

static void selftest_worker(void *arg)
{
    (void)arg;
    for (;;) {
        uint32_t v = 0;
        xTaskNotifyWait(0, UINT32_MAX, &v, portMAX_DELAY);
        app_selftest_run(v == 2);
    }
}

void params_bind_init(void)
{
    temperature_sensor_config_t tc = TEMPERATURE_SENSOR_CONFIG_DEFAULT(TSENSE_MIN_C, TSENSE_MAX_C);
    if (temperature_sensor_install(&tc, &s_tsens) == ESP_OK) {
        temperature_sensor_enable(s_tsens);
    } else {
        ESP_LOGW(TAG, "temperature sensor unavailable");
        s_tsens = NULL;
    }
    xTaskCreate(selftest_worker, "selftest", SELFTEST_TASK_STACK, NULL, SELFTEST_TASK_PRIO, &s_st_task);

    params_register_live(PARAM_HV_STATE, g_hv_state);
    params_register_live(PARAM_HV_CMD, g_hv_cmd);
    params_register_live(PARAM_HV_MON, g_hv_mon);
    params_register_live(PARAM_RSSI, g_rssi);
    params_register_live(PARAM_VTH_MON, g_vth);
    params_register_live(PARAM_TIA, g_tia);
    params_register_live(PARAM_COMP_EN, g_comp);
    params_register_live(PARAM_LINK_VALID, g_link_valid);
    params_register_live(PARAM_LINK_ERR, g_link_err);
    params_register_live(PARAM_TEMP, g_temp);
    params_register_live(PARAM_LOOP_STATE, g_loop_state);
    /* m_est, rssi_drop: owned by app_range, no getter in the agreed contract;
     * left unregistered (reads fail, telemetry shows null). UNRESOLVED. */

    params_register_action(PARAM_HV_CMD, a_hv_cmd);
    params_register_action(PARAM_DAC_HV, a_dac_hv);
    params_register_action(PARAM_TH, a_th);
    params_register_action(PARAM_TIA, a_tia);
    params_register_action(PARAM_COMP_EN, a_comp);
    params_register_action(PARAM_LOOP, a_loop);
    params_register_action(PARAM_FAULTS_CLEAR, a_faults_clear);
    params_register_action(PARAM_SAVE, a_save);
    params_register_action(PARAM_DEFAULTS, a_defaults);
    params_register_action(PARAM_REBOOT, a_reboot);
    params_register_action(PARAM_SELFTEST_RUN, a_selftest);
}
