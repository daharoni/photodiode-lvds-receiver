idf_component_register(SRCS "app_selftest.c"
                       INCLUDE_DIRS "include"
                       REQUIRES
                       PRIV_REQUIRES board app_safety app_range app_telemetry can_link drv_ads1115 drv_gpio
                                     drv_mcp4728 params sense esp_driver_gpio esp_hw_support esp_timer freertos log)
