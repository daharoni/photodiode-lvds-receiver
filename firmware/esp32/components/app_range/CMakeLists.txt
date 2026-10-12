idf_component_register(SRCS "range_fsm.c" "range_m_est.c" "app_range.c"
                       INCLUDE_DIRS "include"
                       REQUIRES
                       PRIV_REQUIRES sense can_link drv_gpio drv_mcp4728 app_safety app_telemetry params board
                                     freertos log esp_timer)
