# app_safety

Status: PROPOSED; compiles (ESP-IDF v5.5.5, esp32c6, 2026-10-12, built against stand-in headers for the other agent's components); not run on hardware.

Fault word (`fault.h`), HV gate state machine, task watchdog check-in, HV ramp task (DAC walk, README s.4 steps 9-10). HV_DIS is only ever written in one spinlock-protected function. Thresholds not in the plan are named constants marked UNRESOLVED in `app_safety.c`. Limitation: after an I2C or DAC EEPROM fault HV stays refused until reboot.
