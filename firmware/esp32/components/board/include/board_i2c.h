#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "driver/i2c_master.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

/** Create the I2C master bus (port 0, IO2/IO3, 400 kHz, no internal pull-ups:
 *  the board has 4.7 k external) and the bus mutex. Idempotent. */
esp_err_t board_i2c_init(void);

/** The bus handle, or NULL before board_i2c_init(). */
i2c_master_bus_handle_t board_i2c_bus(void);

/** Bus mutex (a plain, non-recursive mutex). Contract: the device drivers
 *  (drv_mcp4728, drv_ads1115) take it themselves around each transaction;
 *  callers of the drivers must NOT hold it. NULL before board_i2c_init(). */
SemaphoreHandle_t board_i2c_mutex(void);

/** Bus recovery (README s.4 step 3): if SDA is low, clock SCL 9 times, then
 *  issue a STOP. Must be called BEFORE board_i2c_init() (returns
 *  ESP_ERR_INVALID_STATE afterwards). Returns ESP_OK if SDA is high at the
 *  end (or was high at the start), ESP_FAIL if SDA is still stuck low. */
esp_err_t board_i2c_bus_recover(void);

/** True if a device ACKs its address (takes the bus mutex). */
bool board_i2c_probe(uint8_t addr);
