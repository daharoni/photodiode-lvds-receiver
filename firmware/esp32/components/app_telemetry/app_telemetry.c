#include "app_telemetry.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "app_range.h"
#include "app_safety.h"
#include "app_selftest.h"
#include "can_link.h"
#include "drv_gpio.h"
#include "esp_app_desc.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "driver/usb_serial_jtag.h"
#include "board_time.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "params.h"
#include "sense.h"

#define TLM_TASK_PRIO     5     /* README s.3 */
#define TLM_TASK_TICK_MS  20    /* README s.3 */
#define LED_TASK_PRIO     2     /* README s.3 */
#define LED_TICK_MS       50    /* README s.3 */
#define EVENT_RING        64    /* README s.6.6 */
#define EVENT_LEN         160
#define STATE_PERIOD_MUL  5     /* TLM_STATE 2 Hz at the 10 Hz default (protocol s.1.4) */
#define SLOW_PERIOD_MUL   50    /* TLM_SLOW 0.2 Hz at the 10 Hz default */
#define TLM_MIN_MS        50    /* protocol s.2 */

static volatile bool s_stream;
static volatile uint32_t s_stream_ms;   /* 0 = use tlm_ms */
static const char *s_src = "unknown", *s_cc_class = "none", *s_cc_orient = "none";
static volatile int64_t s_identify_until_us;

static char s_ring[EVENT_RING][EVENT_LEN];
static uint32_t s_ring_head, s_ring_count;
static portMUX_TYPE s_ring_lock = portMUX_INITIALIZER_UNLOCKED;

/* ---- printer queue (review finding 8) ---------------------------------------
 * Event and stream lines from the range and telemetry tasks go through a queue
 * drained by a low-priority task, so a closed USB CDC port (whose buffer never
 * drains, TRM s.32.4 p.1034) cannot block a task that must check in with the
 * watchdog. Lines are written only while a USB host is connected; otherwise
 * they are dropped and counted. */
#define PRINT_Q_LEN     12
#define PRINT_LINE_LEN  512
#define PRINT_TASK_PRIO 1       /* PROPOSED: below every other task */
typedef struct { char s[PRINT_LINE_LEN]; } print_item_t;
static StaticQueue_t s_pq_ctl;
static uint8_t s_pq_store[PRINT_Q_LEN * sizeof(print_item_t)];
static QueueHandle_t s_pq;
static volatile uint32_t s_print_drops;

uint32_t app_telemetry_print_drops(void) { return s_print_drops; }

bool app_telemetry_print_line(const char *line)
{
    if (!s_pq) {
        s_print_drops++;
        return false;
    }
    print_item_t it;
    strncpy(it.s, line, PRINT_LINE_LEN - 1);
    it.s[PRINT_LINE_LEN - 1] = 0;
    if (xQueueSend(s_pq, &it, 0) != pdTRUE) {
        s_print_drops++;
        return false;
    }
    return true;
}

static void printer_task(void *arg)
{
    (void)arg;
    print_item_t it;
    for (;;) {
        if (xQueueReceive(s_pq, &it, portMAX_DELAY) == pdTRUE) {
            if (usb_serial_jtag_is_connected()) {
                printf("%s\n", it.s);      /* may block up to the console driver timeout: nobody else waits on us */
            } else {
                s_print_drops++;
            }
        }
    }
}

static int32_t pget(uint16_t id, bool *ok)
{
    int32_t v = 0;
    bool good = (params_get_i32(id, &v) == ESP_OK);
    if (ok) {
        *ok = good;
    }
    return v;
}

void app_telemetry_set_source(const char *src, const char *cc_class, const char *cc_orient)
{
    s_src = src; s_cc_class = cc_class; s_cc_orient = cc_orient;
}

void app_telemetry_identify(uint8_t seconds)
{
    s_identify_until_us = esp_timer_get_time() + (int64_t)seconds * 1000000;
}

bool app_telemetry_streaming(void) { return s_stream; }

static uint32_t period_ms(void)
{
    uint32_t p = s_stream_ms ? s_stream_ms : (uint32_t)pget(PARAM_TLM_MS, NULL);
    return p < TLM_MIN_MS ? TLM_MIN_MS : p;
}

void app_telemetry_stream(bool on, uint32_t ms)
{
    if (ms) {
        s_stream_ms = ms < TLM_MIN_MS ? TLM_MIN_MS : ms;
    }
    s_stream = on;
}

void app_telemetry_event(const char *line)
{
    taskENTER_CRITICAL(&s_ring_lock);
    char *slot = s_ring[s_ring_head];
    strncpy(slot, line, EVENT_LEN - 1);
    slot[EVENT_LEN - 1] = 0;
    s_ring_head = (s_ring_head + 1) % EVENT_RING;
    if (s_ring_count < EVENT_RING) {
        s_ring_count++;
    }
    taskEXIT_CRITICAL(&s_ring_lock);
    if (s_stream) {
        app_telemetry_print_line(line);
    }
}

void app_telemetry_events_print(void)
{
    char tmp[EVENT_LEN];
    for (uint32_t i = 0; i < s_ring_count; i++) {
        uint32_t idx = (s_ring_head + EVENT_RING - s_ring_count + i) % EVENT_RING;
        taskENTER_CRITICAL(&s_ring_lock);
        memcpy(tmp, s_ring[idx], EVENT_LEN);
        taskEXIT_CRITICAL(&s_ring_lock);
        printf("%s\n", tmp);
    }
}

/* ---- JSON -------------------------------------------------------------- */
typedef struct { char *b; size_t n; size_t pos; } jb_t;

static void jadd(jb_t *j, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static void jadd(jb_t *j, const char *fmt, ...)
{
    if (j->pos >= j->n) {
        return;
    }
    va_list ap;
    va_start(ap, fmt);
    int w = vsnprintf(j->b + j->pos, j->n - j->pos, fmt, ap);
    va_end(ap);
    if (w > 0) {
        j->pos += (size_t)w;
    }
}

static void jnum(jb_t *j, const char *key, bool ok, double v, int dec)
{
    if (ok) {
        jadd(j, "\"%s\":%.*f,", key, dec, v);
    } else {
        jadd(j, "\"%s\":null,", key);
    }
}

int app_telemetry_status_json(char *buf, size_t len)
{
    jb_t j = {buf, len, 0};
    bool ok;
    sense_snapshot_t s;
    bool have = sense_get(&s) && s.valid;
    const esp_app_desc_t *ad = esp_app_get_description();
    bool bus = (can_link_mode() == CAN_MODE_BUS);
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_EFUSE_FACTORY);

    jadd(&j, "{\"t\":%lld,", (long long)(esp_timer_get_time() / 1000));
    jadd(&j, "\"node\":%ld,", (long)pget(PARAM_NODE, NULL));
    jadd(&j, "\"sn\":%ld,", (long)pget(PARAM_SERIAL, NULL));
    jadd(&j, "\"ver\":\"%s\",", ad->version);
    jadd(&j, "\"up\":%lld,", (long long)(esp_timer_get_time() / 1000000));
    jadd(&j, "\"hv\":\"%s\",", app_safety_hv_state_name(app_safety_hv_state()));
    jnum(&j, "hv_v", have, have ? sense_bias_v(&s) : 0, 1);
    jnum(&j, "hv_set", true, pget(PARAM_HV_SET, NULL) * 0.1, 1);
    /* UNRESOLVED: no DAC code getter in the contracts (a live read would cost
     * an I2C transaction); always null for now. */
    jadd(&j, "\"dac_hv\":null,");
    int32_t v = pget(PARAM_M_EST, &ok);
    jnum(&j, "m", ok && v > 0, v * 0.1, 1);
    jnum(&j, "rssi_mv", have, have ? s.rssi_mv : 0, 0);
    v = pget(PARAM_RSSI_DROP, &ok);
    jnum(&j, "rssi_drop", ok, v, 0);
    jnum(&j, "vth_mv", have, have ? s.vth_mv : 0, 0);
    jnum(&j, "th_mv", true, pget(PARAM_TH, NULL) * 0.1, 1);
    jadd(&j, "\"tia\":\"%s\",\"comp\":%d,\"loop\":\"%s\",", drv_gpio_tia_get() ? "20k" : "5k",
         drv_gpio_comp_enabled() ? 1 : 0, app_range_state_name());
    if (bus) {
        jadd(&j, "\"link\":%d,\"err\":%u,", can_link_link_valid() ? 1 : 0, (unsigned)can_link_err_class());
    } else {
        jadd(&j, "\"link\":null,\"err\":null,");
    }
    jadd(&j, "\"faults\":%u,", (unsigned)fault_get());
    v = pget(PARAM_TEMP, &ok);
    jnum(&j, "temp_c", ok, v * 0.1, 1);
    /* UNRESOLVED: TEC/REC are not in the can_link contract (only the stats
     * JSON); null until a getter exists. */
    jadd(&j, "\"can_tec\":null,\"can_rec\":null,");
    jadd(&j, "\"mode\":\"%s\",\"src\":\"%s\",\"cc_class\":\"%s\",\"cc_orient\":\"%s\",",
         bus ? "bus" : "usb", s_src, s_cc_class, s_cc_orient);
    jadd(&j, "\"rev\":%ld,\"mac\":\"%02x%02x%02x%02x%02x%02x\"}", (long)pget(PARAM_BOARD_REV, NULL),
         mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    if (j.pos >= len) {
        j.pos = len - 1;
    }
    return (int)j.pos;
}

/* ---- CAN frames (protocol s.1.4, little endian) ------------------------- */
static void put16(uint8_t *p, uint16_t v) { p[0] = v & 0xFF; p[1] = v >> 8; }

static void send_analog(void)
{
    sense_snapshot_t s;
    if (!sense_get(&s) || !s.valid) {
        return;
    }
    uint8_t d[8];
    int32_t hv_dv = (int32_t)(sense_bias_v(&s) * 10.0f + 0.5f);
    bool ok;
    int32_t m = pget(PARAM_M_EST, &ok);
    put16(d + 0, (uint16_t)(hv_dv < 0 ? 0 : hv_dv));
    put16(d + 2, (uint16_t)(s.rssi_mv < 0 ? 0 : s.rssi_mv));
    put16(d + 4, (uint16_t)(s.vth_mv < 0 ? 0 : s.vth_mv));
    put16(d + 6, (ok && m > 0) ? (uint16_t)m : 0xFFFF);   /* M x 10; 0xFFFF unknown */
    can_link_send_tlm(0, d, 8);
}

static void send_state(void)
{
    uint8_t d[8] = {0};
    bool bus = (can_link_mode() == CAN_MODE_BUS);
    int32_t loop_en = pget(PARAM_LOOP_STATE, NULL);
    d[0] = (uint8_t)((app_safety_hv_state() & 7) | (drv_gpio_tia_get() ? 1 << 3 : 0) | (bus ? 1 << 4 : 0) |
                     (drv_gpio_comp_enabled() ? 1 << 5 : 0) | (can_link_link_valid() ? 1 << 6 : 0) |
                     (pget(PARAM_TIA_AUTO, NULL) ? 1 << 7 : 0));
    d[1] = (uint8_t)loop_en;
    put16(d + 2, fault_get());
    /* bytes 4-5 dac_hv: UNRESOLVED, no getter (see status json) */
    put16(d + 4, 0xFFFF);
    d[6] = can_link_err_class() & 7;
    d[7] = (uint8_t)((drv_gpio_aux_read() ? 1 << 2 : 0) |
                     ((strcmp(s_src, "system") == 0 ? 0 : strcmp(s_src, "host") == 0 ? 1 : 2) << 3));
    /* selftest_last (bits 1:0) not available from the contract: left 0 = never. UNRESOLVED. */
    can_link_send_tlm(1, d, 8);
}

static void send_slow(void)
{
    uint8_t d[8] = {0};
    uint32_t up = (uint32_t)(esp_timer_get_time() / 1000000);
    int32_t t = pget(PARAM_TEMP, NULL);
    memcpy(d, &up, 4);
    put16(d + 4, (uint16_t)(int16_t)t);
    /* can_tec / can_rec bytes 6-7: UNRESOLVED, no getter */
    can_link_send_tlm(2, d, 8);
}

static void telemetry_task(void *arg)
{
    (void)arg;
    static char line[512];
    uint32_t n = 0;
    int64_t next_us = esp_timer_get_time();
    fault_word_t last_faults = fault_get();
    for (;;) {
        vTaskDelay(ticks_at_least_1(TLM_TASK_TICK_MS));
        app_safety_task_checkin(APP_TASK_TELEMETRY);
        int64_t now = esp_timer_get_time();

        fault_word_t f = fault_get();
        if (f != last_faults) {
            char ev[EVENT_LEN];
            snprintf(ev, sizeof(ev), "{\"ev\":\"fault\",\"faults\":\"0x%04x\",\"new\":\"0x%04x\"}",
                     (unsigned)f, (unsigned)(f & ~last_faults));
            app_telemetry_event(ev);
            if (can_link_mode() == CAN_MODE_BUS) {
                send_state();   /* TLM_STATE on change (protocol s.1.4) */
            }
            last_faults = f;
        }

        if (now < next_us) {
            continue;
        }
        next_us = now + (int64_t)period_ms() * 1000;
        n++;
        if (can_link_mode() == CAN_MODE_BUS) {
            send_analog();
            if (n % STATE_PERIOD_MUL == 0) send_state();
            if (n % SLOW_PERIOD_MUL == 0) send_slow();
        }
        if (s_stream) {
            int w = app_telemetry_status_json(line, sizeof(line));
            if (w > 0) {
                app_telemetry_print_line(line);
            }
        }
    }
}

/* ---- LED (README s.8 patterns, PROPOSED). Self-test patterns belong to
 * app_selftest; this task stays off the LED while a test runs. ------------ */
static bool led_pattern(uint32_t tick)
{
    int64_t now = esp_timer_get_time();
    if (now < s_identify_until_us) {
        uint32_t p = tick % 3;   /* 8 Hz double blink at 50 ms ticks: approximated, PROPOSED */
        return p == 0 || p == 1 ? (tick / 3) % 2 == 0 : false;
    }
    if (fault_get() & FAULT_HV_BLOCKING_MASK) {
        return (tick % 4) < 2;   /* 5 Hz: 100 ms on, 100 ms off */
    }
    uint32_t p = tick % 40;      /* 2 s period */
    if (p < 10) return true;     /* 0.5 s pulse */
    if (app_safety_hv_enabled() && p >= 14 && p < 16) return true;   /* second short pulse */
    return false;
}

static void led_task(void *arg)
{
    (void)arg;
    uint32_t tick = 0;
    for (;;) {
        vTaskDelay(ticks_at_least_1(LED_TICK_MS));
        if (!app_selftest_running()) {
            drv_gpio_led_set(led_pattern(tick++));
        }
    }
}

void app_telemetry_start(void)
{
    s_pq = xQueueCreateStatic(PRINT_Q_LEN, sizeof(print_item_t), s_pq_store, &s_pq_ctl);
    xTaskCreate(printer_task, "printer", 3072, NULL, PRINT_TASK_PRIO, NULL);
    xTaskCreate(telemetry_task, "telemetry", 4096, NULL, TLM_TASK_PRIO, NULL);
    xTaskCreate(led_task, "led", 2048, NULL, LED_TASK_PRIO, NULL);
}
