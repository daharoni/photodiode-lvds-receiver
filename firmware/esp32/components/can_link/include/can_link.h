/*
 * can_link.h - TWAI (CAN 2.0) link to the FPGA-side master.
 *
 * Protocol: docs/firmware/can-and-console-protocol.md s.1 (PROPOSED).
 * Boot policy: README s.4 step 7 (listen-only first, TX only after LINK_ALL).
 * Driver: ESP-IDF v5.5.5 node-based TWAI (esp_driver_twai: esp_twai.h,
 * esp_twai_onchip.h), API read from ~/esp/esp-idf/components/esp_driver_twai/include.
 * Status: PROPOSED; compiled against v5.5.5 (see README.md), not run on hardware.
 *
 * Frame codec lives in can_codec.h (pure C, host-tested).
 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "can_codec.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CAN_MODE_LISTEN = 0,   /* TX silent (TWAI listen-only): standalone / USB */
    CAN_MODE_BUS = 1,      /* LINK_ALL heard: TX enabled */
} can_mode_t;

/** Create the TWAI node (IO19 TX / IO18 RX, 125 kbit/s) in LISTEN-only mode and
 *  start the `can` task (prio 12, README s.3). Needs params_init() done. */
esp_err_t can_link_start(void);

/** Force a mode. LISTEN: TX off. BUS: TX on (the node is re-created; frames in
 *  flight are lost). Normally the task switches to BUS by itself on the first
 *  LINK_ALL. A node id of 0 (unassigned) still only sends enumeration frames. */
esp_err_t can_link_set_bus_mode(can_mode_t mode);
can_mode_t can_link_mode(void);

/** True once a LINK_ALL has been heard in this boot. */
bool can_link_master_seen(void);
/** ms since the last LINK_ALL; UINT32_MAX if none was ever heard. */
uint32_t can_link_heartbeat_age_ms(void);
/** LINK_ALL nibble bit3 for this node, false if the heartbeat is older than
 *  the `bus_timeout` parameter (default 2000 ms) or the node id is 0. */
bool can_link_link_valid(void);
/** LINK_ALL error class 0..7 for this node; 7 when the heartbeat is stale
 *  after having been heard; 0 if never heard (standalone). */
uint8_t can_link_err_class(void);

/** Send a periodic telemetry frame (class 3, function func 0..2, this node id).
 *  ESP_ERR_INVALID_STATE in LISTEN mode or with node id 0. dlc <= 8. */
esp_err_t can_link_send_tlm(uint8_t func, const uint8_t *data, uint8_t dlc);
/** Send any frame of this node (class, function): used for SELFTEST_RESULT
 *  (class 2, function 1). Same restrictions as can_link_send_tlm. */
esp_err_t can_link_send_frame(uint8_t cls, uint8_t func, const uint8_t *data, uint8_t dlc);

/** One JSON object with mode, TWAI state, TEC/REC, frame counters, heartbeat
 *  age, link state. Always NUL terminated. */
void can_link_stats_json(char *buf, size_t len);
/** TWAI transmit and receive error counters (0 if the node is down). */
void can_link_tec_rec(uint8_t *tec, uint8_t *rec);
/** Frames received since boot (any ID). */
uint32_t can_link_rx_count(void);

/** README s.8 step 7: with a quiet bus (no frame for 500 ms) re-create the node
 *  in self-test + loopback mode, send 8 frames and count the frames received
 *  back, then restore the previous mode. ESP_OK only if all 8 came back and
 *  TEC = REC = 0. ESP_ERR_INVALID_STATE if the bus is not quiet (the caller
 *  reports `skip`). *frames_ok gets the count. UNRESOLVED: whether loopback
 *  through the unterminated SN65HVD230 is clean (bench check, README s.8). */
esp_err_t can_link_selftest_loopback(int *frames_ok);

#ifdef __cplusplus
}
#endif
