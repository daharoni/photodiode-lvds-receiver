/* ESP32-C6 module controller: boot sequence only (README s.4, steps 1-8).
 * Status: PROPOSED; see firmware/esp32/README.md s.0. Not run on hardware.
 * The radio is never initialised (decision 11). */
#include <stdio.h>
#include <string.h>
#include "app_range.h"
#include "app_safety.h"
#include "app_telemetry.h"
#include "board_i2c.h"
#include "board_pins.h"
#include "can_link.h"
#include "console.h"
#include "drv_ads1115.h"
#include "drv_gpio.h"
#include "drv_mcp4728.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/usb_serial_jtag.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "params.h"
#include "params_bind.h"
#include "sense.h"

static const char *TAG = "boot";

/* ---- constants ----------------------------------------------------------- */
#define ADS_GND_TOL_MV        5      /* README s.4 step 6: AIN3 = 0 V +- 5 mV */
#define HV_STUCK_BOOT_V       30.0f  /* README s.4 step 6: bias above 30 V while disabled */
#define LINK_ALL_LISTEN_MS    1500   /* README s.4 step 7: 1.5 s or longer */
#define LISTEN_POLL_MS        20     /* PROPOSED poll step */
#define CC_AGREE_READS        3      /* README s.4 step 7: three agreeing reads */
#define CC_READ_SPACING_MS    25     /* README s.4 step 7: more than tRpValueChange 10-20 ms */
#define CC_MAX_TRIES          10     /* UNRESOLVED: give up after this many reads */
#define CC_ADC_ATTEN          ADC_ATTEN_DB_6  /* README s.1 / controller.md: "ATTEN2" 0-1.9 V range. The
                                                 orchestrator brief said 11 dB; the schematic doc says ATTEN2
                                                 (= DB_6 in IDF 5.5). Conflict flagged in the report. */
#define CC_DIVIDER            2.0f   /* 100 k + 100 k tap (README s.1), CC pin = reading x 2 */

/* Class thresholds at the CC pin, in mV. UNRESOLVED: USB Type-C R2.0 Table
 * 4-25/4-36 was not available while writing this. The values below are
 * recalled, NOT verified against the spec; the raw mV is always logged so the
 * classification can be corrected without re-measuring. Class is a hint only. */
#define CC_MV_NONE_MAX        200    /* UNRESOLVED: below = no Rp */
#define CC_MV_DEFAULT_MAX     660    /* UNRESOLVED: Default USB Rp upper edge */
#define CC_MV_1A5_MAX         1230   /* UNRESOLVED: 1.5 A upper edge */
#define CC_MV_3A0_MAX         2180   /* UNRESOLVED: 3.0 A upper edge */

static bool s_dac_present, s_adc_present, s_dac_ok, s_adc_ok;
static const char *s_cc_class = "none", *s_cc_orient = "none", *s_src = "unknown";
static adc_oneshot_unit_handle_t s_adc1;

/* ---- step 1 ---------------------------------------------------------------- */
/* HV_DIS = 1 then output; SHDN_N and TIA_CTRL stay inputs; reset reason latched.
 * The task watchdog is started by ESP-IDF from sdkconfig (CONFIG_ESP_TASK_WDT_INIT);
 * the safety task subscribes itself in app_safety_start(). */
static void boot_step_safety(void)
{
    app_safety_init();
    drv_gpio_init();
}

/* ---- step 2 ---------------------------------------------------------------- */
static void boot_step_params(void)
{
    esp_err_t e = params_init();
    if (e != ESP_OK) {
        ESP_LOGW(TAG, "params: %s (defaults used, FAULT_NVS latched)", esp_err_to_name(e));
    }
    params_bind_init();
}

/* ---- step 3 ---------------------------------------------------------------- */
static void boot_step_i2c(void)
{
    if (board_i2c_bus_recover() != ESP_OK) {
        ESP_LOGW(TAG, "I2C SDA stuck low after recovery");
    }
    if (board_i2c_init() != ESP_OK) {
        fault_set(FAULT_I2C_DAC | FAULT_I2C_ADC);
        return;
    }
    s_dac_present = board_i2c_probe(BOARD_I2C_ADDR_MCP4728);
    s_adc_present = board_i2c_probe(BOARD_I2C_ADDR_ADS1115);
    if (!s_dac_present) fault_set(FAULT_I2C_DAC);
    if (!s_adc_present) fault_set(FAULT_I2C_ADC);
}

/* ---- step 4 ---------------------------------------------------------------- */
/* Read command, compare the EEPROM against the required defaults (channel C
 * VREF = VDD, PD 00, 0xFFF; channel B VREF = VDD, PD 00, 0x800; A and D
 * normal): mcp4728_eeprom_defaults_ok() does the comparison. */
static bool s_dac_eeprom_ok;
static void boot_step_dac_verify(void)
{
    if (!s_dac_present) {
        return;
    }
    if (mcp4728_init() != ESP_OK) {
        fault_set(FAULT_I2C_DAC);
        return;
    }
    mcp4728_regs_t r;
    if (mcp4728_read_all(&r) != ESP_OK) {
        fault_set(FAULT_I2C_DAC);
        return;
    }
    s_dac_eeprom_ok = mcp4728_eeprom_defaults_ok(&r);
    if (!s_dac_eeprom_ok) {
        fault_set(FAULT_DAC_EEPROM);
        ESP_LOGW(TAG, "DAC EEPROM defaults wrong: use `dac provision confirm`");
    }
}

/* ---- step 5 ---------------------------------------------------------------- */
static void boot_step_dac_safe(void)
{
    if (!s_dac_present || (fault_get() & FAULT_I2C_DAC)) {
        return;
    }
    int32_t th = 0;
    params_get_i32(PARAM_TH, &th);
    uint16_t th_code = params_th_to_code(th);
    if (mcp4728_write_volatile(BOARD_DAC_CH_HV, BOARD_DAC_HV_SAFE_CODE) != ESP_OK ||
        mcp4728_write_volatile(BOARD_DAC_CH_TH, th_code) != ESP_OK) {
        fault_set(FAULT_I2C_DAC);
        return;
    }
    /* Readback of the input registers against the written codes (Read command). */
    if (mcp4728_readback_verify(BOARD_DAC_CH_HV, BOARD_DAC_HV_SAFE_CODE) != ESP_OK ||
        mcp4728_readback_verify(BOARD_DAC_CH_TH, th_code) != ESP_OK) {
        fault_set(FAULT_I2C_DAC);
        return;
    }
    s_dac_ok = s_dac_eeprom_ok;   /* verified only if the EEPROM check also passed */
}

/* ---- step 6 ---------------------------------------------------------------- */
static void boot_step_adc_check(void)
{
    if (!s_adc_present) {
        return;
    }
    int32_t gnd = 0, hv = 0;
    if (ads1115_init() != ESP_OK || ads1115_read_mv(BOARD_ADC_AIN_GND, &gnd) != ESP_OK ||
        ads1115_read_mv(BOARD_ADC_AIN_HV_MON, &hv) != ESP_OK) {
        fault_set(FAULT_I2C_ADC);
        return;
    }
    float bias = hv * 0.001f * BOARD_HV_MON_DIVIDER;
    ESP_LOGW(TAG, "AIN3 %ld mV, bias %.1f V", (long)gnd, (double)bias);
    if (gnd > ADS_GND_TOL_MV || gnd < -ADS_GND_TOL_MV) {
        fault_set(FAULT_I2C_ADC);   /* PROPOSED: an ADC that cannot read ground is not trusted */
        return;
    }
    if (bias > HV_STUCK_BOOT_V) {
        fault_set(FAULT_HV_STUCK);  /* something forces HV (e.g. jumper J1); report, do not compensate */
    }
    s_adc_ok = true;
}

/* ---- step 7 ---------------------------------------------------------------- */
static int cc_read_mv(adc_channel_t ch)
{
    int raw = 0;
    if (adc_oneshot_read(s_adc1, ch, &raw) != ESP_OK) {
        return -1;
    }
    /* Uncalibrated conversion: 12-bit, full scale per attenuation. PROPOSED
     * rough scale: the ATTEN2 range is 0-1.9 V (controller.md). No curve
     * fitting calibration is applied; UNRESOLVED (the schematic doc quotes
     * +-23 mV only after calibration). */
    return (int)(raw * 1900 / 4095);
}

static const char *cc_classify(int cc_pin_mv)
{
    if (cc_pin_mv < CC_MV_NONE_MAX) return "none";
    if (cc_pin_mv < CC_MV_DEFAULT_MAX) return "default";
    if (cc_pin_mv < CC_MV_1A5_MAX) return "1.5A";
    if (cc_pin_mv < CC_MV_3A0_MAX) return "3.0A";
    return "none";
}

static void read_cc(void)
{
    adc_oneshot_unit_init_cfg_t uc = {.unit_id = ADC_UNIT_1};
    adc_oneshot_chan_cfg_t cc = {.atten = CC_ADC_ATTEN, .bitwidth = ADC_BITWIDTH_DEFAULT};
    if (adc_oneshot_new_unit(&uc, &s_adc1) != ESP_OK ||
        adc_oneshot_config_channel(s_adc1, ADC_CHANNEL_4, &cc) != ESP_OK ||
        adc_oneshot_config_channel(s_adc1, ADC_CHANNEL_5, &cc) != ESP_OK) {
        ESP_LOGW(TAG, "CC ADC init failed");
        return;
    }
    const char *last_c1 = NULL, *last_c2 = NULL;
    int agree = 0, mv1 = 0, mv2 = 0;
    for (int i = 0; i < CC_MAX_TRIES && agree < CC_AGREE_READS; i++) {
        mv1 = cc_read_mv(ADC_CHANNEL_4);
        mv2 = cc_read_mv(ADC_CHANNEL_5);
        if (mv1 < 0 || mv2 < 0) {
            break;
        }
        const char *c1 = cc_classify((int)(mv1 * CC_DIVIDER)), *c2 = cc_classify((int)(mv2 * CC_DIVIDER));
        agree = (last_c1 == c1 && last_c2 == c2) ? agree + 1 : 1;
        last_c1 = c1; last_c2 = c2;
        vTaskDelay(pdMS_TO_TICKS(CC_READ_SPACING_MS));
    }
    ESP_LOGW(TAG, "CC raw: CC1 %d mV CC2 %d mV (at ADC pin), agree=%d", mv1, mv2, agree);
    if (agree >= CC_AGREE_READS) {
        bool a1 = strcmp(last_c1, "none") != 0, a2 = strcmp(last_c2, "none") != 0;
        if (a1 && !a2) { s_cc_class = last_c1; s_cc_orient = "cc1"; }
        else if (a2 && !a1) { s_cc_class = last_c2; s_cc_orient = "cc2"; }
        /* both or neither: leave "none" (hint only) */
    }
    adc_oneshot_del_unit(s_adc1);
    s_adc1 = NULL;
}

static bool s_bus_mode;
static void boot_step_source_and_can(void)
{
    read_cc();
    /* Start the link in listen-only (TX silent) and listen for LINK_ALL for
     * 1.5 s; a lone module on a laptop never transmits into the host's SS
     * receive pair (README s.4 step 7). */
    if (can_link_start() != ESP_OK) {
        ESP_LOGW(TAG, "CAN link failed to start");
    }
    bool master = false;
    for (int t = 0; t < LINK_ALL_LISTEN_MS && !master; t += LISTEN_POLL_MS) {
        vTaskDelay(pdMS_TO_TICKS(LISTEN_POLL_MS));
        master = can_link_master_seen();
    }
    bool sof = usb_serial_jtag_is_connected();   /* USB host present (SOF seen); TRM s.32.5 p.1035 */
    /* Mode table (README s.4 step 7, PROPOSED): LINK_ALL -> bus; else usb. */
    s_bus_mode = master;
    s_src = master ? "system" : (sof ? "host" : "unknown");
    app_telemetry_set_source(s_src, s_cc_class, s_cc_orient);
    if (!master && !sof && strcmp(s_cc_class, "none") == 0) {
        ESP_LOGW(TAG, "no master, no USB host, no Rp: usb mode with a warning");
    }
}

/* ---- step 8 and start ----------------------------------------------------- */
void app_main(void)
{
    boot_step_safety();
    boot_step_params();
    boot_step_i2c();
    boot_step_dac_verify();
    boot_step_dac_safe();
    boot_step_adc_check();
    boot_step_source_and_can();

    app_safety_set_dac_verified(s_dac_ok);
    app_safety_set_adc_ok(s_adc_ok);

    /* Step 8: HV is still off here, whatever faults are latched. */
    printf("BOOT OK fw=%s\n", esp_app_get_description()->version);
    printf("{\"ev\":\"boot\",\"reset\":\"%s\",\"faults\":\"0x%04x\",\"mode\":\"%s\"}\n",
           app_safety_reset_reason_name(), (unsigned)fault_get(), s_bus_mode ? "bus" : "usb");

    if (s_adc_ok) {
        sense_start();
    }
    app_range_start();
    app_safety_start();
    app_telemetry_start();
    console_start();

    /* Step 8(c): NVS flag hv_auto with a heard master and no latched faults
     * (default 0 for the first boards; Daniel decides). */
    int32_t hv_auto = 0;
    params_get_i32(PARAM_HV_AUTO, &hv_auto);
    if (hv_auto && s_bus_mode && fault_get() == 0) {
        app_safety_hv_request(true);
    }
}
