/*
 * drv_mcp4728.c - MCP4728 driver. Datasheet: Microchip DS22187E (2010),
 * docs/datasheets/mcp4728.pdf. Every constant cites the page it was read on.
 * Status: PROPOSED, compiled but not run on hardware.
 */
#include "drv_mcp4728.h"
#include <string.h>
#include "board_i2c.h"
#include "board_pins.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "fault.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "mcp4728";

/* Command bytes (first byte after the address), DS22187E Table 5-1 p.34:
 * Multi-Write = 0 1 0 0 0 DAC1 DAC0 UDAC (Fig 5-8 p.39);
 * Sequential Write = 0 1 0 1 0 DAC1 DAC0 UDAC (Fig 5-9 p.40). */
#define CMD_MULTI_WRITE     0x40
#define CMD_SEQ_WRITE       0x50
#define CMD_UDAC_UPLOAD     0x00   /* UDAC = 0: output updates (Table 4-3 p.25) */

/* Second data byte layout, Fig 5-8 p.39: VREF PD1 PD0 Gx D11..D8. */
#define VREF_VDD            0      /* Table 4-3 p.25 */
#define PD_NORMAL           0
#define GAIN_X1             0

#define LDAC_IDLE_LEVEL     0      /* drv_gpio_init() holds LDAC low (its header); pulse = high then low */
#define LDAC_PULSE_US       2      /* TLDAC >= 210 ns, DS22187E p.6; 2 us gives margin */

#define I2C_TIMEOUT_MS      20     /* PROPOSED: a 24-byte read is ~0.6 ms at 400 kHz */
#define MUTEX_TIMEOUT_MS    100    /* PROPOSED */
#define EEPROM_WAIT_MS      60     /* TWRITE 50 ms max, DS22187E p.6 (25 typ) plus 10 ms margin */
#define EEPROM_FIRST_DELAY_MS 2    /* let RDY/BSY fall after the stop condition: PROPOSED */

static i2c_master_dev_handle_t s_dev;

static esp_err_t take(void)
{
    SemaphoreHandle_t m = board_i2c_mutex();
    if (!m || !s_dev) {
        return ESP_ERR_INVALID_STATE;
    }
    return xSemaphoreTake(m, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) == pdTRUE ? ESP_OK : ESP_ERR_TIMEOUT;
}

static void give(void) { xSemaphoreGive(board_i2c_mutex()); }

esp_err_t mcp4728_init(void)
{
    i2c_master_bus_handle_t bus = board_i2c_bus();
    if (!bus) {
        return ESP_ERR_INVALID_STATE;
    }
    if (s_dev) {
        return ESP_OK;
    }
    const i2c_device_config_t cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = BOARD_I2C_ADDR_MCP4728,
        .scl_speed_hz = BOARD_I2C_FREQ_HZ,
    };
    SemaphoreHandle_t m = board_i2c_mutex();
    if (m && xSemaphoreTake(m, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    esp_err_t e = i2c_master_bus_add_device(bus, &cfg, &s_dev);
    if (m) {
        xSemaphoreGive(m);
    }
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "add device: %s", esp_err_to_name(e));
        return e;
    }
    /* RDY/BSY: open drain with an external pull-up (DS22187E s.3.5 p.30, about 100 k). */
    const gpio_config_t rdy = {
        .pin_bit_mask = 1ULL << BOARD_PIN_DAC_RDY,
        .mode = GPIO_MODE_INPUT,
    };
    gpio_config(&rdy);
    /* LDAC is configured by drv_gpio_init(); this driver only pulses it. */
    return ESP_OK;
}

static void ldac_pulse(void)
{
    gpio_set_level(BOARD_PIN_DAC_LDAC, !LDAC_IDLE_LEVEL);
    esp_rom_delay_us(LDAC_PULSE_US);
    gpio_set_level(BOARD_PIN_DAC_LDAC, LDAC_IDLE_LEVEL);
}

esp_err_t mcp4728_parse_read(const uint8_t raw[24], mcp4728_regs_t *out)
{
    /* Fig 5-15 p.45: per channel 6 bytes: input register (3) then EEPROM (3).
     * Byte 1: RDY/BSY POR DAC1 DAC0 0 A2 A1 A0.
     * Byte 2: VREF PD1 PD0 GX D11 D10 D9 D8.   Byte 3: D7..D0. */
    for (int ch = 0; ch < 4; ch++) {
        for (int k = 0; k < 2; k++) {
            const uint8_t *p = raw + ch * 6 + k * 3;
            if (((p[0] >> 4) & 3) != ch) {
                return ESP_ERR_INVALID_RESPONSE;
            }
            mcp4728_ch_t *c = k == 0 ? &out->input[ch] : &out->eeprom[ch];
            c->vref = (p[1] >> 7) & 1;
            c->pd = (p[1] >> 5) & 3;
            c->gain = (p[1] >> 4) & 1;
            c->code = (uint16_t)(((p[1] & 0x0F) << 8) | p[2]);
        }
    }
    out->rdy = (raw[0] >> 7) & 1;
    return ESP_OK;
}

esp_err_t mcp4728_read_all(mcp4728_regs_t *out)
{
    uint8_t raw[24];
    esp_err_t e = take();
    if (e != ESP_OK) {
        return e;
    }
    e = i2c_master_receive(s_dev, raw, sizeof(raw), I2C_TIMEOUT_MS);   /* address + R/W=1: Read command */
    give();
    if (e != ESP_OK) {
        ESP_LOGW(TAG, "read: %s", esp_err_to_name(e));
        fault_set(FAULT_I2C_DAC);
        return e;
    }
    return mcp4728_parse_read(raw, out);
}

esp_err_t mcp4728_write_volatile(uint8_t ch, uint16_t code)
{
    if (ch > 3 || code > 0xFFF) {
        return ESP_ERR_INVALID_ARG;
    }
    const uint8_t buf[3] = {
        (uint8_t)(CMD_MULTI_WRITE | (ch << 1) | CMD_UDAC_UPLOAD),
        (uint8_t)((VREF_VDD << 7) | (PD_NORMAL << 5) | (GAIN_X1 << 4) | (code >> 8)),
        (uint8_t)(code & 0xFF),
    };
    esp_err_t e = take();
    if (e != ESP_OK) {
        return e;
    }
    e = i2c_master_transmit(s_dev, buf, sizeof(buf), I2C_TIMEOUT_MS);
    give();
    if (e != ESP_OK) {
        ESP_LOGW(TAG, "write ch%u: %s", (unsigned)ch, esp_err_to_name(e));
        fault_set(FAULT_I2C_DAC);
        return e;
    }
    ldac_pulse();
    return ESP_OK;
}

static bool rdy_pin_high(void) { return gpio_get_level(BOARD_PIN_DAC_RDY) != 0; }

esp_err_t mcp4728_write_eeprom_defaults(void)
{
    /* Defaults per README s.4 step 4 and the coordinator contract. */
    static const uint16_t codes[4] = {0x000, BOARD_DAC_TH_ZERO_CODE, BOARD_DAC_HV_SAFE_CODE, 0x000};
    uint8_t buf[1 + 4 * 2];
    buf[0] = (uint8_t)(CMD_SEQ_WRITE | (MCP4728_CH_A << 1) | CMD_UDAC_UPLOAD);   /* start at channel A */
    for (int i = 0; i < 4; i++) {
        buf[1 + i * 2] = (uint8_t)((VREF_VDD << 7) | (PD_NORMAL << 5) | (GAIN_X1 << 4) | (codes[i] >> 8));
        buf[2 + i * 2] = (uint8_t)(codes[i] & 0xFF);
    }
    esp_err_t e = take();
    if (e != ESP_OK) {
        return e;
    }
    e = i2c_master_transmit(s_dev, buf, sizeof(buf), I2C_TIMEOUT_MS);   /* 9 bytes + address <= 10, p.40 */
    give();
    if (e != ESP_OK) {
        fault_set(FAULT_I2C_DAC);
        return e;
    }
    /* EEPROM programming starts at the 4th byte ACK of the last channel (Fig 5-9 note 2 p.40);
     * commands are ignored while RDY/BSY is low (s.5.6.3 p.36). Wait for the pin and the bit. */
    vTaskDelay(pdMS_TO_TICKS(EEPROM_FIRST_DELAY_MS));
    TickType_t start = xTaskGetTickCount();
    for (;;) {
        if (rdy_pin_high()) {
            mcp4728_regs_t r;
            if (take() == ESP_OK) {
                uint8_t raw[24];
                esp_err_t re = i2c_master_receive(s_dev, raw, sizeof(raw), I2C_TIMEOUT_MS);
                give();
                if (re == ESP_OK && mcp4728_parse_read(raw, &r) == ESP_OK && r.rdy) {
                    break;
                }
            }
        }
        if ((xTaskGetTickCount() - start) > pdMS_TO_TICKS(EEPROM_WAIT_MS)) {
            ESP_LOGE(TAG, "EEPROM write did not finish in %d ms", EEPROM_WAIT_MS);
            fault_set(FAULT_I2C_DAC);
            return ESP_ERR_TIMEOUT;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    mcp4728_regs_t r;
    e = mcp4728_read_all(&r);
    if (e != ESP_OK) {
        return e;
    }
    return mcp4728_eeprom_defaults_ok(&r) ? ESP_OK : ESP_FAIL;
}

bool mcp4728_eeprom_defaults_ok(const mcp4728_regs_t *r)
{
    const mcp4728_ch_t *a = &r->eeprom[MCP4728_CH_A], *b = &r->eeprom[MCP4728_CH_B];
    const mcp4728_ch_t *c = &r->eeprom[MCP4728_CH_C], *d = &r->eeprom[MCP4728_CH_D];
    return c->vref == VREF_VDD && c->pd == PD_NORMAL && c->code == BOARD_DAC_HV_SAFE_CODE &&
           b->vref == VREF_VDD && b->pd == PD_NORMAL && b->code == BOARD_DAC_TH_ZERO_CODE &&
           a->pd == PD_NORMAL && d->pd == PD_NORMAL;                      /* README s.4 step 4 */
}

esp_err_t mcp4728_readback_verify(uint8_t ch, uint16_t code)
{
    if (ch > 3) {
        return ESP_ERR_INVALID_ARG;
    }
    mcp4728_regs_t r;
    esp_err_t e = mcp4728_read_all(&r);
    if (e != ESP_OK) {
        return e;
    }
    const mcp4728_ch_t *c = &r.input[ch];
    if (c->vref != VREF_VDD || c->pd != PD_NORMAL || c->code != code) {
        ESP_LOGE(TAG, "readback ch%u: code 0x%03x vref %u pd %u, expected 0x%03x", (unsigned)ch,
                 (unsigned)c->code, (unsigned)c->vref, (unsigned)c->pd, (unsigned)code);
        fault_set(FAULT_I2C_DAC);
        return ESP_FAIL;
    }
    return ESP_OK;
}
