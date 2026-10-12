/* Board pin and constant map. Source: firmware/esp32/README.md s.1 (PROPOSED
 * hardware, docs/schematic/ sheets). Nothing here is measured. */
#pragma once

#define BOARD_PIN_HV_DIS      0   /* HIGH or Hi-Z = APD supply OFF. Written only by app_safety. */
#define BOARD_PIN_SHDN_N      1   /* TLV3605 shutdown, active low; pull-up keeps comparator on */
#define BOARD_PIN_I2C_SDA     2
#define BOARD_PIN_I2C_SCL     3
#define BOARD_PIN_CC1_SENSE   4   /* ADC1_CH4 */
#define BOARD_PIN_CC2_SENSE   5   /* ADC1_CH5 */
#define BOARD_PIN_DAC_LDAC    6
#define BOARD_PIN_AUX         7
#define BOARD_PIN_BOOT        9
#define BOARD_PIN_USB_DN      12
#define BOARD_PIN_USB_DP      13
#define BOARD_PIN_CAN_RX      18  /* swapped 2026-10-10 */
#define BOARD_PIN_CAN_TX      19
#define BOARD_PIN_TIA_CTRL    20  /* 1 = 20k, 0 = 5k; pull-up gives 20k */
#define BOARD_PIN_DAC_RDY     22  /* MCP4728 RDY/BSY, open drain */
#define BOARD_PIN_LED         23

#define BOARD_I2C_ADDR_MCP4728 0x60
#define BOARD_I2C_ADDR_ADS1115 0x48
/* 400 kHz fast mode: MCP4728 DS22187E p.1 (standard/fast/high-speed) and
 * ADS1115 SBAS444E (I2C timing table, fast mode) both support it. VERIFIED
 * by text search of docs/datasheets; the 4.7 k pull-up rise time at 400 kHz is
 * UNRESOLVED (not calculated). */
#define BOARD_I2C_FREQ_HZ      400000

#define BOARD_CAN_BITRATE      125000  /* protocol doc s.1 */

/* MCP4728 channel map (README s.1): index 0=A, 1=B, 2=C, 3=D */
#define BOARD_DAC_CH_TH        1   /* channel B = DAC_TH */
#define BOARD_DAC_CH_HV        2   /* channel C = DAC_HV */

/* ADS1115 channel map */
#define BOARD_ADC_AIN_HV_MON   0
#define BOARD_ADC_AIN_RSSI     1
#define BOARD_ADC_AIN_VTH_MON  2
#define BOARD_ADC_AIN_GND      3

#define BOARD_HV_MON_DIVIDER   101.0f   /* bias = AIN0 x 101 */

/* Safe DAC codes (README s.4 steps 4-5) */
#define BOARD_DAC_HV_SAFE_CODE 0xFFF    /* minimum bias */
#define BOARD_DAC_TH_ZERO_CODE 0x800    /* zero threshold offset */

/* Nominal bias per DAC_HV code, 14.95 mV (README s.4 step 9, calculated) */
#define BOARD_HV_V_PER_CODE    0.01495f
