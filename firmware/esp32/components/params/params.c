#include "params.h"
#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "esp_log.h"
#include "esp_rom_crc.h"
#include "esp_timer.h"
#include "esp_app_desc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "fault.h"

static const char *TAG = "params";

/* ---- limits ------------------------------------------------------------ */
/* README s.4 step 2: hv_min >= 100 V, hv_max default 200 V, absolute 220 V.
 * CAN unit is 0.1 V. */
#define HV_MIN_FLOOR   1000
#define HV_MAX_DEFAULT 2000
#define HV_ABS_MAX     2200
/* th: +-16 mV authority (protocol s.4), CAN unit 0.1 mV. */
#define TH_LIMIT       160
/* tlm_ms minimum 50, default 100 (protocol s.2). Maximum: UNRESOLVED. */
#define TLM_MS_MAX     60000
/* bus_timeout default 2000 ms (protocol s.2). Min and max: UNRESOLVED. */
#define BUS_TIMEOUT_MIN 100
#define BUS_TIMEOUT_MAX 60000
/* m_target default 45 (M x 10 = 450). Range: UNRESOLVED. */
#define M_TARGET_MIN   100
#define M_TARGET_MAX   2000
/* vbr range: UNRESOLVED; 0 = not calibrated. */
#define VBR_MAX        2200

#define NO_LIMIT_MIN INT32_MIN
#define NO_LIMIT_MAX INT32_MAX

/* Table from protocol doc s.2. */
static const param_desc_t k_table[] = {
    /* id,  name, type, unit, scale, access, ns, min, max, def */
    {PARAM_FW_VER, "fw_ver", PT_VERSION, "", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_SERIAL, "serial", PT_INT, "", 1, PARAM_R | PARAM_W | PARAM_S | PARAM_A, PNS_FACTORY, 0, INT32_MAX, 0},
    {PARAM_BOARD_REV, "board_rev", PT_INT, "", 1, PARAM_R | PARAM_W | PARAM_S | PARAM_A, PNS_FACTORY, 0, 255, 0},
    {PARAM_NODE, "node", PT_INT, "", 1, PARAM_R | PARAM_W | PARAM_S, PNS_USER, 0, 14, 0},
    {PARAM_UPTIME, "uptime", PT_INT, "s", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_HV_CMD, "hv_cmd", PT_BOOL, "", 1, PARAM_R | PARAM_W, PNS_NONE, 0, 1, 0},
    {PARAM_HV_STATE, "hv_state", PT_HV_STATE, "", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_HV_SET, "hv_set", PT_INT, "V", 0.1f, PARAM_R | PARAM_W | PARAM_S, PNS_USER, HV_MIN_FLOOR, HV_ABS_MAX, HV_MIN_FLOOR},
    {PARAM_HV_MON, "hv_mon", PT_INT, "V", 0.1f, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_HV_MIN, "hv_min", PT_INT, "V", 0.1f, PARAM_R | PARAM_W | PARAM_S, PNS_USER, HV_MIN_FLOOR, HV_ABS_MAX, HV_MIN_FLOOR},
    {PARAM_HV_MAX, "hv_max", PT_INT, "V", 0.1f, PARAM_R | PARAM_W | PARAM_S, PNS_USER, HV_MIN_FLOOR, HV_ABS_MAX, HV_MAX_DEFAULT},
    {PARAM_DAC_HV, "dac_hv", PT_INT, "code", 1, PARAM_R | PARAM_W, PNS_NONE, 0, 4095, 4095},
    {PARAM_M_EST, "m_est", PT_INT, "M", 0.1f, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_M_TARGET, "m_target", PT_INT, "M", 0.1f, PARAM_R | PARAM_W | PARAM_S, PNS_USER, M_TARGET_MIN, M_TARGET_MAX, 450},
    {PARAM_VBR, "vbr", PT_INT, "V", 0.1f, PARAM_R | PARAM_W | PARAM_S, PNS_FACTORY, 0, VBR_MAX, 0},
    {PARAM_TIA, "tia", PT_TIA, "", 1, PARAM_R | PARAM_W, PNS_NONE, 0, 1, 1},
    {PARAM_TIA_AUTO, "tia_auto", PT_BOOL, "", 1, PARAM_R | PARAM_W | PARAM_S, PNS_USER, 0, 1, 0 /* UNRESOLVED default */},
    {PARAM_RSSI, "rssi", PT_INT, "mV", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_RSSI_DROP, "rssi_drop", PT_INT, "mV", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_VTH_MON, "vth_mon", PT_INT, "mV", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_TH, "th", PT_INT, "mV", 0.1f, PARAM_R | PARAM_W | PARAM_S, PNS_USER, -TH_LIMIT, TH_LIMIT, 0},
    {PARAM_COMP_EN, "comp_en", PT_BOOL, "", 1, PARAM_R | PARAM_W, PNS_NONE, 0, 1, 1},
    {PARAM_LOOP, "loop", PT_BOOL, "", 1, PARAM_R | PARAM_W | PARAM_S, PNS_USER, 0, 1, 1 /* PROPOSED: auto; app_range forces MANUAL standalone */},
    {PARAM_LOOP_STATE, "loop_state", PT_LOOP_STATE, "", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_LINK_VALID, "link_valid", PT_BOOL, "", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_LINK_ERR, "link_err", PT_INT, "", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_FAULTS, "faults", PT_HEX, "", 1, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_FAULTS_CLEAR, "faults_clear", PT_BOOL, "", 1, PARAM_W, PNS_NONE, 0, 1, 0},
    {PARAM_TLM_MS, "tlm_ms", PT_INT, "ms", 1, PARAM_R | PARAM_W | PARAM_S, PNS_USER, 50, TLM_MS_MAX, 100},
    {PARAM_BUS_TIMEOUT, "bus_timeout", PT_INT, "ms", 1, PARAM_R | PARAM_W | PARAM_S, PNS_USER, BUS_TIMEOUT_MIN, BUS_TIMEOUT_MAX, 2000},
    {PARAM_HV_AUTO, "hv_auto", PT_BOOL, "", 1, PARAM_R | PARAM_W | PARAM_S, PNS_USER, 0, 1, 0},
    {PARAM_TEMP, "temp", PT_INT, "C", 0.1f, PARAM_R, PNS_NONE, 0, 0, 0},
    {PARAM_SELFTEST_RUN, "selftest_run", PT_INT, "", 1, PARAM_W, PNS_NONE, 1, 2, 0},
    {PARAM_SAVE, "save", PT_BOOL, "", 1, PARAM_W, PNS_NONE, 1, 1, 0},
    {PARAM_REBOOT, "reboot", PT_BOOL, "", 1, PARAM_W, PNS_NONE, 1, 1, 0},
    {PARAM_DEFAULTS, "defaults", PT_INT, "", 1, PARAM_W, PNS_NONE, 1, 2, 0},
};
#define N_PARAMS ((int)(sizeof(k_table) / sizeof(k_table[0])))

static int32_t s_val[N_PARAMS];
static int32_t (*s_live[N_PARAMS])(void);
static esp_err_t (*s_action[N_PARAMS])(int32_t);
static SemaphoreHandle_t s_mutex;
static bool s_dirty;

/* ---- NVS blob ---------------------------------------------------------- */
#define NS_MAX_ENTRIES 16
#define BLOB_MAGIC 0x50524D31u /* 'PRM1' */
typedef struct {
    uint16_t id;
    uint16_t rsvd;
    int32_t v;
} blob_entry_t;
typedef struct {
    uint32_t magic;
    uint32_t n;
    blob_entry_t e[NS_MAX_ENTRIES];
    uint32_t crc;   /* CRC32 over everything before this field */
} blob_t;

static const char *ns_name(param_ns_t ns)
{
    switch (ns) {
    case PNS_FACTORY: return "factory";
    case PNS_USER: return "user";
    case PNS_STATE: return "state";
    default: return NULL;
    }
}

static int idx_of(uint16_t id)
{
    for (int i = 0; i < N_PARAMS; i++) {
        if (k_table[i].id == id) {
            return i;
        }
    }
    return -1;
}

static int32_t clamp_i32(int32_t v, int32_t lo, int32_t hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

static void apply_defaults(bool include_factory)
{
    for (int i = 0; i < N_PARAMS; i++) {
        if (!include_factory && k_table[i].ns == PNS_FACTORY) {
            continue;
        }
        s_val[i] = k_table[i].def;
    }
}

static esp_err_t load_ns(param_ns_t ns, bool *had_blob)
{
    *had_blob = false;
    nvs_handle_t h;
    esp_err_t err = nvs_open(ns_name(ns), NVS_READONLY, &h);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return ESP_OK; /* first boot */
    }
    if (err != ESP_OK) {
        return err;
    }
    blob_t b;
    size_t len = sizeof(b);
    err = nvs_get_blob(h, "blob", &b, &len);
    nvs_close(h);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return ESP_OK;
    }
    *had_blob = true;
    if (err != ESP_OK || len != sizeof(b) || b.magic != BLOB_MAGIC || b.n > NS_MAX_ENTRIES ||
        esp_rom_crc32_le(0, (const uint8_t *)&b, offsetof(blob_t, crc)) != b.crc) {
        return ESP_ERR_INVALID_CRC;
    }
    for (uint32_t k = 0; k < b.n; k++) {
        int i = idx_of(b.e[k].id);
        if (i < 0 || k_table[i].ns != ns) {
            continue;
        }
        s_val[i] = clamp_i32(b.e[k].v, k_table[i].min, k_table[i].max);
    }
    return ESP_OK;
}

static void normalise_hv_limits(void)
{
    int imin = idx_of(PARAM_HV_MIN), imax = idx_of(PARAM_HV_MAX), iset = idx_of(PARAM_HV_SET);
    if (s_val[imax] < s_val[imin]) {
        s_val[imin] = k_table[imin].def;
        s_val[imax] = k_table[imax].def;
    }
    s_val[iset] = clamp_i32(s_val[iset], s_val[imin], s_val[imax]);
}

esp_err_t params_init(void)
{
    s_mutex = xSemaphoreCreateMutex();
    apply_defaults(true);

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS erased (%s)", esp_err_to_name(err));
        nvs_flash_erase();
        err = nvs_flash_init();
        fault_set(FAULT_NVS);
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs init failed: %s", esp_err_to_name(err));
        fault_set(FAULT_NVS);
        normalise_hv_limits();
        return err;
    }
    esp_err_t result = ESP_OK;
    const param_ns_t nss[] = {PNS_FACTORY, PNS_USER, PNS_STATE};
    for (int k = 0; k < 3; k++) {
        bool had;
        esp_err_t e = load_ns(nss[k], &had);
        if (e != ESP_OK) {
            ESP_LOGW(TAG, "namespace %s bad (%s): defaults", ns_name(nss[k]), esp_err_to_name(e));
            for (int i = 0; i < N_PARAMS; i++) {
                if (k_table[i].ns == nss[k]) {
                    s_val[i] = k_table[i].def;
                }
            }
            fault_set(FAULT_NVS);
            result = ESP_ERR_INVALID_CRC;
        }
    }
    normalise_hv_limits();
    s_dirty = false;
    return result;
}

static esp_err_t save_ns(param_ns_t ns)
{
    blob_t b;
    memset(&b, 0, sizeof(b));
    b.magic = BLOB_MAGIC;
    for (int i = 0; i < N_PARAMS; i++) {
        if (k_table[i].ns == ns && (k_table[i].access & PARAM_S)) {
            if (b.n >= NS_MAX_ENTRIES) {
                return ESP_ERR_NO_MEM;
            }
            b.e[b.n].id = k_table[i].id;
            b.e[b.n].v = s_val[i];
            b.n++;
        }
    }
    b.crc = esp_rom_crc32_le(0, (const uint8_t *)&b, offsetof(blob_t, crc));
    nvs_handle_t h;
    esp_err_t err = nvs_open(ns_name(ns), NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    err = nvs_set_blob(h, "blob", &b, sizeof(b));
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err;
}

esp_err_t params_save(void)
{
    esp_err_t first = ESP_OK;
    const param_ns_t nss[] = {PNS_FACTORY, PNS_USER, PNS_STATE};
    for (int k = 0; k < 3; k++) {
        esp_err_t e = save_ns(nss[k]);
        if (e != ESP_OK && first == ESP_OK) {
            first = e;
        }
    }
    if (first == ESP_OK) {
        s_dirty = false;
    }
    return first;
}

esp_err_t params_defaults(bool all)
{
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    apply_defaults(all);
    normalise_hv_limits();
    xSemaphoreGive(s_mutex);
    return params_save();
}

bool params_dirty(void) { return s_dirty; }

/* ---- access ------------------------------------------------------------ */
const param_desc_t *params_find(const char *name)
{
    for (int i = 0; i < N_PARAMS; i++) {
        if (strcmp(k_table[i].name, name) == 0) {
            return &k_table[i];
        }
    }
    return NULL;
}
const param_desc_t *params_find_id(uint16_t id)
{
    int i = idx_of(id);
    return i < 0 ? NULL : &k_table[i];
}
const param_desc_t *params_at(int i) { return (i >= 0 && i < N_PARAMS) ? &k_table[i] : NULL; }

void params_register_live(uint16_t id, int32_t (*getter)(void))
{
    int i = idx_of(id);
    if (i >= 0) {
        s_live[i] = getter;
    }
}
void params_register_action(uint16_t id, esp_err_t (*set)(int32_t v))
{
    int i = idx_of(id);
    if (i >= 0) {
        s_action[i] = set;
    }
}

esp_err_t params_get_i32(uint16_t id, int32_t *out)
{
    int i = idx_of(id);
    if (i < 0) {
        return ESP_ERR_NOT_FOUND;
    }
    if (id == PARAM_FW_VER) {
        unsigned a = 0, b = 0, c = 0;
        sscanf(esp_app_get_description()->version, "%u.%u.%u", &a, &b, &c);
        *out = (int32_t)((a << 16) | (b << 8) | c);
        return ESP_OK;
    }
    if (id == PARAM_UPTIME) {
        *out = (int32_t)(esp_timer_get_time() / 1000000);
        return ESP_OK;
    }
    if (id == PARAM_FAULTS) {
        *out = fault_get();
        return ESP_OK;
    }
    if (s_live[i]) {
        *out = s_live[i]();
        return ESP_OK;
    }
    if ((k_table[i].access & PARAM_W) == 0 && k_table[i].ns == PNS_NONE && k_table[i].min == 0 &&
        k_table[i].max == 0) {
        return ESP_ERR_INVALID_STATE; /* live value with no owner registered */
    }
    *out = s_val[i];
    return ESP_OK;
}

esp_err_t params_set_i32(uint16_t id, int32_t v)
{
    int i = idx_of(id);
    if (i < 0) {
        return ESP_ERR_NOT_FOUND;
    }
    const param_desc_t *d = &k_table[i];
    if (!(d->access & PARAM_W)) {
        return ESP_ERR_NOT_ALLOWED;
    }
    if ((d->access & PARAM_A) && s_val[i] != 0) {
        return PARAMS_ERR_LOCKED;
    }
    /* hv_set is clamped to the limits rather than rejected (protocol s.4 `hv set`). */
    if (id == PARAM_HV_SET) {
        v = clamp_i32(v, s_val[idx_of(PARAM_HV_MIN)], s_val[idx_of(PARAM_HV_MAX)]);
    }
    if (v < d->min || v > d->max) {
        return ESP_ERR_INVALID_ARG;
    }
    if (id == PARAM_HV_MIN && v > s_val[idx_of(PARAM_HV_MAX)]) {
        return ESP_ERR_INVALID_ARG;
    }
    if (id == PARAM_HV_MAX && v < s_val[idx_of(PARAM_HV_MIN)]) {
        return ESP_ERR_INVALID_ARG;
    }
    if (id == PARAM_NODE || id == PARAM_SERIAL || id == PARAM_BOARD_REV) {
        /* write-once and range handled above; node 0 allowed (unassigned) */
    }
    if (s_action[i]) {
        esp_err_t e = s_action[i](v);
        if (e != ESP_OK) {
            return e;
        }
    }
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    s_val[i] = v;
    if (id == PARAM_HV_MIN || id == PARAM_HV_MAX) {
        s_val[idx_of(PARAM_HV_SET)] = clamp_i32(s_val[idx_of(PARAM_HV_SET)],
                                                s_val[idx_of(PARAM_HV_MIN)], s_val[idx_of(PARAM_HV_MAX)]);
    }
    if (d->access & PARAM_S) {
        s_dirty = true;
    }
    xSemaphoreGive(s_mutex);
    return ESP_OK;
}

esp_err_t params_get_by_name(const char *name, float *out)
{
    const param_desc_t *d = params_find(name);
    if (!d) {
        return ESP_ERR_NOT_FOUND;
    }
    int32_t v;
    esp_err_t e = params_get_i32(d->id, &v);
    if (e == ESP_OK) {
        *out = (float)v * d->scale;
    }
    return e;
}

esp_err_t params_set_by_name(const char *name, float v)
{
    const param_desc_t *d = params_find(name);
    if (!d) {
        return ESP_ERR_NOT_FOUND;
    }
    return params_set_i32(d->id, (int32_t)lroundf(v / d->scale));
}

static const char *const k_hv_names[] = {"off", "ramp", "on", "hold", "fault"};
static const char *const k_loop_names[] = {"OFF", "RAMP", "SEARCH", "TRACK", "LOS", "MANUAL", "FAULT"};

void params_format(const param_desc_t *d, int32_t v, char *buf, size_t len)
{
    switch (d->type) {
    case PT_VERSION:
        snprintf(buf, len, "%d.%d.%d", (int)(v >> 16), (int)((v >> 8) & 0xFF), (int)(v & 0xFF));
        break;
    case PT_HEX:
        snprintf(buf, len, "0x%04x", (unsigned)v);
        break;
    case PT_HV_STATE:
        snprintf(buf, len, "%s", (v >= 0 && v <= 4) ? k_hv_names[v] : "?");
        break;
    case PT_LOOP_STATE:
        snprintf(buf, len, "%s", (v >= 0 && v <= 6) ? k_loop_names[v] : "?");
        break;
    case PT_TIA:
        snprintf(buf, len, "%s", v ? "20k" : "5k");
        break;
    case PT_BOOL:
        snprintf(buf, len, "%d", (int)v);
        break;
    default:
        if (d->scale < 1.0f) {
            snprintf(buf, len, "%.1f", (double)v * d->scale);
        } else {
            snprintf(buf, len, "%ld", (long)v);
        }
        break;
    }
}

uint8_t params_status_from_err(esp_err_t err)
{
    switch (err) {
    case ESP_OK: return 0;
    case ESP_ERR_NOT_FOUND: return 1;
    case ESP_ERR_NOT_ALLOWED: return 2;
    case ESP_ERR_INVALID_ARG: return 3;
    case PARAMS_ERR_LOCKED: return 5;
    case PARAMS_ERR_BUSY: return 6;
    default: return 4;
    }
}
