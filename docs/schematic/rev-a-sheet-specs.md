# Rev A schematic specifications, sheet by sheet

Status labels: VERIFIED (cited datasheet or measurement), PROPOSED (design intent), UNRESOLVED (open). Nothing on this page is measured or simulated. These specs are the brief for populating `hardware/pcb/receiver-module/*.kicad_sch`; the as-built notes live in `docs/schematic/<sheet>.md`. Authority: `docs/decision-log.md` (14 standing corrections), `docs/calculations/apd-bias-design.md`, `docs/research/ulx3s-lvds-input.md`.

Conventions for every sheet:
- Symbols only from the lab library (`${AHARONI_LAB_KICAD_LIB}`); generic R/C/L get an explicit footprint. Default passives 0603 (`R_0603_1608Metric_N`, `C_0603_1608Metric_N`); 0402 only for local decoupling at fast ICs; HV parts 1206/1210 as noted.
- GND is a global label on every sheet. Rails arrive as hierarchical labels (+5V, 3V3, +3V7, -3V7, 5V_A, APD_BIAS).
- Nets at or above 50 V are prefixed `HV_` (plus `APD_BIAS`); the project netclass `HV` (set in the .kicad_pro by the orchestrator) uses a 1.0 mm clearance.
- Every sheet carries a text block "Design intent" with the status labels, and every value that comes from a datasheet or the calculation docs cites it in the as-built note.
- Reference designator ranges (so sheets never collide): Power U1-U9/R1-R49/C1-C49/D1-D9/L1-L9/Q1-Q9/J1-J2/RV1-RV2/TH1/FB1-FB2; Front end U10-U19/R50-R79/C50-C79/D10-D19/JP10-JP19/TP10-TP19; Slicer U20-U29/R80-R99/C80-C99/TP20-TP29; Control U30-U39/R100-R149/C100-C129/D30-D39/JP30-JP39/RV30-RV39/TP30-TP39; Detector U40-U49/R150-R179/C150-C169/D40-D49/JP40-JP49/TP40-TP49; Connector J50-J59/R180-R189/TP50-TP79; MCU J60-J69/R190-R199/C190-C199.

Hierarchical nets beyond the original skeleton: `DAC_HV` (Controller -> Power), `HV_MON` (Power -> Controller, Connector), `HOLD_N` (Connector -> Control), `HV_DIS` (Controller -> Power), `CAN_H`/`CAN_L` (Controller <-> Connector), `AUX` (Connector <-> Controller), `3V3_D` (Power -> Controller), `SHDN_N`/`LE_HYS` (Controller -> Slicer), `LOS` (Control -> Controller, Connector), `PGOOD_VGA` (Power -> Controller).

**Revision 2026-10-08 (decision 11):** the external-MCU header is replaced by an on-module ESP32-C6 controller sheet (section 7) with on-board I2C DAC/ADC, a CAN link in the module cable (section 6), a 3V3_D rail (section 1.5) and an HV disable gate (section 1.4). Facts and citations: docs/research/module-controller.md.

---

## 1. Power sheet (`power.kicad_sch`)

Pins: in +5V, DAC_HV, HV_DIS; out 3V3, 3V3_D, +3V7, -3V7, 5V_A, APD_BIAS, HV_MON, PGOOD_VGA.

### 1.1 Input
- +5V: C 10 uF 0805 X7R 10 V plus 100 nF 0603 at the entry. No reverse protection in Rev A (keyed connector). PROPOSED.
- 5V_A: ferrite bead FB1 (0805, 600 ohm at 100 MHz class, value PROPOSED) from +5V, then 10 uF 0805 + 100 nF 0603. Loads: OPA356 fast buffers on the detector sheet only.

### 1.2 3V3: TPS79901DDCT (U1)
- IN = +5V with 1 uF 0603 at the pin; EN tied to IN; GND.
- FB divider: VOUT = VFB x (1 + R1/R2), VFB 1.193 V typ (TPS799 SBVS056L, Electrical Characteristics, "Internal reference (TPS79901)" 1.169/1.193/1.217 V). R1 17.8 k, R2 10.0 k, 1 %, 0603 -> 3.316 V nominal. CFB 10 nF across R1 (datasheet front-page adjustable circuit shows CFB; agent to confirm the recommended value in the Adjustable section and cite it). PROPOSED.
- OUT = 3V3: 2 x 4.7 uF 0805 X7R 10 V (datasheet needs >= 2 uF effective after DC bias derating).
- Load estimate: OPA857 26.8 mA max + TLV3605 17.5 mA max + 2 x OPA2320 (~4 mA) + TLV3201 ~ 50 mA; dissipation ~0.1 W in SOT-23-5. PROPOSED.

### 1.3 +/-3V7: LM27762 (U2), SNVSAF7C
- VIN = +5V, CIN 4.7 uF 0805; C1 flying 1 uF 0603 between C1+ and C1-; CPOUT 4.7 uF 0805 to GND; COUT+ 2.2 uF 0603 on OUT+; COUT- 2.2 uF 0603 on OUT-. (Datasheet 7.2.2.4: CIN 4.7 uF, C1 0.47-1 uF, CCPOUT 4.7 uF, COUT 2.2 uF ceramic; cite the page.)
- FB+: VOUT+ = 1.2 V x (R3 + R4)/R4, R4 >= 50 k. R3 210 k, R4 100 k -> +3.72 V. FB-: VOUT- = -1.22 V x (R5 + R6)/R6. R5 205 k, R6 100 k -> -3.72 V. 1 % 0603. Standing correction 14 (different references) is why R3 != R5. PROPOSED.
- EN+ and EN- tied to VIN. PGOOD (open drain, active low) pulled up 100 k to 3V3 and to a test point TP "PG_VGA". PAD to GND.
- Place resistors next to the FB pins (datasheet layout note).

### 1.5 3V3_D digital rail: TPS7A2033PDBV (U4)
- IN = +5V with 1 uF; OUT = `3V3_D` with 10 uF 0805 + 1 uF; EN tied to IN; GND. Fixed 3.3 V, 300 mA. Loads: ESP32-C6 (radio OFF, ~20-40 mA est.), SN65HVD230, MCP4728, ADS1115 (~60 mA total est., docs/research/module-controller.md). Constraint stated on the sheet: the ESP32 radio must stay disabled (WiFi TX peaks 251-382 mA exceed this LDO); a buck is the Rev B option if the radio is ever used. Hierarchical output 3V3_D. PROPOSED.
- PGOOD of U2 (already pulled up 100 k to 3V3) also leaves as hierarchical output `PGOOD_VGA`.

### 1.4 APD bias: LT8365EMSE (U3), from `docs/calculations/apd-bias-design.md` section 3.2 and section 4. Implement exactly those values; do not re-derive.
- Input: pi filter from +5V: 10 uF 50 V 1206 + 0.47 uH (use generic L with footprint L_0805_2012Metric_N, PROPOSED) + 10 uF 50 V 1206 + 4.7 uF 50 V 0805 at VIN. Net after the filter `5V_HVIN`.
- EN/UVLO: 200 k top from 5V_HVIN, 200 k bottom to GND (UVLO). HV disable gate (revision, decision 11): Q3 DMN2056U-7 N-MOSFET drain on the EN/UVLO node, source GND, gate = hierarchical input `HV_DIS` with R 100 k pull-up to 3V3_D (so with the ESP32 unprogrammed or absent the gate is high, EN is held low, HV is OFF); the ESP32 drives HV_DIS low to enable after it has verified the DAC. J1 becomes a 2-pin header "HV FORCE ON" (DNP jumper) from the gate to GND for bench use without firmware. PROPOSED.
- SYNC/MODE: floating by default (pulse-skipping); 0 ohm DNP footprints to GND (Burst) and 100 k DNP to GND (per the doc's "Burst+SSFM" option), test point for an external clock. BIAS: to GND, 0 ohm DNP option to 5V_HVIN. INTVCC: 1 uF 0603 to GND. RT: 84.5 k 1 % to GND. SS: 0.22 uF to GND. VC: 84.5 k + 1 nF C0G to GND, optional 10 pF DNP from VC to GND.
- Power stage: L1 10 uH (Wurth 74437324100 footprint) from 5V_HVIN to SW1 and SW2 (both SW pins tied). D1 DFLS1150 SW -> R7 20 ohm 0805 -> `HV_V1` with C5 0.1 uF 200 V 1206 to GND (stage 1 boost, ~70 V). Doubler: C6 0.1 uF 200 V 1206 from SW to `HV_PUMP`; D3 DFLS1150 from HV_V1 to HV_PUMP; D4 DFLS1150 from HV_PUMP to `HV_RAW`; C7 0.1 uF 200 V 1206 from HV_RAW to HV_V1 (stacked, exactly as the DC2838A doubler described in the doc section 2). D2 DFLS1150 anode GND, cathode SW (as in the datasheet p.30 250 V example, purpose not stated; fit, DNP allowed). R_out 47 ohm 1206 from HV_RAW to `HV_OUT`, C 1 nF 500 V 1206 from HV_OUT to GND.
- FBX feedback from HV_OUT: top R8-R11 4 x 2.05 M 1 % 0603 in series to FBX; bottom R12 86.6 k 1 % + TH1 NTC 10 k beta 3950 0603 in series to GND. DAC leg: DAC_HV -> R13 10 k -> node with C 100 nF to GND -> R14 442 k -> FBX. Pot leg: RV1 50 k trimmer (Bourns 3224W) ends 3V3/GND, wiper -> R15 274 k -> FBX (RV1 and R15 DNP in production). Keep the FBX node short; 10 pF DNP from FBX to GND.
- Clamp (doc section 4): Q1 MMBTA42 pass transistor: collector HV_OUT, emitter -> R16 4.02 k -> `HV_CLAMP`; Q2 MMBT3904 base at the Q1 emitter, emitter at HV_CLAMP, collector to Q1 base; R17+R18 2 x 4.99 M in series from HV_OUT to Q1 base. (Verify the arrangement against the doc: Q2 senses the drop across R16 and steals Q1 base drive.)
- Filter stage 1: R19 27 k 1206 (>= 200 V) from HV_CLAMP to `HV_FILT`; C8 10 nF >= 400 V C0G 1210 from HV_FILT to GND. HV_FILT is the hierarchical label `APD_BIAS` (stage 2, 10 k + 10 nF, sits at the cathode on the front-end sheet).
- Monitor: R20 10 M (2 x 4.99 M 0603 in series) from HV_OUT, R21 100 k to GND, node `HV_MON` (~Vout/101, 1.39 V at 140 V) with 10 nF to GND; hierarchical output. PROPOSED.
- Text block: HV warning (220 V, 2.3 mJ stored), never probe HV_OUT directly; DC2838A and LT8365 Rev. A citations.

---

## 2. Front end (`frontend.kicad_sch`)

Pins: in APD_BIAS, 3V3, +3V7, -3V7, VG, VCM_DET; out SDET.
- Stage 2 filter: R50 10 k 1206 (>= 200 V) from APD_BIAS to `HV_K`; C50 10 nF >= 400 V C0G 1210 from HV_K to GND, placed at the cathode (doc section 4; the 2 uC dump risk is noted on the sheet; a 4.7 nF alternative is an open test item).
- D10 S12023-10: pin 1 K = HV_K, pin 3 A = `TIA_IN`, pin 2 CASE = GND. D11 FDS010 (DNP, bench fallback): K = HV_K, A = TIA_IN, case = GND. Standing correction 2.
- U10 OPA857 (SBOS630D): IN (15) = TIA_IN (keep this net tiny, guard, HV keep-out); VS+ (9, 10, 11) = 3V3 with 2 x 100 nF 0402 and 1 uF 0603; all GND pins and PAD = GND; Test_SD (13) = GND; Test_IN (14) = 3V3 (pin table: "Connect to +VS during normal operation"); NC (16) no-connect; CTRL (2) via JP10 SolderJumper_3 (common = CTRL, one side 3V3 = 20 k, other GND = 5 k), default bridged to 3V3 (pin table: logic 1 = 20 k). OUT (8) = `TIA_OUT`, OUTN (5) = `TIA_REF` (1.83 V typ).
- AC coupling (standing correction 1): C51 100 nF TIA_OUT -> `VGA_P`, R51 10 k VGA_P -> GND; C52 100 nF TIA_REF -> `VGA_N`, R52 10 k VGA_N -> GND. Corner 159 Hz.
- U11 VCA821IDGS (SBOS407D): +VIN (4) = VGA_P, -VIN (7) = VGA_N, RG R53 80.6 ohm between +RG (5) and -RG (6), RF R54 402 ohm from OUT (9) to FB (1) (datasheet AVMAX = 20 dB conditions; standing correction 5 says RF is compensation: keep the datasheet network), VG (3) <- VG through R55 100 ohm with C53 1 nF to GND; +VCC (2) = +3V7 with 100 nF 0402 + 2.2 uF 0603; -VCC (8) = -3V7 with 100 nF 0402 + 2.2 uF 0603; GND (10) = GND. OUT (9) = `VGA_OUT`. Note on the sheet: input limit 2 x RG x 2.6 mA ~ 0.42 Vpp (datasheet Figure 1), so the TIA 20 k path saturates the VGA input near 21 uA peak; UNRESOLVED whether RG moves up.
- Level shift: C54 10 nF VGA_OUT -> `SDET`; R56 10 k SDET -> VCM_DET. Corner 1.6 kHz. SDET is the hierarchical output.
- Test points: TP10 VGA_OUT, TP11 SDET, TP12 TIA_REF; no HV test points.
- Text block: OPA857 at 6 pF UNRESOLVED; HV keep-out; APD polarity.

---

## 3. Slicer (`slicer.kicad_sch`)

Pins: in SDET, VTH, 3V3, SHDN_N, LE_HYS; out LVDS_P, LVDS_N.
- U20 TLV3605RVKR (SNOSDA2F): IN+ (4) = SDET, IN- (6) = VTH; VCCI (2) = 3V3 with 100 nF 0402 + 1 uF 0603; VCCO (1) = 3V3 through R80 0 ohm (option for a bead) with its own 100 nF 0402 + 1 uF 0603; VEE (3, 5, 9, 11) and EP (13) = GND.
- SHDN (7): R81 10 k pull-up to 3V3, net SHDN_N (active low, VIH 1.5 V, VIL 0.4 V; standing correction 11).
- LE/HYS (8): R82 150 k to GND (30 mV hysteresis, EC table "RHYST = 150 k"), footprint allows 56 k (60 mV). LE_HYS hierarchical net joins the pin through R83 0 ohm (DNP by default) so the FPGA can force the latch only when fitted; read the datasheet "Latch and hysteresis" section and note on the sheet how latch vs hysteresis is selected by the pin voltage.
- OUT+ (12) = LVDS_P, OUT- (10) = LVDS_N (VOD 350 mV into 100 ohm; termination is on-die in the ECP5, see docs/research/ulx3s-lvds-input.md).
- TP20 VTH, TP21 SDET (DNP, probing loads SDET).

---

## 4. Control (`control.kicad_sch`)

Pins: in 3V3, VHIGH, VLOW, DAC_GAIN, DAC_TH, HOLD_N; out VCM_DET, VG, VTH, LOS, VMID, VSPAN.
Op amps: OPA2320AIDR (SBOS513F) x2 = U30 (A: VCM_DET buffer, B: VMID buffer), U31 (A: VSPAN subtractor, B: integrator); all on 3V3 with 100 nF each. LOS comparator U32 TLV3201AIDBVR on 3V3.
- VCM_DET: R100/R101 10 k/10 k from 3V3 to GND, C100 100 nF at the midpoint, into U30A unity buffer -> VCM_DET (1.65 V). PROPOSED.
- VMID (standing correction 8): R102 10 k 0.1 % from VHIGH and R103 10 k 0.1 % from VLOW to the U30B + input, C101 100 pF to GND; unity buffer -> VMID.
- VSPAN (standing correction 7): U31A with R41 10 k 0.1 % VLOW -> IN-, R42 10 k 0.1 % OUT -> IN-, R43 10 k 0.1 % VHIGH -> IN+, R44 10 k 0.1 % IN+ -> GND. Use the reference designators R41-R44 literally (they are reserved in the power range for exactly this reason). Output VSPAN = VHIGH - VLOW.
- Integrator (standing correction 9): VSPAN -> switch path -> R104 100 k -> U31B IN-; C102 47 nF C0G/PP from OUT to IN-; IN+ = `VTARGET` from R105 23.2 k / R106 10.0 k divider off 3V3 (0.994 V) with C103 1 uF. Output `VINT`. Sign: VSPAN above target drives VINT down, so VG down, gain down.
- Anti-windup/freeze: U33 TMUX1112 (lab library Misc; four SPST switches, verify pinout and logic polarity in its datasheet) with two switches in series in the VSPAN -> R104 path: one controlled by `LOS_N` (closed when signal present), one by HOLD_N (pulled up 100 k to 3V3; FPGA pulls low to freeze). Open path = integrator holds state (freeze, not reset). Remaining two switches unused (inputs tied low, outputs NC). Clamp D30/D31 BAS70 from VINT to `VG_HI` (2.0 V, R107 13 k / R108 20 k divider + 1 uF) and from `VG_LO` (0.2 V, R109 100 k/R110 6.8 k + 1 uF) to VINT, both DNP, marked UNRESOLVED (soft bound only).
- LOS: U32 TLV3201 compares VSPAN (IN+) with `VLOS_TH` (IN-, R111 100 k / R112 10 k from 3V3 = 0.3 V, C 100 nF), hysteresis R113 1 M from OUT to IN+ with R114 10 k series on IN+; output = LOS_N (high when span above threshold). LOS hierarchical output = LOS_N through a text note (the net is active low; name the hierarchical label `LOS` and state on the sheet that it is active-low LOS_N; the orchestrator will rename root pins if needed). Standing note: span alone does not prove signal presence.
- Gain selector JP30 Conn_01x03 header "VG_SEL": 1 = VINT, 2 = VG (common), 3 = `VG_MAN` from RV30 10 k trimmer across 3V3 with wiper -> R115 1 k -> VG_MAN, C 100 nF. DAC_GAIN joins VG through R116 0 ohm DNP. Threshold selector JP31 Conn_01x03 "VTH_SEL": 1 = VMID, 2 = VTH, 3 = `VTH_MAN` from RV31 10 k trimmer + R117 1 k; DAC_TH joins VTH through R118 0 ohm DNP. Headers chosen over solder jumpers because the gain source changes on the bench. PROPOSED.
- Test points: VINT, VSPAN, VMID, VTARGET, VG, VTH, LOS_N.

---

## 5. Detector coupon (`detector.kicad_sch`)

Pins: in SDET, 5V_A, 3V3, VCM_DET; out VHIGH, VLOW. Whole block UNRESOLVED (not a validated 20 ns detector), built to be disconnectable.
- Input: JP40 SolderJumper_2 (default closed) from SDET to R150 49.9 ohm -> `DET_IN`.
- U40 OPA356AIDBVR (SBOS212A, 5V_A supply, 100 nF + 1 uF): unity buffer, + = DET_IN, output -> D40 BAS70 anode, cathode -> `CH` node: C150 47 pF C0G to GND, R151 1 M to VCM_DET. U41 OPA356AIDBVR: unity buffer, + = DET_IN, output -> D41 BAS70 cathode, anode -> `CL` node: C151 47 pF to GND, R152 1 M to VCM_DET. Footprints for CH/CL allow 22-100 pF and RH/RL 0.5-5 M (note on the sheet). OPA356 input range is V- - 0.1 to V+ - 1.5 V (cite), so 5V_A is required.
- U42 OPA2320AIDR (3V3, 100 nF): A buffers CH -> JP41 SolderJumper_2 (closed) -> VHIGH; B buffers CL -> JP42 SolderJumper_2 (closed) -> VLOW.
- Note the Schottky drop (~0.3 V) and droop (47 us) as known errors; two-diode or in-loop detectors are the G2 alternatives.
- TP40 CH, TP41 CL, TP42 DET_IN.

---

## 6. Connector (`connector.kicad_sch`)

Pins: out +5V, HOLD_N; in LVDS_P, LVDS_N, LOS, VMID, VSPAN, HV_MON, 3V3, +3V7, -3V7, 5V_A, 3V3_D; bidirectional CAN_H, CAN_L, AUX.
- J50 Wuerth 61201221621 (2x06 shrouded, 2.54 mm) "MODULE CABLE": 1 +5V, 2 +5V, 3 GND, 4 GND, 5 LVDS_P, 6 LVDS_N, 7 GND, 8 GND, 9 CAN_H, 10 CAN_L, 11 HOLD_N, 12 AUX. (Rows: power, ground, LVDS pair, ground, CAN pair, control; pin pairs 2n-1/2n sit side by side so each differential pair shares a row and is flanked by ground rows; docs/research/module-controller.md section 6.)
- R180 100 ohm 0603 DNP across LVDS_P/LVDS_N at J50 (bench scope only; never fitted with the ECP5 DIFFRESISTOR on). No CAN termination on the module (single split termination lives at the FPGA-end junction, docs/research/module-controller.md section 3); R182/R183 2 x 60.4 ohm + C180 4.7 nF split-termination footprints DNP at J50 so a single-module bench setup can terminate here. State that on the sheet.
- HOLD_N from J50 pin 11 -> R184 1 k series -> U50 SN74LVC1G17DBVR Schmitt buffer (3V3, 100 nF) -> hierarchical output HOLD_N; R185 100 k pull-up to 3V3 on the buffer input (unplugged cable = run). AUX: J50 pin 12 -> R186 1 k -> hierarchical AUX (reserved; ESP32 GPIO10).
- J51 Conn_01x06 "DEBUG": 1 GND, 2 LOS, 3 HOLD_N (buffered), 4 AUX, 5 HV_MON, 6 3V3_D.
- Test points: 3V3, 3V3_D, +3V7, -3V7, 5V_A, VMID, VSPAN, HV_MON, GND x2 (TP50-TP59).
- Text: ULX3S target pairs, LVDS termination rule, CAN termination rule and bit rate (125 kbit/s PROPOSED), HV rule (no bare APD_BIAS pad; HV_MON is the only HV observation point).

---

## 7. Controller (`controller.kicad_sch`, replaces `mcu.kicad_sch`; Sheetname "Controller")

Pins: in 3V3_D, HV_MON, VSPAN, VG, VMID, LOS, PGOOD_VGA; out DAC_GAIN, DAC_TH, DAC_HV, HV_DIS, SHDN_N, LE_HYS; bidirectional CAN_H, CAN_L, AUX. All parts on 3V3_D unless stated. Facts: docs/research/module-controller.md (cite its section numbers on the sheet).
- U60 ESP32-C6-MINI-1 (AharoniLab_MCU): 3V3 = 3V3_D with 10 uF 0805 + 100 nF 0402 at pin 3; all GND pads = GND; EN (8): R190 10 k pull-up to 3V3_D + C190 1 uF to GND + TP "EN" pad; BOOT: GPIO9 with R191 10 k pull-up to 3V3_D and TP "BOOT" pad (pull to GND for download); GPIO8: R192 10 k pull-up (strapping, must be high at boot). GPIO15 (strapping) left unconnected with a no_connect flag and a note. Antenna keep-out note on the sheet (module placed at a board edge, radio unused).
- USB programming: J60 USB4105-GF-A-120 USB-C receptacle. VBUS is NOT a supply for the module (the module is powered from the cable): VBUS goes only to the USBLC6 VBUS pin. CC1 and CC2 each 5.1 k to GND (UFP sink declaration). D+ (A6 and B6 tied) and D- (A7 and B7 tied) -> U61 USBLC6-2SC6 (I/O1 = D+, I/O2 = D-, VBUS = VBUS, GND) -> R193/R194 series (fit 0 ohm; value UNRESOLVED per the research doc, footprint allows 22 ohm) -> GPIO13/USB_D+ and GPIO12/USB_D-. Shield pins to GND through C 1 nF in parallel with R 1 M (DNP); SBU1/SBU2 no_connect. UART fallback: GPIO16/U0TXD and GPIO17/U0RXD to test pads "TXD0"/"RXD0".
- Local I2C (GPIO2 = SDA, GPIO3 = SCL): R195/R196 4.7 k pull-ups to 3V3_D. U62 MCP4728T-E_UN: VDD 3V3_D + 100 nF, VSS GND, SCL/SDA, ~{LDAC} = GPIO11 (so the ESP32 can latch all channels at once; R 10 k pull-up to 3V3_D, note that a high LDAC holds outputs at EEPROM values), RDY/~{BSY} = GPIO22 (input, R 10 k pull-up), OUTA = DAC_GAIN, OUTB = DAC_TH, OUTC = DAC_HV, OUTD = `DAC_D` to a test point (spare; PROPOSED future VTARGET trim). Each DAC output through R 100 ohm + C 100 nF to GND. Sheet note: DAC_HV safe-default rule (EEPROM programmed to full scale = lowest bias, never power-down on channel C, internal 2.048 V ref with gain x2 so the trim does not track the 3V3_D rail; UNRESOLVED until firmware exists), HV is gated by HV_DIS regardless.
- U63 ADS1115IDGSR: VDD 3V3_D + 100 nF, GND, SCL/SDA, ADDR = GND (0x48), ALERT/RDY = GPIO23 (R 10 k pull-up, optional), AIN0 = HV_MON, AIN1 = VSPAN, AIN2 = VG, AIN3 = VMID, each through R 10 k + C 10 nF to GND (inputs must stay within GND-0.3..VDD+0.3; all four sources are <= 3.3 V nodes).
- CAN: U64 SN65HVD230D: VCC 3V3_D + 100 nF, GND, D = GPIO18 (TWAI TX), R = GPIO19 (TWAI RX), RS = R 10 k to GND (slope control, docs/research/module-controller.md section 2), Vref_OUT no_connect, CANH = hierarchical CAN_H, CANL = hierarchical CAN_L. Optional CAN ESD (DNP footprint note only, no part).
- GPIO: HV_DIS = GPIO0 (hierarchical out; the pull-up to 3V3_D lives on the Power sheet), SHDN_N = GPIO1 (hier out; the 10 k pull-up on the Slicer sheet keeps the comparator enabled with an unprogrammed ESP32), LE_HYS = GPIO14 (hier out through R 0 ohm DNP so the default is the Slicer's hysteresis resistor only), LOS = GPIO20 (hier in, active-low LOS_N), PGOOD_VGA = GPIO21 (hier in), AUX = GPIO10 (bidirectional hier) through R 1 k. Status LED D60 (AharoniLab_Passive:LED, footprint AharoniLab_LED_SMD:LED_0805_2012Metric) + R 1 k on GPIO23; therefore the ADS1115 ALERT/RDY pin gets a no_connect flag instead of GPIO23. Avoid IO4, IO5, IO6, IO7, IO8, IO9, IO12, IO13, IO15, IO16, IO17 for anything else (strapping, JTAG, USB, UART0; research doc section 1).
- Unused GPIOs: no_connect flags. Text block: role of the controller (decision 11), what runs without firmware (everything analog; HV off; comparator enabled; HOLD_N wire), pin map table, strapping rules, CAN parameters, UNRESOLVED items (USB series resistors, auto-reset behaviour, DAC default verification, 3V3_D current measurement).
- Reference ranges: U60-U69, R190-R229, C190-C219, D60-D69, J60-J61, TP60-TP69.
