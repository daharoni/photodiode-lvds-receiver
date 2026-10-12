/* HV gate, watchdog and boot-time safety state. README s.4, s.5.
 *
 * The decision logic is the pure state machine in hv_gate.h (host-tested). This
 * component wraps it: the `safety` task (prio 20, every 10 ms) feeds it the
 * faults and the measurement and applies its HV_DIS level; the `hv_exec` task
 * performs the I2C writes it asks for and reports back. Every HV_DIS write goes
 * through one spinlock-protected function that copies the machine's level, so
 * HV_DIS can only go low from the machine's ARMING state after the DAC_HV =
 * 0xFFF readback succeeded in that request. app_safety_hv_off_now() may be
 * called from any task and only raises the pin. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "fault.h"
#include "hv_gate.h"

typedef enum { HV_OFF = 0, HV_RAMP = 1, HV_ON = 2, HV_HOLD = 3, HV_FAULT = 4 } hv_state_t;

/* Watchdog check-in ids for monitored tasks. A task is monitored from its
 * first check-in; the safety task stops feeding the task watchdog if a
 * monitored task stays silent. */
enum { APP_TASK_SENSE = 0, APP_TASK_RANGE, APP_TASK_CAN, APP_TASK_TELEMETRY, APP_TASK_COUNT };

/** FIRST call in app_main (README s.4 step 1): HV_DIS = 1, then output. Reads
 *  the reset reason and latches BROWNOUT / WDT. Never fails. */
void app_safety_init(void);

/** Create the executor task and the `safety` task (call after params_init and
 *  the sensing tasks exist). */
void app_safety_start(void);

/** Reset reason code per protocol s.1.6: 1 power-on, 2 software, 3 brown-out,
 *  4 task watchdog, 5 interrupt watchdog, 6 other. */
uint8_t app_safety_reset_reason(void);
const char *app_safety_reset_reason_name(void);

/** Boot checks tell the gate what has been proven in this boot (README s.4
 *  step 9 preconditions). Both start false. The DAC flag is also cleared by the
 *  safety task whenever FAULT_I2C_DAC or FAULT_DAC_EEPROM is latched. */
void app_safety_set_dac_verified(bool ok);
void app_safety_set_adc_ok(bool ok);
bool app_safety_dac_verified(void);

/** Request HV on or off. on: ESP_ERR_INVALID_STATE if any HV-blocking fault is
 *  latched, the DAC or ADC are not verified, a post-fault safe write of DAC_HV
 *  is still pending, a manual DAC write is in progress or a turn-off ramp is
 *  running. Idempotent when already ON; a request while ARMING or ramping up
 *  restarts from ARMING. off: starts the commanded ramp-down (README s.4 step
 *  10) and suppresses `hv_auto` until the next successful on request. */
esp_err_t app_safety_hv_request(bool on);
/** Same with a per-request absolute bias cap (V, 0 = hv_max + 5 V) and ramp
 *  target (V, <= 0 = follow app_range's target). Used by the self-test. */
esp_err_t app_safety_hv_request_ex(bool on, float cap_v, float target_v);
/** True while HV_DIS is low (supply enabled). */
bool app_safety_hv_enabled(void);
/** Fault path: HV_DIS high immediately, state FAULT if a blocking fault is
 *  latched, else OFF. Callable from any task. */
void app_safety_hv_off_now(void);
hv_state_t app_safety_hv_state(void);
const char *app_safety_hv_state_name(hv_state_t s);
/** Finer state of the gate machine (arming, ramp_up, ramp_down, ...). */
const char *app_safety_gate_state_name(void);

/** app_range owns the ramp target (review finding 16): bias in 0.1 V that the
 *  soft start should walk to, hv_set only if the range FSM says so, otherwise
 *  hv_min. <= 0 means hv_min. Latest value is used at every ramp step. */
void app_safety_set_ramp_target_dv(int32_t dv);

/** Stop `hv_auto` from enabling HV (self-test running). */
void app_safety_set_auto_inhibit(bool inhibit);

/** Console and CAN `dac hv` while HV is OFF (HV_DIS high, gate OFF): write any
 *  code. ESP_ERR_INVALID_STATE otherwise. A later enable re-arms through 0xFFF
 *  anyway. */
esp_err_t app_safety_manual_dac_hv(uint16_t code);

/** Re-prove the DAC after a runtime failure: Read command, EEPROM defaults
 *  check, write 0xFFF to DAC_HV, read it back. Only with HV off. Sets the
 *  DAC-verified flag and clears FAULT_I2C_DAC / FAULT_DAC_EEPROM on success. */
esp_err_t app_safety_reverify_dac(void);

/** `faults clear`: clears every latched bit that is not currently true.
 *  FAULT_I2C_DAC and FAULT_DAC_EEPROM are dropped only after
 *  app_safety_reverify_dac() succeeds (its error is returned and the bits stay
 *  otherwise). FAULT_I2C_ADC stays latched until reboot once the ADC flag is
 *  false (PROPOSED limitation: no ADC re-verify yet). HV_STUCK, HV_OVER are
 *  re-evaluated by the safety task. */
esp_err_t app_safety_faults_clear(void);

/** Watchdog check-in from a monitored task. */
void app_safety_task_checkin(uint8_t task_id);
