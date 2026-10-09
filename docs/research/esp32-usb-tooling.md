# ESP32-C6 USB tooling: flash, console, debug and the browser workflow

Labels: VERIFIED (document and page/section cited), PROPOSED, UNRESOLVED. Checked 2026-10-09. Nothing here was run on a board: no hardware exists yet.
Sources: ESP32-C6 Technical Reference Manual Version 1.2 ("TRM", `docs/datasheets/esp32-c6-trm.pdf`, printed page numbers; raw download in `docs/research/downloads/esp32-c6-trm/`); ESP32-C6 Datasheet v1.5 ("C6 DS"); ESP32-C6-MINI-1 Datasheet v1.5 ("MINI DS"); web pages cited by URL (fetched 2026-10-09, summarised by a fetch tool, so quotes are as returned; re-read the page before relying on a version-specific detail).
Design context: `firmware/esp32/README.md` (plan), `docs/schematic/controller.md` (USB-C J60 on IO12/IO13, BOOT IO9, EN RC).

## 1. Answer to Daniel's question

"Could we do a USB connection and support programming and some communication to it like ESPHome does?" Yes, and it needs no extra chip. The ESP32-C6 has a USB Serial/JTAG controller that is a hardwired CDC-ACM serial port plus a JTAG adapter on IO12/IO13 (section 2). One USB-C cable gives: flashing (esptool or a browser), a console and JSON telemetry stream, and hardware debugging. ESPHome's flashing and log experience is built on the same chip feature; it is not an ESPHome-only capability. Recommendation: option (a), section 6.

## 2. USB Serial/JTAG facts

| # | Fact | Label | Citation |
|---|---|---|---|
| 1 | The controller integrates a USB-to-serial converter and a USB-to-JTAG adapter; "only two pins" (the USB data lines) are needed and "an external chip or adapter" is not. | VERIFIED | TRM s.32.1, p.1027 |
| 2 | USB 2.0 Full-speed (12 Mbit/s) device only; "Hardwired for CDC-ACM ... and JTAG adapter functionality"; CDC-ACM is "plug-and-play on most modern OSes"; two OUT and three IN endpoints plus EP0, 64-byte packets. | VERIFIED | TRM s.32.2, p.1027; C6 DS s.4.2.1.6 |
| 3 | It is a composite device: a CDC-ACM class function plus a vendor-specific class function for JTAG. | VERIFIED | TRM s.32.2, p.1028 |
| 4 | Pins: GPIO12 = USB_D-, GPIO13 = USB_D+, IO MUX only (priority-1 pins). D+/D- can be swapped with USB_SERIAL_JTAG_EXCHG_PINS (eFuse EFUSE_USB_EXCHG_PINS exists). | VERIFIED | C6 DS pin tables (QFN32 pins 16/17, "USB_D- (P1)"), note 1 under the IO MUX table; MINI DS Table 3-1 p.10-11; TRM eFuse list |
| 5 | CDC-ACM control requests accepted: SET_LINE_CODING, GET_LINE_CODING (default 9600 8N1, "can be changed through software"), SET_CONTROL_LINE_STATE (RTS/DTR), SEND_BREAK ignored. Baud rate is cosmetic: transfer runs at USB speed. | VERIFIED | TRM Table 32.3-1, p.1029 |
| 6 | DTR/RTS combinations are decoded by hardware into "Reset ESP32-C6", "Set download mode flag" and "Clear download mode flag"; a reset with the flag set reboots into download mode, with the flag clear boots from flash. Recommended host sequences are given for both. All of this can be disabled by eFuse. | VERIFIED | TRM Table 32.3-2 p.1030; s.32.4, Tables 32.4-1 and 32.4-2 p.1035 |
| 7 | Therefore esptool can reset the chip into download mode automatically over USB with no BOOT button. esptool names this strategy "usb-reset" ("custom reset sequence for USB-JTAG-Serial"); "Usually, this option doesn't have to be used directly. Esptool should be able to detect connection through USB-JTAG-Serial." esptool-js (the library behind browser flashing) has a `UsbJtagSerialReset` class. | VERIFIED (TRM) / VERIFIED (esptool and esptool-js docs, web) | TRM Tables 32.4-1/2; https://docs.espressif.com/projects/esptool/en/latest/esp32c6/esptool/advanced-options.html ; https://cdn.jsdelivr.net/npm/esptool-js@0.6.0/lib/reset.d.ts |
| 8 | The USB-triggered reset does not re-sample the strapping pins ("a chip that entered download mode manually may remain there"). Practical rule: after a manual BOOT+RESET session, power-cycle or press RESET without BOOT held. | VERIFIED | esptool advanced-options page (same URL as 7) |
| 9 | Manual fallback: hold BOOT (GPIO9) low and pulse EN/RESET. Download boot needs GPIO8 = 1 and GPIO9 = 0 at reset; our IO8 has the 10 k pull-up. Internal pulls are about 45 kohm, so use a hard 10 k or button pull-down. | VERIFIED | MINI DS Table 4-3 p.13 and p.26; esptool boot-mode page https://docs.espressif.com/projects/esptool/en/latest/esp32c6/advanced-topics/boot-mode-selection.html (its text is about external USB-UART chips; it states the same manual BOOT+EN procedure) |
| 10 | Download mode can also be forced from running firmware's side by the DTR/RTS flag; if an application breaks USB (reconfigures GPIO12/13, disables the controller, deep sleep), the chip disappears from the host and only BOOT low + reset recovers it. | VERIFIED | https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-guides/usb-serial-jtag-console.html ; TRM s.32.4 p.1035 (Deep-sleep powers the controller down) |
| 11 | USB Serial/JTAG needs the BBPLL for its 48 MHz PHY clock; if the PLL is disabled USB stops. Firmware must never put the part to sleep or disable the PLL in the USB-attached case (our design never sleeps). | VERIFIED | TRM s.32.4, p.1034 |
| 12 | If no host has the CDC port open, flushed packets are never picked up and the send buffer never empties, so firmware must use a timeout on writes. ESP-IDF's console behaves this way: output goes to a small buffer, then one 50 ms wait, then drops. | VERIFIED | TRM s.32.4 p.1034; ESP-IDF USB Serial/JTAG console page (URL in 10) |
| 13 | JTAG: base clock 48 MHz, TCK 24 MHz at the default divider; the JTAG function is a separate USB interface from the serial port, so debugging and console run at the same time. The chip enumerates as VID 0x303A, PID 0x1001. No SWD. | VERIFIED | TRM s.32.3.6, Tables 32.3-4/5 p.1033-34; ESP-IDF JTAG page https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-guides/jtag-debugging/index.html |
| 14 | JTAG source selection at boot: with default eFuses the USB Serial/JTAG controller is the JTAG source (GPIO15 only matters if EFUSE_JTAG_SEL_ENABLE = 1). External JTAG pads are therefore not needed and not used on our board. | VERIFIED | TRM Table 9.2-4, p.378; MINI DS Table 4-7 p.15 (via docs/research/module-controller.md) |
| 15 | ROM boot messages can print to USB Serial/JTAG (default: UART0 and USB). | VERIFIED | TRM s.9.2.3, p.377 |
| 16 | The chip has a 48-bit factory MAC (EFUSE_MAC, BLOCK1) and 256 bits of user eFuse data (EFUSE_USR_DATA, BLOCK3). Uniqueness of the MAC is Espressif's convention, not stated in the TRM table. | VERIFIED (fields exist) / PROPOSED (treat MAC as unique) | TRM Table 6.3-3 (~p.184) |
| 17 | On-die temperature sensor, measurement range -40 to 125 C, software triggered. It reads die temperature (includes self-heating), not APD temperature. | VERIFIED (range) / PROPOSED (use) | C6 DS s.4.2.2.2, p.58 |

### Operating systems and drivers (the "random laptop" requirement)

| OS | Serial (flash, console, stream) | Label |
|---|---|---|
| Windows 10 and later | Microsoft ships an in-box CDC driver (Usbser.sys) that loads automatically for class 02 / subclass 02 devices without an INF; the C6's CDC function is a standard CDC-ACM class function (TRM s.32.3.1). So no driver install is expected. The C6 is a composite device; whether Windows binds Usbser to the CDC interface of this composite with no prompt on a clean Windows 10 machine was NOT tested: confirm on the first board. The JTAG interface (not needed for flashing or the console) needs a WinUSB-type driver; Espressif's installer (`eim install-drivers`) provides it. | VERIFIED (Usbser behaviour: Microsoft Learn "USB Serial Driver (Usbser.sys)", https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-driver-installation-based-on-compatible-ids ; JTAG driver: ESP-IDF configure-builtin-jtag page) / UNRESOLVED (clean-machine test) |
| macOS | Appears as `/dev/cu.usbmodem*` style device; ESP-IDF page lists `/dev/cu*`. No driver. macOS CDC-ACM is inbox (general knowledge, not cited): confirm on first board. | VERIFIED (port naming only) / UNRESOLVED |
| Linux | `/dev/ttyACM*`. User needs dialout/uucp group membership for serial access; JTAG additionally needs OpenOCD udev rules. Browsers use the same permission. | VERIFIED (ESP-IDF console page; JTAG page for udev) |

Port-name caveat (VERIFIED, esptool advanced-options page): some reset modes can make the port re-enumerate on Linux (/dev/ttyACM0 to ttyACM1). Browser tools handle this by asking again; scripts should match by VID:PID 303A:1001, not by name.

## 3. Console, logging and an application protocol over the same port

- VERIFIED: `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG` (under the console-UART choice) makes the USB port the primary console; the REPL needs the primary option, not the secondary (output-only) one. ESP-IDF stable console page (URL in row 10).
- VERIFIED: `esp_console_new_repl_usb_serial_jtag()` starts a REPL over USB Serial/JTAG; commands are registered with `esp_console_cmd_register()`, parsed with argtable3; line editing needs an ANSI-capable terminal, but the parser works with plain `fgets`-style input, so a script or web page can type lines without a terminal emulator. https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-reference/system/console.html
- PROPOSED: JSON telemetry as lines that start with `{` on the same port; ESP_LOG output kept at WARN so a parser can ignore any line not starting with `{`. Detail in `docs/firmware/can-and-console-protocol.md`.
- PROPOSED: one port serves everything; a Web Serial page and a terminal cannot both open it at once (single opener), which is acceptable.

## 4. Browser workflow: ESP Web Tools and Web Serial

- VERIFIED (https://esphome.github.io/esp-web-tools/): ESP Web Tools combines Web Serial, Improv Wi-Fi (optional) and a manifest describing the firmware. You load its script module and place `<esp-web-install-button manifest="manifest.json">`. The site "must be served over https://" and cross-origin hosting needs CORS. The manifest lists `builds` per `chipFamily` (ESP32-C6 is a listed family), each with `parts` of `{path, offset}`; paths are relative to the manifest. ESP-IDF v4+ projects must be merged into one image first.
- VERIFIED (same page): Web Serial is available in Chrome and Microsoft Edge; the page also lists Firefox and says Android support "has not been implemented yet" and that it does not work on iOS. UNRESOLVED: Firefox claim not independently checked; Daniel's target is Chrome/Edge on Windows, macOS and Linux desktop.
- VERIFIED (esp-idf bootloader page, https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32c6/api-guides/bootloader.html): on the ESP32-C6 the second-stage bootloader is at flash offset 0x0 (partition table 0x8000 by default). So a merged image for the manifest is a single part at offset 0. Produce it with `idf.py` merge-bin (or `esptool merge_bin --chip esp32c6`): PROPOSED, the exact command is not tested here.
- VERIFIED: Improv is a protocol to provision Wi-Fi credentials over serial (https://www.improv-wifi.com/serial/). It is NOT relevant here: the radio is off by design (decision 11) and there is nothing to provision. ESP Web Tools treats Improv as optional; `new_install_improv_wait_time: 0` disables the detection step (ESP Web Tools page). Set it to 0 in the manifest so the button does not wait for an Improv device.
- PROPOSED page design (one static HTTPS page, no server logic): (1) `<esp-web-install-button>` for flash; (2) after flashing, a "Connect console" button that opens Web Serial itself (the flasher releases the port when done), sends `selftest`, shows the pass/fail table; (3) a live view of the `stream on` JSON lines (HV, M, RSSI, VTH, TIA, state). The same page works from a local folder served by `python -m http.server` on `http://localhost` (browsers treat localhost as a secure context; general behaviour, not cited here: confirm). The repo location would be `tools/web/` (not created by this document).
- PROPOSED: release artifacts (merged `.bin`, `manifest.json`, version) published by CI to a static host; the page's version string is checked against the firmware's `status` reply so the person can see what is running.

## 5. Debugging

VERIFIED: OpenOCD with `board/esp32c6-builtin.cfg` and `riscv32-esp-elf-gdb` over the same USB port (ESP-IDF JTAG page URL in row 13); on Linux add the OpenOCD udev rules, on Windows install the driver. Serial and JTAG run at once. Consequence for the board: IO6/IO7 (the external MTCK/MTDO pins) are free for LDAC and AUX (docs/schematic/controller.md), because external JTAG is not needed. PROPOSED: JTAG is a developer tool, not part of the "anyone can verify" flow.

## 6. Option comparison and recommendation

| Criterion | (a) ESP-IDF app + esp_console + ESP Web Tools page + host JSON dashboard | (b) ESPHome |
|---|---|---|
| Chip support | ESP-IDF supports C6 since v5.1 (for C6 revision v0.2 Espressif lists recommended minimum point releases per branch, v5.4 and later in all cases: https://github.com/espressif/esp-idf/blob/master/COMPATIBILITY.md) | ESPHome supports ESP32-C6, ESP-IDF framework only, default framework (https://esphome.io/components/esp32.html). VERIFIED |
| Flash from browser | ESP Web Tools: manifest + merged image. VERIFIED (section 4) | ESPHome dashboard/"ESPHome Web" flashing over Web Serial is widely known; the pages fetched here (esphome.io FAQ, web.esphome.io) returned no usable text, so details are UNRESOLVED |
| Serial console / logs | esp_console + our JSON stream; full control. | Logger defaults to USB_SERIAL_JTAG on C6 (https://esphome.io/components/logger.html). VERIFIED. Logs only; a typed command console is not part of ESPHome. |
| Peripherals | Own drivers: MCP4728 incl. EEPROM read/verify, ADS1115, TWAI. About 600 lines. | `mcp4728` output and `ads1115` sensor components exist; `esp32_can` supports C6 with two controllers (https://esphome.io/components/canbus/esp32_can.html). VERIFIED. No evidence it can read back or verify MCP4728 EEPROM defaults (UNRESOLVED; likely needs a custom component). |
| Radio off | Trivial: never initialise Wi-Fi or BLE. | Built around Wi-Fi, the native API and Home Assistant; the FAQ page describes behaviour such as rebooting "when the Wi-Fi connection cannot be made" (when configured). Whether a config with no `wifi:` and no `api:` runs cleanly was not established: UNRESOLVED. With the radio off by design (3V3_D LDO is 300 mA; Wi-Fi TX is 251-382 mA, C6 DS Table 6-4 via module-controller.md) any accidental radio start is a brown-out risk. |
| Safety-critical boot order | Explicit: verify DAC EEPROM, then HV, hardware watchdog, state machine in C. | Component setup order and lambdas: possible, but the HV safety logic would live in YAML lambdas or an external component, harder to review and test. PROPOSED judgement. |
| Range loop and CAN protocol | Normal C code, unit-testable on host. | Lambdas or custom C++ component anyway. |
| Dashboard | Small Python or browser page on the JSON lines; the CAN master side needs the same JSON from a different source. | Home Assistant, not needed here. |
| Extra tooling | Needs ESP-IDF to build (developers only); end users need only a browser. | Needs ESPHome (Python) to build; end users need only a browser or the dashboard. |

Recommendation: **(a)**. Reasons: the radio is off and the 300 mA rail cannot carry it; the HV safe-default sequence and range state machine must be reviewable C, not YAML; the self-test, the CAN enumerate/telemetry protocol and EEPROM provisioning are custom either way; and the end-user experience Daniel asked for (plug in, flash from a browser, see telemetry, run `selftest`) is fully provided by ESP Web Tools plus a static page. PROPOSED. Option (c), a custom ESPHome external component, is possible but adds the Wi-Fi/API framework for no gain; rejected.

## 7. UNRESOLVED

1. Clean-machine tests on Windows 10, Windows 11, macOS, Ubuntu with Chrome and Edge: enumeration without prompts, flash by ESP Web Tools, Web Serial console. First board.
2. Whether the browser flasher successfully resets a C6 into download mode from running firmware that is using the USB CDC console (expected from TRM s.32.4; esptool-js has the strategy; not tested). If a build breaks USB, BOOT + RESET (pads/buttons: hardware agent) is the recovery.
3. Whether ESP Web Tools' own "logs and console" view and our page can coexist: ours opens the port after the flasher closes it (design assumption).
4. Firefox support for Web Serial (page claim, unchecked).
5. ESPHome without Wi-Fi (not needed for the recommendation).
