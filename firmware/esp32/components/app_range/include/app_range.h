/*
 * app_range.h - range-trim task: runs range_fsm every 100 ms, trims DAC_HV in
 * closed loop on HV_MON, switches the TIA, estimates M.
 *
 * README s.6 (PROPOSED). Pure logic lives in range_fsm.h / range_m_est.h.
 * Status: PROPOSED; compiled (see README.md), host-tested logic only,
 * not run on hardware.
 *
 * DAC_HV ownership: app_safety walks the DAC during ramp up/down
 * (hv_state RAMP); this task writes DAC_HV only while app_safety_hv_state()
 * is HV_ON. It never touches HV_DIS.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "range_fsm.h"
#include "range_m_est.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Create the `range` task (prio 8, 100 ms). Needs sense_start() and the
 *  drivers initialised. Registers the live getter for param m_est. */
void app_range_start(void);

/** State name: "OFF", "RAMP", "SEARCH", "TRACK", "LOS", "MANUAL", "FAULT". */
const char *app_range_state_name(void);
/** Numeric state (protocol s.1.4 loop_state enumeration). */
int app_range_state(void);

/** `loop auto` (true) or `loop manual` (false). Standalone (no LINK_ALL) is
 *  MANUAL regardless (README s.6.5). */
void app_range_set_mode(bool automatic);
bool app_range_is_auto(void);

/** Manual DAC_HV code target (console `dac hv`, CAN dac_hv, self-test slope
 *  step) while HV is ON and the loop is in manual mode. The range task moves
 *  the code toward it at most 134 codes per 100 ms and keeps the modelled bias
 *  within [hv_min, hv_max] and the code above the open-loop bound (hv_gate.h
 *  hvg_code_min). ESP_ERR_INVALID_STATE in auto mode or when HV is not ON,
 *  ESP_ERR_INVALID_ARG above 0xFFF. */
esp_err_t app_range_manual_set_code(uint16_t code);

/** Estimated M x 10, or -1 until calibrated (README s.6.4). */
int32_t app_range_m_est_x10(void);

/** Last DAC_HV code this task knows of (read back from the MCP4728 at least
 *  every 2 s while HV is on). */
uint16_t app_range_dac_code(void);

/** Calibration entry points (README s.6.4; the console agent decided not to
 *  call them yet, so `cal` commands are not wired: UNRESOLVED).
 *  v100: bias for M = 100 at 25 C. */
void app_range_cal_set_v100(float v100);
/** Room-temperature (code, measured bias) pair for the code-to-volt map. */
void app_range_cal_set_code(uint16_t code, float bias_v);
/** Restore a saved lock (V_lock) so the next ramp starts there (README s.6.3 RAMP). */
void app_range_set_last_lock(float v_lock);

#ifdef __cplusplus
}
#endif
