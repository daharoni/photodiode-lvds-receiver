# ESP32-C6 firmware on the lab HIL bench

Labels: VERIFIED (cited), PROPOSED (design intent), UNRESOLVED (open). Written 2026-10-12. No bench for this module exists yet; nothing in this file has been run on hardware. Companion documents: `README.md` (firmware plan), `docs/firmware/can-and-console-protocol.md` (console commands and the self-test JSON), the lab bench controller `Aharoni-Lab/hil-bench-controller` (README, `docs/esp32-targets.md`, `examples/firmware-ci.yml`).

## 1. What the bench is for

The lab's HIL (hardware-in-the-loop) bench is a Raspberry Pi 5 running `benchctl` as a self-hosted GitHub Actions runner. For this module it flashes every firmware build over the module's own USB-C port, watches the console, checks the HV-disable line with a Pi GPIO and runs the built-in self-test. The goal is that every push that touches `firmware/esp32/` is proven on a real module to still (a) boot with the APD bias OFF, (b) talk to the DAC and ADC, (c) pass the quick self-test, before anyone flashes it in the lab. PROPOSED.

## 2. Bench hardware (PROPOSED)

| Bench item | Connects to | Note |
|---|---|---|
| Pi 5 USB-A port, through a USB-C cable | module J50 (the single 24-pin USB-C receptacle) | Flash and console share the chip's USB Serial/JTAG CDC port (`docs/research/esp32-usb-tooling.md` s.2, VERIFIED there). The module is powered from this port through the eFuse; a laptop-class source is all it gets, as in the field |
| USB power switching | between the Pi and the module | `benchctl` has a `power: relay` option; alternatively a hub with per-port power control. Needed so a build that disables the USB PHY (tooling doc s.2 row 10) can be recovered by a power cycle plus BOOT held low |
| Pi GPIO (open-drain drive: output-low or input, never output-high) | TP60 (EN) | `reset` pin in the bench config. EN has R190 10 k + C190 1 uF on the module (`docs/schematic/controller.md`), so the Pi only ever pulls it low |
| Pi GPIO (open-drain drive) | TP61 (BOOT, IO9) | `boot` pin. Held low across an EN pulse forces download mode (MINI-1 datasheet Table 4-3 p.13, VERIFIED in controller.md); used only for recovery, esptool normally resets into download mode over USB |
| Pi GPIO input | J1 pin 1 (the HV_DIS gate node, after R34 1 k; Power sheet) | `hv_dis` pin. HIGH = APD bias supply OFF. The Pi reads it; it must never drive it, and J1 (HV FORCE ON) must never be fitted on a bench module |
| nothing | APD | Not fitted on the bench module. The HV self-test step verifies the supply at HV_MON, which is independent of the APD (README s.8 step 9) |

The Pi and the module are both 3.3 V logic; no level shifting. Grounds are shared through the USB cable; the Pi GPIO wires share that ground, so keep them short. UNRESOLVED: whether the Pi's USB port current limit (nominally 500 mA per port on the Pi 5 with the 5 A supply; not verified here) is compatible with the module's eFuse start-up current (README s.9: about 110-130 mA before enumeration, estimate).

## 3. CI flow

`.github/workflows/esp32-firmware.yml` (receiver repo): the `build` job compiles with the official ESP-IDF container, runs the host unit tests under `test_host/`, and uploads the merged flash image. The `hil-test` job runs only when the repository variable `HIL_ESP32C6_BENCH` is `true`, on a runner labelled `self-hosted, hil, esp32c6`, one job at a time (concurrency group). Its steps, in order:

1. `benchctl health --check config --check probe`
2. `benchctl flash --firmware receiver-esp32c6-merged.bin --target esp32c6_receiver` (esptool over the CDC port, `usb-reset` strategy, merged image at 0x0; the port re-enumerates after the hard reset and benchctl waits for it)
3. `benchctl serial expect --pattern "BOOT OK" --timeout 20`: the firmware prints `BOOT OK fw=<version>` once after boot step 8 with HV still off, whatever faults are latched (README s.4)
4. `benchctl gpio get --pin hv_dis --expect high`: HV is off after boot. This is the one check that must never be made optional
5. `benchctl serial send "selftest quick"` then `benchctl serial expect --pattern '"pass":true' --timeout 60`

Target name, pins and the esptool probe type are in the bench config example in the HIL repo (`configs/bench-config.example.yaml`, target `esp32c6_receiver`). PROPOSED until a bench exists.

## 4. What the bench proves, and what it cannot

Proven by `selftest quick` (README s.8 steps 1-8): identity, I2C bus, MCP4728 EEPROM defaults, DAC write/readback and the VTH_MON shift, ADC windows with HV off, the GPIO pull-ups, CAN loopback through the transceiver (UNRESOLVED: loopback through an unterminated SN65HVD230 needs a first bench check), die temperature.

Proven by `selftest full` (adds step 9): the LT8365 bias supply comes up at DAC_HV 0xFFF and settles within 95-115 V (`hv_floor_v`, PROPOSED window, UNRESOLVED until measured), the 60-code slope is 10-30 V per V, the step's 120 V absolute cap is enforced by the HV gate machine, and the bias decays after HV_DIS goes high. Run `full` in CI only after the HV safety rules for the bench are settled (200 V creepage/clearance on the module is a design rule; the bench module sits in an enclosure or on standoffs with the HV area untouched): Daniel decides. Default in CI: `quick`.

Not provable on this bench: anything optical (eye, BER, RSSI versus light), the comparator and LVDS output, the range-trim loop against a real link (needs the FPGA CAN master and a modulated light source), the USB-C source classification with real hosts (G1 item in `docs/bringup/gates.md`). The console `cc_class`/`usb_host` fields are logged only.

## 5. Later stages (PROPOSED, not started)

- **CAN master emulation**: a CAN interface on the Pi (an MCP2515 HAT or a USB CAN adapter) with a small script that sends LINK_ALL at 20 Hz with a scripted `link_valid`/error-class pattern, so the range state machine can be driven through SEARCH/TRACK/LOS in bus mode on the bench without an FPGA. Needs a `can` capability in `benchctl` (not in the HIL controller today).
- **Fault injection**: the Pi pulls EN during a self-test, or the relay drops USB power mid-ramp, and the next boot's reset reason and fault bits are checked over the console (README s.5, s.11).
- **Optical stage**: an LED driven by the FPGA test pattern in front of the bench module turns this into a G2/G3 bench; out of scope for the firmware CI.

## 6. Gate mapping

Items in `docs/bringup/gates.md` that this bench covers once it exists: G1 "boot with a blank MCP4728 then provision" (manual, once per module), G1/G3 fault injection (stage 5), the clean-machine flash test (section 11 of README, by hand). The CI self-test is a regression guard, not a gate measurement; it never replaces the gate items that need instruments.
