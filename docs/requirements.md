# Requirements

Status key: ANSWERED (user stated it), PARTIAL (some of it known), ASSUMED (our working guess). Facts are from the user, 2026-10-08, unless noted. Scope: this receiver is not required to be backward compatible with the Miniscope Zero headstage. The headstage (emitter, driver, encoder) will be redesigned to match this receiver.

## Requirement table

| Requirement | Current answer | Working assumption | Status |
|---|---|---|---|
| 1. Rate / protocol | 50 Mbps line rate, 8b/10b (40 Mbps payload), UI = 20 ns. Soft target: higher is welcome, lower acceptable. Miniscope Zero tops out near 12 Mbps. | Continuous stream with regular commas; framed packets with sequence numbers. SAMD51 headstage can generate 8b/10b at this rate (user tested). | PARTIAL |
| 1b. Emitter co-design | Emitter wavelength, radiant intensity, drive and modulation are co-design variables, not constraints. NIR preferred. Headstage brightness can increase; headstage may move to an FPGA later. | Start from the NIR part below (QBLP601-2IR4) as a reference emitter only. Two bands (630 nm and 765 nm) supported by one module with a swappable filter. | ASSUMED |
| 2. Optical link budget | No received-power measurement exists. | Estimate from LED datasheets at the paper's 70 cm single-receiver coverage diameter; flagged as an estimate and a joint transmitter/receiver budget. Detector is now a silicon APD (decision-log entry 8; docs/calculations/link-budget.md, docs/research/apd-selection.md): a bare PIN was 18-23 dB optical short at 35 cm lateral; APD gain with a modestly brighter NIR emitter closes it. 6 pF worst case (S12023-10 and FDS010 alike). Ambient is multiplied by M, so the optical bandpass filter is mandatory; OPA857 20k linear range (60 uA input) is the saturation bound. | PARTIAL (budget is an estimate, PROPOSED) |
| 2b. Detector | Silicon APD, primary Hamamatsu S12023-10 (phi 1.0 mm, 6 pF, VBR 150 V typ / 200 V max, operating about 120-190 V for M = 50-100, dVBR/dT about 0.65 V/C, TO-18 window); fallback S12023-05 (phi 0.5 mm, 2 pF). Bias: programmable, temperature-compensated, low-noise 100-220 V supply (selection pending, docs/research/apd-bias-supply.md). FDS010 is a bench fallback only. | Slow AGC absorbs slow gain drift; bias still needs coarse temperature compensation. | PROPOSED |
| 3. Error / timing targets | Paper used packet error rate 1e-3 as coverage threshold with 40,256-bit payloads. | Provisional test goals, NOT approved requirements: BER <= 1e-9, reacquisition <= 20 ms, local analog LOS <= 1 ms. | ASSUMED |
| 4. Electrical / mechanical envelope | Input 5 V. Module exposes power, ground, one LVDS pair, debug pads. Shielded aluminum housing, swappable optical bandpass filter. Sits in a 6.63 MHz QSCR wireless-power field (in-band for the receiver). No size constraint now; smaller is better, condense after validation. One PCB, hierarchical sheets. ECP5 on ULX3S first. | Input up to 5.25 V. ULX3S LVDS pairs gp/gn[8..13] (bank 7), gp/gn[14..21] (banks 2/3), VCCIO 3.3 V, no on-board 100 ohm termination (use ECP5 DIFFRESISTOR). LVDS input on a 3.3 V bank is UNVERIFIED. | PARTIAL |
| 5. Redundancy contract | Multiple receiver lanes merged in the FPGA. Skew and merge policy not specified. | Framed packets with sequence numbers; select validated copies. | ASSUMED |
| 6. Fade / startup behavior | Maximum fade rate and ambient illumination not known. Blue ~470 nm behavioral light is filtered. IR 38 kHz downlink transmitter is separate, not on this board. | Local analog LOS within 1 ms (provisional); FPGA owns validity and reacquisition. | ASSUMED |

## Previous system baseline (Miniscope Zero)

Historical baseline, not a constraint (see scope note above).

- Link: bioRxiv 10.64898/2026.09.05.745822. Maximum about 12 Mbps (8 Mbps Manchester, about 16 Mbaud).
- Receiver: Hamamatsu C15522-3010SA SiPM module (3x3 mm, 10-15 MHz bandwidth, the cause of the ceiling), custom high-gain amplifier plus adaptive digitizer, Opal Kelly XEM7310 FPGA.
- Why abandoned: SiPM limited custom electronics, bandwidth and has poor NIR response. The user is open to an APD, other PIN diodes, or a lens/concentrator. An Edmund compound parabolic concentrator was tried earlier without success, possibly user error.
- Red emitter: Wurth 150060RS75003, 0603, 630 nm peak, 530 mcd at 20 mA, no speed spec.
- NIR emitter: QT Brightek QBLP601-2IR4, 765 nm peak, 1.0 mW/sr typ at 20 mA, 140 degree viewing angle, 1 A pulsed at 1% duty.
- Driver: EPC2038 GaN FET. Encoder: SAMD51.
- Coverage: 70 cm diameter for a single receiver (paper).

## Detector facts (FDS010, bench fallback only; the APD path is the design)

Capacitance 6 pF typ at 10 V, rise/fall 1 ns (830 nm, 50 Ω, 10 V), dark current 0.3 nA typ / 1.0 nA max at 10 V, 25 V max reverse, peak 0.44 A/W at 730 nm, active area 0.8 mm² (Ø1.0 mm), TO-5. VERIFIED against 0636-S01 Rev I (2017-03-16), docs/datasheets/fds010.pdf. Pins: 1 anode, 2 case, 3 cathode (drawing p.3).

## Open items

1. Ambient/behavioral illumination level at the receiver.
2. Maximum fade rate.
3. Burst/idle structure of the new 8b/10b stream (assume continuous with commas).
4. Maximum skew and merge policy between redundant lanes.
5. Measured received optical power (none yet) and the joint link budget.
6. Detector choice: APD selected (PROPOSED; S12023-10 primary, S12023-05 fallback); final part pending bias design.
7. Emitter co-design: wavelength, radiant intensity, drive and modulation.
8. Whether ECP5 accepts LVDS input on a 3.3 V bank (UNVERIFIED).
9. Installed detector capacitance (6 pF datasheet typ) by measurement at the actual bias, including lead and pad parasitics.
10. Approval of the provisional BER, reacquisition and LOS goals.
11. APD bias supply selection (UNRESOLVED; options in docs/research/apd-bias-supply.md, pending).
12. APD temperature compensation method: thermistor network (Rev A) refined by the on-module ESP32 via the MCP4728 DAC_HV trim (UNRESOLVED until G1).
13. Measure actual S12023-10 operating voltage per unit (UNRESOLVED; datasheet gives VBR only, Vop is graph-read).
14. OPA857 stability at 6 pF source capacitance (UNRESOLVED; datasheet gives noise plot only).
