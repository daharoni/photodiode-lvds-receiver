#pragma once
#include <stdbool.h>

/** Configure the GPIOs for boot (README s.4 step 1). SHDN_N and TIA_CTRL are
 *  left as plain inputs so the hardware pull-ups give comparator on and 20k.
 *  LED is an output (off). AUX is high-Z. DAC_LDAC (IO6) is an output held
 *  high (UDAC = 0 writes update their own channel). DAC_RDY belongs to
 *  drv_mcp4728 (mcp4728_init configures it). HV_DIS is NOT touched here
 *  (app_safety owns it). */
void drv_gpio_init(void);

/** TIA gain: true = 20k (pin released, pull-up), false = 5k (pin driven low,
 *  open-drain). */
void drv_gpio_tia_set(bool is_20k);
/** Current TIA pin level: true = 20k. */
bool drv_gpio_tia_get(void);

/** Comparator: true = on (SHDN_N released, pull-up), false = shutdown (driven
 *  low). Shutdown is not a guaranteed zero output (standing correction 11). */
void drv_gpio_comp_enable(bool on);
bool drv_gpio_comp_enabled(void);

void drv_gpio_led_set(bool on);

/** AUX (IO7): high impedance (default) or driven. */
void drv_gpio_aux_set_hiz(void);
void drv_gpio_aux_set(bool level);
/** Read the AUX pin level (for aux_in telemetry). */
bool drv_gpio_aux_read(void);

/** Read HV_DIS pad: true = high = HV disabled. */
bool drv_gpio_hv_dis_read(void);

/** SAFETY ONLY: write HV_DIS (true = disabled = pin high). Only app_safety
 *  may call this; nothing else in the firmware writes IO0. */
void drv_gpio_hv_dis_write(bool disabled);
