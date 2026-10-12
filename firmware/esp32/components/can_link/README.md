# can_link

Status: PROPOSED; compiled (ESP-IDF v5.5.5, 2026-10-12); `can_codec` host-tested (`test_host`, see the repo run record in the agent report); the TWAI wrapper is not host-tested and not run on hardware.

- `can_codec.h/.c`: pure C ID pack/unpack and payload codec for every frame of protocol s.1.
- `can_link.c`: TWAI node-based driver (`esp_driver_twai`: `twai_new_node_onchip`, `twai_node_*`, `twai_node_receive_from_isr`), API read from the installed v5.5.5 headers. Starts listen-only (README s.4 step 7); on the first LINK_ALL it re-creates the node with TX enabled and sends BOOT. GET/SET are answered through `params_get_i32/params_set_i32`; FAULT_EVENT on change and every 1 s while latched; ENUM and ASSIGN per s.1.2; IDENTIFY calls `app_telemetry_identify`.
- The TWAI TX queue holds pointers to frames, so TX frames come from a static slot pool released in `on_tx_done` (verified in `esp_twai_onchip.c`).
- A node with id 0 (unassigned) never transmits anything except ENUM announcements (never another node's ID, protocol s.1.1).
- Sets FAULT_CAN_BUSOFF on bus-off and calls `twai_node_recover`. FAULT_CAN_TIMEOUT is set by app_safety from `can_link_heartbeat_age_ms()` and cleared here when LINK_ALL is heard again (BUSOFF too, once the node is not bus-off). Broadcast SET of `hv_cmd` = 1 and `dac_hv` is ignored (protocol doc s.1.3, PROPOSED). Waits use `ticks_at_least_1()`.
- crc16 for ENUM slots is CRC-16/CCITT-FALSE: the protocol doc does not name a polynomial (PROPOSED choice).
- UNRESOLVED: sampling point is the driver default; hardware retry count 3 is a guess; ISR callbacks are IRAM_ATTR but `CONFIG_TWAI_ISR_CACHE_SAFE` is not enabled.
