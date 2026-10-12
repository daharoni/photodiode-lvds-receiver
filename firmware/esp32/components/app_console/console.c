#include "console.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "app_range.h"
#include "app_safety.h"
#include "app_selftest.h"
#include "app_telemetry.h"
#include "board_pins.h"
#include "can_link.h"
#include "drv_gpio.h"
#include "drv_mcp4728.h"
#include "esp_app_desc.h"
#include "esp_console.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "params.h"
#include "sense.h"

#define CONSOLE_TASK_PRIO  3     /* README s.3 */
#define CONSOLE_STACK      8192  /* UNRESOLVED: first guess */
#define STREAM_DEFAULT_MS  100   /* protocol s.4 */

static const char *err_text(esp_err_t e)
{
    switch (e) {
    case ESP_ERR_NOT_FOUND: return "unknown";
    case ESP_ERR_NOT_ALLOWED: return "read-only";
    case ESP_ERR_INVALID_ARG: return "range";
    case ESP_ERR_INVALID_STATE: return "refused";
    case PARAMS_ERR_LOCKED: return "locked";
    case PARAMS_ERR_BUSY: return "busy";
    case ESP_ERR_NOT_SUPPORTED: return "not-implemented";
    default: return esp_err_to_name(e);
    }
}

static int done(esp_err_t e, const char *okmsg)
{
    if (e == ESP_OK) {
        printf("ok %s\n", okmsg ? okmsg : "");
        return 0;
    }
    printf("err %s\n", err_text(e));
    return 0;
}

static int usage(const char *u)
{
    printf("err usage: %s\n", u);
    return 0;
}

static int set_param(const char *name, const char *arg)
{
    char *end;
    float v = strtof(arg, &end);
    if (end == arg || *end) {
        printf("err not-a-number\n");
        return 0;
    }
    esp_err_t e = params_set_by_name(name, v);
    if (e != ESP_OK) {
        return done(e, NULL);
    }
    float rb = 0;
    params_get_by_name(name, &rb);
    char msg[48];
    snprintf(msg, sizeof(msg), "%s=%g", name, (double)rb);
    return done(ESP_OK, msg);
}

static int set_i32(uint16_t id, int32_t v) { return done(params_set_i32(id, v), NULL); }

/* ---- commands ----------------------------------------------------------- */
static int cmd_version(int argc, char **argv)
{
    (void)argc; (void)argv;
    printf("ok fw=%s\n", esp_app_get_description()->version);
    return 0;
}

static void print_params(void)
{
    char buf[32];
    for (int i = 0; params_at(i); i++) {
        const param_desc_t *d = params_at(i);
        int32_t v;
        if (!(d->access & PARAM_R) || params_get_i32(d->id, &v) != ESP_OK) {
            continue;
        }
        params_format(d, v, buf, sizeof(buf));
        printf("%-12s %s %s\n", d->name, buf, d->unit);
    }
}

static int cmd_status(int argc, char **argv)
{
    if (argc > 1 && strcmp(argv[1], "-j") == 0) {
        static char line[640];
        app_telemetry_status_json(line, sizeof(line));
        printf("%s\n", line);
        return 0;
    }
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_EFUSE_FACTORY);
    printf("mac          %02x:%02x:%02x:%02x:%02x:%02x\n", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    printf("loop_state   %s\n", app_range_state_name());
    printf("mode         %s\n", can_link_mode() == CAN_MODE_BUS ? "bus" : "usb");
    printf("reset        %s\n", app_safety_reset_reason_name());
    printf("hv_gate      %s\n", app_safety_gate_state_name());
    printf("print_drops  %lu\n", (unsigned long)app_telemetry_print_drops());
    print_params();
    app_telemetry_events_print();
    printf("ok\n");
    return 0;
}

static int cmd_hv(int argc, char **argv)
{
    if (argc < 2) return usage("hv on|off|set <V>|limits <min> <max>");
    if (strcmp(argv[1], "on") == 0) {
        if (app_selftest_running()) {
            printf("err selftest-running\n");
            return 0;
        }
        return done(app_safety_hv_request(true), "hv ramp started");
    }
    if (strcmp(argv[1], "off") == 0) {
        return done(app_safety_hv_request(false), "hv off ramp started");
    }
    if (strcmp(argv[1], "set") == 0 && argc == 3) return set_param("hv_set", argv[2]);
    if (strcmp(argv[1], "limits") == 0 && argc == 4) {
        float lo = strtof(argv[2], NULL), hi = strtof(argv[3], NULL);
        float cur_hi = 0;
        params_get_by_name("hv_max", &cur_hi);
        esp_err_t e;
        /* order matters: keep min <= max at every step */
        if (lo > cur_hi) {
            e = params_set_by_name("hv_max", hi);
            if (e == ESP_OK) e = params_set_by_name("hv_min", lo);
        } else {
            e = params_set_by_name("hv_min", lo);
            if (e == ESP_OK) e = params_set_by_name("hv_max", hi);
        }
        return done(e, NULL);
    }
    return usage("hv on|off|set <V>|limits <min> <max>");
}

static int cmd_dac(int argc, char **argv)
{
    if (argc < 2) return usage("dac hv <code>|show|provision [confirm]");
    if (strcmp(argv[1], "hv") == 0 && argc == 3) {
        return set_i32(PARAM_DAC_HV, (int32_t)strtol(argv[2], NULL, 0));
    }
    if (strcmp(argv[1], "show") == 0) {
        mcp4728_regs_t r;
        esp_err_t e = mcp4728_read_all(&r);
        if (e != ESP_OK) return done(e, NULL);
        /* Field layout belongs to drv_mcp4728; print the raw struct bytes. */
        printf("dac raw:");
        const uint8_t *p = (const uint8_t *)&r;
        for (size_t i = 0; i < sizeof(r); i++) printf(" %02x", p[i]);
        printf("\n");
        printf("ok eeprom_defaults_ok=%d\n", mcp4728_eeprom_defaults_ok(&r) ? 1 : 0);
        return 0;
    }
    if (strcmp(argv[1], "provision") == 0) {
        if (argc < 3 || strcmp(argv[2], "confirm") != 0) {
            printf("err needs: dac provision confirm\n");
            return 0;
        }
        if (app_safety_hv_enabled()) {
            printf("err refused hv-enabled\n");
            return 0;
        }
        esp_err_t e = mcp4728_write_eeprom_defaults();
        mcp4728_regs_t r;
        if (e == ESP_OK) e = mcp4728_read_all(&r);
        if (e == ESP_OK && !mcp4728_eeprom_defaults_ok(&r)) e = ESP_FAIL;
        return done(e, "provisioned; reboot to verify");
    }
    return usage("dac hv <code>|show|provision [confirm]");
}

static int cmd_tia(int argc, char **argv)
{
    if (argc != 2) return usage("tia 20k|5k|auto");
    if (strcmp(argv[1], "auto") == 0) return set_i32(PARAM_TIA_AUTO, 1);
    if (strcmp(argv[1], "20k") == 0) { params_set_i32(PARAM_TIA_AUTO, 0); return set_i32(PARAM_TIA, 1); }
    if (strcmp(argv[1], "5k") == 0) { params_set_i32(PARAM_TIA_AUTO, 0); return set_i32(PARAM_TIA, 0); }
    return usage("tia 20k|5k|auto");
}

static int cmd_th(int argc, char **argv)
{
    if (argc != 2) return usage("th <mV>");
    return set_param("th", argv[1]);
}

static int cmd_comp(int argc, char **argv)
{
    if (argc != 2) return usage("comp on|off");
    if (strcmp(argv[1], "on") == 0) return set_i32(PARAM_COMP_EN, 1);
    if (strcmp(argv[1], "off") == 0) return set_i32(PARAM_COMP_EN, 0);
    return usage("comp on|off");
}

static int cmd_loop(int argc, char **argv)
{
    if (argc != 2) return usage("loop auto|manual");
    if (strcmp(argv[1], "auto") == 0) return set_i32(PARAM_LOOP, 1);
    if (strcmp(argv[1], "manual") == 0) return set_i32(PARAM_LOOP, 0);
    return usage("loop auto|manual");
}

static int cmd_m(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "target") == 0) return set_param("m_target", argv[2]);
    return usage("m target <M>");
}

static int cmd_get(int argc, char **argv)
{
    if (argc != 2) return usage("get <name>");
    const param_desc_t *d = params_find(argv[1]);
    if (!d) return done(ESP_ERR_NOT_FOUND, NULL);
    int32_t v;
    esp_err_t e = params_get_i32(d->id, &v);
    if (e != ESP_OK) return done(e, NULL);
    char buf[32];
    params_format(d, v, buf, sizeof(buf));
    printf("ok %s=%s%s%s\n", d->name, buf, d->unit[0] ? " " : "", d->unit);
    return 0;
}

static int cmd_set(int argc, char **argv)
{
    if (argc != 3) return usage("set <name> <value>");
    const param_desc_t *d = params_find(argv[1]);
    if (!d) return done(ESP_ERR_NOT_FOUND, NULL);
    /* text values for enum-like parameters */
    if (d->type == PT_TIA) {
        if (strcmp(argv[2], "20k") == 0) return set_i32(d->id, 1);
        if (strcmp(argv[2], "5k") == 0) return set_i32(d->id, 0);
    }
    return set_param(argv[1], argv[2]);
}

static int cmd_stream(int argc, char **argv)
{
    if (argc < 2) return usage("stream on [ms]|off");
    if (strcmp(argv[1], "on") == 0) {
        uint32_t ms = argc > 2 ? (uint32_t)strtoul(argv[2], NULL, 0) : STREAM_DEFAULT_MS;
        app_telemetry_stream(true, ms);
        printf("ok stream on\n");
        return 0;
    }
    if (strcmp(argv[1], "off") == 0) {
        app_telemetry_stream(false, 0);
        printf("ok stream off\n");
        return 0;
    }
    return usage("stream on [ms]|off");
}

static int cmd_cal(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "vbr") == 0) return set_param("vbr", argv[2]);
    /* UNRESOLVED: cal vop / rssi-idle / sweep / clear have no backend in the
     * agreed contracts (app_range owns calibration, README s.6.4). */
    printf("err not-implemented\n");
    return 0;
}

static int cmd_save(int argc, char **argv)
{
    (void)argc; (void)argv;
    return done(params_save(), "saved");
}

static int cmd_defaults(int argc, char **argv)
{
    bool all = (argc > 1 && strcmp(argv[1], "all") == 0);
    return done(params_defaults(all), all ? "defaults all" : "defaults");
}

static int cmd_selftest(int argc, char **argv)
{
    bool full = !(argc > 1 && strcmp(argv[1], "quick") == 0);   /* full is the default (README s.8) */
    esp_err_t e = app_selftest_run(full);
    const char *j = app_selftest_last_json();
    if (j && j[0]) printf("%s\n", j);
    return done(e, "selftest done");
}

static int cmd_identify(int argc, char **argv)
{
    /* default duration: UNRESOLVED (protocol gives `[seconds u8]`, no default) */
    unsigned s = argc > 1 ? (unsigned)strtoul(argv[1], NULL, 0) : 10;
    app_telemetry_identify((uint8_t)(s > 255 ? 255 : s));
    return done(ESP_OK, "identify");
}

static int cmd_ident_set(const char *what, uint16_t id, int argc, char **argv)
{
    if (argc != 3 || strcmp(argv[1], "set") != 0) {
        printf("err usage: %s set <n>\n", what);
        return 0;
    }
    esp_err_t e = params_set_i32(id, (int32_t)strtol(argv[2], NULL, 0));
    if (e == ESP_OK) e = params_save();
    return done(e, NULL);
}
static int cmd_serial(int argc, char **argv) { return cmd_ident_set("serial", PARAM_SERIAL, argc, argv); }
static int cmd_rev(int argc, char **argv) { return cmd_ident_set("rev", PARAM_BOARD_REV, argc, argv); }
static int cmd_node(int argc, char **argv) { return cmd_ident_set("node", PARAM_NODE, argc, argv); }

static int cmd_can(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "stat") == 0) {
        static char buf[384];
        can_link_stats_json(buf, sizeof(buf));
        printf("%s\n", buf);
        printf("ok heartbeat_age_ms=%lu\n", (unsigned long)can_link_heartbeat_age_ms());
        return 0;
    }
    return usage("can stat");
}

static int cmd_faults(int argc, char **argv)
{
    if (argc > 1 && strcmp(argv[1], "clear") == 0) {
        esp_err_t ce = app_safety_faults_clear();
        if (ce != ESP_OK) {
            printf("err dac-not-reverified %s (I2C_DAC / DAC_EEPROM stay latched)\n", esp_err_to_name(ce));
        }
    }
    fault_word_t f = fault_get();
    printf("faults 0x%04x", (unsigned)f);
    for (int b = 0; b < 16; b++) {
        if (f & (1u << b)) printf(" %s", fault_name(b));
    }
    printf("\nok\n");
    return 0;
}

static int cmd_reboot(int argc, char **argv)
{
    (void)argc; (void)argv;
    app_safety_hv_off_now();   /* HV drops first (protocol s.2 reboot) */
    printf("ok rebooting\n");
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(100));
    esp_restart();
    return 0;
}

static const esp_console_cmd_t k_cmds[] = {
    {.command = "version", .help = "firmware version", .func = cmd_version},
    {.command = "status", .help = "status [-j]", .func = cmd_status},
    {.command = "hv", .help = "hv on|off|set <V>|limits <min> <max>", .func = cmd_hv},
    {.command = "dac", .help = "dac hv <code>|show|provision [confirm]", .func = cmd_dac},
    {.command = "tia", .help = "tia 20k|5k|auto", .func = cmd_tia},
    {.command = "th", .help = "th <mV offset>", .func = cmd_th},
    {.command = "comp", .help = "comp on|off", .func = cmd_comp},
    {.command = "loop", .help = "loop auto|manual", .func = cmd_loop},
    {.command = "m", .help = "m target <M>", .func = cmd_m},
    {.command = "get", .help = "get <name>", .func = cmd_get},
    {.command = "set", .help = "set <name> <value>", .func = cmd_set},
    {.command = "stream", .help = "stream on [ms]|off", .func = cmd_stream},
    {.command = "cal", .help = "cal vbr <V> (others not implemented)", .func = cmd_cal},
    {.command = "save", .help = "persist parameters", .func = cmd_save},
    {.command = "defaults", .help = "defaults [all]", .func = cmd_defaults},
    {.command = "selftest", .help = "selftest [quick|full]", .func = cmd_selftest},
    {.command = "identify", .help = "identify [seconds]", .func = cmd_identify},
    {.command = "serial", .help = "serial set <n> (write-once)", .func = cmd_serial},
    {.command = "rev", .help = "rev set <n> (write-once)", .func = cmd_rev},
    {.command = "node", .help = "node set <1..14>", .func = cmd_node},
    {.command = "can", .help = "can stat", .func = cmd_can},
    {.command = "faults", .help = "faults [clear]", .func = cmd_faults},
    {.command = "reboot", .help = "reset the module", .func = cmd_reboot},
};

void console_start(void)
{
    esp_console_repl_t *repl = NULL;
    esp_console_repl_config_t rc = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
    rc.prompt = "rx> ";
    rc.task_priority = CONSOLE_TASK_PRIO;
    rc.task_stack_size = CONSOLE_STACK;
    esp_console_dev_usb_serial_jtag_config_t dc = ESP_CONSOLE_DEV_USB_SERIAL_JTAG_CONFIG_DEFAULT();
    if (esp_console_new_repl_usb_serial_jtag(&dc, &rc, &repl) != ESP_OK) {
        ESP_LOGE("console", "REPL init failed");
        return;
    }
    esp_console_register_help_command();
    for (size_t i = 0; i < sizeof(k_cmds) / sizeof(k_cmds[0]); i++) {
        esp_console_cmd_register(&k_cmds[i]);
    }
    esp_console_start_repl(repl);
}
