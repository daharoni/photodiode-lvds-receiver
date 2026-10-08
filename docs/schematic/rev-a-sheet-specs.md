# Rev A schematic specifications, sheet by sheet

Status labels: VERIFIED (cited datasheet or measurement), PROPOSED (design intent), UNRESOLVED (open). Nothing on this page is measured or simulated. These specs are the brief for populating `hardware/pcb/receiver-module/*.kicad_sch`; the as-built notes live in `docs/schematic/<sheet>.md`. Authority: `docs/decision-log.md` (14 standing corrections), `docs/calculations/apd-bias-design.md`, `docs/research/ulx3s-lvds-input.md`.

Conventions for every sheet:
- Symbols only from the lab library (`${AHARONI_LAB_KICAD_LIB}`); generic R/C/L get an explicit footprint. Default passives 0603 (`R_0603_1608Metric_N`, `C_0603_1608Metric_N`); 0402 only for local decoupling at fast ICs; HV parts 1206/1210 as noted.
- GND is a global label on every sheet. Rails arrive as hierarchical labels (+5V, 3V3, +3V7, -3V7, 5V_A, APD_BIAS).
- Nets at or above 50 V are prefixed `HV_` (plus `APD_BIAS`); the project netclass `HV` (set in the .kicad_pro by the orchestrator) uses a 1.0 mm clearance.
- Every sheet carries a text block "Design intent" with the status labels, and every value that comes from a datasheet or the calculation docs cites it in the as-built note.
- Reference designator ranges (so sheets never collide): Power U1-U9/R1-R49 (R41-R44 free again)/C1-C49/D1-D9/L1-L9/Q1-Q9/J1-J2/RV1-RV2/TH1/FB1-FB2; Front end U10-U19/R50-R79/C50-C79/D10-D19/JP10-JP19/TP10-TP19; Slicer U20-U29/R80-R99/C80-C99/TP20-TP29; Monitor U30-U39/R100-R149/C100-C129/D30-D39/JP30-JP39/RV30-RV39/TP30-TP39; Connector J50-J59/R180-R189/C180-C189/U50/TP50-TP59; Controller U60-U69/R190-R229/C190-C219/D60-D69/J60-J61/TP60-TP69.

Hierarchical nets (revision 2): rails `3V3`, `3V3_D`, `APD_BIAS` (Power -> users); `DAC_HV`, `HV_DIS` (Controller -> Power); `HV_MON` (Power -> Controller, Connector); `TIA_CTRL` (Controller -> Front End); `TIA_TAP` (Front End -> Monitor, RSSI pick-off); `SDET_P`, `SDET_N` (Front End -> Slicer); `VCM_REF` (Monitor -> Front End, Slicer); `RSSI` (Monitor -> Controller, Connector); `DAC_TH` (Controller -> Slicer); `VTH_MON` (Slicer -> Controller); `SHDN_N`, `LE_HYS` (Controller -> Slicer); `LVDS_P/N` (Slicer -> Connector); `CAN_H`, `CAN_L`, `AUX`, `AUX2` (Controller <-> Connector); `+5V` (Connector -> Power).

**Revision 2 (decision 12, 2026-10-08):** the VCA821 VGA, AGC loop, detector coupon, +/-3.7 V and 5V_A rails are removed; the chain is TIA -> AC coupling -> OPA855 x7 -> low-pass -> AC coupling to a 1.65 V baseline -> TLV3605. The Control sheet becomes the Monitor sheet (reference and RSSI); the Detector sheet is deleted. Sections 2, 3, 4 and 7 below are rewritten; section 5 is gone. Facts: docs/research/post-amp-slicer.md.

**Revision 1 (decision 11):** the external-MCU header is replaced by an on-module ESP32-C6 controller sheet (section 7) with on-board I2C DAC/ADC, a CAN link in the module cable (section 6), a 3V3_D rail (section 1.5) and an HV disable gate (section 1.4). Facts and citations: docs/research/module-controller.md.

---

## 1. Power sheet (`power.kicad_sch`)

Pins: in +5V, DAC_HV, HV_DIS; out 3V3, 3V3_D, APD_BIAS, HV_MON. (Revision 2: the LM27762 +/-3V7 block, the 5V_A bead/caps, PGOOD_VGA and TP1 are removed.)

### 1.1 Input
- +5V: C 10 uF 0805 X7R 10 V plus 100 nF 0603 at the entry. No reverse protection in Rev A (keyed connector). PROPOSED.

### 1.2 3V3: TPS79901DDCT (U1)
- IN = +5V with 1 uF 0603 at the pin; EN tied to IN; GND.
- FB divider: VOUT = VFB x (1 + R1/R2), VFB 1.193 V typ (TPS799 SBVS056L). R1 17.8 k, R2 10.0 k, 1 %, 0603 -> 3.316 V. CFB 1 nF across R1 (value UNRESOLVED, see power.md). OUT = 3V3: 2 x 4.7 uF 0805 X7R 10 V.
- Load estimate: OPA857 26.8 mA max + OPA855 (SBOS622D, check Iq at 3.3 V) + TLV3605 17.5 mA max + OPA2320 ~2 mA ~ 65 mA. PROPOSED.

### 1.5 3V3_D digital rail: TPS7A2033PDBV (U4)
- As built: IN = +5V with 1 uF; OUT = 3V3_D with 10 uF 0805 + 1 uF; EN tied to IN. Radio must stay disabled (300 mA LDO). PROPOSED.

### 1.4 APD bias: LT8365EMSE (U3)
- As built per `docs/calculations/apd-bias-design.md` sections 3.2 and 4, with the HV disable gate (Q3 on EN/UVLO, gate pulled up to 3V3_D, driven by HV_DIS, J1 "HV FORCE ON" DNP jumper) and the HV_MON divider. Unchanged in revision 2.

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

Pins: out +5V; in LVDS_P, LVDS_N, RSSI, HV_MON, 3V3, 3V3_D; bidirectional CAN_H, CAN_L, AUX, AUX2.
- J50 Wuerth 61201221621 "MODULE CABLE": 1 +5V, 2 +5V, 3 GND, 4 GND, 5 LVDS_P, 6 LVDS_N, 7 GND, 8 GND, 9 CAN_H, 10 CAN_L, 11 AUX2, 12 AUX. AUX and AUX2 each through R 1 k to the hierarchical labels (reserved ESP32 GPIOs). U50 Schmitt buffer, R184/R185 and the HOLD_N path are removed.
- R180 100 ohm DNP across LVDS at J50; DNP split termination R182/R183 60.4 ohm + C180 4.7 nF on the CAN pair (single-module bench only).
- J51 Conn_01x06 "DEBUG": 1 GND, 2 RSSI, 3 AUX2, 4 AUX, 5 HV_MON, 6 3V3_D.
- Test points: 3V3, 3V3_D, RSSI, HV_MON, GND x2 (TP50-TP55).
- Text: cable table, ULX3S pairs + LVDS termination rule, CAN rule (no module termination, 125 kbit/s PROPOSED), HV rule.

---

## 7. Controller (`controller.kicad_sch`)

Pins: in 3V3_D, HV_MON, RSSI, VTH_MON; out DAC_TH, DAC_HV, HV_DIS, SHDN_N, LE_HYS, TIA_CTRL; bidirectional CAN_H, CAN_L, AUX, AUX2.
- As built (revision 1) with these changes: MCP4728 OUTA -> `DAC_A` test pad only (spare; DAC_GAIN is gone), OUTB = DAC_TH, OUTC = DAC_HV, OUTD = `DAC_D` test pad. ADS1115: AIN0 = HV_MON, AIN1 = RSSI, AIN2 = VTH_MON, AIN3 = `VCM_MON`? No reference line is routed here, so AIN3 = GND through its RC (spare). GPIO map: HV_DIS = IO0, SHDN_N = IO1, I2C IO2/IO3, LDAC IO6, AUX IO7, LE_HYS IO14, TIA_CTRL = IO15? IO15 is a strapping pin: NO. Use IO20 for TIA_CTRL (the former LOS input; now an output, Hi-Z at reset is fine because the Front End pull-up makes it 20 k), AUX2 = IO21 (the former PGOOD_VGA input) through R 1 k, CAN TX/RX IO18/IO19, DAC_RDY IO22, STATUS LED IO23, USB IO12/13, UART IO16/17, BOOT IO9, IO8 pull-up, IO4/IO5/IO15 no_connect. Remove the LOS and PGOOD_VGA labels and the VSPAN/VG/VMID inputs.
- Text: update the pin map table and the role text (decision 12: firmware range trim = DAC_HV + TIA_CTRL from RSSI and FPGA validity; module runs unprogrammed at 20k and the resistor-set bias).
