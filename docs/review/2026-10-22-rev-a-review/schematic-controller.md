# Review: Controller sheet and its cross-sheet nets (Rev A, 2026-10-22)

Scope: controller.kicad_sch, netlist.xml pin->net, MCP4728/ADS1115/SN65HVD230/ESP32-C6(-MINI-1) datasheets, power.md and apd-bias-design.md for the HV path, firmware/esp32 board_pins.h and README for cross-check. Read-only; nothing measured or simulated.

## Executive summary
1. No pin-level wiring errors found on U60-U64: every ESP32 pad, strapping pull, USB pair, I2C address, CAN pin and ADC input checked against datasheets and netlist is correct (list at the end).
2. MAJOR: the MCP4728 does NOT power up Hi-Z; its factory EEPROM is code 0 on every channel (DS22187E Table 4-2 p.24). DAC_HV = 0 V is the MAXIMUM-bias end of the hardware range (about 166 V with the pot leg DNP, by my arithmetic), but apd-bias-design.md s.3.2 still says "DAC pin Hi-Z at reset -> 135.9 V". Firmware knows this; the hardware and the J1 bench path do not protect it.
3. MAJOR (conflict with hard rule 1 as worded): with HV_DIS pulled up (R33) and J1 DNP, an unprogrammed ESP32 gives NO APD bias, so the module does not "decode with the ESP32 unprogrammed". Closing that needs J1 fitted AND a safe DAC_HV default, which today needs a one-time ESP32 provisioning of the MCP4728 EEPROM.
4. MINOR items: DAC_TH default 0 V = about -16 mV comparator offset; C200 has both pins on GND; U4 300 mA LDO vs the module's 0.5 A supply requirement; R199 at the datasheet 100 k limit; some doc rot.

## MAJOR

### M1. Blank MCP4728 drives DAC_HV = 0 V = highest bias; docs assume Hi-Z
- Where: U62 OUTC -> R212 100R -> DAC_HV -> Power sheet R13 10k -> R14 442k -> FBX (/Power/FBX); firmware/esp32 README s.4 vs docs/calculations/apd-bias-design.md s.3.2.
- Saw: MCP4728 Table 4-2 (DS22187E p.24) factory EEPROM, all channels: VREF = 1 (internal 2.048 V), PD = 00, GX = 0, data = 0x000. Section 4.2 p.23: on POR the EEPROM is loaded into the input and output registers and "the analog output voltage of each channel is available immediately". So a blank part outputs 0 V on OUTA-D (VERIFIED, datasheet text). apd-bias-design.md line 82 says "DAC pin Hi-Z at reset -> 135.9 V" (that is a prior-DAC assumption, wrong for this part).
- Effect: using the doc's own divider equation (Vfb 1.6 V, Rt 8.2 M, Rb 96.6 k at 25 C, Rd 442 k + R13 10 k): DAC floating gives about 137 V (doc says 135.9); DAC at 0 V gives 1.6 x (1 + 8200/79.6) = about 166 V (my arithmetic, PROPOSED, not simulated; pot leg RV1/R15 is DNP in production per the doc). The doc's own "DAC alone +/-30.6 V" is consistent. 166 V is above the S12023-10 typical VBR of 150 V (apd-selection.md via firmware README); the clamp Q1/Q2 limits current to about 150 uA but the TIA would saturate and the APD sits in breakdown.
- When it bites: (a) J1 "HV FORCE ON" fitted with a blank/replaced MCP4728 (power.md says "set the DAC first", but with an unprogrammed ESP32 nobody can); (b) MCP4728 brown-out/POR while HV_DIS is low (3V3_D glitch resets the DAC to its EEPROM value; the ESP32 may not reset, so firmware keeps HV on); (c) EEPROM never provisioned. Firmware handles the normal path well (README s.4 steps 4-5: verify EEPROM, write 0xFFF, HV_DIS low only after read-back). Hardware does not.
- Fix (PROPOSED): (1) provision EEPROM C = 0xFFF, VREF = VDD at first power-up (firmware already has mcp4728_write_eeprom_defaults) and make that a mandatory factory step in the bring-up gates; (2) correct apd-bias-design.md line 82 and module-controller.md s.1 to say 0 V; (3) consider a series option on the DAC leg (R13 or R14 as a DNP-able 0R) plus fitting the pot leg RV1/R15, so a "no-ESP32 bench" build gets a resistor-set bias independent of the DAC (this is what decision 11/12 text "manual trimmers" / "resistor-set bias" implies); (4) firmware: treat MCP4728 POR status (Read command POR bit, DS p.45 Fig 5-15) as a fault that forces HV_DIS high.
- Confidence: HIGH on the DAC default (datasheet); MED on 166 V (arithmetic from doc values).

### M2. "Decodes with the ESP32 unprogrammed" is not true as built (hard rule 1 / decision 11-12 wording)
- Where: Power Q3/R33/R34/J1 (HV_DIS), controller.md "Unprogrammed ESP32" paragraph, CLAUDE.md hard rule 1, decision 12 ("module runs with the ESP32 unprogrammed at a fixed M and 20k").
- Saw: R33 100k pulls the Q3 gate to 3V3_D, Q3 pulls LT8365 EN/UVLO low: HV OFF when IO0 is Hi-Z (VERIFIED against C6 DS Table 2-1: IO0 no setting at reset; netlist /HV_DIS = U60 pad 12 + R34 only). J1 (gate to GND) is DNP. controller.md itself says "an unprogrammed module has NO APD bias; bench jumper J1 forces it on". With J1 fitted the DAC is at its blank default (M1: highest bias).
- Why it matters: the fixed-gain slicer chain is analog, but without bias the detector produces nothing; the "analog-first, ESP32 only trims" claim holds for the signal path, not for the bias enable. This is a deliberate safety choice (HV off by default), so I do not recommend reversing it; but the authority text should say so, or the design should offer a real unprogrammed path (M1 fix 3 plus J1 fitted).
- Fix: either (a) amend decision 12 / hard-rule wording: "slicing is analog; APD bias needs a provisioned ESP32 (or J1 + trimmer build)"; or (b) implement M1 fix 3 and fit J1 on a bench variant. Put under QUESTIONS for Daniel if you do not want to touch the rule. Confidence HIGH on the facts, the policy call is Daniel's.

## MINOR

### m1. DAC_TH default 0 V shifts the comparator threshold by about -16 mV
- Where: U62 OUTB -> R211 100R + C202 -> DAC_TH -> Slicer R85 100k -> SDET_N, with R84 1k from VCM_REF (slicer.md; netlist: R85 pin 2 = DAC_TH).
- Saw: blank MCP4728 gives DAC_TH = 0 V; the divider R84:R85 puts SDET_N at 1.65 V x 100/101 = about 1.634 V, i.e. -16 mV from baseline (arithmetic, ignoring R86 10k to the ADC node; PROPOSED). Against the 105-175 mVpp comparator input of decision 12 this is a 10-15 % duty/eye-centre shift, larger near sensitivity. controller.md already lists "DAC_TH safe default direction" as UNRESOLVED.
- Fix: same EEPROM provisioning as M1 (B = 0x800, firmware default already). For a truly unprovisioned module nothing else helps; accept and document the -16 mV. Confidence MED.

### m2. C200 (AIN3 filter cap) has both pins on GND
- Netlist: C200 pin1 = GND, pin2 = GND; /Controller/ADC_AIN3 contains only U63 pin 7 and R209 pin 1. Doc says AIN3 is "tied to GND through its RC". Harmless electrically (AIN3 is already 0 V through R209 10k) but it is an ERC-invisible miswire (cap shorted out of circuit) and C200 is a wasted part. Fix: wire C200 pin 1 to ADC_AIN3 (or delete C200/R209 and tie AIN3 to GND). HIGH.

### m3. 3V3_D LDO (TPS7A2033, 300 mA) vs ESP32-C6 supply requirement 0.5 A
- ESP32-C6 datasheet v1.5 Table 6-? "Current delivered by external power supply" IVDD min 0.5 A (VERIFIED, text of recommended operating conditions); U4 is rated 300 mA; power.md already notes Wi-Fi TX 251-382 mA exceeds it and requires the radio never be initialised (firmware README line 5 agrees). With radio off the load is about 60 mA (estimate, not measured). Risk is limited to someone enabling RF/BLE or a future OTA stack. Fix: keep the radio-off rule in firmware CI (CONFIG_ESP_WIFI/BT disabled), or fit a larger LDO footprint option in Rev B. MED.

### m4. R199 = 100k sits exactly at the SN65HVD230 maximum wave-shaping resistance
- SLOS346O Rs recommended operating range 0..100 kOhm (VERIFIED, p.5 recommended operating conditions text "Wave-shaping resistance, Rs 0 100 kΩ"); a 1 % 100k part can be 101 kOhm. Rise 600/800/1200 ns at 100k (p.8). Fix: use 91k or 82k (or confirm tolerance). Slew choice itself is fine at 125 kbit/s. MED.

### m5. RS has no GPIO, so "RS high (standby)" in the firmware/spec text cannot be used
- rev-a-sheet-specs.md s.7 and controller.md say "CAN TX stays silent (RS high or listen-only)". Netlist: U64 pin 8 only goes to R199 to GND. Only TWAI listen-only is available; confirm the transceiver's recessive state does not load the USB SS RX pair of a foreign host (HVD230 bus pins are Hi-Z/biased when D = high, SLOS346O p.1-2 summary, not re-read in detail). Fix: edit the text, optionally add an RS option to a free GPIO (IO21 is free). MED.

### m6. Floating GPIOs: IO14 (R205 DNP), IO15, IO21
- Pads 19/20/27 have no external pull. Inputs enabled by default (C6 DS Table 2-1: IO15 IE) so they float until firmware sets pulls; harmless to function, adds minor current. IO15 is a strapping pin whose only effect is the JTAG source when EFUSE_JTAG_SEL_ENABLE is burnt (MINI-1 DS s.4 p.12, default eFuse 0, VERIFIED), so leaving it open is fine. Fix: firmware sets pull-downs/outputs on 14/15/21. LOW.

### m7. Documentation inconsistencies found in the controller scope
- docs/research/module-controller.md s.? line 69: "Keep HV_EN (IO0) low by an external pull-down" is the opposite polarity of what was built (HV_DIS high = off, pull-up R33). Obsolete; mark superseded.
- apd-bias-design.md line 82 Hi-Z statement (see M1).
- firmware/esp32/README.md line 29 quotes "DAC alone spans 61 V ... 104 V with the trimmer at its default" while the trimmer leg is DNP; state both builds.
LOW.

### m8. EN net is routed about 50 mm of track length (DRC evidence + pcbnew on a copy)
- /Controller/EN: 20 track segments, 49.8 mm total, 0.05 mm dangling stub at (120.675, 84.7) (the track_dangling item); R190/C190/SW60 are at x about 65-71 mm and U60 pad 8 at x 37 mm. A long high-impedance reset line near the J50 end picks up noise (the module datasheet does not specify, Espressif's guideline is to keep it short, not re-read); consider moving C190 next to U60 pad 8 (the RC works at either end). LOW, layout item.

## QUESTIONS / UNRESOLVED
- Q1. Antenna keep-out: U60 is on B.Cu at (43.0, 38.7) with the antenna end at the front edge; ANT_KEEPOUT 35.3-50.7 x 44.2-50 (README line 92). The module datasheet's side/forward clearance was not checked by me; J51 pins start 3.65 mm from the keep-out edge and TP62/63 are close. Check MINI-1 datasheet s.9/Fig 9-2 and HDG antenna section (UNRESOLVED, PCB reviewer's scope).
- Q2. Power-up ordering of HV: if 5V rises before 3V3_D, Q3 gate floats low for the LDO start-up time and EN/UVLO could cross threshold. My estimate (PROPOSED): TPS7A20 starts at about 1.5 V in, EN/UVLO divider reaches threshold only at 5V >= 3.15 V (power.md table), so the gate is pulled up first; not verified against the DMN2056U Vgs(th) or a simulation. power.md already marks it UNRESOLVED.
- Q3. USBLC6-2SC6 pin-5 (VBUS) clamp behaviour and ESP32 USB D+ "fluctuates at power-up" (HDG s.1.3.13 p.15) when the module powers up attached to a host; no datasheet for USBLC6 is in docs/datasheets, so not checked. Already UNRESOLVED in controller.md.
- Q4. 22 ohm series on D+/D-: HDG says initial 22/33 ohm (VERIFIED p.15); nothing says the C6 integrates them, so keeping 22R is reasonable; effect with USBLC6 untested.

## Checked and found correct
- U60 pin map vs MINI-1 DS v1.5 Table 3-1 (p.10-11): all 31 signal pads match the netlist (IO2 pad5, IO3 6, EN 8, IO4 9, IO5 10, IO0 12, IO1 13, IO6 15, IO7 16, IO12/USB_D- 17, IO13/USB_D+ 18, IO14 19, IO15 20, IO8 22, IO9 23, IO18 24, IO19 25, IO20 26, IO21 27, IO22 28, IO23 29, RXD0 30, TXD0 31); NC pads 4/7/21/32-35 unconnected. VERIFIED.
- Strapping: GPIO9 weak pull-up default + R191 10k + SW61 to GND; GPIO8 R192 10k to 3V3_D (needed for download: GPIO8 = 1, GPIO9 = 0, MINI-1 Table 4-3 p.13); IO4/IO5 strapping only selects SDIO edges (Table 4-4); IO15 NC fine. A plain power-up boots SPI flash; BOOT+RESET gives download. VERIFIED. No GPIO used for I/O conflicts with the internal flash (MINI-1-N4 exposes none of GPIO24-30).
- EN: R190 10k + C190 1u (the datasheet-recommended RC, MINI-1 DS p.40), SW60 to GND, TP60. CHIP_PU not floating. VERIFIED.
- 3V3 decoupling at pad 3: C191 10u + C192 100n (placed within 1.5 mm of pads, PCB). OK.
- USB: D-/D+ on GPIO12/13 native Serial/JTAG (no bridge), U61 pins 1/3 (J50 side) and 6/4 (chip side) correct for USBLC6-2SC6, R193/R194 22R between U61 and U60 pads 18/17, D+ not swapped (pad 17 = USB_E_DN, 18 = USB_E_DP). Blank-flash USB download is documented (HDG "waiting for download", p.30). VERIFIED / decision 13 requirement met in schematic.
- Default states with ESP32 unprogrammed/in reset: HV_DIS high via R33 -> HV OFF (Q3 on pulls EN/UVLO low); TIA_CTRL: IO20 has WPU at reset (SDIO pad, C6 DS Table 2-1) plus R57 100k to 3V3, OPA857 CTRL high = 20k (OPA857 p.4 pin table: logic 1 = 20 kOhm); JP10 open by default; SHDN_N: R81 10k pull-up, IO1 Hi-Z at reset, comparator on; LE_HYS: R205 DNP, LE/HYS left open; CAN_TX IO19 WPU at reset = recessive. VERIFIED.
- I2C: MCP4728 0x60 (factory A2:A0 = 000, DS22187E p.24/Sec 5.3), ADS1115 ADDR = GND = 0x48 (SBAS444E Table 7-2): no collision. 4.7k pull-ups to 3V3_D shared (TP64/65 on the lines); 400 kHz rise time about 0.85 x 4.7k x C, i.e. below 300 ns up to about 75 pF (arithmetic, PROPOSED). LDAC R197 10k pull-up (firmware holds high, UDAC = 0 writes), RDY R198 pull-up on an open-drain output. Pin maps of U62/U63/U64 match their datasheets. VERIFIED.
- ADS1115 inputs (3V3_D supply, abs input must be GND-0.3..VDD+0.3, p.2/p.4 VERIFIED): HV_MON = HV/101 = 2.18 V at 220 V; RSSI is an OPA2320 output on 3V3 (U30 pin 8 = 3V3), so cannot exceed the rail; VTH_MON about 1.65 V; each has 10k + 10n. Source impedance of HV_MON is about 100 k, versus the ADS1115 15 MOhm input impedance at +/-4.096 V FSR (p.5 table), about 0.7 % deterministic gain error that HV calibration absorbs (arithmetic, PROPOSED). ALERT/RDY NC is acceptable for an open-drain output.
- CAN: U64 pins D1, GND2, VCC3 (3V3_D), R4, Vref5 NC, CANL6, CANH7, RS8 correct; RS to GND via R199 = slope control (SLOS346O p.5/p.8, VERIFIED); termination is DNP on the module (R182/R183/C180 DNP, 60.4R split) and belongs at the FPGA end (SLLA270 p.4/p.8; module-controller.md section 3 option A), consistent with the star topology; two RX pairs bused. TXD = IO19, RXD = IO18 via GPIO matrix.
- CC1_SENSE/CC2_SENSE: 100k/100k taps keep the pin below 3.3 V even with 5.5 V VCONN (2.75 V) and typical Rp levels (below about 1.1 V); GPIO4/5 are ADC1_CH4/5 (MINI-1 Table 3-1). AUX: IO7 -> R204 1k -> AUX -> R186 1k -> SBU. J51: 1 GND, 2/3 LVDS_DBG, 4 CAN_P, 5 CAN_N, 6 AUX, matches decision 14 text. D60 + R203 1k on IO23 (WPU at reset gives a dim LED, fine). Footprints consistent with values (0603 R/C, C191 0805, C190 0603, SOT-23-6, SOIC-8, MSOP-10, PTS810).
- Cross-check of firmware board_pins.h against the netlist: all GPIO numbers match; DAC channel map B = TH, C = HV; firmware verifies the MCP4728 EEPROM and only then releases HV_DIS.
