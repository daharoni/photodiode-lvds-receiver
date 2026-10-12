idf_component_register(
    SRCS "params.c"
    INCLUDE_DIRS "include"
    REQUIRES nvs_flash esp_rom app_safety esp_app_format esp_timer log)
