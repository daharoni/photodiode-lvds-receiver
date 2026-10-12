# app_safety

Status: PROPOSED; compiles (ESP-IDF v5.5.5, esp32c6, 2026-10-12, built against stand-in headers for the other agent's components); not run on hardware.

Fault word (`fault.h`), the pure-C HV gate machine `hv_gate.h/.c` (states OFF, ARMING, RAMP_UP, ON, RAMP_DOWN, FAULT; host-tested in `test_host/test_hv_gate.c` against a plant model only), the wrapper `app_safety.c` (inputs, one spinlock-protected HV_DIS writer that copies the machine's level, the `hv_exec` DAC executor, task watchdog check-in, `hv_auto` poll). Status (2026-10-12): review findings 2, 4, 5 (per-request cap), 6, 7, 9, 16 implemented; logic host-tested, wrapper compiled only, nothing run on hardware. `faults clear` re-proves the DAC (`app_safety_reverify_dac`) before it drops I2C_DAC / DAC_EEPROM; FAULT_I2C_ADC still stays until reboot once the ADC flag is false (no ADC re-verify yet). Thresholds not in the plan are named constants in `hv_gate.h` marked UNRESOLVED.
