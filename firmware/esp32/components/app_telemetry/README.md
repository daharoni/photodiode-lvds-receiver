# app_telemetry

Status: PROPOSED; compiles (ESP-IDF v5.5.5, esp32c6, 2026-10-12, built against stand-in headers for the other agent's components); not run on hardware.

CAN TLM_ANALOG/STATE/SLOW frames (only in bus mode), NDJSON stream and `status -j` line, 64-entry event ring, LED patterns, identify. dac_hv, can_tec/can_rec and selftest_last are not available from the contracts and are null or fixed (see source comments).
