# Module controller research: ESP32-C6-MINI-1, CAN link, local I2C parts

Scope: decision 11 / architecture item 11 (controller on the receiver module, CAN to the FPGA side, MCP4728 + ADS1115 over I2C). Everything below is research input. Labels: VERIFIED (datasheet cited), PROPOSED, UNRESOLVED. Page numbers are printed page numbers of the files in `docs/datasheets/` (manifest rows added 2026-10-08). Nothing here was simulated or measured.

Documents used: ESP32-C6-MINI-1/-1U datasheet v1.5 ("MINI DS"); ESP32-C6 series datasheet v1.5 ("C6 DS"); SN65HVD230 SLOS346O (Apr 2018); TCAN334 SLLSEQ7F (May 2025); MCP4728 DS22187E; ADS1115 SBAS444E (Dec 2024); TI SLLA270 (Jan 2008). Not read: ESP32-C6 Technical Reference Manual and Hardware Design Guidelines (not downloaded).

## 1. ESP32-C6-MINI-1

- VERIFIED: Module: 13.2 x 16.6 x 2.4 mm (-1, PCB antenna); -1U (external antenna via MHF III/W.FL class connector) exists: 13.2 x 12.5 x 2.4 mm, no keepout. Variants N4 (-40..85 C, 4 MB), H4 (-40..105 C), H8 (8 MB). MINI DS p.1, p.4 (Tables 1-1, 1-2), p.42 (connector).
- VERIFIED: 22 GPIOs, 53 pads, 3V3 on pad 3, EN on pad 8 ("do not leave EN floating"). MINI DS p.10-11, Table 3-1.
- VERIFIED: Two TWAI controllers (ISO 11898-1, CAN 2.0, 11/29-bit IDs, 1 kbit/s to 1 Mbit/s, listen-only, self-test, single-shot). C6 DS p.4 (feature list), MINI DS p.21 (section 5.2.1.7).
- VERIFIED: TWAI has no fixed IO MUX pins: in the peripheral pin assignment table every GPIO appears for TWAI as P2 (free) or P3 (strapping/JTAG/USB/UART0 pins, use with caution). So TX/RX can sit on any GPIO through the GPIO matrix. C6 DS p.26-27 (Tables 2-10/2-11, priority definitions p.25-26).
- VERIFIED: USB Serial/JTAG on IO12 = USB_D- (pad 17), IO13 = USB_D+ (pad 18), fixed pins (IO MUX only). MINI DS p.11; C6 DS p.25-26 ("assigned only to priority 1 pins"). Two I2C controllers (main + LP). C6 DS p.51. LP I2C fixed on IO6 (SDA), IO7 (SCL); the main I2C controller goes through the GPIO matrix (C6 DS Table 2-11).
- VERIFIED: Strapping pins (chip names MTMS = module IO4 pad 9, MTDI = IO5 pad 10, GPIO8 = IO8 pad 22, GPIO9 = IO9 pad 23, GPIO15 = IO15 pad 20). Defaults: GPIO9 weak pull-up (1), GPIO8/MTMS/MTDI/GPIO15 floating. MINI DS p.12 Table 4-1.
  - Boot mode: SPI boot needs GPIO9 = 1 (GPIO8 any); joint download boot (USB-Serial-JTAG, UART, SDIO) needs GPIO8 = 1 and GPIO9 = 0. Table 4-3 p.13. Hold time after EN rises: 3 ms min, setup 0 (Table 4-2 p.13). Latched at reset, usable as GPIO afterwards.
  - GPIO8 also gates ROM message printing to UART0 (Table 4-5 p.14). MTMS/MTDI select SDIO edge only (Table 4-4), irrelevant to us. GPIO15 selects the JTAG source only when eFuse EFUSE_JTAG_SEL_ENABLE = 1; with default eFuses it is "ignored" (Table 4-7 p.15), and the pin has no internal pull ("must not be Hi-Z" if used for that).
- VERIFIED: Pin state at reset (QFN32 chip, C6 DS Table 2-2 p.17-18): IO0, IO1, IO14 have no setting at reset (high impedance); IO2, IO3 input-enabled; IO18-IO23 (SDIO pads) have weak pull-up at reset; IO6 (MTCK) pull-up only after reset; U0TXD (IO16) is an enabled output with pull-up after reset; GPIO9 pull-up; GPIO13 USB pull-up. Internal pull resistors typ 45 kohm (MINI DS p.26). Default drive 20 mA (40 mA on IO12/IO13).
- VERIFIED: Supply 3.0-3.6 V, abs max 3.6 V; "current delivered by external supply" min 0.5 A (MINI DS p.26 Tables 6-1, 6-2). Logic: VIH 0.75 VDD, VIL 0.25 VDD, IOH 40 mA / IOL 28 mA at PAD_DRIVER 3 (Table 6-3 p.26).
- VERIFIED: Current at 3.3 V, 25 C: Wi-Fi TX peak 251-382 mA (802.11ax MCS9 / 11b 1 Mbps), BLE TX 94-309 mA, RX 73-82 mA (Tables 6-4..6-6 p.27). Modem-sleep, CPU running 160 MHz: 27 mA (peripheral clocks off) to 38 mA (all on); CPU idle 17-28 mA; 80 MHz running 19-30 mA (Table 6-7 p.28). Light sleep 180 uA, deep sleep 7 uA (Table 6-8).
- PROPOSED: Radio unused and never initialised: expect about 20-40 mA typical at 80-160 MHz. This is an estimate from Table 6-7, not a measurement, and the datasheet gives no figure for "radio never started". Size the 3V3_D regulator for >= 500 mA output (the datasheet's own 0.5 A rule) even though the radio is off; budget total typ about 60 mA (ESP32 40 + CAN transceiver 10 + DAC 0.8 + ADC 0.15), so an LDO from the 5 V rail dissipates about 0.1 W typ (1.7 V x 60 mA). 3V3_D must be its own rail (architecture item 11).
- PROPOSED pin map (all on the three safest groups; avoids strapping IO4, IO5, IO8, IO9, IO15, USB IO12/13, UART0, JTAG IO6/IO7):
  - IO0 HV_EN, IO1 SHDN_N, IO14 LE_HYS (outputs): the only pads that are Hi-Z at reset, so external resistors fix the safe default state before firmware runs (HV off; SHDN_N and LE_HYS default per detector spec, UNRESOLVED). Do not use IO18-IO23 for outputs whose reset level matters (pull-up at reset).
  - IO2 I2C SDA, IO3 I2C SCL (4.7 kohm pull-ups to 3V3_D); IO18 TWAI_TX, IO19 TWAI_RX (pull-up at reset gives recessive TX); IO20 LOS (in), IO21 PGOOD (in), IO22 ADS1115 ALERT/RDY (in, optional), IO23 spare (MCP4728 RDY/BSY optional).
  - Boot/programming: IO9 to a pad/button to GND (download), IO8 10 kohm pull-up to 3V3 (needed =1 for download; MINI DS Figure 9-1 uses R8 10 kohm on IO8 and a "boot option" jumper on IO9, p.40), IO15 leave unconnected (default eFuses ignore it), IO4/IO5 unconnected.

## 2. CAN transceiver at 3.3 V

| Item | SN65HVD230 (SLOS346O) | TCAN334 (SLLSEQ7F) |
|---|---|---|
| Supply | 3.0-3.6 V (p.6); ICC 10 mA typ, 17 mA max, dominant or recessive, no load (p.7) | 3.0-3.6 V (p.5); recessive 3.5 mA (max col), dominant 55-60 mA at 60/50 ohm (p.6) |
| Package | SOIC-8 (D) only | SOIC-8 (D) or SOT-23-8 (DCN), p.1 |
| Mode pin | pin 8 Rs: 0 V = high speed, 10-100 kohm to GND = slope control, >= 0.75 VCC = standby (p.4, p.6); standby 370 uA typ | pin 8 STB and pin 5 SHDN, both internal pull-down, so floating = normal (p.4); standby 15 uA, shutdown 1 uA (p.6) |
| Loop delay | 70/115 ns typ/max (Rs 0), 105/175 (Rs 10 k), 535/920 (Rs 100 k) (p.8) | 100 / 135 ns typ/max (p.9) |
| Edge time (tr) | Rs 0: 25/50/100 ns; Rs 10 k: 80/120/160; Rs 100 k: 600/800/1200 (p.8) | 17 ns rise, 9 ns fall listed (p.9); no slew control |
| Common mode | -2 to +7 V (p.6) | +/-12 V (p.1) |
| Bus fault / ESD | abs max -4 to +16 V; thermal shutdown; +/-16 kV HBM bus pins (p.5-6); no dominant time-out | +/-14 V bus fault, HBM +/-25 kV, IEC 61000-4-2 contact +/-12 kV, TXD/RXD dominant time-outs, current limit (p.1, p.5) |
| Pinout (SOIC-8) | 1 D, 2 GND, 3 VCC, 4 R, 5 Vref (VCC/2 out), 6 CANL, 7 CANH, 8 RS (p.4) | 1 TXD, 2 GND, 3 VCC, 4 RXD, 5 SHDN, 6 CANL, 7 CANH, 8 STB (p.4) |

- PROPOSED recommendation: SN65HVD230D with Rs = 10 kohm to GND. Reason: edge rate is the real constraint in section 3 (SLLA270 stub rule), and only the HVD230 gives controlled slow edges; slow edges also reduce coupling of CAN edges into the TIA and the LVDS pair in the same cable (coupling not measured). The symbol and SOIC-8 footprint already exist in the lab library (AharoniLab_Interface, SN65HVD230D).
- PROPOSED: Use the SOIC-8 pad pattern so TCAN334D (also SOIC-8) is a drop-in fallback: pin 8 with 10 kohm to GND reads as STB = low (normal) on the TCAN334, pin 5 left open (Vref on the HVD230, internal pull-down SHDN on the TCAN334). Whether a 10 kohm pull-down is within the TCAN334 STB input spec is not checked (UNRESOLVED). If edges are acceptable, TCAN334 is the better part on every other row (fault protection, +/-12 V CM, lower current, active lifecycle).
- UNRESOLVED: lifecycle status of SN65HVD230 (the 2018 revision was the one TI served on 2026-10-08; "NRND" status not checked).

## 3. CAN bus physical layer for our star

- VERIFIED (SLLA270 p.5, Table 1): bus length vs signalling rate: 40 m at 1 Mbps, 100 m at 0.5, 200 m at 0.25, 500 m at 0.1, 1000 m at 0.05; typical twisted-pair delay 5 ns/m (p.5). Our total leg length (<= 3 m each, a star of maybe 10 m of cable in total) is far inside every row, so bus length does not limit the rate; the stub rule does.
- VERIFIED (SLLA270 p.9, section 4.8): stub-lines are unterminated; keep stub length <= 1/3 of the critical length, where critical length = driver transition time / (2 x 5 ns/m). ISO 11898 recommends <= 0.3 m at 1 Mbps. Worked example in the note: 50 ns edge gives 1.67 m; HVD230 with 10 kohm Rs (160 ns edge) gives 5.3 m (p.10).
- Hand calculation from the SN65HVD230 table (PROPOSED, applying that rule): Rs 0 (50 ns typ): 1.7 m; Rs 10 k (120 ns typ, 80 ns min): 4.0 m typ, 2.7 m worst case; Rs 100 k (800 ns typ, 600 min): 27 m typ, 20 m min. TCAN334 (17 ns): 0.57 m. So a 3 m leg fails the rule on the TCAN334 and at Rs = 0, and passes marginally at Rs = 10 k; Rs = 100 k passes with wide margin and still has <= 990 ns loop delay (p.8), tolerable at 8 us bit time.
- Why the rule is conservative here (PROPOSED reasoning): a 3 m leg has a 30 ns round trip, so reflections die within about 0.2 us, much earlier than the sample point of an 8 us bit. At 125 kbit/s, ringing is irrelevant to bit decisions; it matters for EMC and for coupling.
- PROPOSED bit rate: 125 kbit/s (8 us bit). It carries trims, monitors and ID with large margin, keeps loop delays (<1 us) a small fraction of the bit, and is well below the ESP32 TWAI limit of 1 Mbit/s. 250 kbit/s is the upper candidate; do not go to 1 Mbps. Verify on the bench at G1/G2.
- Termination options (star, N legs of 1-3 m joining at the FPGA end; N unknown, all PROPOSED):
  - A (recommended): one 120 ohm at the FPGA-end junction only; module ends open. SLLA270 p.4 advises against putting RL on a node because a disconnected node removes the termination; the FPGA end is the permanent point, modules are plug-in. DC load 120 ohm is lighter than ISO 11898's 60 ohm. The resulting dominant/recessive levels have to be checked on the bench (not simulated).
  - B: two 120 ohm in parallel (60 ohm) at the junction, if dominant level or recessive decay is poor with more legs.
  - C (rejected): 120 ohm at each module end. DC load is 120/N (40 ohm at N = 3, below the 50 ohm "high bus load" test of the TCAN334 p.6 and the HVD230 drive rating), and the termination leaves with the module.
  - D: Rt = 60 x N at each module end gives 60 ohm total DC load; unmatched by 1.5x for N = 3. Only if A and B both fail.
- Split termination: VERIFIED that SLLA270 p.8 (Figure 10, section 4.5.2) shows 2 x 60 ohm (+/-1 %) with a coupling capacitor, typically 4.7 nF, 3 dB at 1.1 Mbps, to filter common-mode noise and improve EMC, and that the resistors must be matched. PROPOSED: use it at the FPGA-end junction (2 x 60 ohm 1 % + 4.7 nF to ground; at 125 kbit/s the filter corner is not a concern). Advisable because the 50 Mbps LVDS pair and the nA-level optical receiver share the cable. HVD230 Vref (VCC/2) can replace the capacitor to ground (SLLA270 Figure 9); either is untested.
- VERIFIED (SLLA270 p.6, 4.3-4.4): ground the network at a single point (source side) and terminate shields with a short pig-tail to a ground pin at the connector. Unused wires: ground at alternate ends. Our supply return makes a single point impossible; PROPOSED use ground pins on both sides of each pair.
- UNRESOLVED: the FPGA-side CAN node. The ULX3S carries its own ESP32 (ulx3s-schematics-v317.pdf lists an ESP32 module, U9) but its TWAI pin availability, and whether a transceiver can attach, were not checked. Alternative: second ESP32-C6 adapter board next to the ULX3S.

## 4. Local I2C parts

MCP4728 (DS22187E):
- VERIFIED: I2C address = 1100 A2 A1 A0. There are no address pins: A2:A0 live in EEPROM, factory default 000, giving 0x60 (7-bit); reprogramming uses the "Write I2C address bits" command with the LDAC pin used as device select (section 5.3 p.30, Table 3-1 p.21, section 3.4 p.22). Point-to-point: every module has its own private I2C bus, so all modules can keep the identical default 0x60; no address programming and no LDAC address gymnastics are needed. ADS1115 is 0x48 with ADDR = GND, so no clash on the same bus.
- VERIFIED: At power-up the device loads EEPROM into input and output registers and drives the saved outputs immediately (p.23). Below VPOR (2 V typ) all circuits are disabled and there is no analog output (section 4.1). Factory EEPROM default (Table 4-2 p.24): all four channels VREF = 1 (internal 2.048 V), PD = 00 (normal mode), gain x1, code 0x000. So an unprogrammed part outputs 0 V on all channels, not Hi-Z.
- VERIFIED: Power-down modes PD1:PD0: 01 = 1 kohm, 10 = 100 kohm, 11 = 500 kohm to ground, "most circuits off" (p.5 spec, section 4.3 p.23). In normal mode the output impedance is about 1 ohm; load should be > 5 kohm and up to 1000 pF (section 4.3.1 p.23).
- VERIFIED: Vref options per channel: external = VDD (0 to VDD, gain fixed x1), or internal 2.048 V (2.007-2.089 V, 125 ppm/C below 0 C) with gain x1 (0-2.048 V) or x2 (0-4.096 V). 12-bit; supply 2.7-5.5 V; IDD about 0.8 mA, 1.4 mA max (p.1, p.5). At VDD 3.3 V and VREF = VDD, LSB = 3.3/4096 = 0.81 mV (calculated). Gain x2 above VDD cannot be reached (output cannot exceed the supply; inferred, not a datasheet statement).
- VERIFIED: LDAC low transfers input registers to outputs (all four channels at once); tied permanently low, outputs update at the last ACK (p.22). RDY/BSY is open drain, needs an external pull-up (about 100 kohm) and flags EEPROM write activity (Table 3-1 p.21, 3.5 p.22). PROPOSED: tie LDAC to GND, route RDY/BSY to IO23 (or just wait/poll), pull-up 100 kohm.
- PROPOSED: DAC_HV safety. Bias design 3.2 "Range": DAC = 0 V is the maximum bias trim (both trims at 0 V = 215 V, apd-bias-design.md), DAC Hi-Z at reset = 135.9 V, and the leg is 442 kohm + 10 kohm. The MCP4728 factory default (0 V, normal mode) and every power-down mode (output tied to ground through 1 k/100 k/500 k, effectively a low DAC voltage into a 452 kohm leg) all drive the bias HIGH. Only the pre-POR state (outputs disabled) is mid-range. Therefore:
  1. Never use the power-down modes on the DAC_HV channel; set VREF = VDD, PD = 00, and program EEPROM for DAC_HV to a high code (e.g. 0xFFF = 3.3 V = lowest bias, 55 V hardware floor) during production, so the power-on value is the safe end. Verify after programming with the MCP4728 Read command, which returns the EEPROM contents (DS22187E 5.6.9 p.37, Fig. 5-15 p.45); the General Call Read returns only the address bits (5.4.4 p.32-33) and cannot be used for this.
  2. Keep HV_EN (IO0) low by an external pull-down until firmware has read back DAC_HV and written the intended code; the bias design already allows EN/UVLO to be pulled low by a GPIO. This also covers a fresh or replaced MCP4728 (0 V default). An ESP32 reset without a DAC reset leaves the DAC at its last value, which is acceptable.
  3. Inverting the polarity of the leg would make 0 V the safe end but needs an inverting op-amp stage (extra part, noise on the bias node): UNRESOLVED, not recommended unless step 1 + 2 are judged insufficient. Daniel decides.
  4. The same question applies to DAC_GAIN and DAC_TH (default 0 V): the safe direction depends on the VGA and comparator polarity, UNRESOLVED.
- PROPOSED / calculated: with VREF = VDD, DAC_HV tracks 3V3_D. Bias slope about 18.5 V/V (61 V span / 3.3 V, from apd-bias-design.md), so a 1 % rail error at mid-scale is about 0.3 V of bias, compared with the +/-0.70 V thermistor budget. Use 3V3_D with <= 1 % accuracy or calibrate from HV_MON via the ADS1115. The internal 2.048 V reference is +/-2 % and cannot reach 3.3 V at x1.

ADS1115 (SBAS444E):
- VERIFIED: address from ADDR: GND 0x48, VDD 0x49, SDA 0x4A, SCL 0x4B (Table 7-2 p.20). Four single-ended or two differential inputs, 16 bit, 8-860 SPS, PGA FSR +/-6.144, 4.096, 2.048, 1.024, 0.512, 0.256 V (Table 7-1 p.4, FSR p.5), supply 2.0-5.5 V, 150 uA continuous, internal reference and oscillator, fast mode 400 kHz.
- VERIFIED: analog inputs must stay within GND - 0.3 V to VDD + 0.3 V (abs max p.2; recommended GND to VDD, p.5), regardless of PGA range: at VDD 3.3 V, FSR +/-4.096 V is usable only up to 3.3 V, so single-ended codes cover about 0 to 32767 (15 bit, LSB 125 uV at +/-4.096 V; 62.5 uV at +/-2.048 V). HV_MON, VSPAN, VG, VMID dividers must keep <= 3.3 V with fault margin. Input impedance at FSR +/-2.048 V is 6 Mohm common-mode / 4.9 Mohm differential, and 10/22 Mohm at +/-6.144 V (p.5), so source impedances above a few tens of kohm add gain error (not computed).
- VERIFIED: ALERT/RDY is open drain, needs a pull-up (Table 4-1 p.3); general-call reset 0x06 puts it in power-down (section 7.5.1.2). PROPOSED: not required for this design; poll or use single-shot mode; wire ALERT/RDY to IO22 only if conversion-ready interrupts are wanted.

## 5. Programming and bring-up

- VERIFIED: IO12/IO13 are the fixed USB Serial/JTAG pins; download via USB-Serial-JTAG needs GPIO8 = 1, GPIO9 = 0 at reset (MINI DS Table 4-3 p.13). UART0 download is also available on pads TXD0/RXD0 (U0TXD IO16, U0RXD IO17).
- PROPOSED: native USB: USB4105-GF-A-120 (USB-C, in the lab library) -> USBLC6-2SC6 (ESD, in the lab library) -> IO12/IO13 direct. The Espressif reference schematic leaves R6/R7 (series) and C7/C8 as TBD (MINI DS Figure 9-1 p.40); the values are UNRESOLVED (not given in the datasheet); consult the Hardware Design Guidelines. CC1/CC2 5.1 kohm pull-downs on the receptacle. VBUS OR-ing against the 5 V cable rail (diode or ideal-diode) so the 5 V cable and USB never back-feed each other: UNRESOLVED.
- PROPOSED: EN pad with 10 kohm pull-up + 1 uF to GND (the datasheet's recommended RC power-up delay, p.40) and a 2-pin pad/tact switch to GND; IO9 pad/tact switch to GND (BOOT). IO8 pull-up 10 kohm. A 4-pin UART pad (3V3, TXD0, RXD0, GND) as a fallback. Test pads for SDA, SCL, CAN_TX, CAN_RX.
- PROPOSED: no DTR/RTS auto-reset circuit. The ESP32-C6 USB Serial/JTAG controller handles reset into download mode over USB (esptool behaviour on the C-series chips; not documented in the two datasheets read, so confirm on the first board) and the EN/BOOT pads cover recovery.
- UNRESOLVED: antenna keepout. The -1 has a "Keepout Zone" along the antenna edge (MINI DS Figure 3-1 p.10, Figure 11-1 p.44 "Antenna Area"); numeric clearances are in the Hardware Design Guidelines (not read). Radio is unused, so use the -1U (no keepout, no antenna) if board space matters; its pad pattern is the same minus the antenna end (Figure 11-2). Choosing -1 vs -1U: PROPOSED -1U with the antenna connector left unpopulated; it saves 4.1 mm of board length. Note the lab footprint is for the -1 (Espressif_ESP32-C6-MINI-1); -1U would need a new library part (PR to the lab library).

## 6. Cable pinout (Wuerth 61201221621, 2 x 6, 2.54 mm; pins 1-2 are the first row)

| Row | Pin (odd) | Pin (even) | Why |
|---|---|---|---|
| 1 | 1 +5V | 2 +5V | two pins share the supply current; first row away from signals |
| 2 | 3 GND | 4 GND | power return, kept next to +5V |
| 3 | 5 LVDS_P | 6 LVDS_N | the 50 Mbps pair on adjacent pins (use a twisted pair or a pair-matched ribbon) |
| 4 | 7 GND | 8 GND | shield row between LVDS and CAN |
| 5 | 9 CAN_H | 10 CAN_L | CAN pair adjacent |
| 6 | 11 HOLD_N | 12 SPARE | level signal; spare to be wired to GND at both ends when unused |

- PROPOSED. The requested list (+5V x2, GND x3, LVDS x2, CAN x2, HOLD_N, one spare) has 11 items for 12 pins; the table adds a fourth GND (pin 8) so that each fast pair has ground on both sides. Daniel decides whether pin 12 becomes GND.
- Reasoning (PROPOSED, not measured): the LVDS return current is carried mainly by its own pair, but the bulk ground return must not share its only neighbour with the +5V pins, so supply return (pins 3, 4) and signal grounds (7, 8) are separated by the LVDS pair. CAN is a different case: SLLA270 p.5-6 stresses a common ground and a low common-mode offset, and the transceiver tolerates -2 to +7 V common mode (HVD230 p.6; +/-12 V for TCAN334 p.1), more than a few mV of IR drop on 3 GND pins. HOLD_N is the one single-ended line (3.3 V from the FPGA); filter it at the module if the hold timing allows (RC not sized). All grounds join in one plane on the module.
- UNRESOLVED: connector keying and shield on the cable; Wuerth 61201221621 is shrouded with a polarising notch; a cable ground/drain wire to pin 7/8 at the FPGA side only follows SLLA270 4.3.

## 7. Open items

1. UNRESOLVED: FPGA-end CAN node (ULX3S on-board ESP32 pins vs separate adapter), and the termination plus 4.7 nF split-capacitor board at that end (section 3).
2. UNRESOLVED: bench check of recommended 125 kbit/s with N legs of 1-3 m, Rs = 10 kohm vs 100 kohm (G1/G2); crosstalk from CAN edges into LVDS and TIA, not measured.
3. UNRESOLVED: reset defaults of SHDN_N, LE_HYS, HV_EN pull resistors; DAC_GAIN / DAC_TH safe default direction; whether Daniel prefers the inverting DAC_HV leg (section 4).
4. UNRESOLVED: MCP4728 factory part is 0 V on all channels: production step must program EEPROM and read back before HV_EN is released.
5. UNRESOLVED: TCAN334 STB tolerance of the 10 kohm pull-down; SN65HVD230 lifecycle.
6. UNRESOLVED: USB series resistors/caps, VBUS back-feed, -1 vs -1U and the antenna keepout numbers (read the ESP32-C6 Hardware Design Guidelines); ESP32-C6-MINI-1U lab part missing.
7. UNRESOLVED: measured 3V3_D current with firmware running and no radio (estimate only, section 1); regulator part choice.
8. UNRESOLVED: lab library symbols for TCAN334 (not present) and the MCP4728T-E_UN / ADS1115IDGSR pin names; MCP4728 and ADS1115 use 3V3_D bus pull-ups sized for 400 kHz with the cable-free local bus (not computed).
