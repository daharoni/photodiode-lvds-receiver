# board

Status: PROPOSED; compiles (ESP-IDF v5.5.5, esp32c6, 2026-10-12, built against stand-in headers for the other agent's components); not run on hardware.

Pin map (`board_pins.h`, README s.1), I2C master bus and mutex, bus recovery and probe (`board_i2c.h`). The drivers take the bus mutex themselves; callers must not hold it.
