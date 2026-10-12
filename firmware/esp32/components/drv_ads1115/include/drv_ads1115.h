/*
 * drv_ads1115.h - ADS1115 16-bit ADC driver (I2C 0x48).
 *
 * Datasheet: TI SBAS444E (Dec 2024), docs/datasheets/ads1115.pdf, read from the
 * PDF text for this file. Status: PROPOSED; not run on hardware.
 * Every transaction takes board_i2c_mutex(). Failures set FAULT_I2C_ADC.
 */
#pragma once
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Add the I2C device (0x48, 400 kHz) to board_i2c_bus() and check that it
 *  answers a Config register read. Needs board_i2c_init() first. */
esp_err_t ads1115_init(void);

/** Single-shot, single-ended AINx vs GND (MUX 100+x), PGA +-4.096 V
 *  (125 uV/LSB), 128 SPS, average of 4 conversions, result in millivolts
 *  (rounded). ain 0..3 else ESP_ERR_INVALID_ARG. Polls the OS bit with a
 *  30 ms timeout per conversion; on a timeout or any I2C error sets
 *  FAULT_I2C_ADC and returns the error (ESP_ERR_TIMEOUT for the conversion
 *  timeout). Takes about 4 x 7.8 ms = 31 ms per call (128 SPS), so a round of
 *  three channels is about 100 ms. */
esp_err_t ads1115_read_mv(uint8_t ain, int32_t *out_mv);

/** Same with a caller-chosen number of averaged conversions (1..16). */
esp_err_t ads1115_read_mv_n(uint8_t ain, int n_avg, int32_t *out_mv);

/** Pure helper: raw signed code to millivolts at +-4.096 V FSR (Table 7-1 p.15:
 *  125 uV LSB). Rounds to nearest. */
int32_t ads1115_raw_to_mv(int32_t raw_sum, int n);

#ifdef __cplusplus
}
#endif
