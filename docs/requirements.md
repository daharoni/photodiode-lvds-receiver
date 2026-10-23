# Requirements

Status key: ANSWERED (user stated it), PARTIAL (some of it known), ASSUMED (our working guess). Facts are from the user, 2026-10-08, unless noted. Scope: this receiver is not required to be backward compatible with the Miniscope Zero headstage. The headstage (emitter, driver, encoder) will be redesigned to match this receiver.

## Requirement table

| Requirement | Current answer | Working assumption | Status |
|---|---|---|---|
| 1. Rate / protocol | 50 Mbps line rate, 8b/10b (40 Mbps payload), UI = 20 ns. Soft target: higher is welcome, lower acceptable. Miniscope Zero tops out near 12 Mbps. | Continuous stream with regular commas; framed packets with sequence numbers. SAMD51 headstage can generate 8b/10b at this rate (user tested). | PARTIAL |
| 1b. Emitter co-design | Emitter wavelength, radiant intensity, drive and modulation are co-design variables, not constraints. NIR preferred. Headstage brightness can increase; headstage may move to an FPGA later. | Start from the NIR part below (QBLP601-2IR4) as a reference emitter only. Two bands (630 nm and 765 nm) supported by one module with a swappable filter. | ASSUMED |
| 2. Optical link budget | No received-power measurement exists. | Estimate from LED datasheets at the paper's 70 cm single-receiver coverage diameter; flagged as an estimate and a joint transmitter/receiver budget. Detector is now a silicon APD (decision-log entry 8; docs/calculations/link-budget.md, docs/research/apd-selection.md): a bare PIN was 18-23 dB optical short at 35 cm lateral; APD gain closes it only with an emitter about 4.5 to 4.8x the reference QBLP601 at 50 mA on the direct path alone (11 to 12 mW/sr on axis over 140 degrees for Q = 6 at the built 70 MHz noise bandwidth, M 83 to 100; decision 31, link-budget.md revision 2026-10-22). Optics on the direct path, the reflective arena and receiver tiling are PROPOSED credits against that, not margin; working emitter assumption: 1 W class 850 nm LED at 30 to 100 mA on-state, up to 200 mA without the credits. Range in optical dB: 10 to 12 dB unclipped per setting, firmware adds 18 to 19 dB at the strong end only; fade margin equals emitter margin. 6 pF worst case (S12023-10 and FDS010 alike). Ambient is multiplied by M, so the optical bandpass filter is mandatory; OPA857 20k linear range (60 uA input) is the saturation bound. | PARTIAL (budget is an estimate, PROPOSED) |
| 2b. Detector | Silicon APD, primary Hamamatsu S12023-10 (phi 1.0 mm, 6 pF, VBR 150 V typ / 200 V max, operating about 120-190 V for M = 50-100, dVBR/dT about 0.65 V/C, TO-18 window); fallback S12023-05 (phi 0.5 mm, 2 pF). Bias: programmable, temperature-compensated, low-noise 100-220 V supply, on-board LT8365 boost plus doubler (decision 9, docs/calculations/apd-bias-design.md). FDS010 is a bench-only reference (D11 dropped from Rev A 2026-10-09). | The NTC network in the bias feedback gives coarse temperature tracking; the ESP32 trims M slowly through DAC_HV and selects 20k/5k (decision 12); no analog AGC. | PROPOSED |
| 3. Error / timing targets | Paper used packet error rate 1e-3 as coverage threshold with 40,256-bit payloads. | Provisional test goals, NOT approved requirements: BER <= 1e-9, reacquisition <= 20 ms; loss of signal is judged by the FPGA decoder validity on an independent-clock timeout (no analog LOS since decision 12), detection time goal 1 ms. | ASSUMED |
| 4. Electrical / mechanical envelope | Input 5 V on the VBUS of one 24-pin USB-C receptacle (decision 14). The module exposes 5 V, ground, the LVDS pair (duplicated on both SS TX pairs), CAN and USB D+/D- on that one connector, plus a scope header J51 and debug pads. Cable rule (PROPOSED): passive full-featured, USB 3.2 Gen 1, 3 A, e-marked, <= 2 m certified; 3 m only after a bench check of the specific cable. Shielded aluminum housing, swappable optical bandpass filter. Sits in a 6.63 MHz QSCR wireless-power field (in-band for the receiver). No size constraint now; smaller is better, condense after validation. One PCB, hierarchical sheets. ECP5 on ULX3S first. | Input up to 5.25 V. ULX3S LVDS pairs gp/gn[8..13] (bank 7), gp/gn[14..21] (banks 2/3), VCCIO 3.3 V, no on-board 100 ohm termination (use ECP5 DIFFRESISTOR). LVDS input on a 3.3 V bank is UNVERIFIED. | PARTIAL |
| 5. Redundancy contract | Multiple receiver lanes merged in the FPGA. Skew and merge policy not specified. | Framed packets with sequence numbers; select validated copies. | ASSUMED |
| 6. Fade / startup behavior | Maximum fade rate and ambient illumination not known. Blue ~470 nm behavioral light is filtered. IR 38 kHz downlink transmitter is separate, not on this board. | FPGA owns LOS, validity and reacquisition (decoder validity plus an independent-clock timeout; no analog LOS since decision 12); detection within 1 ms is a provisional goal. | ASSUMED |

## USB standalone requirement

Daniel's requirement, 2026-10-09 (user-supplied, ANSWERED): "anyone should be able to plug a module into a random laptop over USB, program it and verify it, with no FPGA attached". Still satisfied: first realised by decision 13, now realised by decision 14 (one 24-pin USB-C; VBUS through the TPS259631 eFuse is the only 5 V input; D+/D- to the ESP32-C6; the TPS2121 two-source mux is gone). PROPOSED until G1 and G4 measurements.

## Previous system baseline (Miniscope Zero)

Historical baseline, not a constraint (see scope note above).

- Link: bioRxiv 10.64898/2026.09.05.745822. Maximum about 12 Mbps (8 Mbps Manchester, about 16 Mbaud).
- Receiver: Hamamatsu C15522-3010SA SiPM module (3x3 mm, 10-15 MHz bandwidth, the cause of the ceiling), custom high-gain amplifier plus adaptive digitizer, Opal Kelly XEM7310 FPGA.
- Why abandoned: SiPM limited custom electronics, bandwidth and has poor NIR response. The user is open to an APD, other PIN diodes, or a lens/concentrator. An Edmund compound parabolic concentrator was tried earlier without success, possibly user error.
- Red emitter: Wurth 150060RS75003, 0603, 630 nm peak, 530 mcd at 20 mA, no speed spec.
- NIR emitter: QT Brightek QBLP601-2IR4, 765 nm peak, 1.0 mW/sr typ at 20 mA, 140 degree viewing angle, 1 A pulsed at 1% duty.
- Driver: EPC2038 GaN FET. Encoder: SAMD51.
- Coverage: 70 cm diameter for a single receiver (paper).
- Environment and system facts (Daniel, 2026-10-23): optics will be placed in front of the APD to improve collection; the arena walls are reflective, so the headstage LED illuminates the whole environment rather than a point-to-point path; several receiver modules will watch the same LED and the FPGA merges their lanes (row 5), so tiling is expected to keep at least one receiver in strong signal across the arena. Arena dimensions and wall reflectance at 850 nm: UNRESOLVED.

## Detector facts (FDS010, bench-only reference; the APD is the design and the FDS010 footprint is not on the Rev A board since 2026-10-09)

Capacitance 6 pF typ at 10 V, rise/fall 1 ns (830 nm, 50 Ω, 10 V), dark current 0.3 nA typ / 1.0 nA max at 10 V, 25 V max reverse, peak 0.44 A/W at 730 nm, active area 0.8 mm² (Ø1.0 mm), TO-5. VERIFIED against 0636-S01 Rev I (2017-03-16), docs/datasheets/fds010.pdf. Pins: 1 anode, 2 case, 3 cathode (drawing p.3).

## Open items

1. Ambient/behavioral illumination level at the receiver.
2. Maximum fade rate.
3. Burst/idle structure of the new 8b/10b stream (assume continuous with commas).
4. Maximum skew and merge policy between redundant lanes.
5. Measured received optical power (none yet) and the joint link budget.
6. Detector choice: APD selected (PROPOSED; S12023-10 primary, fitted as D10 on Rev A; S12023-05 fallback); confirm per unit at G1.
7. Emitter co-design: wavelength, radiant intensity, drive and modulation.
8. Whether ECP5 accepts LVDS input on a 3.3 V bank (UNVERIFIED).
9. Installed detector capacitance (6 pF datasheet typ) by measurement at the actual bias, including lead and pad parasitics.
10. Approval of the provisional BER, reacquisition and LOS goals.
11. APD bias supply: LT8365 boost plus doubler selected and drawn (decision 9, docs/calculations/apd-bias-design.md); PROPOSED until measured at G1.
12. APD temperature compensation method: thermistor network (Rev A) refined by the on-module ESP32 via the MCP4728 DAC_HV trim (UNRESOLVED until G1).
13. Measure actual S12023-10 operating voltage per unit (UNRESOLVED; datasheet gives VBR only, Vop is graph-read).
14. OPA857 stability at 6 pF source capacitance (UNRESOLVED; datasheet gives noise plot only).
