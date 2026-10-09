# Bring-up gates

No gate has been started. Goals marked "goal" are provisional, not user-approved requirements.

## G1: fast-path proof

Acceptance: manual-gain optical eye is open at target rate across bias range and both TIA gains; supplies meet worst-case VGA needs; TIA->VGA interface is within limits.

- [ ] Verify APD VBR and gain-vs-bias curve per unit at room temperature (S12023-10; record operating voltage for M = 50 and 100)
- [ ] Confirm APD bias supply ripple/noise at the APD node with the TIA running (HV safety rules observed); compare SYNC/MODE float (pulse-skip) vs Burst
- [ ] Cathode-capacitor discharge test into a sacrificial TIA (C50 10 nF vs 4.7 nF)
- [ ] Verify bias temperature tracking over 15-35 C (gain stays within AGC range)
- [ ] Verify ambient saturation margin with the real optical filter (OPA857 20k linear range, 60 uA input)
- [ ] Record wavelength and optical power; FDS010 checks only if the bench fallback is used
- [ ] Load-test supplies including worst-case VGA rails, sequencing, ripple, thermal, bias startup
- [ ] Optical eye/step/saturation test across the bias range and both TIA gains at the fixed post-amp gain (decision 12)
- [ ] Post-amp clip test: 2x and 10x over the 9 uA (20k) clip point with a 5-UI pattern; measure recovery and zero-crossing shift against the 3 ns datasheet figure
- [ ] Comparator small-signal test: 5-30 mV pulses at VCM 1.65 V; delay, jitter, effective input noise; bias-current offset through the 1 k returns
- [ ] Chain noise at the comparator input with the APD (6 pF) connected, 20k and 5k
- [ ] Measure AC-coupling response to training, gaps and abrupt light changes (baseline wander with 8b/10b)
- [ ] CTRL (20k/5k) and bias-step switching transients: how long until the slicer is valid again
- [ ] USB source mux U5 (decision 13): time to +5V after first plug-in (settling tSET, no datasheet formula) and inrush current with C32 220 nF; compare the estimate of a 5 V ramp in about 13-14 ms
- [ ] U5 both-sources behaviour: cable only, USB only, both, cable removed while running (switchover about 100 us typ, hold-up droop on +5V and 3V3_D), USB removed while on cable; confirm no current into either source and near-0 V on the unpowered input; PR1 chatter with a real ULX3S rail
- [ ] USB auto-reset and download through the 22 ohm R193/R194 and the USBLC6: esptool/browser flashing of an empty-flash module from a laptop root port, RESET/BOOT recovery, 3V3_D rise versus the EN RC
- [ ] USB-alone self-test current: total +5V input current at dark, with HV at 220 V and 0.5-1 mA load, and at ESP32 boot/flash-write peaks, against the 0.19 A (0.24 A margin) estimate and the 0.5 A USB default; check VBUS_SENSE and PWR_SRC levels in all four states

## G2: range-trim proof (replaces the detector-coupon proof; decision 12)

Goal: show that the ESP32's slow trim (APD bias via DAC_HV, TIA_CTRL 20k/5k) holds the link near the Q(M) optimum using RSSI and FPGA validity, and that no analog AGC is needed because intensity changes track animal motion.

- [ ] RSSI vs photocurrent across M and 20k/5k; monotonic, repeatable, temperature drift bounded
- [ ] PRBS BER vs photocurrent at fixed settings: confirm the ~39 dB single-setting window and the clip-region behaviour
- [ ] Trim-loop step response: light step of 10 dB up and down; time to valid frames; no oscillation between 20k/5k
- [ ] APD M vs bias and temperature per unit; DAC_HV EEPROM default and HV_DIS gating verified

## G3: system-behaviour proof

- [ ] Dark start, weak light, sudden strong light, interruption and return (firmware trim + FPGA reacquisition)
- [ ] Threshold trim (DAC_TH) eye walk: BER vs threshold offset, centre found by firmware
- [ ] Latch/shutdown/independent-clock timeout behaviour; CAN link under load; module identity
- [ ] 6.63 MHz field injection with the module in the housing

## G4: system proof

Acceptance: BER measured against known transmitted truth meets the approved target (BER <= 1e-9 is a provisional goal); redundancy works; CAD checks pass before any board order.

- [ ] BER vs known transmitted truth
- [ ] Redundancy tests: skew, missing lane, conflicting frames, CRC errors, rejoin
- [ ] Pre-order CAD checks: symbols/footprints/pin maps, ERC, DRC, stackup, independent review
- [ ] Both sources plugged (decision 13): verify no current into either source; measure with a USB power meter on the laptop port and a series ammeter on the cable +5V
