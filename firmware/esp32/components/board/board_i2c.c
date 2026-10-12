#include "board_i2c.h"
#include "board_pins.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"
#include "esp_log.h"

static const char *TAG = "board_i2c";
static i2c_master_bus_handle_t s_bus;
static SemaphoreHandle_t s_mutex;

#define PROBE_TIMEOUT_MS 50  /* UNRESOLVED: first guess */
#define RECOVERY_HALF_PERIOD_US 5  /* about 100 kHz clocking; first guess */

esp_err_t board_i2c_init(void)
{
    if (s_bus) {
        return ESP_OK;
    }
    if (!s_mutex) {
        s_mutex = xSemaphoreCreateMutex();
        if (!s_mutex) {
            return ESP_ERR_NO_MEM;
        }
    }
    i2c_master_bus_config_t cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = BOARD_PIN_I2C_SDA,
        .scl_io_num = BOARD_PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = false,
    };
    esp_err_t err = i2c_new_master_bus(&cfg, &s_bus);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "bus create failed: %s", esp_err_to_name(err));
        s_bus = NULL;
    }
    return err;
}

i2c_master_bus_handle_t board_i2c_bus(void) { return s_bus; }
SemaphoreHandle_t board_i2c_mutex(void) { return s_mutex; }

esp_err_t board_i2c_bus_recover(void)
{
    if (s_bus) {
        return ESP_ERR_INVALID_STATE;
    }
    gpio_config_t sda = {
        .pin_bit_mask = 1ULL << BOARD_PIN_I2C_SDA,
        .mode = GPIO_MODE_INPUT_OUTPUT_OD,
    };
    gpio_config_t scl = {
        .pin_bit_mask = 1ULL << BOARD_PIN_I2C_SCL,
        .mode = GPIO_MODE_INPUT_OUTPUT_OD,
    };
    gpio_set_level(BOARD_PIN_I2C_SDA, 1);
    gpio_set_level(BOARD_PIN_I2C_SCL, 1);
    gpio_config(&sda);
    gpio_config(&scl);
    esp_rom_delay_us(RECOVERY_HALF_PERIOD_US);

    esp_err_t res = ESP_OK;
    if (gpio_get_level(BOARD_PIN_I2C_SDA) == 0) {
        ESP_LOGW(TAG, "SDA low at boot, clocking SCL");
        for (int i = 0; i < 9 && gpio_get_level(BOARD_PIN_I2C_SDA) == 0; i++) {
            gpio_set_level(BOARD_PIN_I2C_SCL, 0);
            esp_rom_delay_us(RECOVERY_HALF_PERIOD_US);
            gpio_set_level(BOARD_PIN_I2C_SCL, 1);
            esp_rom_delay_us(RECOVERY_HALF_PERIOD_US);
        }
        /* STOP: SDA low -> high while SCL high */
        gpio_set_level(BOARD_PIN_I2C_SDA, 0);
        esp_rom_delay_us(RECOVERY_HALF_PERIOD_US);
        gpio_set_level(BOARD_PIN_I2C_SDA, 1);
        esp_rom_delay_us(RECOVERY_HALF_PERIOD_US);
        if (gpio_get_level(BOARD_PIN_I2C_SDA) == 0) {
            res = ESP_FAIL;
        }
    }
    gpio_reset_pin(BOARD_PIN_I2C_SDA);
    gpio_reset_pin(BOARD_PIN_I2C_SCL);
    return res;
}

bool board_i2c_probe(uint8_t addr)
{
    if (!s_bus) {
        return false;
    }
    bool ok = false;
    if (xSemaphoreTake(s_mutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        ok = (i2c_master_probe(s_bus, addr, PROBE_TIMEOUT_MS) == ESP_OK);
        xSemaphoreGive(s_mutex);
    }
    return ok;
}
