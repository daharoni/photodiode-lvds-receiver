idf_component_register(
    SRCS "app_telemetry.c"
    INCLUDE_DIRS "include"
    REQUIRES
    PRIV_REQUIRES params app_safety drv_gpio board sense can_link app_range app_selftest
                  esp_timer esp_driver_usb_serial_jtag esp_app_format esp_hw_support freertos log)
