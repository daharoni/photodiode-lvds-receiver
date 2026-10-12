# ESP32-C6 module controller firmware plan

Labels: VERIFIED (document, revision and page cited), PROPOSED (design intent), UNRESOLVED (open). Written 2026-10-09. Nothing here is implemented, simulated or measured; every threshold and time constant below is a first guess to be tuned at gates G1-G3 (docs/bringup/gates.md). Companion documents: `docs/firmware/can-and-console-protocol.md` (commands, telemetry, self-test result), `docs/research/esp32-usb-tooling.md` (USB, flashing, browser workflow).

Hard rules carried over (CLAUDE.md): slicing is analog and the module decodes with the ESP32 unprogrammed; this firmware only does slow range trim (APD bias, TIA 20k/5k), monitoring, HV gating, identity, telemetry and the CAN link. The radio is never initialised (decision 11).

## 0. Status

A firmware skeleton exists (2026-10-12), PROPOSED and not run on hardware: ESP-IDF project `receiver_esp32c6` (v0.1.0) with `main/` (boot steps 1-8 of s.4, parameter wiring), and components `board`, `drv_gpio`, `app_safety`, `params`, `app_console` (the s.3 `console/`, renamed because a project component named `console` shadows ESP-IDF's own), `app_telemetry`, plus the drivers, sensing, CAN link, range loop and self-test components written alongside. Build status: see the line below; the first board has not been programmed, no behaviour in this plan has been observed, and every threshold remains a first guess. Hardware-in-the-loop procedure: `firmware/esp32/HIL.md`.

Build: the full project (all twelve components and `main`) compiles and links with ESP-IDF v5.5.5 for esp32c6 on Daniel's Mac (2026-10-12, `source tools/esp-idf-env.sh && cd firmware/esp32 && idf.py set-target esp32c6 && idf.py build`): no warnings, app 0x4fc50 bytes, 84 % of the 2 MB factory partition free. The host unit tests under `test_host/` (CAN codec, range state machine, M estimator: 30 tests) pass with ctest. Nothing has been flashed or run on hardware; the drivers, the TWAI wrapper, the self-test and the boot sequence are untested beyond compiling.

## 1. What the hardware gives the firmware (all from docs/schematic/*.md, PROPOSED hardware)

| Function | Pin / part | Note |
|---|---|---|
| HV_DIS | IO0, 100 k pull-up to 3V3_D (R33), 1 k to Q3 gate | HIGH or Hi-Z = APD supply OFF; LOW = enabled. The only HV enable (power.md). Hi-Z at reset (module-controller.md s.1) |
| SHDN_N | IO1, TLV3605 shutdown, pull-up keeps comparator on | active low; shutdown is not a guaranteed zero output (standing correction 11) |
| TIA_CTRL | IO20, 100 k pull-up (frontend R57) | 1 = 20k, 0 = 5k; unprogrammed = 20k |
| I2C | IO2 SDA, IO3 SCL, 4.7 k pull-ups | MCP4728 0x60, ADS1115 0x48 |
| LDAC / RDY | IO6 / IO22 | MCP4728 LDAC; RDY/BSY open drain (EEPROM write busy) |
| CAN | IO19 TX, IO18 RX (swapped 2026-10-10 for layout), SN65HVD230, RS R199 100 k (decision 14: slow edges for stubs up to 3 m), 125 kbit/s | one split termination at the FPGA end |
| USB | IO12 D-, IO13 D+ (native USB Serial/JTAG), UART0 pads IO16/IO17 fallback | no USB-UART chip |
| Straps | IO9 BOOT (pull-up, button), IO8 10 k pull-up, EN 10 k + 1 uF | download boot needs IO8 = 1, IO9 = 0 (MINI DS Table 4-3 p.13, VERIFIED) |
| CC1_SENSE / CC2_SENSE | IO4 / IO5 (ADC1_CH4 / CH5), each a 100 k + 100 k + 100 nF tap from the receptacle CC pin (ATTEN2 range) | PROPOSED hardware, decision 14 (`docs/research/decision-14-draft-usbc-single-connector.md` 3e, spec revision 4). Firmware derives `cc_class` (`default`, `1.5A`, `3.0A`, `none`) and `cc_orient` (`cc1`, `cc2`, `none`) as hints only (logged in telemetry); `usb_host` = USB Serial/JTAG SOF seen. Never a basis to clear HV_DIS by themselves |
| BOOT / RESET | tactile switches on IO9 and EN | same document |
| AUX | IO7, 1 k to the tied SBU1/SBU2 net (AUX_CAB) on the USB-C receptacle; IO21 is free (AUX2 removed, decision 14) | spare GPIO to the FPGA (used for lane identification, protocol doc s.1.2); firmware holds the AUX driver high-Z until LINK_ALL or the host class is known |
| STATUS LED | IO23 | |
| DAC_HV | MCP4728 OUTC | 0 V = MAXIMUM bias about 215 V, full scale = minimum (about 104 V with the trimmer at its default; 55 V hardware floor with both trims at full scale); DAC alone spans 61 V, 14.9 mV per code at the DAC pin, about 15 mV of bias per code (apd-bias-design.md s.3.2, calculated) |
| DAC_TH | MCP4728 OUTB | threshold offset = (DAC - VCM_REF) x 1/101, +-16.3 mV, 8 uV per code (slicer.md, calculated); code 2048 (1.65 V at VDD ref) = zero offset |
| ADS1115 | AIN0 HV_MON = APD_BIAS/101, AIN1 RSSI (negative-peak detector of the TIA output, falls with light, idle about 1.9-2.0 V, tau 1 ms), AIN2 VTH_MON (comparator threshold node), AIN3 GND | each input 10 k + 10 nF; inputs must stay within GND-0.3 V to VDD+0.3 V (SBAS444E p.2, VERIFIED) |
| Temperature | NTC in the LT8365 feedback divider (hardware, not readable); ESP32-C6 die sensor (-40 to 125 C, C6 DS s.4.2.2.2 p.58, VERIFIED) | die temperature is telemetry only; it is not the APD temperature |

## 2. Toolchain

- ESP-IDF v5.5.x, pinned to one point release in the repo (latest at 2026-10-09: v5.5.5, 2026-07-17, GitHub releases). PROPOSED. Reasons: the C6 is supported since v5.1 and Espressif's compatibility table recommends v5.4 or later for the newest C6 chip revisions (https://github.com/espressif/esp-idf/blob/master/COMPATIBILITY.md, VERIFIED); v5.5 is mature while v6.0.x and v6.1 (2026-08-27) exist; a release is supported 30 months, 12 of them in "Service" (ESP-IDF support policy page, VERIFIED). Revisit at the first board. UNRESOLVED: which C6 silicon revision the MINI-1 modules carry.
- The CAN peripheral sits behind `can_link`, because the TWAI driver API changed: v5.5 provides the node-based `esp_driver_twai` (`twai_new_node_onchip`, `twai_node_enable`; flags for self-test mode, listen-only and loopback) (https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/peripherals/twai.html, VERIFIED for the classic ESP32 page; the C6 page was not read).
- Console: `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG`, `esp_console` REPL over USB Serial/JTAG (docs/research/esp32-usb-tooling.md s.3). Brown-out detector on, task watchdog panic on, log level WARN.
- Build artefact for browsers: merged flash image (bootloader at 0x0 on the C6) plus `manifest.json` for ESP Web Tools (research doc s.4).

## 3. Software structure

```
firmware/esp32/
  main/            app_main: boot sequence only
  components/
    drv_mcp4728/   I2C driver: fast/multi write, sequential write (EEPROM), Read command (24 B), LDAC, RDY
    drv_ads1115/   I2C driver: single-shot channel read, PGA, averaging
    drv_gpio/      HV_DIS (owner: safety), SHDN_N, TIA_CTRL, LED, AUX
    can_link/      TWAI wrapper, frame codec (protocol doc), enumerate, heartbeat age
    console/       esp_console commands, JSON stream, shared parameter table
    params/        parameter registry + NVS (one table for CAN and console)
    app_safety/    HV gate, fault word, watchdog, boot sequence checks
    app_range/     range-trim state machine, M estimator, calibration
    app_selftest/  self-test steps
    app_telemetry/ periodic CAN frames and JSON lines
```

| FreeRTOS task | Priority | Period | Job |
|---|---|---|---|
| safety | 20 | 10 ms | sole writer of HV_DIS; evaluates faults; feeds the task watchdog only if every monitored task checked in |
| can_rx / can_tx | 12 | event | frame decode, heartbeat, command dispatch |
| sense | 10 | about 30 ms per round | reads AIN0-AIN2 (ADS1115 128 SPS, about 8 ms each, 4-sample average); publishes a lock-protected snapshot |
| range | 8 | 100 ms | state machine of section 6 |
| telemetry | 5 | 20 ms | CAN frames and `stream on` JSON |
| console | 3 | event | esp_console REPL thread |
| led | 2 | 50 ms | STATUS LED patterns |

One I2C mutex; all I2C from `sense`, `range` (DAC writes) and the console (calibration), never from `safety`. The C6 high-performance core is a single RISC-V core at up to 160 MHz (C6 DS), so priorities, not cores, set the order. Nothing is hard real-time; the control bandwidth is seconds because the optical intensity changes at animal-motion speed, below 10 Hz (Daniel, 2026-10-08). USB console output uses timeouts (a closed CDC port never drains the buffer, TRM s.32.4 p.1034, VERIFIED).

## 4. Boot sequence and safe defaults (in order)

State before any firmware runs (hardware, PROPOSED): HV_DIS pulled high so HV is OFF; TIA at 20k; comparator on; MCP4728 outputs per its EEPROM, and the factory EEPROM is 0 V on all channels, which on channel C means MAXIMUM bias (MCP4728 DS22187E Table 4-2 p.24 via module-controller.md, VERIFIED; apd-bias-design.md s.3.2). Therefore HV stays off until the DAC is proven safe. Bench jumper J1 (HV FORCE ON) defeats this: with J1 fitted and an unprogrammed DAC the bias goes to about 215 V; firmware cannot prevent that.

1. **First instructions of app_main:** write HV_DIS = 1 and only then enable it as an output (no glitch); leave SHDN_N and TIA_CTRL as inputs (hardware pull-ups give comparator on and 20k). Start the task watchdog. Read the reset reason: power-on, software, brown-out, watchdog. After a brown-out or watchdog reset set the BROWNOUT / WDT fault bit; HV then stays off until a deliberate command clears it.
2. **NVS and parameters:** load, check CRC, clamp every value to its limits (hv_min >= 100 V, hv_max <= 200 V default and 220 V absolute). Corrupt NVS gives factory defaults and fault flag; `hv_set` defaults to the hv_min value.
3. **I2C:** if SDA is low, clock out 9 SCL pulses (bus recovery). Probe 0x60 and 0x48. Missing either gives I2C fault; HV stays off; console and CAN still start so the board can be diagnosed.
4. **Verify the DAC EEPROM defaults.** Send the MCP4728 Read command (R/W = 1; returns for each channel the input register and the EEPROM contents, 24 bytes: DS22187E s.5.6.9 p.37 and Figure 5-15 p.45, VERIFIED). Required: channel C (DAC_HV) VREF = VDD, PD = 00 (never power-down), code 0xFFF; channel B (DAC_TH) VREF = VDD, PD = 00, code 0x800; channels A and D normal mode. Correction to docs/schematic/controller.md and module-controller.md, which name the "General Call Read": that command reads only the I2C address bits (DS22187E s.5.4.4 p.32-33, VERIFIED); the EEPROM contents come from the Read command. Anything else: DAC_EEPROM fault; the guarded console command `dac provision` writes the defaults with the Sequential Write command and re-reads them (EEPROM write time 25 ms typ, 50 ms max, p.6, VERIFIED; wait on RDY/BSY (IO22) or poll). EEPROM is written only by provisioning, never by the loop (endurance figure not looked up: UNRESOLVED).
5. **Force the live outputs to the safe values** with Multi-Write (volatile): DAC_HV = 0xFFF (minimum bias), DAC_TH = code for `th` (default 0x800). LDAC is on IO6, so tie updates together with a pulse or use the UDAC bit; read the registers back and compare. Mismatch gives I2C_DAC fault.
6. **ADS1115 check:** read AIN3 (expected 0 V +- 5 mV) and AIN0. With HV_DIS high the boost output rests near the 5 V input minus a diode drop, so HV_MON is about 0.05 V (bias about 4-5 V; calculated). If bias above 30 V is read while HV is disabled, set HV_STUCK (something forces HV, such as J1) and report; do not try to compensate.
7. **Read the source and start CAN.** Read CC1/CC2 (`cc_class`, `cc_orient`: three consecutive agreeing reads over more than tRpValueChange, 10-20 ms, TC R2.0 Table 4-31 p.239-240) and watch for USB SOF (`usb_host`; TRM v1.2 s.32.5 p.1035). **Start the CAN link in listen-only (TX silent, RS high) and listen for LINK_ALL at every boot for 1.5 s or longer** (the breakout must apply VBUS first and the FPGA may boot later): heard = **bus mode** and CAN TX is enabled (BOOT frame sent); not heard = **standalone (USB) mode** with CAN TX still silent until bus traffic or the FPGA master is seen, so a lone module on a laptop never transmits into the host's SS receive pair. Mode is re-evaluated at boot, except that hearing LINK_ALL later switches standalone to bus mode. Mode table (PROPOSED): LINK_ALL yes -> `bus` (host console allowed if SOF seen); LINK_ALL no, SOF yes -> `usb` standalone (stepped HV start); neither, class 1.5 A -> `usb` until LINK_ALL arrives, then `bus`; neither, no Rp -> `usb` with a warning. The eFuse current limit (about 0.76 A, decision 14) can reset the module, so the boot log records the reset reason (step 1).
8. **HV is still off.** HV turns on only by (a) `hv on` from the console (standalone), (b) a master `hv_cmd` = 1 over CAN, or (c) NVS flag `hv_auto` = 1 together with a heard master and no latched faults (default 0 for the first boards, Daniel decides). PROPOSED.
9. **HV soft start** (state RAMP), preconditions: no faults 0-2, DAC verified in this boot, ADC alive. (a) TIA_CTRL: leave at 20k unless the saved `tia` says 5k. (b) Drive HV_DIS low; the LT8365 soft-start (0.22 uF on SS, about 2 uA charge current, lt8365.pdf Rev. A p.4) ramps the supply to the DAC-set minimum, about 104-110 V (design value). (c) Walk DAC_HV down from 0xFFF toward `hv_set` closed-loop on HV_MON: each 100 ms read the bias, step the code by (target - measured)/(14.95 mV per code nominal), limit the slew to 20 V/s (the cathode step injects Cj x dV/dt; apd-bias-design.md s.7 says ramp slowly, no number given: PROPOSED value) and the step to 150 codes. (d) Arrival: within 2 V of target for 1 s; timeout 10 s gives HV_UNDER and HV off. Then state ON and the range loop takes over.
10. **Turn-off (commanded):** ramp DAC_HV back to 0xFFF at 50 V/s, then HV_DIS high. **Turn-off (fault):** HV_DIS high immediately, DAC_HV to 0xFFF afterwards. The LT8365 output is not actively discharged and decays through the divider loads over seconds (estimated, not measured; fault HV_STUCK detects a bias that does not decay).

Any ESP32 reset, crash or loss of the 3V3_D rail releases IO0, so HV_DIS goes high through R33 and HV turns off with no firmware action (reset behaviour VERIFIED for IO0 via C6 DS Table 2-2 p.17-18 as quoted in module-controller.md; the floating-gate case when 3V3_D itself is absent is UNRESOLVED in power.md).

## 5. Fault, loss and watchdog policy

HV_DIS goes high on all of the following (`safety` task, within 10 ms of detection):

| Event | HV | Recovery |
|---|---|---|
| I2C or ADS1115 failure (HV can no longer be monitored) | off, latched | `faults clear` after the cause is gone, then `hv on` |
| HV_MON above hv_max + 5 V; target not reached; collapse below 70 % of set | off, latched | same |
| CAN bus-off, or no LINK_ALL for bus_timeout (default 2 s) in bus mode | off, latched | the master heartbeat returns; `hv_auto` or a master `hv_cmd` re-arms |
| Brown-out reset (ESP-IDF detector) | off (reset releases IO0) | stays off until commanded; fault bit BROWNOUT |
| Task or interrupt watchdog (C6 has two timer-group watchdogs, an RTC watchdog and an analog super watchdog, C6 DS s.4.1.3.9 p.44, VERIFIED) | off (panic reset releases IO0) | stays off until commanded; WDT bit |
| `safety` task starved (a monitored task missed its check-in) | off | watchdog reset as above |
| Console `hv off`, USB cable pulled | off on command only | the USB host disappearing is not a fault in standalone mode: bench HV continues until commanded (a powered-from-USB module loses power with the cable anyway) |

CAN loss deliberately takes the link down; it also happens when the FPGA reconfigures, and the soft start recovers in about 5 s (estimate). If Daniel prefers "hold last bias for T seconds on CAN loss", it is the `bus_timeout` parameter plus a HOLD state: UNRESOLVED decision.

## 6. Range-trim loop

### 6.1 What the loop can and cannot see

| Input | Source | Use |
|---|---|---|
| bias | AIN0 x 101 | set-point closure, M estimate, fault checks |
| rssi_drop | AIN1, idle minus present; RSSI is the negative-peak envelope of the TIA output including DC ambient photocurrent, so it cannot tell signal from ambient (docs/schematic/control.md) | TIA overload guard, "light present", logging. Never used to choose the M optimum |
| link valid, error class | FPGA over CAN (LINK_ALL nibble, protocol doc s.1.5) | the optimum search and recovery (8b/10b validity and invalid-code counts; not a BER) |
| temperature | hardware NTC inside the bias divider (about 0.64 V/C tracked, +-0.7 V residual over 15-35 C; apd-bias-design.md s.3.2, calculated) | none: the firmware sees temperature only as bias drift at a fixed DAC code |

Outputs: DAC_HV code (slew-limited), TIA_CTRL. Q(M) is broad: for the S12023-10 at the 30 mW/sr target the model (ambient 0) gives Q 16 at M = 30, 15.8 at M = 50, 15.2 at M = 75 (docs/calculations/link-budget.md Table A, calculated, not measured), peak M about 35-60 (Table B), and ambient light multiplies by M as well and moves the optimum lower. So coarse tracking is enough; the real jobs are keeping the TIA out of saturation and finding the lowest bias that gives a clean link with margin.

### 6.2 Strategy (PROPOSED): lowest clean bias plus a margin, found in bias space

Search in bias volts, not in absolute M, so the loop works without per-unit calibration. A strong signal then settles at the minimum bias with the 20k or 5k gain (best for ambient and saturation); a weak one walks up until the FPGA reports valid frames, then adds margin. Absolute M is only for telemetry (6.4).

### 6.3 State machine

| State | Entry | Actions | Exit |
|---|---|---|---|
| OFF | boot, `hv off`, fault | HV off | HV on, ramp done: SEARCH (bus mode) or MANUAL (standalone) |
| RAMP | soft start (s.4.9) | DAC walks to the starting bias = hv_set if it came from NVS and the last lock is valid, else hv_min | arrival: SEARCH |
| SEARCH | ramp done, or LOS timeout | raise bias 2 V per 400 ms (about +14 % M with the datasheet-derived 7 %/V; apd-selection.md, graph-read) until valid for 1 s clean (class 0); then add margin +8 V (about 1.7x M) limited to hv_max; record V_lock. If hv_max is reached with no valid frames: stay, report LOS, retry from hv_min every 30 s | clean 1 s: TRACK |
| TRACK | locked | hold bias. Error class >= 2 averaged over 2 s: +2 V, then wait 1 s, repeat (max +6 V per 5 s, limit hv_max). Class 0 for 60 s and bias above V_lock: down-trial -4 V for 5 s, restore +4 V on any class >= 1 and double the trial interval (60 s up to 10 min). | valid = 0 or class 7 for 1 s: LOS |
| LOS | link lost in TRACK | hold bias and TIA for 5 s (animal turned away or brief occlusion; do not hunt); then SEARCH from the last lock minus 8 V | valid again: TRACK |
| MANUAL | standalone, or `loop manual` | bias stays at `hv_set`, TIA at the user's setting; the loop only reports. With `tia auto` the overload guard still switches the TIA | `hv off`, fault, `loop auto` |
| FAULT | any latched fault that turned HV off | HV off | `faults clear` and a deliberate enable |

TIA overload guard (runs in every state with `loop auto` or `tia auto`; PROPOSED thresholds; RSSI is relative):

| Condition | Action |
|---|---|
| rssi_drop above 0.80 V for 100 ms (TIA saturates at 60 uA at 20k = about 1.1 V of swing; OPA857 SBOS630D p.15, VERIFIED, 1.2 V swing; 0.8 V is two thirds of it) or RSSI below 0.3 V | lower bias 2 V per 200 ms down to hv_min; if still above 0.80 V at hv_min and the TIA is 20k, set 5k (the drop falls 4x) |
| at 5k, rssi_drop below 0.10 V (equivalent to under 0.40 V at 20k) for 10 s | set 20k |
| any switch | at least 10 s between switches; ignore link metrics for 300 ms after a switch (switching transient not yet measured: G1 item); never switch while HV is ramping |

SIMULATED input to the 20k/5k scheduling (ngspice 47, TI OPA857 v1.0 model, `docs/simulation/README.md` Sim 2; model fidelity at 6 pF not validated, nothing measured): at the S12023-10's 6 pF the 20k mode shows about 1 dB peaking and 13.8 % overshoot, taking 12.6 ns to settle to 2 % of the 20 ns UI (pattern-dependent ISI at 50 Mb/s), while 5k is clean (1.7 % overshoot, 4.7 ns). So the scheduling should treat 5k as the preferred mode whenever the signal budget allows and 20k as the sensitivity fallback. This does not change the loop structure or thresholds here; how much that shifts the 5k-to-20k up-switch (rssi_drop below 0.10 V at 5k) is decided at G1/G2 from the measured 20k eye at 6 pF. UNRESOLVED until measured.

The two thresholds (0.80 V down, 0.40 V up-equivalent) give a factor-2 (6 dB) band, the 10 s dwell prevents chatter. The post-amp clips at about 9 uA pp at 20k and 36.5 uA at 5k but the comparator keeps slicing because the clip is symmetric about the baseline (decision 12); the guard protects the TIA, not the post-amp.

### 6.4 M estimation and per-unit calibration

- Model (PROPOSED, datasheet-derived): near M = 50-100 the gain doubles per about 10 V, so d ln M / dV = 0.069 per volt (docs/research/apd-selection.md, graph-read from Hamamatsu KAPDB0017EC, not VERIFIED to the printed value). `M = 100 x exp(0.069 x (V25 - V100))` where V100 is the bias for M = 100 at 25 C and V25 is the 25 C-equivalent bias. Because the hardware NTC keeps bias minus V100 nearly constant over temperature (residual about 0.008 V/C), the estimator maps the DAC code, not the measured volts, to M: V25(code) is the bias measured at that code during calibration at a known room temperature.
- Per-unit anchor: VBR is 150 V typical and 200 V maximum for the S12023-10 and M = 100 sits near 130-135 V for a typical part (apd-selection.md); per-unit values are UNRESOLVED. So `m_est` is null until a `cal vop 100 <V>` or `cal vbr <V>` is stored. How to calibrate (PROPOSED): (1) bench (G1): measure the gain-vs-bias curve of the actual APD with a known light level and record the voltages for M = 50 and 100; enter them with `cal vop`. (2) firmware-assisted: `cal sweep` steps the bias from hv_min up in 1 V steps under a steady light with the TIA at 5k and logs `rssi_drop` per step; the slope of ln(drop) against V gives the local exponent. It cannot give absolute M because the hardware cannot reach the M = 1 plateau (the DAC only spans 61 V above 104 V), so absolute M needs the bench reference. Stored in NVS with the DAC code to bias map.
- Error budget (calculated): +-0.7 V NTC residual plus about +-2 V code-to-volt calibration at room temperature gives about +-2.7 V x 6.9 %/V = about +-19 % in M, small against a Q(M) that is flat within about 5 % from M = 30 to 75.
- Optional telemetry (PROPOSED): once code and bias are calibrated at a known 25 C, bias minus the stored bias at the same code divided by 0.642 V/C is a temperature estimate of the NTC (APD) location: the hardware NTC becomes readable for free. Accuracy limited by the same tolerances.

### 6.5 Standalone USB mode (FPGA absent)

No link metric exists, so the loop is MANUAL: it holds the user-set bias (`hv set`, volts; the closed loop on HV_MON trims the DAC to that bias) and the user's TIA gain, and reports. Because the bias target is in volts while the NTC moves the bias with temperature, a pure volts set point would cancel the temperature compensation: in MANUAL the loop therefore holds the DAC code that gave the requested bias at the time of the command, and only the closed loop at ramp time uses volts. Documented behaviour: after `hv set 180` the reported bias drifts by about 0.64 V/C. PROPOSED.

### 6.6 Logging and NVS

- NVS namespaces: `factory` (serial, board_rev, MAC copy, calibration: V100/VBR, DAC code to volts table, rssi idle for 20k and 5k; write-once per field), `user` (hv_set, hv_min, hv_max, tia, loop mode, node, tlm_ms, bus_timeout, hv_auto, th), `state` (V_lock, last result). Writes happen only on `save` or commissioning commands, never from the loop (NVS wear). A CRC covers each blob.
- Log rules: ESP_LOG at WARN; every event worth keeping (state change, TIA switch, fault, lock) goes out as a JSON event line `{"ev":"tia","to":"5k","drop":0.83,...}` when `stream on`, and into a small RAM ring (64 events) printed by `status`. No flash logging. A host script or the browser page can store the stream. PROPOSED.

## 7. Module identity

Unique ID: the 48-bit factory MAC from eFuse BLOCK1 (read-only; TRM Table 6.3-3, VERIFIED field; uniqueness by Espressif convention). Board serial (`serial`) and revision (`board_rev`) in NVS `factory`, written once by the `serial set` console command during production (not eFuse, so a mistake is recoverable). Both appear in `status`, in the JSON telemetry, in the ENUM announce (MAC) and by GET (serial). PROPOSED. The firmware version is built in (`fw_ver`).

## 8. Built-in self-test (`selftest`, quick and full)

Purpose (Daniel, 2026-10-09): anyone plugs a module into a laptop, flashes it from a browser and verifies it with no FPGA, cable or toolchain. Run from the console, the web page or over CAN. `quick` is steps 1-8 without HV; `full` (default for `selftest`) adds step 9. Total about 15 s plus HV decay. Result: human lines, then one JSON line (protocol doc s.6). All windows are PROPOSED first guesses (nothing measured) to be tightened with the first board's data.

| # | Step | Pass criterion |
|---|---|---|
| 1 | identity | firmware version, MAC, serial and rev present (missing serial is a warning, result `info`) |
| 2 | I2C bus | SDA and SCL idle high before init; ACK at 0x60 and 0x48; other addresses reported |
| 3 | MCP4728 EEPROM defaults | Read command: channel C = VDD ref, PD 00, 0xFFF; channel B = VDD ref, PD 00, 0x800 (section 4 step 4) |
| 4 | DAC write/readback | write DAC_HV 0xFFF and DAC_TH codes; Read command returns the same; VTH_MON shift: step DAC_TH by +-0.5 V and require the node to move by 4.95 mV +-30 % (0.5 V x 1/101, calculated) |
| 5 | ADC and windows (HV off) | AIN3 = 0 +-5 mV; RSSI idle 1.5-2.3 V (expected 1.9-2.0, control.md); VTH_MON 1.65 V +-0.10 V (VCM_REF 1.65 V, slicer.md); HV_MON under 0.1 V (bias under about 10 V) |
| 6 | GPIO | SHDN_N: read pull-up level 1 as an input, drive 0 and 1, read back, return to input. TIA_CTRL likewise. HV_DIS reads high. These prove the pin and pull-up only: the comparator and TIA effect is not observable by the ESP32 (UNRESOLVED; RSSI may show the 4x TIA change under room light: report as `info`, never fail on it) |
| 7 | CAN | with a quiet bus (no frame for 500 ms): TWAI self-test mode with loopback, send and receive 8 frames at 125 kbit/s, which exercises TX, the SN65HVD230 and RX; error counters 0. Active bus: `skip` and report frames seen. UNRESOLVED: loopback through the unterminated transceiver needs a bench check |
| 8 | die temperature | -10 to 60 C (sensor works, C6 DS s.4.2.2.2) |
| 9 | HV supply (full only) | set DAC_HV 0xFFF; confirm HV_MON low; HV_DIS low; walk the code to a **test bias of 100 V** (absolute cap 110 V for this step regardless of settings; 100 V is the firmware minimum and below the S12023-10 typical VBR of 150 V; per-unit VBR minimum is not known: UNRESOLVED) within 5 s, +-5 %; require the code-to-volt slope between 10 and 30 V per V (nominal 18.5, calculated); hold 2 s stable (+-1 V); re-read RSSI and VTH_MON (windows of step 5, RSSI may fall with room light); ramp down and HV_DIS high; wait until bias below 30 V or 30 s (decay is passive) and report `hv_peak_v`. Does not need an APD fitted: the bias is verified at HV_MON, which is independent of the APD |

Result codes drive the STATUS LED (IO23), PROPOSED: running = fast 5 Hz blink; PASS = three 1 s on / 1 s off blinks then 0.2 s pulse every 2 s; FAIL = the number of the first failing step as that many flashes, a 2 s pause, repeated; normal operation = 0.5 s pulse every 2 s while HV is off, a second short pulse when HV is on; fault = steady 5 Hz; IDENTIFY = 8 Hz double blink. The result is also saved to `state` so `status` shows the last result and the CAN TLM_STATE `selftest_last` bits.

### 8.1 Browser verification

The static page described in research/esp32-usb-tooling.md s.4 flashes (ESP Web Tools), then opens Web Serial, sends `selftest`, renders each step as pass or fail and shows the live JSON telemetry. Flashing needs Chrome or Edge on Windows, macOS or Linux; the CDC port needs no driver (TRM s.32.2-32.3 p.1027-1029, Microsoft Usbser.sys; clean Windows 10 test pending). No FPGA, cable or toolchain involved. PROPOSED.

## 9. USB-only operation and its current budget (input to the hardware agent)

The USB power path is PROPOSED hardware described in `docs/research/usb-standalone-power.md` (historical decision-13 text; decision 14 replaced the mux with a TPS259631 eFuse on one 24-pin USB-C; worst-case 5 V draw there about 0.19 A with a 1 mA HV load, 0.24 A with margin). This section gives the firmware-side self-test draw, to be compared with that budget. Estimates only, nothing measured; datasheet typical-to-maximum values, from 5 V:

| Load | Estimate | Source |
|---|---|---|
| ESP32-C6, radio never started, 160 MHz | 27-38 mA (about 40 mA with margin) | C6 DS Table 6-7 p.28 modem-sleep running; the datasheet has no "radio never started" figure |
| SN65HVD230 | 10 mA typ, 17 mA max | SLOS346O p.7 |
| MCP4728, ADS1115, LED | 1.4 + 0.15 + about 2 mA | DS22187E p.5, SBAS444E, 1 k LED |
| 3V3_D total (LDO, so equals 5 V draw) | about 60 mA | module-controller.md |
| 3V3 analog: OPA857 26.8, OPA855 19.5, TLV3605 17.5, OPA2320 about 2 (maxima) | about 66 mA | power.md |
| LT8365 at the 100 V test bias: loads FBX divider about 12 uA, HV_MON 10 uA, clamp bias 10 uA = 32 uA x 100 V = 3.2 mW; at 70 % efficiency 4.6 mW = 0.9 mA at 5 V; plus controller quiescent with BIAS tied to GND (1.2 mA active not switching) and the pulse-skip cost "hundreds of uA" | about 2.5-3 mA average; the 0.3 A inductor peaks are filtered by the input capacitors | lt8365.pdf Rev. A p.3 (quiescent) and p.7 (SYNC/MODE); apd-bias-design.md s.2 (70 % is that document's assumption); loads calculated from the design values |
| LT8365 start-up energy into the pump capacitors (about 0.5 uF at 50 V) | under 1 mJ over the soft-start; average under 10 mW | calculated |
| **Total steady, self-test at 100 V** | **about 130 mA** (design ceiling 150 mA) | |

The usb-standalone-power.md worst case (0.19 A) is higher because it assumes 0.5-1 mA of HV load (36-69 mA at 5 V); the self-test bias load is tens of microamps, so the self-test sits below that budget. Normal operation at 140 V with the APD adds only the same tens of microamps plus dark and photocurrent (nA to uA), so the 1 mA bound is conservative for this design (PROPOSED reading, not measured).

Points for the hardware side: (a) USB 2.0 allows 100 mA before enumeration and up to 500 mA after the host grants it (recalled, not verified: the same open item as usb-standalone-power.md s.4); the C6's hardwired descriptor declares some bMaxPower that is not documented in the TRM: UNRESOLVED, read it with `lsusb -v -d 303a:1001` on any C6 dev board. About 110-130 mA flows before enumeration because the regulators start at once: the exposure is the same as in that document. (b) Firmware use of the sense lines: the telemetry `src`/`cc_class`/`cc_orient` fields and the standalone decision in boot step 7; they do not gate HV. A brown-out during a self-test is reported by the reset reason on the next boot. (c) The firmware cannot measure the 5 V level (only a threshold), so a sagging USB supply shows up as brown-out resets.

## 10. FPGA-end CAN master: can the ULX3S's own ESP32 do it? (PROPOSED, not tested)

Sources: ULX3S schematic v3.1.7, PDF page 7 (docs/datasheets/ulx3s-schematics-v317.pdf, WiFi sheet, VERIFIED reading), emard/ulx3s MANUAL (https://github.com/emard/ulx3s/blob/master/doc/MANUAL.md), ESP-IDF TWAI page (ESP32 has one TWAI controller; classic ESP32 page v5.5).

- The ULX3S carries an ESP32 module (U9, WROOM/WROVER footprint; the note "WROVER GPIO16,17 used internally for PSRAM" shows both fit). The classic ESP32 has one TWAI controller, which is enough for a master (VERIFIED, ESP-IDF page).
- Free-looking GPIOs that reach the J1 header (page 7, v3.1.7): IO32 = net GN12, IO33 = net GP12, IO36 = net GP13, IO39 = net GN13 (IO34 goes to JTAG_TDO). IO34, IO35, IO36, IO39 are input-only on the classic ESP32 (general knowledge, not in the cited pages: confirm), so only **IO32 (TX) and IO33 (RX)** can be TWAI pins. The MANUAL says the J1 GP/GN 11-13 positions are shared with the ESP32 on v2.0 and later: the exact sharing for v3.1.7 should be confirmed by checking the gpio sheet. All other ESP32 pins go to the FPGA (bank 6: IO0, IO5, IO19, IO21, IO22, IO25-IO27, IO35, UART0), the SD card (IO2, IO4, IO12-IO15) or JTAG/LED.
- Proposed wiring: a small breakout with an SN65HVD230 (3.3 V, RS 100 k as on the modules, decision 14) plugged on header J1 at the GP12/GN12 positions plus a 3V3 and GND header pin, and the split termination (2 x 60 ohm + 4.7 nF) at the star junction (module-controller.md s.3). ECP5 pins on those header positions must stay tristated (FPGA constraint). Consequence: **do not use gp/gn 12 and 13 for LVDS lanes**; gp/gn 8-11 (bank 7) and 14-21 (banks 2/3, docs/research/ulx3s-lvds-input.md) remain for the modules' pairs (pairs 9-10 were ESP32-shared only on v1.7).
- Link status path: the FPGA can send a UART or SPI to the ESP32 on the FPGA-connected ESP32 pins (bank 6, same page 7), carrying the 14 link nibbles; the ESP32 builds LINK_ALL and runs the ENUM and telemetry logic; it can forward telemetry to a laptop over its WiFi (this ESP32 is not constrained by the module's radio-off rule) or over the board's USB serial through the FPGA pass-through. PROPOSED.
- Costs and risks: the ESP32 on the ULX3S normally runs the user's WiFi/programming firmware, so this repurposes it (it stays flashable over the FTDI path: ULX3S page 6, WiFi programming pins TXD RXD RTS DTR, VERIFIED reading; programming interplay with GPIO0 and the FPGA, per the MANUAL R56 note, UNRESOLVED); IO12 is a boot strap on this ESP32 and shared with the SD card (not used here). Alternative if this is unwanted: a second ESP32-C6 adapter board (the module controller code with a master personality). Recommendation: try the ULX3S ESP32 first; no extra hardware beyond one transceiver breakout. UNRESOLVED until a ULX3S is wired.

## 11. Verification plan (maps to docs/bringup/gates.md)

| Item | Gate |
|---|---|
| Boot sequence with a blank MCP4728 (0 V EEPROM): HV must stay off; `dac provision` then HV on at 100 V; scope the bias | G1 |
| Fault injection: unplug I2C, kill CAN master, pull 3V3_D, hang a task: HV_DIS goes high each time | G1/G3 |
| RSSI vs photocurrent across M and 20k/5k; rssi idle windows; thresholds D_hi and 10 s dwell | G2 |
| Step response of the loop: 10 dB light steps up and down, time to valid frames, no 20k/5k chatter | G2 |
| M vs bias vs temperature per unit; `cal vop` against the bench reference | G1/G2 |
| Dark start, weak light, sudden strong light, occlusion and return | G3 |
| CAN load with 14 emulated nodes at defaults; enumerate with 3 real nodes; confirm the section-3 arithmetic | G3 |
| Clean-machine flash and self-test from Chrome and Edge on Windows 10/11, macOS and Linux | before first user build |

## 12. UNRESOLVED (summary)

1. Per-unit APD VBR and the gain curve (G1); until then `m_est` is null and the loop works in bias space.
2. All loop thresholds, dwell times, windows and the +8 V margin (tuned at G2/G3); whether the search margin or a down-trial may perturb a live link (default off for the down-trial is an option; Daniel decides).
3. `hv_auto` default and CAN-loss behaviour (HV off vs hold for T seconds).
4. TIA and bias-step switching transient time (G1) sets the post-switch blanking.
5. TWAI loopback through the transceiver, enumerate collisions, ULX3S ESP32 as master (bench).
6. USB: declared bMaxPower, pre-enumeration current, clean-machine driver behaviour, VBUS monitor (hardware agent).
7. MCP4728 EEPROM endurance (not looked up); J1 bench override defeats the safe-default logic.
8. IDF release choice and C6 chip revision on the MINI-1.
9. 20k eye at 6 pF (SIMULATED 13.8 % overshoot, 12.6 ns to 2 % settle; model not validated at 6 pF): decides how strongly firmware prefers 5k and whether the 5k-to-20k up-switch threshold moves (G1).
