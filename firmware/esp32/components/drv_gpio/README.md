# drv_gpio

Status: PROPOSED; compiles (ESP-IDF v5.5.5, esp32c6, 2026-10-12, built against stand-in headers for the other agent's components); not run on hardware.

DAC_LDAC (IO6, output held high since 2026-10-12), SHDN_N, TIA_CTRL (open-drain release or pull low, boot state is plain input), LED, AUX, HV_DIS read. `drv_gpio_hv_dis_write` is for app_safety only.
