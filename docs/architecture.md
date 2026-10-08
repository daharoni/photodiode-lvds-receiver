# Architecture

Labels: VERIFIED (checked against a cited datasheet/measurement), PROPOSED (design intent, not yet proven), UNRESOLVED (open). Nothing here is measured or simulated yet; hence few VERIFIED labels. The architecture is analog-first by user decision.

The three biggest open risks are the **APD bias supply**, the **fast high/low detector** and **OPA857 behavior at 6 pF source capacitance**. The detector is a silicon APD (decision-log entry 8, PROPOSED): a bare PIN was 18-23 dB optical short at 35 cm lateral and APD gain closes the link with a modest NIR emitter. The link budget is a joint transmitter/receiver budget: the headstage emitter (wavelength, radiant intensity, drive, modulation) is redesigned to match this receiver, so neither side is fixed.

## Rails

| Rail | Source | Use | Label |
|---|---|---|---|
| 5V in | Board input (up to 5.25 V) | All rails | PROPOSED |
| 3V3 | TPS79901 LDO | OPA857, comparator, logic | PROPOSED |
| +3V7 / -3V7 | LM27762 | VCA821 (min +/-3.5 V; tolerance analysis pending) | PROPOSED |
| 5V_A | Filtered 5 V | Analog supply feed | PROPOSED |
| APD_BIAS (HV) 100-220 V | Programmable, temperature-compensated, low-noise APD bias supply (IC/module TBD; options pending in docs/research/apd-bias-supply.md), RC-filtered | APD cathode via RC filter (e.g. 10 kohm + 10 nF, >= 250 V C0G, values PROPOSED) and series current limit. Needs 200 V creepage/clearance and keep-out from TIA_IN. Replaces the MAX15032 6.5-15 V block | PROPOSED (supply UNRESOLVED) |

LM27762 positive and negative references differ (1.2 V vs 1.22 V), so the rails use different divider ratios.

## Signal chain

1. **APD (APD_BIAS, TIA_IN).** Primary Hamamatsu S12023-10 (phi 1.0 mm, 6 pF, VBR 150 V typ / 200 V max, operating about 120-190 V for M = 50-100, dVBR/dT about 0.65 V/C, TO-18 with window; datasheet figures per docs/research/apd-selection.md). Fallback S12023-05 (phi 0.5 mm, 2 pF). Cathode to APD_BIAS through the RC filter and a series current limit, anode to TIA_IN (same polarity as before); reverse bias is about cathode voltage minus 1.83 V. Slow AGC absorbs slow gain drift, but the bias needs coarse temperature compensation (thermistor network or a future SAMD51 DAC). Ambient light is multiplied by M too, so the optical bandpass filter is mandatory and the OPA857 20k linear range (60 uA input) is the saturation bound. The HV node needs 200 V creepage/clearance and keep-out from the TIA input. FDS010 (TO-5, 6 pF) is kept only as a bench fallback footprint. Label: PROPOSED (part and bias design not final; operating voltage per unit UNRESOLVED).
2. **OPA857 TIA (TIA_OUT, TIA_REF).** A transimpedance stage first because the diode is a current source with large capacitance; converting to voltage at the source keeps noise and bandwidth under control before any variable gain. Differential output with OUTN about 1.83 V reference. Label: PROPOSED (stability with 6 pF source capacitance UNRESOLVED; datasheet gives noise plot only).
3. **AC coupling.** OPA857 outputs are never DC-wired to the VCA821: OUTN is about 1.83 V and the VCA821 +IN common-mode limit is +1.6 V. AC coupling also removes ambient/DC photocurrent and offset, at the cost of baseline wander with long runs; 8b/10b bounds run length and DC balance, which is why it is acceptable. 6.63 MHz field pickup is in-band and is handled by shielding, not filtering. Label: PROPOSED.
4. **VCA821 VGA (VGA_P/N, VGA_OUT).** Variable gain after the TIA so the TIA runs at fixed gain and noise performance, and dynamic range is handled by the VGA. RF is compensation (use datasheet networks); RG current limit about +/-2.6 mA can overload the input even at low gain. Label: PROPOSED.
5. **Level shift (VCM_DET, SDET).** Shift to about 1.65 V for the comparator and the detectors. Label: PROPOSED.
6. **Shared fast high/low capture (VHIGH, VLOW).** One capture block feeds both slicer threshold and AGC, so they see the same signal. A unity buffer plus diode is not a precision peak detector; this is the main unresolved block and is built as a disconnectable, swappable sub-circuit. Label: UNRESOLVED.
7. **VMID and VSPAN.** VMID = (VHIGH+VLOW)/2 via two matched 10k into a high-impedance buffer; threshold trim (VTH) through a source selector or proper summing stage, never a resistor into a buffer output. VSPAN = VHIGH-VLOW via subtractor R41 VLOW->IN-, R42 OUT->IN-, R43 VHIGH->IN+, R44 IN+->GND, all 10k 0.1%. Label: PROPOSED.
8. **AGC integrator (VINT, VG).** A true integrator (C in feedback, 100k/47 nF, 4.7 ms) compares VSPAN to a target and drives VG. An integrator gives zero steady-state span error, which a proportional loop does not. Anti-windup acts on integrator state; freeze is not reset. Post-AGC span alone cannot prove signal presence (a noise-only input is amplified up to target), so gain bounds plus dwell plus FPGA digital validity decide. Label: PROPOSED.
9. **TLV3605 comparator (LVDS_P/N, SHDN_N, LE_HYS).** Slices against VMID and outputs LVDS directly, giving a clean digital edge with low skew and noise immunity over a cable to the FPGA. SHDN_N is active-low; shutdown is not a guaranteed zero; LE/HYS low latches the last state; both constant LVDS states are "invalid" after an FPGA timeout on an independent clock. Label: PROPOSED.
10. **ECP5 FPGA (ULX3S first).** The FPGA does clock recovery, 8b/10b decode, framing and redundant-lane merge, because no clock is sent: a digital CDR is flexible, lets the rate change, and avoids a PLL on the module. Its watchdog uses an independent local clock and the CDR and framing are reacquired after release; invalid-code counts are not a BER measurement. ULX3S true pairs: gp/gn[8..13] (bank 7), gp/gn[14..21] (banks 2/3); VCCIO 3.3 V; use DIFFRESISTOR for termination. LVDS input on a 3.3 V bank is UNVERIFIED. Label: UNRESOLVED (pending that check).
11. **SAMD51 hooks (optional).** ADC monitoring, 12-bit DACs for gain/threshold. OPA320 is single, OPA2320 dual. Not in the primary signal path. Label: PROPOSED.

## States

| State | Entry | Behavior | Exit |
|---|---|---|---|
| POWER-UP / SEARCH | Rails up, bias starting | Integrator held at known gain (max or preset); comparator in defined state; FPGA searches for valid code | Span in bounds with dwell |
| ACQUIRE | Signal-like span seen | AGC converging; FPGA CDR locking, framing | Gain settled and FPGA reports valid frames |
| TRACK | Valid frames | AGC integrating normally; thresholds follow | Loss of span or digital validity |
| LOS / FAULT | Gain at bound with dwell, or FPGA timeout | Integrator frozen (not reset) with anti-windup; comparator state invalid; FPGA reacquires after release | Span returns, then ACQUIRE |

Entry/exit thresholds and dwell times are UNRESOLVED until G3. Provisional goals: local analog LOS <= 1 ms, reacquisition <= 20 ms (not approved).
