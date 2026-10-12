idf_component_register(SRCS "sense.c"
                       INCLUDE_DIRS "include"
                       REQUIRES drv_ads1115 board
                       PRIV_REQUIRES app_safety drv_gpio params freertos log esp_timer)
