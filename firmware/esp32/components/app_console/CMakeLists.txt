idf_component_register(
    SRCS "console.c"
    INCLUDE_DIRS "include"
    PRIV_REQUIRES console params app_safety drv_gpio board app_telemetry sense can_link app_range
                  app_selftest drv_mcp4728 esp_hw_support esp_system esp_app_format
                  esp_driver_usb_serial_jtag freertos log)
