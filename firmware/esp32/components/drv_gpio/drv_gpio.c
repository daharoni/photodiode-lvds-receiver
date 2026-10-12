#include "drv_gpio.h"
#include "board_pins.h"
#include "driver/gpio.h"

/* Open-drain "release or pull low" helper: level 1 = released (the board's
 * pull-up supplies the high), level 0 = driven low. The first call switches
 * the pin from plain input to open-drain I/O, setting the level first so
 * there is no glitch. */
static void od_set(int pin, int level)
{
    gpio_set_level(pin, level);
    gpio_set_direction(pin, GPIO_MODE_INPUT_OUTPUT_OD);
}

void drv_gpio_init(void)
{
    gpio_config_t in = {
        .pin_bit_mask = (1ULL << BOARD_PIN_SHDN_N) | (1ULL << BOARD_PIN_TIA_CTRL),
        .mode = GPIO_MODE_INPUT,
    };
    gpio_config(&in);

    gpio_set_level(BOARD_PIN_LED, 0);
    gpio_config_t out = {
        .pin_bit_mask = (1ULL << BOARD_PIN_LED),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&out);

    /* DAC_LDAC (IO6): output held HIGH. With LDAC = 1 and UDAC = 0 each
     * MCP4728 write updates only its own channel at the data ACK (DS22187E
     * Table 4-5 p.26); mcp4728 writes no longer pulse it (review finding 10). */
    gpio_set_level(BOARD_PIN_DAC_LDAC, 1);
    gpio_config_t ld = {
        .pin_bit_mask = 1ULL << BOARD_PIN_DAC_LDAC,
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&ld);

    drv_gpio_aux_set_hiz();
}

void drv_gpio_tia_set(bool is_20k) { od_set(BOARD_PIN_TIA_CTRL, is_20k ? 1 : 0); }
bool drv_gpio_tia_get(void) { return gpio_get_level(BOARD_PIN_TIA_CTRL) != 0; }

void drv_gpio_comp_enable(bool on) { od_set(BOARD_PIN_SHDN_N, on ? 1 : 0); }
bool drv_gpio_comp_enabled(void) { return gpio_get_level(BOARD_PIN_SHDN_N) != 0; }

void drv_gpio_led_set(bool on) { gpio_set_level(BOARD_PIN_LED, on ? 1 : 0); }

void drv_gpio_aux_set_hiz(void)
{
    gpio_config_t c = { .pin_bit_mask = 1ULL << BOARD_PIN_AUX, .mode = GPIO_MODE_INPUT };
    gpio_config(&c);
}

void drv_gpio_aux_set(bool level)
{
    gpio_set_level(BOARD_PIN_AUX, level ? 1 : 0);
    gpio_set_direction(BOARD_PIN_AUX, GPIO_MODE_INPUT_OUTPUT);
}

bool drv_gpio_aux_read(void) { return gpio_get_level(BOARD_PIN_AUX) != 0; }

bool drv_gpio_hv_dis_read(void) { return gpio_get_level(BOARD_PIN_HV_DIS) != 0; }

void drv_gpio_hv_dis_write(bool disabled)
{
    gpio_set_level(BOARD_PIN_HV_DIS, disabled ? 1 : 0);
    gpio_set_direction(BOARD_PIN_HV_DIS, GPIO_MODE_INPUT_OUTPUT);
}
