/*
 * can_link.c - TWAI link (node-based driver of ESP-IDF v5.5.x).
 * PROPOSED; compiled but not run on hardware.
 *
 * API facts checked in ~/esp/esp-idf (v5.5.5) components/esp_driver_twai:
 *  - twai_new_node_onchip(), twai_onchip_node_config_t  (esp_twai_onchip.h)
 *  - twai_node_enable/disable/delete/recover/transmit/get_info/
 *    register_event_callbacks, twai_node_receive_from_isr (esp_twai.h)
 *  - callbacks must be registered while the node is disabled;
 *  - the TX queue stores POINTERS to twai_frame_t, so frames and buffers must
 *    stay valid until on_tx_done (esp_twai_onchip.c: tx_mount_queue holds
 *    twai_frame_t *): this file uses a static slot pool released in on_tx_done;
 *  - a listen-only node refuses transmit (ESP_ERR_NOT_SUPPORTED).
 */
#include "can_link.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include "app_safety.h"
#include "app_telemetry.h"
#include "board_pins.h"
#include "board_time.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "esp_twai.h"
#include "esp_twai_onchip.h"
#include "fault.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "params.h"

static const char *TAG = "can";

#define CAN_TASK_PRIO            12      /* README s.3 task table */
#define CAN_TASK_STACK           5120    /* PROPOSED */
#define RX_QUEUE_LEN             32      /* PROPOSED: 32 frames = 34 ms at the worst-case 1.08 ms/frame */
#define TX_QUEUE_DEPTH           8       /* PROPOSED */
#define TX_POOL                  8       /* must be >= TX_QUEUE_DEPTH + 1 in flight */
#define TX_RETRY                 3       /* hardware retries before a frame is dropped, PROPOSED */
#define TASK_TICK_MS             5       /* rx queue wait: also the enum/fault scheduling resolution (ticks_at_least_1: 5 ms is 0 ticks at 100 Hz) */
#define FAULT_CHECK_MS           50      /* PROPOSED */
#define FAULT_RESEND_MS          1000    /* protocol s.1.6: re-sent every 1 s while latched */
#define ENUM_MIN_SLOT_MS         2       /* protocol s.1.2: slot_ms >= 2 */
#define DEFAULT_BUS_TIMEOUT_MS   2000    /* protocol s.2 bus_timeout default */
#define LOOPBACK_QUIET_MS        500     /* README s.8 step 7 */
#define LOOPBACK_FRAMES          8       /* README s.8 step 7 */
#define LOOPBACK_ID_BASE         0x7E0   /* class 7, function 14 is unallocated in protocol s.1.1; PROPOSED */
#define LOOPBACK_WAIT_MS         200     /* PROPOSED: 8 frames take about 9 ms at 125 kbit/s */
#define TX_TIMEOUT_MS            0       /* never block a caller on a full TX queue */

typedef struct {
    uint32_t id;
    uint8_t dlc;
    uint8_t data[8];
} rx_msg_t;

typedef struct {
    twai_frame_t f;
    uint8_t buf[8];
    volatile bool busy;
} tx_slot_t;

static twai_node_handle_t s_node;
static SemaphoreHandle_t s_cfg_mtx;       /* guards node re-creation */
static QueueHandle_t s_rxq;
static tx_slot_t s_tx[TX_POOL];
static portMUX_TYPE s_pool_lock = portMUX_INITIALIZER_UNLOCKED;
static volatile can_mode_t s_mode = CAN_MODE_LISTEN;
static volatile bool s_bus_off_flag;
static volatile bool s_lb_active;
static volatile uint32_t s_lb_count;
static volatile uint32_t s_rx_count, s_tx_ok, s_tx_fail, s_rx_drop, s_bus_err;
static volatile int64_t s_last_rx_us;
static volatile int64_t s_last_link_all_us;
static volatile bool s_master_seen;
static volatile uint8_t s_my_nibble = 0;   /* last LINK_ALL nibble for this node */
static volatile bool s_my_nibble_ok;
static uint8_t s_mac[6];
static volatile int64_t s_enum_due_us;     /* 0 = none pending */
static fault_word_t s_fault_sent;
static int64_t s_fault_sent_us;
static bool s_boot_sent;

/* ---- ISR callbacks ---------------------------------------------------------- */

static bool IRAM_ATTR on_rx_done(twai_node_handle_t h, const twai_rx_done_event_data_t *e, void *ctx)
{
    (void)e;
    (void)ctx;
    uint8_t buf[TWAI_FRAME_MAX_LEN];
    twai_frame_t f = {.buffer = buf, .buffer_len = sizeof(buf)};
    if (twai_node_receive_from_isr(h, &f) != ESP_OK) {
        return false;
    }
    s_rx_count++;
    s_last_rx_us = esp_timer_get_time();
    if (s_lb_active) {
        if (f.header.id >= LOOPBACK_ID_BASE && f.header.id < LOOPBACK_ID_BASE + LOOPBACK_FRAMES) {
            s_lb_count++;
        }
        return false;
    }
    if (f.header.ide || f.header.rtr || f.header.dlc > 8) {
        return false;   /* only 11-bit data frames are used (protocol s.1) */
    }
    rx_msg_t m = {.id = f.header.id, .dlc = (uint8_t)f.header.dlc};
    memcpy(m.data, buf, m.dlc);
    BaseType_t woken = pdFALSE;
    if (xQueueSendFromISR(s_rxq, &m, &woken) != pdTRUE) {
        s_rx_drop++;
    }
    return woken == pdTRUE;
}

static bool IRAM_ATTR on_tx_done(twai_node_handle_t h, const twai_tx_done_event_data_t *e, void *ctx)
{
    (void)h;
    (void)ctx;
    for (int i = 0; i < TX_POOL; i++) {
        if (e->done_tx_frame == &s_tx[i].f) {
            s_tx[i].busy = false;
            break;
        }
    }
    if (e->is_tx_success) {
        s_tx_ok++;
    } else {
        s_tx_fail++;
    }
    return false;
}

static bool IRAM_ATTR on_state_change(twai_node_handle_t h, const twai_state_change_event_data_t *e, void *ctx)
{
    (void)h;
    (void)ctx;
    if (e->new_sta == TWAI_ERROR_BUS_OFF) {
        s_bus_off_flag = true;
    }
    return false;
}

static bool IRAM_ATTR on_error(twai_node_handle_t h, const twai_error_event_data_t *e, void *ctx)
{
    (void)h;
    (void)e;
    (void)ctx;
    s_bus_err++;
    return false;
}

/* ---- node management ------------------------------------------------------------ */

static void tx_pool_reset(void)
{
    for (int i = 0; i < TX_POOL; i++) {
        s_tx[i].busy = false;
    }
}

/* Caller holds s_cfg_mtx. Creates and enables a node with the given flags. */
static esp_err_t node_create(bool listen_only, bool self_test_loopback)
{
    const twai_onchip_node_config_t cfg = {
        .io_cfg = {.tx = BOARD_PIN_CAN_TX, .rx = BOARD_PIN_CAN_RX, .quanta_clk_out = -1, .bus_off_indicator = -1},
        .bit_timing = {.bitrate = BOARD_CAN_BITRATE},   /* sampling point left to the driver default */
        .fail_retry_cnt = TX_RETRY,
        .tx_queue_depth = TX_QUEUE_DEPTH,
        .flags = {.enable_listen_only = listen_only, .enable_self_test = self_test_loopback,
                  .enable_loopback = self_test_loopback},
    };
    twai_node_handle_t n = NULL;
    esp_err_t e = twai_new_node_onchip(&cfg, &n);
    if (e != ESP_OK) {
        return e;
    }
    const twai_event_callbacks_t cbs = {
        .on_tx_done = on_tx_done,
        .on_rx_done = on_rx_done,
        .on_state_change = on_state_change,
        .on_error = on_error,
    };
    e = twai_node_register_event_callbacks(n, &cbs, NULL);
    if (e == ESP_OK) {
        e = twai_node_enable(n);
    }
    if (e != ESP_OK) {
        twai_node_delete(n);
        return e;
    }
    tx_pool_reset();
    s_bus_off_flag = false;
    s_node = n;
    return ESP_OK;
}

static void node_destroy(void)
{
    if (s_node) {
        twai_node_disable(s_node);      /* error if already disabled is ignored */
        twai_node_delete(s_node);
        s_node = NULL;
    }
}

esp_err_t can_link_set_bus_mode(can_mode_t mode)
{
    if (!s_cfg_mtx) {
        return ESP_ERR_INVALID_STATE;
    }
    xSemaphoreTake(s_cfg_mtx, portMAX_DELAY);
    esp_err_t e = ESP_OK;
    if (mode != s_mode || !s_node) {
        node_destroy();
        e = node_create(mode == CAN_MODE_LISTEN, false);
        if (e == ESP_OK) {
            s_mode = mode;
        } else {
            s_mode = CAN_MODE_LISTEN;
            ESP_LOGE(TAG, "node create failed: %s", esp_err_to_name(e));
        }
    }
    xSemaphoreGive(s_cfg_mtx);
    return e;
}

can_mode_t can_link_mode(void) { return s_mode; }

/* ---- TX ------------------------------------------------------------------------- */

static esp_err_t tx_raw(uint16_t id, const uint8_t *data, uint8_t dlc)
{
    if (dlc > 8 || (dlc && !data)) {
        return ESP_ERR_INVALID_ARG;
    }
    if (s_mode != CAN_MODE_BUS || !s_node) {
        return ESP_ERR_INVALID_STATE;
    }
    tx_slot_t *slot = NULL;
    taskENTER_CRITICAL(&s_pool_lock);
    for (int i = 0; i < TX_POOL; i++) {
        if (!s_tx[i].busy) {
            s_tx[i].busy = true;
            slot = &s_tx[i];
            break;
        }
    }
    taskEXIT_CRITICAL(&s_pool_lock);
    if (!slot) {
        return ESP_ERR_NO_MEM;
    }
    memset(&slot->f, 0, sizeof(slot->f));
    memcpy(slot->buf, data, dlc);
    slot->f.header.id = id;
    slot->f.header.dlc = dlc;
    slot->f.buffer = slot->buf;
    slot->f.buffer_len = dlc;      /* the driver requires dlc == len2dlc(buffer_len) when both are non-zero */
    esp_err_t e = twai_node_transmit(s_node, &slot->f, TX_TIMEOUT_MS);
    if (e != ESP_OK) {
        slot->busy = false;
    }
    return e;
}

static uint8_t my_node(void)
{
    int32_t n = 0;
    if (params_get_i32(PARAM_NODE, &n) != ESP_OK || n < 1 || n > 14) {
        return 0;
    }
    return (uint8_t)n;
}

esp_err_t can_link_send_frame(uint8_t cls, uint8_t func, const uint8_t *data, uint8_t dlc)
{
    uint8_t n = my_node();
    if (n == 0) {
        return ESP_ERR_INVALID_STATE;     /* unassigned: never transmit another node's ID (protocol s.1.1) */
    }
    return tx_raw(can_id_pack(cls, func, n), data, dlc);
}

esp_err_t can_link_send_tlm(uint8_t func, const uint8_t *data, uint8_t dlc)
{
    return can_link_send_frame(CAN_CLS_TLM, func, data, dlc);
}

/* ---- link state ------------------------------------------------------------------- */

static uint32_t bus_timeout_ms(void)
{
    int32_t t = 0;
    if (params_get_i32(PARAM_BUS_TIMEOUT, &t) != ESP_OK || t <= 0) {
        return DEFAULT_BUS_TIMEOUT_MS;
    }
    return (uint32_t)t;
}

bool can_link_master_seen(void) { return s_master_seen; }

uint32_t can_link_heartbeat_age_ms(void)
{
    if (!s_master_seen) {
        return UINT32_MAX;
    }
    int64_t d = (esp_timer_get_time() - s_last_link_all_us) / 1000;
    return d < 0 ? 0 : (d > (int64_t)UINT32_MAX - 1 ? UINT32_MAX - 1 : (uint32_t)d);
}

bool can_link_link_valid(void)
{
    if (!s_master_seen || !s_my_nibble_ok || can_link_heartbeat_age_ms() > bus_timeout_ms()) {
        return false;
    }
    return CAN_NIBBLE_VALID(s_my_nibble) != 0;
}

uint8_t can_link_err_class(void)
{
    if (!s_master_seen) {
        return 0;
    }
    if (can_link_heartbeat_age_ms() > bus_timeout_ms() || !s_my_nibble_ok) {
        return CAN_NIBBLE_CLASS(0xF);    /* 7: LOS */
    }
    return CAN_NIBBLE_CLASS(s_my_nibble);
}

void can_link_tec_rec(uint8_t *tec, uint8_t *rec)
{
    twai_node_status_t st = {0};
    twai_node_record_t rcd = {0};
    *tec = 0;
    *rec = 0;
    if (s_cfg_mtx && xSemaphoreTake(s_cfg_mtx, ticks_at_least_1(20)) == pdTRUE) {
        if (s_node && twai_node_get_info(s_node, &st, &rcd) == ESP_OK) {
            *tec = st.tx_error_count > 255 ? 255 : (uint8_t)st.tx_error_count;
            *rec = st.rx_error_count > 255 ? 255 : (uint8_t)st.rx_error_count;
        }
        xSemaphoreGive(s_cfg_mtx);
    }
}

uint32_t can_link_rx_count(void) { return s_rx_count; }

void can_link_stats_json(char *buf, size_t len)
{
    if (!buf || len == 0) {
        return;
    }
    uint8_t tec, rec;
    can_link_tec_rec(&tec, &rec);
    uint32_t age = can_link_heartbeat_age_ms();
    char hb[16];
    if (age == UINT32_MAX) {
        snprintf(hb, sizeof(hb), "null");
    } else {
        snprintf(hb, sizeof(hb), "%" PRIu32, age);
    }
    snprintf(buf, len,
             "{\"can\":{\"mode\":\"%s\",\"node\":%u,\"tec\":%u,\"rec\":%u,\"rx\":%" PRIu32 ",\"tx_ok\":%" PRIu32
             ",\"tx_fail\":%" PRIu32 ",\"rx_drop\":%" PRIu32 ",\"bus_err\":%" PRIu32 ",\"master\":%d,\"hb_ms\":%s"
             ",\"link\":%d,\"err\":%u}}",
             s_mode == CAN_MODE_BUS ? "bus" : "listen", (unsigned)my_node(), tec, rec, s_rx_count, s_tx_ok,
             s_tx_fail, s_rx_drop, s_bus_err, s_master_seen ? 1 : 0, hb, can_link_link_valid() ? 1 : 0,
             (unsigned)can_link_err_class());
    buf[len - 1] = '\0';
}

static bool node_not_bus_off(void)
{
    bool ok = false;
    twai_node_status_t st = {0};
    twai_node_record_t rcd = {0};
    if (s_cfg_mtx && xSemaphoreTake(s_cfg_mtx, ticks_at_least_1(20)) == pdTRUE) {
        ok = s_node && twai_node_get_info(s_node, &st, &rcd) == ESP_OK && st.state != TWAI_ERROR_BUS_OFF;
        xSemaphoreGive(s_cfg_mtx);
    }
    return ok;
}

/* ---- frame handling (rx task) ------------------------------------------------------ */

static void send_reply(uint8_t node, uint16_t param, uint8_t status, int32_t value)
{
    uint8_t d[8];
    uint8_t dlc = can_reply_encode(param, status, value, d);
    tx_raw(can_id_pack(CAN_CLS_RESP, CAN_FN_REPLY, node), d, dlc);
}

static void handle_get_set(uint8_t func, uint8_t target, const rx_msg_t *m, uint8_t me)
{
    if (me == 0 || (target != me && target != CAN_NODE_BROADCAST)) {
        return;
    }
    bool reply = target == me;
    uint16_t param;
    int32_t v = 0;
    esp_err_t e;
    if (func == CAN_FN_GET) {
        if (!can_get_decode(m->data, m->dlc, &param)) {
            return;
        }
        e = params_get_i32(param, &v);       /* broadcast GET gets no reply: nothing to do */
        if (reply) {
            send_reply(me, param, e == ESP_OK ? CAN_ST_OK : params_status_from_err(e), e == ESP_OK ? v : 0);
        }
    } else {
        if (!can_set_decode(m->data, m->dlc, &param, &v)) {
            return;
        }
        /* Broadcast SET is refused for the HV-affecting commands (review finding 3; protocol
         * doc s.1.3 is silent, PROPOSED rule noted there): hv_cmd = 1 and dac_hv must be
         * addressed to one node. A broadcast hv_cmd = 0 (off) is the safe direction and passes. */
        if (target == CAN_NODE_BROADCAST && ((param == PARAM_HV_CMD && v != 0) || param == PARAM_DAC_HV)) {
            return;
        }
        e = params_set_i32(param, v);
        if (reply) {
            int32_t rb = 0;
            if (params_get_i32(param, &rb) != ESP_OK) {
                rb = 0;                      /* write-only action parameters have no read-back */
            }
            send_reply(me, param, e == ESP_OK ? CAN_ST_OK : params_status_from_err(e), rb);
        }
    }
}

static uint8_t fw_major(void)
{
    int32_t v = 0;
    params_get_i32(PARAM_FW_VER, &v);
    return (uint8_t)(v >> 16);
}

static uint8_t fw_minor(void)
{
    int32_t v = 0;
    params_get_i32(PARAM_FW_VER, &v);
    return (uint8_t)(v >> 8);
}

static void send_boot_frame(void)
{
    int32_t v = 0;
    params_get_i32(PARAM_FW_VER, &v);
    can_boot_t b = {.reset_reason = app_safety_reset_reason(), .fw_major = (uint8_t)(v >> 16),
                    .fw_minor = (uint8_t)(v >> 8), .fw_patch = (uint8_t)v, .node = my_node()};
    uint8_t d[8];
    can_boot_encode(&b, d);
    can_link_send_frame(CAN_CLS_EVENT, CAN_FN_BOOT, d, 8);
}

static void send_enum_answer(void)
{
    uint8_t me = my_node();
    uint8_t d[8];
    can_enum_announce_encode(s_mac, me, fw_major(), fw_minor(), d);
    uint16_t id = me ? can_id_pack(CAN_CLS_ENUM, CAN_FN_ENUM_ANNOUNCE, me)
                     : can_id_pack(CAN_CLS_ENUM, CAN_FN_ENUM_NEW, can_enum_hash4(s_mac));
    tx_raw(id, d, 8);    /* sent by this node even when unassigned: protocol s.1.2 (func 2 + MAC hash) */
}

static void handle_frame(const rx_msg_t *m)
{
    uint8_t cls, func, node;
    if (!can_id_unpack(m->id, &cls, &func, &node)) {
        return;
    }
    const uint8_t me = my_node();

    if (cls == CAN_CLS_CMD && func == CAN_FN_LINK_ALL && node == CAN_NODE_MASTER) {
        can_link_all_t l;
        if (!can_link_all_decode(m->data, m->dlc, &l)) {
            return;
        }
        s_last_link_all_us = esp_timer_get_time();
        s_master_seen = true;
        /* The master heartbeat is back: README s.5 recovery for CAN_TIMEOUT (finding 7). BUSOFF
         * is dropped once the node is not bus-off any more (frames are being received). */
        fault_clear(FAULT_CAN_TIMEOUT);
        if ((fault_get() & FAULT_CAN_BUSOFF) && !s_bus_off_flag && node_not_bus_off()) {
            fault_clear(FAULT_CAN_BUSOFF);
        }
        if (me) {
            s_my_nibble = can_link_all_nibble(&l, me);
            s_my_nibble_ok = true;
        } else {
            s_my_nibble_ok = false;
        }
        if (s_mode != CAN_MODE_BUS) {          /* README s.4 step 7: LINK_ALL heard -> bus mode, TX enabled */
            if (can_link_set_bus_mode(CAN_MODE_BUS) == ESP_OK && !s_boot_sent) {
                s_boot_sent = true;
                s_fault_sent = 0;
                send_boot_frame();
            }
        }
        return;
    }
    if (cls == CAN_CLS_CMD && (func == CAN_FN_GET || func == CAN_FN_SET)) {
        handle_get_set(func, node, m, me);
        return;
    }
    if (cls == CAN_CLS_CMD && func == CAN_FN_IDENTIFY) {
        uint8_t sec;
        if (me && (node == me || node == CAN_NODE_BROADCAST) && can_identify_decode(m->data, m->dlc, &sec)) {
            app_telemetry_identify(sec);
        }
        return;
    }
    if (cls == CAN_CLS_ENUM && func == CAN_FN_ENUM_REQ && node == CAN_NODE_BROADCAST) {
        uint8_t round, slot_ms;
        if (can_enum_req_decode(m->data, m->dlc, &round, &slot_ms)) {
            if (slot_ms < ENUM_MIN_SLOT_MS) {
                slot_ms = ENUM_MIN_SLOT_MS;
            }
            s_enum_due_us = esp_timer_get_time() + (int64_t)can_enum_slot(s_mac) * slot_ms * 1000;
        }
        return;
    }
    if (cls == CAN_CLS_ENUM && func == CAN_FN_ENUM_ASSIGN && node == CAN_NODE_BROADCAST) {
        uint8_t mac[6], nid, flags;
        if (can_enum_assign_decode(m->data, m->dlc, mac, &nid, &flags) && memcmp(mac, s_mac, 6) == 0 &&
            nid >= 1 && nid <= 14) {
            if (params_set_i32(PARAM_NODE, nid) == ESP_OK && (flags & 1u)) {
                params_save();                  /* flags bit0 = persist (protocol s.1.2). Saves all S params. */
            }
        }
        return;
    }
}

static void fault_events(void)
{
    if (s_mode != CAN_MODE_BUS || my_node() == 0) {
        return;
    }
    fault_word_t w = fault_get();
    int64_t now = esp_timer_get_time();
    bool changed = w != s_fault_sent;
    bool resend = w != 0 && (now - s_fault_sent_us) >= (int64_t)FAULT_RESEND_MS * 1000;
    if (!changed && !resend) {
        return;
    }
    int32_t ls = 0;
    params_get_i32(PARAM_LOOP_STATE, &ls);
    can_fault_event_t ev = {.faults = w, .new_faults = (fault_word_t)(w & ~s_fault_sent), .hv_state = (uint8_t)app_safety_hv_state(),
                            .loop_state = (uint8_t)ls, .reset_reason = app_safety_reset_reason()};
    uint8_t d[8];
    can_fault_event_encode(&ev, d);
    if (can_link_send_frame(CAN_CLS_EVENT, CAN_FN_FAULT_EVENT, d, 8) == ESP_OK) {
        s_fault_sent = w;
        s_fault_sent_us = now;
    }
}

static void can_task(void *arg)
{
    (void)arg;
    int64_t next_fault_check = 0;
    for (;;) {
        app_safety_task_checkin(APP_TASK_CAN);
        rx_msg_t m;
        if (xQueueReceive(s_rxq, &m, ticks_at_least_1(TASK_TICK_MS)) == pdTRUE) {
            handle_frame(&m);
            continue;       /* drain before the housekeeping */
        }
        int64_t now = esp_timer_get_time();
        if (s_bus_off_flag) {
            s_bus_off_flag = false;
            fault_set(FAULT_CAN_BUSOFF);        /* protocol s.5 bit 6; safety turns HV off */
            if (s_cfg_mtx && xSemaphoreTake(s_cfg_mtx, ticks_at_least_1(50)) == pdTRUE) {
                if (s_node) {
                    esp_err_t e = twai_node_recover(s_node);
                    if (e != ESP_OK) {
                        ESP_LOGW(TAG, "recover: %s", esp_err_to_name(e));
                    }
                }
                xSemaphoreGive(s_cfg_mtx);
            }
        }
        if (s_enum_due_us && now >= s_enum_due_us) {
            s_enum_due_us = 0;
            send_enum_answer();
        }
        if (now >= next_fault_check) {
            next_fault_check = now + (int64_t)FAULT_CHECK_MS * 1000;
            fault_events();
        }
    }
}

esp_err_t can_link_start(void)
{
    if (s_cfg_mtx) {
        return ESP_OK;
    }
    esp_read_mac(s_mac, ESP_MAC_EFUSE_FACTORY);      /* eFuse read, no radio started (README s.7) */
    s_cfg_mtx = xSemaphoreCreateMutex();
    s_rxq = xQueueCreate(RX_QUEUE_LEN, sizeof(rx_msg_t));
    if (!s_cfg_mtx || !s_rxq) {
        return ESP_ERR_NO_MEM;
    }
    esp_err_t e = can_link_set_bus_mode(CAN_MODE_LISTEN);
    if (e != ESP_OK) {
        return e;
    }
    if (xTaskCreate(can_task, "can", CAN_TASK_STACK, NULL, CAN_TASK_PRIO, NULL) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

esp_err_t can_link_selftest_loopback(int *frames_ok)
{
    if (frames_ok) {
        *frames_ok = 0;
    }
    if (!s_cfg_mtx || !s_node) {
        return ESP_ERR_INVALID_STATE;
    }
    if ((esp_timer_get_time() - s_last_rx_us) < (int64_t)LOOPBACK_QUIET_MS * 1000 && s_rx_count > 0) {
        return ESP_ERR_INVALID_STATE;      /* active bus: caller reports skip */
    }
    xSemaphoreTake(s_cfg_mtx, portMAX_DELAY);
    can_mode_t prev = s_mode;
    node_destroy();
    s_lb_count = 0;
    s_lb_active = true;
    esp_err_t e = node_create(false, true);
    int ok = 0;
    uint8_t tec = 0, rec = 0;
    if (e == ESP_OK) {
        /* use the TX pool directly: tx_raw() refuses LISTEN mode and unassigned nodes */
        for (int i = 0; i < LOOPBACK_FRAMES; i++) {
            tx_slot_t *s = &s_tx[i];
            memset(&s->f, 0, sizeof(s->f));
            for (int k = 0; k < 8; k++) {
                s->buf[k] = (uint8_t)(i * 16 + k);
            }
            s->f.header.id = LOOPBACK_ID_BASE + i;
            s->f.header.dlc = 8;
            s->f.buffer = s->buf;
            s->f.buffer_len = 8;
            s->busy = true;
            esp_err_t te = twai_node_transmit(s_node, &s->f, 50);
            if (te != ESP_OK) {
                s->busy = false;
                e = te;
                break;
            }
        }
        if (e == ESP_OK) {
            twai_node_transmit_wait_all_done(s_node, LOOPBACK_WAIT_MS);
            vTaskDelay(ticks_at_least_1(5));
        }
        twai_node_status_t st = {0};
        twai_node_record_t rcd = {0};
        if (twai_node_get_info(s_node, &st, &rcd) == ESP_OK) {
            tec = st.tx_error_count > 255 ? 255 : (uint8_t)st.tx_error_count;
            rec = st.rx_error_count > 255 ? 255 : (uint8_t)st.rx_error_count;
        }
        ok = (int)s_lb_count;
    }
    s_lb_active = false;
    node_destroy();
    esp_err_t re = node_create(prev == CAN_MODE_LISTEN, false);
    if (re != ESP_OK) {
        ESP_LOGE(TAG, "restore after loopback failed: %s", esp_err_to_name(re));
        s_mode = CAN_MODE_LISTEN;
    }
    xSemaphoreGive(s_cfg_mtx);
    if (frames_ok) {
        *frames_ok = ok;
    }
    if (e != ESP_OK) {
        return e;
    }
    return (ok == LOOPBACK_FRAMES && tec == 0 && rec == 0) ? ESP_OK : ESP_FAIL;
}
