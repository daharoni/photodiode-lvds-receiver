/* Parameter registry shared by the CAN link and the console.
 * Table: docs/firmware/can-and-console-protocol.md s.2 (PROPOSED, not frozen).
 * NVS namespaces: README s.6.6. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

/* Parameter ids (protocol doc s.2). */
enum {
    PARAM_FW_VER = 0x0001, PARAM_SERIAL = 0x0002, PARAM_BOARD_REV = 0x0003,
    PARAM_NODE = 0x0004, PARAM_UPTIME = 0x0005,
    PARAM_HV_CMD = 0x0010, PARAM_HV_STATE = 0x0011, PARAM_HV_SET = 0x0012,
    PARAM_HV_MON = 0x0013, PARAM_HV_MIN = 0x0014, PARAM_HV_MAX = 0x0015,
    PARAM_DAC_HV = 0x0016, PARAM_M_EST = 0x0017, PARAM_M_TARGET = 0x0018,
    PARAM_VBR = 0x0019,
    PARAM_TIA = 0x0020, PARAM_TIA_AUTO = 0x0021, PARAM_RSSI = 0x0022,
    PARAM_RSSI_DROP = 0x0023, PARAM_VTH_MON = 0x0024, PARAM_TH = 0x0025,
    PARAM_COMP_EN = 0x0026,
    PARAM_LOOP = 0x0030, PARAM_LOOP_STATE = 0x0031,
    PARAM_LINK_VALID = 0x0040, PARAM_LINK_ERR = 0x0041,
    PARAM_FAULTS = 0x0050, PARAM_FAULTS_CLEAR = 0x0051,
    PARAM_TLM_MS = 0x0060, PARAM_BUS_TIMEOUT = 0x0061,
    /* Not in protocol s.2: NVS flag named in README s.4 step 8(c). PROPOSED
     * id, add to the protocol table if kept. */
    PARAM_HV_AUTO = 0x0062,
    PARAM_TEMP = 0x0070,
    PARAM_SELFTEST_RUN = 0x0080,
    PARAM_SAVE = 0x0090, PARAM_REBOOT = 0x0091, PARAM_DEFAULTS = 0x0092,
};

/* Access flags (protocol s.2). */
#define PARAM_R 0x01   /* readable (always) */
#define PARAM_W 0x02   /* writable */
#define PARAM_S 0x04   /* persisted by save */
#define PARAM_A 0x08   /* write-once (locked once non-zero) */

/* How to print a value in console units. */
typedef enum {
    PT_INT,       /* scaled number */
    PT_VERSION,   /* major<<16 + minor<<8 + patch */
    PT_HEX,
    PT_HV_STATE,  /* enum 0..4 */
    PT_LOOP_STATE,/* enum 0..6 */
    PT_TIA,       /* 1 = 20k, 0 = 5k */
    PT_BOOL,
} param_type_t;

typedef enum { PNS_NONE = 0, PNS_FACTORY, PNS_USER, PNS_STATE } param_ns_t;

typedef struct {
    uint16_t id;
    const char *name;
    param_type_t type;
    const char *unit;     /* console unit text */
    float scale;          /* console value = CAN value * scale */
    uint8_t access;       /* PARAM_R | PARAM_W | PARAM_S | PARAM_A */
    param_ns_t ns;        /* NVS namespace when PARAM_S */
    int32_t min, max;     /* CAN units, for writable parameters */
    int32_t def;          /* factory default, CAN units */
} param_desc_t;

/* Error codes beyond the standard ones (mapped to protocol status by
 * params_status_from_err): ESP_ERR_NOT_FOUND unknown(1), ESP_ERR_NOT_ALLOWED
 * read-only(2), ESP_ERR_INVALID_ARG out of range(3), ESP_ERR_INVALID_STATE
 * refused(4), PARAMS_ERR_LOCKED write-once locked(5), PARAMS_ERR_BUSY busy(6). */
#define PARAMS_ERR_LOCKED ((esp_err_t)0x6501)
#define PARAMS_ERR_BUSY   ((esp_err_t)0x6502)

/** Map an esp_err_t from params_set/get to the CAN reply status byte (0..6). */
uint8_t params_status_from_err(esp_err_t err);

/** Init NVS, load namespaces `factory`, `user`, `state`, check the CRC of each
 *  blob, clamp every value to its limits. Corrupt or missing blobs give the
 *  factory defaults and set FAULT_NVS (a missing blob on first boot is not an
 *  error). Returns ESP_OK, or ESP_ERR_INVALID_CRC if any blob was bad. */
esp_err_t params_init(void);

/** Read a parameter in CAN units (live getter if registered, else RAM). */
esp_err_t params_get_i32(uint16_t id, int32_t *out);
/** Write a parameter in CAN units: checks access, range, write-once lock, and
 *  calls the registered action hook if there is one. RAM only; use
 *  params_save to persist. hv_set is clamped to [hv_min, hv_max]. */
esp_err_t params_set_i32(uint16_t id, int32_t v);
/** Same in console units (value / scale rounded to nearest). */
esp_err_t params_get_by_name(const char *name, float *out_console_units);
esp_err_t params_set_by_name(const char *name, float v);
/** Lookup; NULL if unknown. */
const param_desc_t *params_find(const char *name);
const param_desc_t *params_find_id(uint16_t id);
/** Iterate the table: returns descriptor i, or NULL past the end. */
const param_desc_t *params_at(int i);

/** Format a value of a parameter in console units into buf. */
void params_format(const param_desc_t *d, int32_t can_value, char *buf, size_t len);

/** Persist all S parameters (the namespaces `factory`, `user`, `state`). */
esp_err_t params_save(void);
/** Erase the user and state parameters back to defaults (RAM and NVS). With
 *  all = true also serial, board_rev and calibration (README s.6.6 / protocol
 *  s.2 `defaults`). */
esp_err_t params_defaults(bool all);

/** Register a live getter for a read-only value (hv_mon, rssi, ...). The
 *  owner component or main/params_bind.c calls this at init. */
void params_register_live(uint16_t id, int32_t (*getter)(void));
/** Register an action hook for a writable parameter with a side effect
 *  (hv_cmd, tia, ...). The hook receives the already range-checked value;
 *  if it returns ESP_OK the value is stored in RAM, otherwise the error is
 *  returned to the caller. */
void params_register_action(uint16_t id, esp_err_t (*set)(int32_t v));

/** True if the user changed anything since the last save (dirty flag). */
bool params_dirty(void);
