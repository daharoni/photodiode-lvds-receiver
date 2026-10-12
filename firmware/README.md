# Firmware

Planned contents:

- `ecp5/`: gateware for the ECP5 FPGA (ULX3S first): LVDS input, clock recovery, 8b/10b decode, framing, redundant-lane merge, independent-clock watchdog for the comparator SHDN_N/LE_HYS control.
- `esp32/`: ESP32-C6 module controller (decision 11): slow range trim, monitors, HV gating, identity, CAN link and USB console. The headstage 8b/10b transmit test code (location TBD).

Location: both live in this repository (Daniel, 2026-10-12: keep the gateware here for now; a move to a system-level repository would carry `ecp5/` across with `git subtree split`). The ECP5 gateware spec, skeleton and simulation tests are in `ecp5/` (`ecp5/README.md`); the line protocol it defines is the contract for the headstage transmitter, and its Python golden model in `ecp5/model/` is the test oracle the headstage firmware should reuse. Nothing has run on an FPGA.

ESP32-C6 module controller: the firmware plan is in `esp32/README.md` (boot and safe defaults, range-trim state machine, self-test, USB workflow); the command and telemetry protocol (CAN and USB console) is in `../docs/firmware/can-and-console-protocol.md`; USB flashing and browser tooling facts are in `../docs/research/esp32-usb-tooling.md`. An ESP-IDF project skeleton now exists in `esp32/` (not run on hardware).
