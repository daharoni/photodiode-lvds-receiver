/* HV gate, watchdog and boot-time safety state. README s.4, s.5.
 * The `safety` task (prio 20, 10 ms) is the only place that decides the level
 * of HV_DIS. app_safety_hv_off_now() may also drive it high from any task (the
 * safe direction); every write goes through one spinlock-protected function so
 * a concurrent enable cannot override a fault. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "fault.h"

typedef enum { HV_OFF = 0, HV_RAMP = 1, HV_ON = 2, HV_HOLD = 3, HV_FAULT = 4 } hv_state_t;

/* Watchdog check-in ids for monitored tasks. A task is monitored from its
 * first check-in; the safety task stops feeding the task watchdog if a
 * monitored task stays silent. */
enum { APP_TASK_SENSE = 0, APP_TASK_RANGE, APP_TASK_CAN, APP_TASK_TELEMETRY, APP_TASK_COUNT };

/** FIRST call in app_main (README s.4 step 1): HV_DIS = 1, then output. Reads
 *  the reset reason and latches BROWNOUT / WDT. Never fails. */
void app_safety_init(void);

/** Create the ramp task and the `safety` task (call after params_init and the
 *  sensing tasks exist). */
void app_safety_start(void);

/** Reset reason code per protocol s.1.6: 1 power-on, 2 software, 3 brown-out,
 *  4 task watchdog, 5 interrupt watchdog, 6 other. */
uint8_t app_safety_reset_reason(void);
const char *app_safety_reset_reason_name(void);

/** Boot checks tell the gate what has been proven in this boot (README s.4
 *  step 9 preconditions). Both start false. */
void app_safety_set_dac_verified(bool ok);
void app_safety_set_adc_ok(bool ok);

/** Request HV on or off. on: returns ESP_ERR_INVALID_STATE if any
 *  HV-blocking fault is latched or the DAC or ADC are not verified in this
 *  boot, or a turn-off ramp is running. Idempotent when already on. off:
 *  starts the commanded ramp-down (README s.4 step 10). */
esp_err_t app_safety_hv_request(bool on);
/** True while HV_DIS is low (supply enabled). */
bool app_safety_hv_enabled(void);
/** Fault path: HV_DIS high immediately, state FAULT if a blocking fault is
 *  latched, else OFF. Callable from any task. */
void app_safety_hv_off_now(void);
hv_state_t app_safety_hv_state(void);
const char *app_safety_hv_state_name(hv_state_t s);

/** Watchdog check-in from a monitored task. */
void app_safety_task_checkin(uint8_t task_id);

/** `faults clear`: clears every latched bit that is not currently true.
 *  HV_STUCK, HV_OVER are re-evaluated by the safety task. Faults that need a
 *  re-verification (I2C, DAC_EEPROM) also keep the DAC/ADC verified flags
 *  false, so HV stays refused until the next reboot (PROPOSED, limitation). */
void app_safety_faults_clear(void);
