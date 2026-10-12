idf_component_register(SRCS "can_codec.c" "can_link.c"
                       INCLUDE_DIRS "include"
                       REQUIRES esp_driver_twai
                       PRIV_REQUIRES board app_safety params app_telemetry esp_hw_support esp_timer
                                     esp_driver_gpio freertos log)
