/*
 * drv_mcp4728.h - MCP4728 quad 12-bit DAC driver (I2C 0x60).
 *
 * Datasheet: Microchip DS22187E (2010), docs/datasheets/mcp4728.pdf, read
 * from the PDF text for this file. Status: PROPOSED; not run on hardware.
 * DAC_TH = channel B (index 1), DAC_HV = channel C (index 2) (board contract).
 * All I2C transactions take board_i2c_mutex(). Failures set FAULT_I2C_DAC.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MCP4728_CH_A 0
#define MCP4728_CH_B 1   /* DAC_TH */
#define MCP4728_CH_C 2   /* DAC_HV */
#define MCP4728_CH_D 3

/** One channel as returned by the Read command (DS22187E Fig 5-15 p.45). */
typedef struct {
    uint8_t vref;    /* 0 = VDD, 1 = internal 2.048 V (Table 4-3 p.25) */
    uint8_t pd;      /* power-down bits PD1:PD0, 0 = normal */
    uint8_t gain;    /* GX, 0 = x1 */
    uint16_t code;   /* 12-bit */
} mcp4728_ch_t;

typedef struct {
    mcp4728_ch_t input[4];    /* DAC input registers */
    mcp4728_ch_t eeprom[4];   /* power-on EEPROM contents */
    bool rdy;                 /* RDY/BSY bit of the first byte: 1 = EEPROM idle */
} mcp4728_regs_t;

/** Add the I2C device (0x60, 400 kHz) to board_i2c_bus() and configure
 *  LDAC (output, idle high) and RDY/BSY (input) GPIOs. Needs board_i2c_init() first. */
esp_err_t mcp4728_init(void);

/** Read command (R/W = 1, 24 bytes): DS22187E s.5.6.9 p.37 and Fig 5-15 p.45.
 *  NOT the General Call Read (that only returns address bits, s.5.4.4).
 *  ESP_ERR_INVALID_RESPONSE if the channel-select bits of a returned byte
 *  do not match the expected channel (framing check, PROPOSED). */
esp_err_t mcp4728_read_all(mcp4728_regs_t *out);

/** Volatile write of one channel's input register and output (EEPROM untouched):
 *  Multi-Write, UDAC = 0 (output updates at the 4th byte ACK, DS22187E s.5.6.2
 *  p.35 and Fig 5-8 p.39), VREF = VDD, PD = 00, gain x1; then an LDAC pulse
 *  (low >= 210 ns, p.6). ch 0..3, code 0..0xFFF, else ESP_ERR_INVALID_ARG. */
esp_err_t mcp4728_write_volatile(uint8_t ch, uint16_t code);

/** Program the power-on defaults into EEPROM with the Sequential Write command
 *  (s.5.6.3 p.36, Fig 5-9 p.40): A normal 0, B 0x800, C 0xFFF, D normal 0, all
 *  VREF = VDD, PD = 00, gain x1. Waits for RDY/BSY (pin and bit) up to 60 ms
 *  (TWRITE 25 ms typ, 50 ms max, p.6) and re-reads. GUARDED: call only from
 *  the console `dac provision confirm` path. Does not touch HV_DIS. */
esp_err_t mcp4728_write_eeprom_defaults(void);

/** README s.4 step 4 criteria applied to r->eeprom: C = VDD ref, PD 00, 0xFFF;
 *  B = VDD ref, PD 00, 0x800; A and D PD 00 (normal mode). Pure function. */
bool mcp4728_eeprom_defaults_ok(const mcp4728_regs_t *r);

/** Read back and require input[ch] == {vref 0, pd 0, code}. Sets FAULT_I2C_DAC
 *  on mismatch (protocol s.5 bit 0). ESP_FAIL on mismatch. */
esp_err_t mcp4728_readback_verify(uint8_t ch, uint16_t code);

/** Pure parser of a 24-byte Read response (exposed for tests). */
esp_err_t mcp4728_parse_read(const uint8_t raw[24], mcp4728_regs_t *out);

#ifdef __cplusplus
}
#endif
