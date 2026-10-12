idf_component_register(
    SRCS "app_main.c" "params_bind.c"
    INCLUDE_DIRS "."
    REQUIRES board app_safety params drv_gpio app_console app_telemetry
             drv_mcp4728 drv_ads1115 sense can_link app_range app_selftest
             nvs_flash esp_adc esp_driver_gpio esp_driver_tsens esp_system
             esp_app_format esp_timer esp_driver_usb_serial_jtag log freertos)
