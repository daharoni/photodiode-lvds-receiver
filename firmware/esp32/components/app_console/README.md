# app_console

Status: PROPOSED; compiles (ESP-IDF v5.5.5, esp32c6, 2026-10-12, built against stand-in headers for the other agent's components); not run on hardware.

esp_console REPL over USB Serial/JTAG with the protocol s.4 commands. Named `app_console` because a component named `console` would shadow ESP-IDF's own `console` component; the header is still `console.h`. `cal` except `cal vbr` replies `err not-implemented` (no backend in the contracts).

`faults clear` now runs the DAC re-verify and prints `err dac-not-reverified` if the I2C_DAC / DAC_EEPROM bits cannot be dropped; `status` also shows `hv_gate` (fine gate state) and `print_drops` (2026-10-12; compiled only).
