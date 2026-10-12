/*
 * app_selftest.h - built-in self-test, README s.8 steps 1-9 (all windows
 * PROPOSED first guesses; nothing measured). Result JSON: protocol s.6.
 * Status: PROPOSED; compiled (see README.md); not run on hardware.
 *
 * Step ids (in order): identity, i2c, dac_eeprom, dac_rw, adc, gpio, can,
 * temp, hv (full only). Each step result is pass, fail, skip or info; a
 * short diagnostic "d" string is added to each step (extra key, protocol s.6
 * shows only id and r).
 *
 * Step 9 never writes HV_DIS: it uses app_safety_hv_request(). It caps the
 * bias at 110 V absolute (README s.8 step 9) and calls app_safety_hv_off_now()
 * on any reading above the cap.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Run the test synchronously (call from a task with >= 6 KB stack; main's
 *  selftest worker does). quick = steps 1-8, full = steps 1-9.
 *  ESP_ERR_INVALID_STATE if a test is already running or HV is not OFF at the
 *  start. Otherwise ESP_OK even when steps fail: read app_selftest_last_json()
 *  (the overall verdict is "pass" inside it). Sets FAULT_SELFTEST on a failed
 *  test and clears it on a passing one. Prints the human lines through
 *  ESP_LOGW only; the JSON line is returned, not printed. Also sends
 *  SELFTEST_RESULT (0x21n) if the CAN link is in bus mode. During the run the
 *  range loop is forced to manual (restored afterwards). */
esp_err_t app_selftest_run(bool full);

/** True while a test runs and during the short LED result display after it
 *  (<= about 8 s, so the telemetry LED task stays off the LED). */
bool app_selftest_running(void);

/** Last result JSON line, or "" if none. Valid until the next run starts. */
const char *app_selftest_last_json(void);

/** 0 never run, 1 pass, 2 fail (TLM_STATE selftest_last bits, protocol s.1.4). */
uint8_t app_selftest_last_status(void);

/** Pure helpers exposed for host or unit tests. */
/** True if |ratio-expected|/expected <= tol_frac. */
bool app_selftest_within(double value, double expected, double tol_frac);

#ifdef __cplusplus
}
#endif
