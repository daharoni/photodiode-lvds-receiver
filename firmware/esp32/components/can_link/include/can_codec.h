/*
 * can_codec.h - pure-C CAN frame codec for the receiver module.
 *
 * No ESP-IDF includes: host-testable (firmware/esp32/test_host).
 * Source of every layout: docs/firmware/can-and-console-protocol.md s.1
 * (all PROPOSED, nothing measured; byte order little endian, s.1 table).
 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ID classes, protocol s.1.1, PROPOSED. ID = class<<8 | func<<4 | node. */
#define CAN_CLS_EVENT   0
#define CAN_CLS_CMD     1
#define CAN_CLS_RESP    2
#define CAN_CLS_TLM     3
#define CAN_CLS_ENUM    7

/* Functions per class, protocol s.1.1 table, PROPOSED. */
#define CAN_FN_FAULT_EVENT   0   /* class 0 */
#define CAN_FN_BOOT          1   /* class 0 */
#define CAN_FN_GET           0   /* class 1 */
#define CAN_FN_SET           1   /* class 1 */
#define CAN_FN_IDENTIFY      2   /* class 1 */
#define CAN_FN_LINK_ALL      15  /* class 1, 0x1F0, node field 0 */
#define CAN_FN_REPLY         0   /* class 2 */
#define CAN_FN_SELFTEST      1   /* class 2 */
#define CAN_FN_TLM_ANALOG    0   /* class 3 */
#define CAN_FN_TLM_STATE     1   /* class 3 */
#define CAN_FN_TLM_SLOW      2   /* class 3 */
#define CAN_FN_ENUM_REQ      0   /* class 7, 0x70F */
#define CAN_FN_ENUM_ANNOUNCE 1   /* class 7, 0x71n */
#define CAN_FN_ENUM_NEW      2   /* class 7, 0x72h */
#define CAN_FN_ENUM_ASSIGN   3   /* class 7, 0x73F */

#define CAN_NODE_MASTER      0   /* protocol s.1 table: node 0 = master */
#define CAN_NODE_BROADCAST   15  /* node 15 = broadcast */

/* Reply status codes, protocol s.1.3, PROPOSED. */
#define CAN_ST_OK            0
#define CAN_ST_UNKNOWN       1
#define CAN_ST_READ_ONLY     2
#define CAN_ST_RANGE         3
#define CAN_ST_REFUSED       4
#define CAN_ST_LOCKED        5
#define CAN_ST_BUSY          6

/* Parameter ids, protocol s.2 (PROPOSED, not frozen). */
#define CAN_PARAM_FW_VER      0x0001
#define CAN_PARAM_SERIAL      0x0002
#define CAN_PARAM_BOARD_REV   0x0003
#define CAN_PARAM_NODE        0x0004
#define CAN_PARAM_UPTIME      0x0005
#define CAN_PARAM_HV_CMD      0x0010
#define CAN_PARAM_HV_STATE    0x0011
#define CAN_PARAM_HV_SET      0x0012
#define CAN_PARAM_HV_MON      0x0013
#define CAN_PARAM_HV_MIN      0x0014
#define CAN_PARAM_HV_MAX      0x0015
#define CAN_PARAM_DAC_HV      0x0016
#define CAN_PARAM_M_EST       0x0017
#define CAN_PARAM_M_TARGET    0x0018
#define CAN_PARAM_TIA         0x0020
#define CAN_PARAM_TIA_AUTO    0x0021
#define CAN_PARAM_RSSI        0x0022
#define CAN_PARAM_RSSI_DROP   0x0023
#define CAN_PARAM_VTH_MON     0x0024
#define CAN_PARAM_LOOP        0x0030
#define CAN_PARAM_LOOP_STATE  0x0031
#define CAN_PARAM_LINK_VALID  0x0040
#define CAN_PARAM_LINK_ERR    0x0041
#define CAN_PARAM_FAULTS      0x0050
#define CAN_PARAM_BUS_TIMEOUT 0x0061
#define CAN_PARAM_TEMP        0x0070
#define CAN_PARAM_SELFTEST    0x0080
#define CAN_PARAM_SAVE        0x0091

/** Pack class/function/node into an 11-bit ID. Inputs are masked to 3/4/4 bits. */
uint16_t can_id_pack(uint8_t cls, uint8_t func, uint8_t node);
/** Unpack an 11-bit ID. Returns false (outputs untouched) if id > 0x7FF. */
bool can_id_unpack(uint32_t id, uint8_t *cls, uint8_t *func, uint8_t *node);

/* ---- command frames (s.1.3) ---- */
/** GET payload [param u16]; returns DLC (2). */
uint8_t can_get_encode(uint16_t param, uint8_t out[8]);
/** Decode GET; false if dlc != 2. */
bool can_get_decode(const uint8_t *d, uint8_t dlc, uint16_t *param);
/** SET payload [param u16, value i32]; returns DLC (6). */
uint8_t can_set_encode(uint16_t param, int32_t value, uint8_t out[8]);
/** Decode SET; false if dlc != 6. */
bool can_set_decode(const uint8_t *d, uint8_t dlc, uint16_t *param, int32_t *value);
/** Reply payload [param u16, status u8, value i32]; returns DLC (7). */
uint8_t can_reply_encode(uint16_t param, uint8_t status, int32_t value, uint8_t out[8]);
bool can_reply_decode(const uint8_t *d, uint8_t dlc, uint16_t *param, uint8_t *status, int32_t *value);
/** IDENTIFY payload [seconds u8]; DLC 1. */
bool can_identify_decode(const uint8_t *d, uint8_t dlc, uint8_t *seconds);

/* ---- LINK_ALL (s.1.5) ---- */
typedef struct {
    uint8_t nibble[14];   /* index node-1; bit3 valid, bits2:0 class */
    uint8_t seq;          /* byte 7 */
} can_link_all_t;
/** Decode a LINK_ALL payload (DLC must be 8). */
bool can_link_all_decode(const uint8_t *d, uint8_t dlc, can_link_all_t *out);
/** Encode (for tests and the emulated master); returns DLC 8. */
uint8_t can_link_all_encode(const can_link_all_t *in, uint8_t out[8]);
/** Nibble of node n (1..14); returns 0xFF if n out of range. */
uint8_t can_link_all_nibble(const can_link_all_t *l, uint8_t node);
#define CAN_NIBBLE_VALID(n)  (((n) >> 3) & 1u)
#define CAN_NIBBLE_CLASS(n)  ((n) & 7u)

/* ---- telemetry (s.1.4) ---- */
typedef struct { uint16_t hv_dv, rssi_mv, vth_mv, m_x10; } can_tlm_analog_t;
uint8_t can_tlm_analog_encode(const can_tlm_analog_t *t, uint8_t out[8]);
bool can_tlm_analog_decode(const uint8_t *d, uint8_t dlc, can_tlm_analog_t *t);

typedef struct {
    uint8_t hv_state;       /* bits 2:0 */
    bool tia_20k, bus_mode, comp_en, link_valid, tia_auto;
    uint8_t loop_state;
    uint16_t faults, dac_hv;
    uint8_t link_err;       /* 0..7 */
    uint8_t selftest_last;  /* bits 1:0 */
    bool aux_in;            /* byte7 bit2 */
    uint8_t src;            /* byte7 bits 4:3 */
} can_tlm_state_t;
uint8_t can_tlm_state_encode(const can_tlm_state_t *t, uint8_t out[8]);
bool can_tlm_state_decode(const uint8_t *d, uint8_t dlc, can_tlm_state_t *t);

typedef struct { uint32_t uptime_s; int16_t temp_dc; uint8_t tec, rec; } can_tlm_slow_t;
uint8_t can_tlm_slow_encode(const can_tlm_slow_t *t, uint8_t out[8]);
bool can_tlm_slow_decode(const uint8_t *d, uint8_t dlc, can_tlm_slow_t *t);

/* ---- fault / boot / selftest (s.1.6) ---- */
typedef struct {
    uint16_t faults, new_faults;
    uint8_t hv_state, loop_state, reset_reason;
} can_fault_event_t;
uint8_t can_fault_event_encode(const can_fault_event_t *e, uint8_t out[8]);
bool can_fault_event_decode(const uint8_t *d, uint8_t dlc, can_fault_event_t *e);

typedef struct { uint8_t reset_reason, fw_major, fw_minor, fw_patch, node; } can_boot_t;
uint8_t can_boot_encode(const can_boot_t *b, uint8_t out[8]);
bool can_boot_decode(const uint8_t *d, uint8_t dlc, can_boot_t *b);

typedef struct { uint8_t pass, steps_run; uint16_t fail_mask, hv_peak_dv; } can_selftest_t;
uint8_t can_selftest_encode(const can_selftest_t *s, uint8_t out[8]);
bool can_selftest_decode(const uint8_t *d, uint8_t dlc, can_selftest_t *s);

/* ---- enumeration (s.1.2) ---- */
/** CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF). The protocol doc says
 *  "crc16(mac)" without naming the polynomial: this choice is PROPOSED. */
uint16_t can_crc16(const uint8_t *d, size_t n);
/** Slot (0..63) a node answers in: crc16(mac) mod 64, s.1.2 step 2. */
uint8_t can_enum_slot(const uint8_t mac[6]);
/** 4-bit hash of the MAC for ID 0x72h (low nibble of crc16, PROPOSED). */
uint8_t can_enum_hash4(const uint8_t mac[6]);
bool can_enum_req_decode(const uint8_t *d, uint8_t dlc, uint8_t *round, uint8_t *slot_ms);
/** ENUM_ANNOUNCE payload [mac[6], node u8, fw u8 = major<<4|minor]; DLC 8. */
uint8_t can_enum_announce_encode(const uint8_t mac[6], uint8_t node, uint8_t fw_major, uint8_t fw_minor, uint8_t out[8]);
bool can_enum_announce_decode(const uint8_t *d, uint8_t dlc, uint8_t mac[6], uint8_t *node, uint8_t *fw);
/** ASSIGN payload [mac[6], node u8, flags u8]; DLC 8. */
uint8_t can_enum_assign_encode(const uint8_t mac[6], uint8_t node, uint8_t flags, uint8_t out[8]);
bool can_enum_assign_decode(const uint8_t *d, uint8_t dlc, uint8_t mac[6], uint8_t *node, uint8_t *flags);

#ifdef __cplusplus
}
#endif
