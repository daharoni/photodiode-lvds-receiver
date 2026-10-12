/* sense.c - see sense.h. PROPOSED; not run on hardware. */
#include "sense.h"
#include "app_safety.h"
#include "board_pins.h"
#include "drv_ads1115.h"
#include "drv_gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "params.h"

static const char *TAG = "sense";

#define SENSE_TASK_PRIO        10     /* README s.3 task table */
#define SENSE_TASK_STACK       3072   /* PROPOSED */
#define SENSE_GND_EVERY        10     /* AIN3 every 10th round: PROPOSED */
#define SENSE_ERR_BACKOFF_MS   50     /* PROPOSED: retry pause after an I2C error */
#define RSSI_IDLE_DEFAULT_MV   1950   /* README s.1 "idle about 1.9-2.0 V", PROPOSED */
#define IDLE_LEARN_BIAS_V      10.0f  /* learn only while bias < 10 V (HV off), README s.8 step 5 HV_MON window */

static SemaphoreHandle_t s_mtx;
static sense_snapshot_t s_snap;
static bool s_have;
static int32_t s_idle_mv[2] = {RSSI_IDLE_DEFAULT_MV, RSSI_IDLE_DEFAULT_MV};   /* [0] = 5k, [1] = 20k */
static bool s_idle_learned[2];

int32_t sense_lowpass8(int32_t idle, int32_t x) { return idle + (x - idle) / 8; }

float sense_bias_v(const sense_snapshot_t *s)
{
    return (float)s->hv_mon_mv * BOARD_HV_MON_DIVIDER / 1000.0f;
}

bool sense_get(sense_snapshot_t *out)
{
    if (!s_mtx) {
        return false;
    }
    xSemaphoreTake(s_mtx, portMAX_DELAY);
    *out = s_snap;
    bool have = s_have;
    xSemaphoreGive(s_mtx);
    return have;
}

int32_t sense_rssi_idle_mv(void)
{
    int tia = drv_gpio_tia_get() ? 1 : 0;
    /* If this gain was never learned but the other was, reuse it (UNRESOLVED: gains may differ). */
    if (!s_idle_learned[tia] && s_idle_learned[!tia]) {
        return s_idle_mv[!tia];
    }
    return s_idle_mv[tia];
}

int32_t sense_rssi_drop_mv(void)
{
    sense_snapshot_t s;
    if (!sense_get(&s)) {
        return 0;
    }
    return sense_rssi_idle_mv() - s.rssi_mv;
}

void sense_rssi_idle_set(bool tia_20k, int32_t mv)
{
    s_idle_mv[tia_20k ? 1 : 0] = mv;
    s_idle_learned[tia_20k ? 1 : 0] = true;
}

static int32_t g_rssi_drop(void) { return sense_rssi_drop_mv(); }

static void learn_idle(const sense_snapshot_t *s)
{
    if (sense_bias_v(s) >= IDLE_LEARN_BIAS_V) {
        return;
    }
    int tia = drv_gpio_tia_get() ? 1 : 0;
    if (!s_idle_learned[tia]) {
        s_idle_mv[tia] = s->rssi_mv;           /* first sample seeds the filter */
        s_idle_learned[tia] = true;
    } else {
        s_idle_mv[tia] = sense_lowpass8(s_idle_mv[tia], s->rssi_mv);
    }
}

static void sense_task(void *arg)
{
    (void)arg;
    unsigned round = 0;
    sense_snapshot_t w = {0};
    for (;;) {
        app_safety_task_checkin(APP_TASK_SENSE);
        bool ok = ads1115_read_mv(BOARD_ADC_AIN_HV_MON, &w.hv_mon_mv) == ESP_OK &&
                  ads1115_read_mv(BOARD_ADC_AIN_RSSI, &w.rssi_mv) == ESP_OK &&
                  ads1115_read_mv(BOARD_ADC_AIN_VTH_MON, &w.vth_mv) == ESP_OK;
        if (ok && (round % SENSE_GND_EVERY) == 0) {
            ok = ads1115_read_mv(BOARD_ADC_AIN_GND, &w.gnd_mv) == ESP_OK;
        }
        round++;
        w.t_us = esp_timer_get_time();
        w.valid = ok;
        xSemaphoreTake(s_mtx, portMAX_DELAY);
        if (ok) {
            s_snap = w;
            s_have = true;
            learn_idle(&w);
        } else {
            s_snap.valid = false;      /* keep the stale values, mark them invalid */
        }
        xSemaphoreGive(s_mtx);
        if (!ok) {
            vTaskDelay(pdMS_TO_TICKS(SENSE_ERR_BACKOFF_MS));
        }
    }
}

void sense_start(void)
{
    if (s_mtx) {
        return;
    }
    s_mtx = xSemaphoreCreateMutex();
    params_register_live(PARAM_RSSI_DROP, g_rssi_drop);
    if (xTaskCreate(sense_task, "sense", SENSE_TASK_STACK, NULL, SENSE_TASK_PRIO, NULL) != pdPASS) {
        ESP_LOGE(TAG, "task create failed");
    }
}
