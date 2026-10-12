/*
 * drv_ads1115.c - ADS1115 driver. Datasheet: TI SBAS444E (Dec 2024).
 * Page numbers are the printed footer numbers of the PDF.
 * Status: PROPOSED, compiled but not run on hardware.
 */
#include "drv_ads1115.h"
#include "board_i2c.h"
#include "board_pins.h"
#include "esp_log.h"
#include "fault.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "ads1115";

/* Address pointer values P[1:0], Table 8-1 p.24 */
#define REG_CONVERSION      0x00
#define REG_CONFIG          0x01
/* Config register bit fields, Table 8-3 p.25-26 (Fig 8-5 p.25) */
#define CFG_OS              (1u << 15)         /* write 1 = start single conversion; read 1 = idle */
#define CFG_MUX_AINx_GND(x) ((uint16_t)((4u + (x)) << 12))   /* MUX 100..111 = AIN0..3 vs GND */
#define CFG_PGA_4V096       (1u << 9)          /* PGA 001 = +-4.096 V; covers 3.3 V rails (README s.1) */
#define CFG_MODE_SINGLE     (1u << 8)          /* MODE = 1 single-shot */
#define CFG_DR_128SPS       (4u << 5)          /* DR 100 = 128 SPS (default) */
#define CFG_COMP_DISABLE    3u                 /* COMP_QUE 11 = comparator disabled (reset value) */
#define CFG_RESET_VALUE     0x8583u            /* Config register reset value, p.25 */

#define LSB_UV              125                /* +-4.096 V FSR: 125 uV, Table 7-1 p.15 */
#define CONV_POLL_MS        1                  /* PROPOSED */
#define CONV_TIMEOUT_MS     30                 /* 1/128 s = 7.8 ms nominal; 30 ms is PROPOSED margin */
#define I2C_TIMEOUT_MS      20                 /* PROPOSED */
#define MUTEX_TIMEOUT_MS    100                /* PROPOSED */
#define N_AVG_DEFAULT       4                  /* README s.3 task table: 4-sample average */

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

static esp_err_t read_reg(uint8_t reg, uint16_t *v)
{
    uint8_t rx[2];
    esp_err_t e = i2c_master_transmit_receive(s_dev, &reg, 1, rx, 2, I2C_TIMEOUT_MS);
    if (e == ESP_OK) {
        *v = (uint16_t)((rx[0] << 8) | rx[1]);   /* MSB first, Fig 7-8 */
    }
    return e;
}

esp_err_t ads1115_init(void)
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
        .device_address = BOARD_I2C_ADDR_ADS1115,   /* ADDR to GND = 1001000b, Table 7-2 p.21 */
        .scl_speed_hz = BOARD_I2C_FREQ_HZ,
    };
    SemaphoreHandle_t m = board_i2c_mutex();
    if (m && xSemaphoreTake(m, pdMS_TO_TICKS(MUTEX_TIMEOUT_MS)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    esp_err_t e = i2c_master_bus_add_device(bus, &cfg, &s_dev);
    if (e == ESP_OK) {
        uint16_t c = 0;
        e = read_reg(REG_CONFIG, &c);
        if (e == ESP_OK && c != CFG_RESET_VALUE) {
            /* Not necessarily an error (a previous boot may have written it): informational. */
            ESP_LOGW(TAG, "config reg 0x%04x (reset value 0x8583)", (unsigned)c);
        }
    }
    if (m) {
        xSemaphoreGive(m);
    }
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "init: %s", esp_err_to_name(e));
        fault_set(FAULT_I2C_ADC);
    }
    return e;
}

int32_t ads1115_raw_to_mv(int32_t raw_sum, int n)
{
    int64_t uv = (int64_t)raw_sum * LSB_UV;           /* microvolts times n */
    int64_t d = (int64_t)n * 1000;
    return (int32_t)(uv >= 0 ? (uv + d / 2) / d : -((-uv + d / 2) / d));
}

static esp_err_t convert_once(uint8_t ain, int16_t *raw)
{
    const uint16_t cfg = CFG_OS | CFG_MUX_AINx_GND(ain) | CFG_PGA_4V096 | CFG_MODE_SINGLE |
                         CFG_DR_128SPS | CFG_COMP_DISABLE;
    const uint8_t w[3] = {REG_CONFIG, (uint8_t)(cfg >> 8), (uint8_t)cfg};
    esp_err_t e = take();
    if (e != ESP_OK) {
        return e;
    }
    e = i2c_master_transmit(s_dev, w, sizeof(w), I2C_TIMEOUT_MS);   /* OS = 1 starts the conversion, s.7.4.2.1 p.18 */
    give();
    if (e != ESP_OK) {
        return e;
    }
    TickType_t start = xTaskGetTickCount();
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(CONV_POLL_MS));
        uint16_t c = 0;
        e = take();
        if (e != ESP_OK) {
            return e;
        }
        e = read_reg(REG_CONFIG, &c);
        give();
        if (e != ESP_OK) {
            return e;
        }
        if (c & CFG_OS) {                                            /* OS = 1: conversion done (Table 8-3 p.25) */
            break;
        }
        if ((xTaskGetTickCount() - start) > pdMS_TO_TICKS(CONV_TIMEOUT_MS)) {
            return ESP_ERR_TIMEOUT;
        }
    }
    uint16_t v = 0;
    e = take();
    if (e != ESP_OK) {
        return e;
    }
    e = read_reg(REG_CONVERSION, &v);
    give();
    if (e == ESP_OK) {
        *raw = (int16_t)v;                                           /* two's complement, s.8.1.2 p.24 */
    }
    return e;
}

esp_err_t ads1115_read_mv_n(uint8_t ain, int n_avg, int32_t *out_mv)
{
    if (ain > 3 || n_avg < 1 || n_avg > 16 || !out_mv) {
        return ESP_ERR_INVALID_ARG;
    }
    int32_t sum = 0;
    for (int i = 0; i < n_avg; i++) {
        int16_t raw = 0;
        esp_err_t e = convert_once(ain, &raw);
        if (e != ESP_OK) {
            ESP_LOGW(TAG, "AIN%u: %s", (unsigned)ain, esp_err_to_name(e));
            fault_set(FAULT_I2C_ADC);
            return e;
        }
        sum += raw;
    }
    *out_mv = ads1115_raw_to_mv(sum, n_avg);
    return ESP_OK;
}

esp_err_t ads1115_read_mv(uint8_t ain, int32_t *out_mv)
{
    return ads1115_read_mv_n(ain, N_AVG_DEFAULT, out_mv);
}
