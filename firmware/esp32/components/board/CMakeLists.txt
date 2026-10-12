idf_component_register(
    SRCS "board_i2c.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_driver_i2c esp_driver_gpio freertos esp_rom log)
