idf_component_register(
    SRCS "fault.c" "app_safety.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_driver_gpio
    PRIV_REQUIRES drv_gpio board params sense can_link drv_mcp4728 esp_system esp_timer
                  esp_driver_gpio freertos log)
