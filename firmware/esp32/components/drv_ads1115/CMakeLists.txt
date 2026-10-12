idf_component_register(SRCS "drv_ads1115.c"
                       INCLUDE_DIRS "include"
                       REQUIRES board app_safety esp_driver_i2c
                       PRIV_REQUIRES freertos log)
