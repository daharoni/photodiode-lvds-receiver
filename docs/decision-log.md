# Decision log

All entries dated 2026-10-08 (user session). Labels are PROPOSED unless noted.

## Decisions

1. **Analog-first.** AGC and slicing are analog; MCU/ADC hooks are optional. Rationale: user decision, lowest latency and independent of firmware.
2. **Single PCB, hierarchical sheets.** Rapid iteration instead of many coupons.
3. **ULX3S first FPGA target.** Available now. LVDS input on the 3.3 V banks VERIFIED (docs/research/ulx3s-lvds-input.md): ECP5 differential inputs run from VCCAUX and DIFFRESISTOR=100 exists on banks 7 and 2/3, so the TLV3605 pair goes straight to gp/gn[8..13] or [14..21] with no receiver IC and no external termination.
4. **Shielded housing and swappable filter.** 6.63 MHz QSCR field is in-band; one module serves 630 nm and 765 nm.
5. **Rails +/-3.7 V; APD_BIAS 100–220 V (superseded PD_BIAS >= 6.5 V on 2026-10-08).** See corrections 4 and 14 and decision 8.
6. **All new parts via lab-library PR.** No project-local symbols; library at ~/Projects/kicad-lab-library.
7. **Headstage co-designed with receiver; no backward compatibility requirement.** Emitter wavelength, radiant intensity, drive and modulation are co-design variables (NIR preferred); the link budget is joint. Miniscope Zero emitter facts are baseline only.
8. **Detector: silicon APD selected (2026-10-08).** The link budget (docs/calculations/link-budget.md) shows a bare FDS010 PIN into the OPA857 is 18–23 dB optical short of Q = 6 at 35 cm lateral with any headstage-power-compatible emitter, because photocurrent (1–3 nA) is far below TIA noise (8–26 nA). Étendue caps optics at ~2× for a ±45° field of view. An APD with M ≈ 50 plus a modestly brighter NIR emitter closes the link with margin. Daniel approved the APD path. Consequences: the 6.5–15 V MAX15032 bias block is replaced by a 150–200 V temperature-compensated APD bias supply; the FDS010 remains a drop-in fallback only if a compatible footprint is kept; part selection is tracked in docs/research/apd-selection.md. PROPOSED until a part and bias design are chosen.

9. **APD bias supply: on-board LT8365 boost + charge-pump stage (2026-10-08).** Daniel prefers to handle as much as reasonable on our own PCB rather than a purchased HV module. Rev A therefore carries an LT8365-based 100–220 V generator (datasheet Rev. A and DC2838A demo manual Rev. 0 archived in docs/datasheets/), a two-stage RC cathode filter, series current limit, NTC temperature-tracking divider with a DAC-trim hook, and a footprint/pads for an external HV module as bench fallback. Design calculations in docs/calculations/apd-bias-design.md. PROPOSED until measured.

10. **Rev A schematic choices (2026-10-08, PROPOSED).** Captured in docs/schematic/rev-a-sheet-specs.md and the per-sheet as-built notes:
   - The analog LOS comparator (TLV3201 on VSPAN) is a status output only and does not freeze the AGC integrator. Reason: a weak eye at power-up would set LOS, freeze the integrator and leave the gain unable to rise (startup deadlock found during sheet population). With no signal the loop runs VG toward its upper bound, which is the SEARCH state in the architecture state table. The FPGA's HOLD_N (via a TMUX1112 switch in the integrator input path) is the only freeze; a DNP 0 ohm resistor keeps the LOS-freeze option for bench experiments. The VG upper bound versus the VCA821 0-2 V gain-control range is UNRESOLVED (BAS70 clamps footprinted, DNP).
   - Gain and threshold sources are 3-pin headers (VINT / pot / DAC and VMID / pot / DAC) because they change on the bench; the detector coupon and the OPA857 gain select use solder jumpers.
   - APD bias filter split: clamp + 27 k/10 nF on the Power sheet, 10 k/10 nF at the cathode on the Front End sheet; HV nets are prefixed HV_ and sit in the project net class HV (1.0 mm clearance). HV_MON (10 M/100 k, Vout/101) is the only HV observation point; no bare APD_BIAS pad.
   - No SAMD51 on Rev A: a 6-pin MCU header carries DAC_GAIN, DAC_TH, DAC_HV and HV_MON with 100 k pull-downs (polarity UNRESOLVED).
   - Standard KiCad power symbols (power:PWR_FLAG, power:GND) are allowed alongside the lab library, as in the lab's CaRacterize project.

11. **Module controller: ESP32-C6 on each receiver, CAN to the FPGA side, no BLE (2026-10-08, PROPOSED).** Daniel is moving away from the SAMD51 and wants each module to carry an ESP32 as its single point of contact with the FPGA side (module identification, future-proofing); the ESP32 then talks to everything slow on the module. Consequences: (a) on-board MCP4728 12-bit I2C DAC (DAC_GAIN, DAC_TH, DAC_HV trims) and ADS1115 16-bit I2C ADC (HV_MON, VSPAN, VG, VMID monitors) driven by the ESP32 over local I2C, replacing the external-MCU header; (b) CAN_H/CAN_L in the per-module cable next to the LVDS pair through a 3.3 V transceiver, cables joined star-fashion at the FPGA end, low bit rate so stubs are tolerable (physical-layer limits in docs/research/module-controller.md); the ULX3S's own ESP32 or an FPGA soft core is the master; (c) HOLD_N stays a direct FPGA wire so the AGC freeze does not depend on firmware; (d) SHDN_N, LE_HYS, HV_EN and LOS/PGOOD readback move to ESP32 GPIO; (e) a separate 3V3_D LDO rail for the ESP32 keeps its current steps off the analog 3V3; (f) the radio is unpopulated in use, so the shielded housing needs no RF window; BLE was considered and rejected (shielding, TX noise next to the TIA, and a wired bus already exists). Analog-first is unchanged: the ESP32 is not in the signal path and the module works with the ESP32 unprogrammed (manual trimmers, HOLD_N wire).

## Standing corrections (from the prior design review)

1. OPA857 OUT/OUTN are AC-coupled into the VCA821, never DC-wired. Rationale: OUTN is about 1.83 V; VCA821 +IN common-mode limit is +1.6 V.
2. Photodiode/APD cathode to positive bias (through the RC filter and current limit), anode to OPA857 IN; reverse bias is about cathode voltage minus 1.83 V. Rationale: sets polarity and real bias. Applies unchanged to the S12023-10 APD.
3. FDS010 capacitance is 6 pF typ at 10 V reverse bias. VERIFIED 2026-10-08 against Thorlabs 0636-S01 Rev I (March 16, 2017), docs/datasheets/fds010.pdf p.1; the older Rev E 2 pF figure is superseded. Pinout verified from the Rev I drawing (p.3): pin 1 anode, pin 2 case, pin 3 cathode.
4. +/-3.5 V is the VCA821 minimum; nominal rails +/-3.7 V (tolerance analysis pending). Rationale: margin above the minimum.
5. VCA821 RF is compensation; use datasheet networks; RG current limit about +/-2.6 mA can overload the input even at low gain. Rationale: stability and input overload.
6. Unity buffer plus diode is not a precision peak detector; the fast high/low detector is the main unresolved block, built as a disconnectable, swappable sub-circuit. Rationale: accuracy and risk isolation.
7. VSPAN subtractor: R41 VLOW->IN-, R42 OUT->IN-, R43 VHIGH->IN+, R44 IN+->GND, all 10k 0.1% matched. Rationale: ratio accuracy sets span error.
8. VMID: two matched 10k into a high-impedance buffer; threshold trim via a source selector or proper summing stage, never a resistor into a buffer output. Rationale: a resistor into a buffer output does not sum.
9. AGC is a true integrator (C in feedback), 100k/47 nF giving 4.7 ms; anti-windup acts on integrator state; freeze is not reset. Rationale: zero steady-state error and defined recovery.
10. Post-AGC span alone cannot prove signal presence; gain bounds, dwell and FPGA digital validity decide. Rationale: AGC amplifies noise to target.
11. TLV3605 SHDN is active-low; shutdown is not a guaranteed zero; LE/HYS low latches the last state; both constant LVDS states are "invalid" after an FPGA timeout on an independent clock. Rationale: avoid mistaking a stuck output for data.
12. FPGA watchdog runs on an independent local clock; reacquire CDR and framing after release; invalid-code counts are not a BER measurement. Rationale: watchdog must survive loss of recovered clock; counts miss errors.
13. SAMD51 DACs are 12-bit; OPA320 is single, OPA2320 dual. Rationale: correct resolution and part selection.
14. LM27762 positive/negative references differ (1.2 V vs 1.22 V), so rails use different divider ratios. Rationale: regulator limits. (The MAX15032 VIN+1 V bound, bias rail >= 6.5 V, applied to the PIN design and is retired with decision 8; the APD bias supply is selected in docs/research/apd-bias-supply.md.)
