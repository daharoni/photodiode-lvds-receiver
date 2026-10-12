# params

Status: PROPOSED; compiles (ESP-IDF v5.5.5, esp32c6, 2026-10-12, built against stand-in headers for the other agent's components); not run on hardware.

Table-driven parameter registry (protocol doc s.2), NVS namespaces `factory`, `user`, `state` with CRC32 per blob, live getters and action hooks registered by `main/params_bind.c`.
