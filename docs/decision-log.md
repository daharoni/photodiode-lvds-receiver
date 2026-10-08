# Decision log

All entries dated 2026-10-08 (user session). Labels are PROPOSED unless noted.

## Decisions

1. **Analog-first.** AGC and slicing are analog; MCU/ADC hooks are optional. Rationale: user decision, lowest latency and independent of firmware.
2. **Single PCB, hierarchical sheets.** Rapid iteration instead of many coupons.
3. **ULX3S first FPGA target.** Available now; LVDS-on-3.3 V-bank still UNVERIFIED.
4. **Shielded housing and swappable filter.** 6.63 MHz QSCR field is in-band; one module serves 630 nm and 765 nm.
5. **Rails +/-3.7 V; APD_BIAS 100–220 V (superseded PD_BIAS >= 6.5 V on 2026-10-08).** See corrections 4 and 14 and decision 8.
6. **All new parts via lab-library PR.** No project-local symbols; library at ~/Projects/kicad-lab-library.
7. **Headstage co-designed with receiver; no backward compatibility requirement.** Emitter wavelength, radiant intensity, drive and modulation are co-design variables (NIR preferred); the link budget is joint. Miniscope Zero emitter facts are baseline only.
8. **Detector: silicon APD selected (2026-10-08).** The link budget (docs/calculations/link-budget.md) shows a bare FDS010 PIN into the OPA857 is 18–23 dB optical short of Q = 6 at 35 cm lateral with any headstage-power-compatible emitter, because photocurrent (1–3 nA) is far below TIA noise (8–26 nA). Étendue caps optics at ~2× for a ±45° field of view. An APD with M ≈ 50 plus a modestly brighter NIR emitter closes the link with margin. Daniel approved the APD path. Consequences: the 6.5–15 V MAX15032 bias block is replaced by a 150–200 V temperature-compensated APD bias supply; the FDS010 remains a drop-in fallback only if a compatible footprint is kept; part selection is tracked in docs/research/apd-selection.md. PROPOSED until a part and bias design are chosen.

9. **APD bias supply: on-board LT8365 boost + charge-pump stage (2026-10-08).** Daniel prefers to handle as much as reasonable on our own PCB rather than a purchased HV module. Rev A therefore carries an LT8365-based 100–220 V generator (datasheet Rev. A and DC2838A demo manual Rev. 0 archived in docs/datasheets/), a two-stage RC cathode filter, series current limit, NTC temperature-tracking divider with a DAC-trim hook, and a footprint/pads for an external HV module as bench fallback. Design calculations in docs/calculations/apd-bias-design.md. PROPOSED until measured.

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
