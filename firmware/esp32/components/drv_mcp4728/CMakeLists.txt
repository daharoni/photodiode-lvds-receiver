idf_component_register(SRCS "drv_mcp4728.c"
                       INCLUDE_DIRS "include"
                       REQUIRES board app_safety esp_driver_gpio esp_driver_i2c esp_timer
                       PRIV_REQUIRES freertos log esp_rom)
