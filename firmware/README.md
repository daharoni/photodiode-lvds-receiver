# Firmware

Planned contents:

- `ecp5/`: gateware for the ECP5 FPGA (ULX3S first): LVDS input, clock recovery, 8b/10b decode, framing, redundant-lane merge, independent-clock watchdog for the comparator SHDN_N/LE_HYS control.
- `esp32/`: ESP32-C6 module controller (decision 11): slow range trim, monitors, HV gating, identity, CAN link and USB console. The headstage 8b/10b transmit test code (location TBD).

Location is undecided: this code may live here or move to a separate repository. Nothing is written yet.

ESP32-C6 module controller: the firmware plan is in `esp32/README.md` (boot and safe defaults, range-trim state machine, self-test, USB workflow); the command and telemetry protocol (CAN and USB console) is in `../docs/firmware/can-and-console-protocol.md`; USB flashing and browser tooling facts are in `../docs/research/esp32-usb-tooling.md`. Nothing is implemented yet.
