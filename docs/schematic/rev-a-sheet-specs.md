# Rev A schematic specifications, sheet by sheet

Status labels: VERIFIED (cited datasheet or measurement), PROPOSED (design intent), UNRESOLVED (open). Nothing on this page is measured or simulated. These specs are the brief for populating `hardware/pcb/receiver-module/*.kicad_sch`; the as-built notes live in `docs/schematic/<sheet>.md`. Authority: `docs/decision-log.md` (14 standing corrections), `docs/calculations/apd-bias-design.md`, `docs/research/ulx3s-lvds-input.md`.

Conventions for every sheet:
- Symbols only from the lab library (`${AHARONI_LAB_KICAD_LIB}`); generic R/C/L get an explicit footprint. Default passives 0603 (`R_0603_1608Metric_N`, `C_0603_1608Metric_N`); 0402 only for local decoupling at fast ICs; HV parts 1206/1210 as noted.
- GND is a global label on every sheet. Rails arrive as hierarchical labels (+5V_CABLE on Power, 3V3, +3V7, -3V7, 5V_A, APD_BIAS).
- Nets at or above 50 V are prefixed `HV_` (plus `APD_BIAS`); the project netclass `HV` (set in the .kicad_pro by the orchestrator) uses a 1.0 mm clearance.
- Every sheet carries a text block "Design intent" with the status labels, and every value that comes from a datasheet or the calculation docs cites it in the as-built note.
- Reference designator ranges (so sheets never collide): Power U1-U9/R1-R49 (R35-R42 now used by U5, see 1.1; R43-R44 free)/C1-C49 (C32-C34 used by U5)/D1-D9/L1-L9/Q1-Q9/J1-J2/RV1-RV2/TH1/FB1-FB2; Front end U10-U19/R50-R79/C50-C79/D10-D19/JP10-JP19/TP10-TP19; Slicer U20-U29/R80-R99/C80-C99/TP20-TP29; Monitor U30-U39/R100-R149/C100-C129/D30-D39/JP30-JP39/RV30-RV39/TP30-TP39; Connector J50-J59/R180-R189/C180-C189/U50/TP50-TP59; Controller U60-U69/R190-R229 (R215, R216 VBUS sense)/C190-C219 (C205-C207 VBUS sense and DNP D+/D- caps)/D60-D69/J60-J61/SW60-SW61 (RESET, BOOT)/TP60-TP69.

Hierarchical nets (revision 3): rails `3V3`, `3V3_D`, `APD_BIAS` (Power -> users); `DAC_HV`, `HV_DIS` (Controller -> Power); `HV_MON` (Power -> Controller, Connector); `TIA_CTRL` (Controller -> Front End); `TIA_TAP` (Front End -> Monitor, RSSI pick-off); `SDET_P`, `SDET_N` (Front End -> Slicer); `VCM_REF` (Monitor -> Front End, Slicer); `RSSI` (Monitor -> Controller, Connector); `DAC_TH` (Controller -> Slicer); `VTH_MON` (Slicer -> Controller); `SHDN_N`, `LE_HYS` (Controller -> Slicer); `LVDS_P/N` (Slicer -> Connector); `CAN_H`, `CAN_L`, `AUX`, `AUX2` (Controller <-> Connector); `+5V_CABLE` (Connector -> Power, mux priority input; renamed from `+5V` in revision 3); `VBUS` (Controller -> Power, mux fallback input); `PWR_SRC` (Power -> Controller, mux status). `+5V` is now the internal merged rail (U5 OUT) inside the Power sheet and is not a hierarchical net. Root: PWR_FLAG `#FLG04` moves from Power.+5V to the `+5V_CABLE` net; `#FLG60` on VBUS stays inside the Controller sheet.

**Revision 3 (decision 13, 2026-10-09):** USB-standalone power and programming: TPS2121 source mux U5 on the Power sheet (cable priority, USB-C fallback), RESET/BOOT switches, 22 ohm D+/D- series resistors, VBUS_SENSE on IO4 and PWR_SRC on IO5. `+5V` becomes `+5V_CABLE` on the cable side; `+5V` remains the merged internal rail (mux OUT). Facts and citations: docs/research/usb-standalone-power.md. All of it PROPOSED, nothing simulated or measured.

**Revision 2 (decision 12, 2026-10-08):** the VCA821 VGA, AGC loop, detector coupon, +/-3.7 V and 5V_A rails are removed; the chain is TIA -> AC coupling -> OPA855 x7 -> low-pass -> AC coupling to a 1.65 V baseline -> TLV3605. The Control sheet becomes the Monitor sheet (reference and RSSI); the Detector sheet is deleted. Sections 2, 3, 4 and 7 below are rewritten; section 5 is gone. Facts: docs/research/post-amp-slicer.md.

**Revision 1 (decision 11):** the external-MCU header is replaced by an on-module ESP32-C6 controller sheet (section 7) with on-board I2C DAC/ADC, a CAN link in the module cable (section 6), a 3V3_D rail (section 1.5) and an HV disable gate (section 1.4). Facts and citations: docs/research/module-controller.md.

---

## 1. Power sheet (`power.kicad_sch`)

Pins: in +5V_CABLE, VBUS, DAC_HV, HV_DIS; out 3V3, 3V3_D, APD_BIAS, HV_MON, PWR_SRC. (Revision 2: the LM27762 +/-3V7 block, the 5V_A bead/caps, PGOOD_VGA and TP1 are removed.)

### 1.1 Input: source mux U5 (TPS2121RUXR)
- U5 AharoniLab_Power:TPS2121RUXR, footprint AharoniLab_Package_DFN_QFN:RUX0012A. IN1 (pin 7) = +5V_CABLE (system cable, priority). IN2 (pin 2) = VBUS (USB-C, fallback). OUT (pins 1 and 8) = +5V, the internal merged rail used by U1, U3 (via the L2 pi filter) and U4. GND pin 12. CP2 (pin 3) = GND. Symbol is `Validated: No` in the lab library; first use here is its validation.
- Priority: PR1 (pin 6) from +5V_CABLE through R35 294k / R36 100k (1 %, 0603): cable selected above about 3.98-4.33 V rising, dropped below about 3.90-4.10 V. PROPOSED (TPS2121 SLVSEA3F p.7-8 VREF 0.99-1.10 V, p.18 Table 9-3). UNRESOLVED: chatter near the threshold with a real ULX3S rail (hysteresis only about 0.08 V on the rail).
- Overvoltage: OV1 (pin 5) from +5V_CABLE through R39 464k / R40 100k; OV2 (pin 4) from VBUS through R41 464k / R42 100k (1 %, 0603); trip about 5.6-6.2 V, below the TPS799 7.0 V abs max (SBVS056L p.4); OV pin range 0-5.5 V (SLVSEA3F p.6). PROPOSED.
- ST (pin 9): R37 10k pull-up to 3V3_D, output net PWR_SRC (hierarchical output): high = cable (or OUT Hi-Z), low = USB. VERIFIED behaviour SLVSEA3F p.18; pull-up range 6-20k p.6.
- ILM (pin 10): R38 100k to GND (maximum RILM; ILM = 65.2/RILM^0.861 = 1.24 A typ, SLVSEA3F p.13). UNRESOLVED: the datasheet table has no 100k row (1.5 A typ at 80k, p.8), so the minimum limit at 100k is probably just above 1 A but is not stated. SS (pin 11): C32 220 nF X7R 10 V 0603 to GND (about 350-400 V/s, p.13 Table 9-1 scaled, estimate). PROPOSED; first-plug settling time (tSET, no formula, p.12) and inrush UNRESOLVED until measured. Role of the limit: protects U5 and the cable and closes `apd-bias-design.md` section 7 item 10; it does NOT enforce the 0.5 A USB budget (the laptop port does).
- Caps: C33 4.7 uF 10 V X5R 0805 on +5V_CABLE at IN1, C34 4.7 uF 10 V X5R 0805 on VBUS at IN2, as close to the pins as possible (TI recommends a larger input capacitor to damp cable ringing, SLVSEA3F p.33). UNRESOLVED: USB attach capacitance limit not checked against the USB spec. C1 10 uF 0805 X7R 10 V and C2 100 nF 0603 stay on the +5V (OUT) rail; the L2 pi filter into the LT8365 is fed from +5V (U5 OUT). No TVS (24 V abs max, p.6; ring on a hot-plug estimated by scaling TI's plot, p.32: PROPOSED). No other reverse protection in Rev A (keyed connector). PROPOSED.
- No back-feed: fast reverse-current blocking and <= 1 uA leakage (SLVSEA3F p.7, p.15) mean neither source is back-driven. Both present: cable powers, USB carries data only. J50 pins 1,2 are +5V_CABLE. PWR_FLAG on +5V_CABLE sits on the root (see hierarchical nets); +5V (U5 OUT, power_out) needs no flag. Source loss: switchover to USB in about 100 us typ (tSW, p.7); hold-up droop about 1 V estimated with about 20 uF effective, PROPOSED, not measured.
- Budget: worst case about 0.19 A (0.24 A with 25 % margin) from +5V, against 0.5 A USB default and U5 ILM 1.24 A typ (docs/research/usb-standalone-power.md section 1.5; datasheet maxima plus an assumed 70 % LT8365 efficiency, not measured). Radio must stay disabled (Wi-Fi TX peaks 251-382 mA would break the budget). UNRESOLVED: whether a bus-powered hub or unconfigured device is held to 100 mA; document "use a laptop root port or a powered hub".

### 1.2 3V3: TPS79901DDCT (U1)
- IN = +5V with 1 uF 0603 at the pin; EN tied to IN; GND.
- FB divider: VOUT = VFB x (1 + R1/R2), VFB 1.193 V typ (TPS799 SBVS056L). R1 17.8 k, R2 10.0 k, 1 %, 0603 -> 3.316 V. CFB 1 nF across R1 (value UNRESOLVED, see power.md). OUT = 3V3: 2 x 4.7 uF 0805 X7R 10 V.
- Load estimate: OPA857 26.8 mA max + OPA855 (SBOS622D, check Iq at 3.3 V) + TLV3605 17.5 mA max + OPA2320 ~2 mA ~ 65 mA. PROPOSED.

### 1.5 3V3_D digital rail: TPS7A2033PDBV (U4)
- As built: IN = +5V with 1 uF; OUT = 3V3_D with 10 uF 0805 + 1 uF; EN tied to IN. Radio must stay disabled (300 mA LDO). R37 ST pull-up returns to 3V3_D. PROPOSED.

### 1.4 APD bias: LT8365EMSE (U3)
- As built per `docs/calculations/apd-bias-design.md` sections 3.2 and 4, with the HV disable gate (Q3 on EN/UVLO, gate pulled up to 3V3_D, driven by HV_DIS, J1 "HV FORCE ON" DNP jumper) and the HV_MON divider. Unchanged in revision 2; input now from +5V (U5 OUT). Revision 3: USB-alone, HV_DIS default-off and the DAC_HV safe-end rule are unchanged; firmware starts HV at the low-bias end of DAC_HV in steps, watching HV_MON and supply sag (a faulted HV start can trip a USB port; PROPOSED). The LT8365 EN/UVLO (R22/R23, rising 3.15-3.80 V) does not guard against USB sag in the legal range.

---

## 2. Front end (`frontend.kicad_sch`)

Pins: in APD_BIAS, 3V3, TIA_CTRL, VCM_REF; out SDET_P, SDET_N, TIA_TAP.
- Stage 2 filter: R50 10 k 1206 (>= 200 V) from APD_BIAS to `HV_K`; C50 10 nF >= 400 V C0G 1210 from HV_K to GND, at the cathode. D10 S12023-10: 1 K = HV_K, 3 A = `TIA_IN`, 2 CASE = GND. D11 FDS010 (DNP) on the same nets. Standing correction 2.
- U10 OPA857 (SBOS630D): IN (15) = TIA_IN; VS+ (9, 10, 11) = 3V3 with 2 x 100 nF 0402 + 1 uF 0603; GND pins and PAD = GND; Test_SD (13) = GND; Test_IN (14) = 3V3; NC (16) no_connect. CTRL (2) = hierarchical input `TIA_CTRL` from the ESP32 (logic 1 = 20 k, 0 = 5 k; VIH 2 V) with R57 100 k pull-up to 3V3 so an unprogrammed ESP32 gives 20 k; JP10 SolderJumper_3 (common = CTRL, sides 3V3 / GND) stays for bench forcing, open by default. OUT (8) = `TIA_OUT`, OUTN (5) = `TIA_REF`.
- RSSI pick-off: `TIA_TAP` = TIA_OUT through R58 1 k (so the Monitor sheet's peak detector loads the TIA lightly); hierarchical output.
- Coupling into the post-amp (research doc section 4): C51 100 nF from TIA_OUT to `PA_IN`; R51 1 k from PA_IN to VCM_REF (corner 1.6 kHz; the research asks for >= 10 us time constant: 1 k x 100 nF = 100 us, fine). TIA_REF (OUTN) is left unused except for TP12 (single-ended post-amp; the differential option is noted on the sheet as UNRESOLVED).
- U11 OPA855IDSGR (SBOS622D; library branch add-opa855): non-inverting gain 7: IN+ = PA_IN; RF R53 301 ohm from OUT to IN-, RG R54 49.9 ohm from IN- to `PA_REF` where PA_REF = VCM_REF decoupled by C53 1 uF (so the gain is referenced to the baseline, not GND; the stage output idles at VCM_REF); check the datasheet's recommended RF/RG for G = 7 and use those values if they differ, citing the page. VS+ = 3V3 with 100 nF 0402 + 1 uF 0603 at the pin; VS- = GND; PD (power-down) pin: check polarity in the datasheet and tie it to the "enabled" level (via R 10 k) ; exposed pad per datasheet. OUT = `PA_OUT`. Place a 0 ohm DNP bypass R55 from PA_IN to PA_OUT? No: keep it simple, no bypass.
- Low-pass: R56 49.9 ohm from PA_OUT to `LPF_OUT`, C54 33 pF C0G to GND (corner ~97 MHz; values PROPOSED, the research asks for 60-80 MHz: use R 49.9 + C 47 pF = 68 MHz). Then the comparator coupling: C55 100 nF LPF_OUT -> `SDET_P`; R59 1 k SDET_P -> VCM_REF; the comparator's other input `SDET_N` = VCM_REF through R60 1 k (matched) with C56 100 nF from SDET_N to GND? No: SDET_N must carry the threshold trim, which lives on the Slicer sheet; so Front End outputs only SDET_P and the Slicer builds SDET_N. Hierarchical outputs SDET_P (signal, baseline VCM_REF) and TIA_TAP.
- Test points: TP10 PA_OUT, TP11 SDET_P, TP12 TIA_REF; no HV test points.
- Text: design intent (decision 12), clip thresholds (9 uA pp at 20k, 36 uA at 5k, TIA saturation 60 uA), OPA857 at 6 pF UNRESOLVED, HV keep-out, APD polarity.

---

## 3. Slicer (`slicer.kicad_sch`)

Pins: in SDET_P, VCM_REF, DAC_TH, 3V3, SHDN_N, LE_HYS; out LVDS_P, LVDS_N, VTH_MON.
- U20 TLV3605RVKR (SNOSDA2F): IN+ (4) = SDET_P (arrives already coupled and returned to VCM_REF on the Front End sheet); IN- (6) = `SDET_N` = threshold node: R84 1 k from VCM_REF to SDET_N (matches the IN+ return, bias-current cancellation), DAC_TH injected through R85 100 k into SDET_N (authority about +/-16 mV around VCM_REF when the DAC spans 0-3.3 V with VCM_REF at 1.65 V: trim = (DAC - 1.65) x 1k/101k; state the number), C84 10 nF from SDET_N to GND (keeps IN- quiet). VTH_MON = SDET_N through R86 10 k (hierarchical output to the ADC).
- External hysteresis 2-4 mV (research doc section 4): R87 from OUT+ (LVDS, ~350 mV swing into the 100 ohm termination at the FPGA) to IN+ with the IN+ source impedance being the 1 k return in parallel with the coupling path; compute R87 for ~3 mV (about 100 k with a 1 k source; show the arithmetic on the sheet and label PROPOSED; footprint 0603). LE/HYS pin: R82 to GND footprint DNP (internal hysteresis off = floating; the smallest internal step ~8 mV is too large), R83 0 ohm DNP to LE_HYS for the latch option, as before.
- VCCI (2) = 3V3 with 100 nF 0402 + 1 uF; VCCO (1) = 3V3 via R80 0 ohm with 100 nF 0402 + 1 uF; VEE and EP = GND; SHDN (7) = SHDN_N with R81 10 k pull-up to 3V3; OUT+ (12) = LVDS_P, OUT- (10) = LVDS_N.
- TP20 SDET_N, TP21 SDET_P (DNP).
- Text: baseline slicing rationale (8b/10b DC balance), bias current 1-5 uA x 1 k = 1-5 mV offset (trimmed by DAC_TH), hysteresis arithmetic, SHDN not a guaranteed zero (standing correction 11).

---

## 4. Monitor (`control.kicad_sch` keeps its file name and uuid; Sheetname "Monitor")

Pins: in 3V3, TIA_TAP; out VCM_REF, RSSI.
- U30 OPA2320AIDR (3V3, 100 nF): unit A = VCM_REF buffer: R100/R101 10 k/10 k from 3V3 to GND, C100 100 nF at the midpoint, unity buffer -> VCM_REF (1.65 V), with C101 1 uF at the output? OPA2320 drives capacitive loads poorly: use R102 10 ohm isolation then C101 1 uF, and take VCM_REF after the resistor (note). The buffer sources the return currents of three 1 k resistors: negligible.
- RSSI peak detector (telemetry only, not precision): TIA_TAP -> D30 BAS70 (anode at TIA_TAP? The TIA output swings DOWN from OUTN on light (OPA857 inverting; check SBOS630D and state it), so detect the NEGATIVE peak: D30 cathode at TIA_TAP, anode at `RSSI_HOLD`), C102 1 nF C0G from RSSI_HOLD to GND, R103 1 M from RSSI_HOLD to VCM_REF (so with no signal RSSI_HOLD sits at 1.65 V and dips with signal; tau 1 ms), unit B unity buffer -> RSSI (hierarchical output, read by the ADS1115). Note: diode drop and the 1 k tap resistor make it a relative indicator; the ESP32 calibrates. PROPOSED.
- TP30 VCM_REF, TP31 RSSI, TP32 RSSI_HOLD.
- Everything else from the former Control sheet (VMID, VSPAN, integrator, TMUX1112, TLV3201, selectors, trimmers, clamps) is removed.

---

## 5. Detector coupon: removed (decision 12). Delete `detector.kicad_sch`, `gen/detector.py`, `docs/schematic/detector.md`.

---

## 6. Connector (`connector.kicad_sch`)

Pins: out +5V_CABLE; in LVDS_P, LVDS_N, RSSI, HV_MON, 3V3, 3V3_D; bidirectional CAN_H, CAN_L, AUX, AUX2.
- J50 Wuerth 61201221621 "MODULE CABLE": 1 +5V_CABLE, 2 +5V_CABLE, 3 GND, 4 GND, 5 LVDS_P, 6 LVDS_N, 7 GND, 8 GND, 9 CAN_H, 10 CAN_L, 11 AUX2, 12 AUX. AUX and AUX2 each through R 1 k to the hierarchical labels (reserved ESP32 GPIOs). U50 Schmitt buffer, R184/R185 and the HOLD_N path are removed.
- R180 100 ohm DNP across LVDS at J50; DNP split termination R182/R183 60.4 ohm + C180 4.7 nF on the CAN pair (single-module bench only).
- Revision 3: the hierarchical output and the J50 pin 1 hierarchical label are renamed `+5V` -> `+5V_CABLE`; the pin 2 local label follows. +5V_CABLE is the system rail, mux priority input, never sourced by the module.
- J51 Conn_01x06 "DEBUG": 1 GND, 2 RSSI, 3 AUX2, 4 AUX, 5 HV_MON, 6 3V3_D.
- Test points: 3V3, 3V3_D, RSSI, HV_MON, GND x2 (TP50-TP55).
- Text: cable table, ULX3S pairs + LVDS termination rule, CAN rule (no module termination, 125 kbit/s PROPOSED), HV rule.

---

## 7. Controller (`controller.kicad_sch`)

Pins: in 3V3_D, HV_MON, RSSI, VTH_MON, PWR_SRC; out DAC_TH, DAC_HV, HV_DIS, SHDN_N, LE_HYS, TIA_CTRL, VBUS; bidirectional CAN_H, CAN_L, AUX, AUX2.
- As built (revision 1) with these changes: MCP4728 OUTA -> `DAC_A` test pad only (spare; DAC_GAIN is gone), OUTB = DAC_TH, OUTC = DAC_HV, OUTD = `DAC_D` test pad. ADS1115: AIN0 = HV_MON, AIN1 = RSSI, AIN2 = VTH_MON, AIN3 = `VCM_MON`? No reference line is routed here, so AIN3 = GND through its RC (spare). GPIO map: HV_DIS = IO0, SHDN_N = IO1, I2C IO2/IO3, LDAC IO6, AUX IO7, LE_HYS IO14, TIA_CTRL = IO15? IO15 is a strapping pin: NO. Use IO20 for TIA_CTRL (the former LOS input; now an output, Hi-Z at reset is fine because the Front End pull-up makes it 20 k), AUX2 = IO21 (the former PGOOD_VGA input) through R 1 k, CAN TX/RX IO18/IO19, DAC_RDY IO22, STATUS LED IO23, USB IO12/13, UART IO16/17, BOOT IO9, IO8 pull-up, IO4 = VBUS_SENSE and IO5 = PWR_SRC (revision 3), IO15 only no_connect. Remove the LOS and PGOOD_VGA labels and the VSPAN/VG/VMID inputs.
- Revision 3 USB-C: VBUS now leaves the sheet as hierarchical output `VBUS` (to Power U5 IN2) in addition to U61 pin 5. Keep #FLG60 PWR_FLAG. CC1/CC2 R200/R201 5.1k, shield C193 + R202, unchanged. UNRESOLVED: USBLC6-2SC6 VBUS-pin clamp behaviour not verified (ST datasheet not read); VBUS surge protection is U5 (24 V abs max) with C34, not the USBLC6.
- D+/D- series R193/R194: change from 0R to 22R (ESP32-C6 Hardware Design Guidelines (HDG) PDF p.18 section 1.3.13: reserve 22/33 ohm and capacitors to ground; MINI-1 datasheet v1.5 Fig. 9-1 p.40 leaves them TBD). Add C206 and C207 (DNP, C_0402_1005Metric_N, value TBD on the first board) from USB_DP_E and USB_DM_E to GND on the module side of R193/R194. PROPOSED. UNRESOLVED: effect of 22 ohm with the USBLC6 and USB4105 untested; auto-reset (below) untested through them.
- Buttons (new lab part, library PR required: AharoniLab_Switch category, symbol PTS810, footprint AharoniLab_Switch_SMD:SW_SPST_PTS810): SW60 RESET from EN to GND, SW61 BOOT from BOOT (IO9) to GND. TP60/TP61 stay in parallel. R190 10k + C190 1u is the reset debounce and the recommended EN RC (MINI-1 datasheet p.40, HDG p.10); no series resistor, no extra capacitor on IO9. Download Boot is GPIO9 = 0 with GPIO8 = 1 at EN rising (MINI-1 datasheet Table 4-3 p.13; HDG p.15 Table 4), VERIFIED. Fit both buttons even though RTS/DTR auto-reset exists (TRM v1.2 PDF p.1030 Table 32.3-2: RTS 0/DTR 1 download flag, RTS 1/DTR 0 reset): recovery for empty flash or a disabled USB PHY (HDG p.30). UNRESOLVED: EN-side ESD diode (optionally a DNP TPD1E10B06 footprint); 13 ms mux soft start versus the 10 ms EN RC.
- VBUS sense: R215 100k (VBUS to VBUS_SENSE), R216 150k (VBUS_SENSE to GND), C205 1n (VBUS_SENSE to GND), 0603/0402; VBUS_SENSE -> U60 pad 9 (IO4), replacing its no_connect. Ratio 0.6: 2.64 V at 4.4 V, 3.15 V at 5.25 V, 3.3 V at 5.5 V (calculated); reads high above VBUS about 4.1 V (VIH 0.75 x VDD, MINI-1 datasheet Table 6-3 p.26); 21 uA at 5.25 V. PROPOSED. The USB Serial/JTAG controller has no VBUS-detect (text search of TRM v1.2 found none: absence of a statement, UNRESOLVED), hence the divider.
- PWR_SRC: hierarchical input from Power U5 ST (open-drain, pull-up on the Power sheet) -> U60 pad 10 (IO5), replacing its no_connect. Low = USB powers the module, high = cable. IO4/IO5 are strapping pins (MTMS/MTDI) that only select SDIO sampling edges (MINI-1 datasheet Table 4-4 p.14); SDIO unused, PROPOSED harmless.
- Pin map additions: 9 IO4 VBUS_SENSE; 10 IO5 PWR_SRC. IO15 only remains no_connect.
- Firmware states by (VBUS_SENSE, PWR_SRC): (0,1) cable only; (1,0) USB only (standalone self-test); (1,1) both, cable powers; (0,0) cannot occur with power present. The ESP32 must not clear HV_DIS on the basis of these inputs alone. UNRESOLVED: firmware policy for the D+ pull-up backdrive into an unpowered host (override register, TRM p.1042); self-test cannot prove the comparator or LVDS output without an FPGA or optical source (no free GPIO tap except strapping IO15); ground offset between laptop and FPGA supply not analysed.
- Text: update the pin map table and the role text (decision 12: firmware range trim = DAC_HV + TIA_CTRL from RSSI and FPGA validity; module runs unprogrammed at 20k and the resistor-set bias).
