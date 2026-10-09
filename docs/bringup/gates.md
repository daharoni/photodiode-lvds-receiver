# Bring-up gates

No gate has been started. Goals marked "goal" are provisional, not user-approved requirements.

## G1: fast-path proof

Simulation inputs (SIMULATED, ngspice 47 with TI models, `docs/simulation/README.md`; no parasitics, no tolerances, nothing measured): compare each G1 measurement below with the simulated number named in its item. The sims could not show: the cascade OPA857 -> C51 -> OPA855 end to end; the TLV3605 or any noise/BER (no model); the real OPA855 clip level and recovery (the model clips 0.25-0.35 V below the datasheet VOL and limit-cycles); the OPA855 loop-gain phase in a second simulator (ngspice AC polarity quirk); the OPA857 at 6 pF in silicon (model validated only at 1.5 pF); PCB and package parasitics, tolerances, temperature.

Acceptance: manual-gain optical eye is open at target rate across bias range and both TIA gains; supplies meet worst-case VGA needs; TIA->VGA interface is within limits.

- [ ] Verify APD VBR and gain-vs-bias curve per unit at room temperature (S12023-10; record operating voltage for M = 50 and 100)
- [ ] Confirm APD bias supply ripple/noise at the APD node with the TIA running (HV safety rules observed); compare SYNC/MODE float (pulse-skip) vs Burst
- [ ] Cathode-capacitor discharge test into a sacrificial TIA (C50 10 nF vs 4.7 nF)
- [ ] Verify bias temperature tracking over 15-35 C (gain stays within AGC range)
- [ ] Verify ambient saturation margin with the real optical filter (OPA857 20k linear range, 60 uA input)
- [ ] Record wavelength and optical power; FDS010 checks only if the bench fallback is used
- [ ] Load-test supplies including worst-case VGA rails, sequencing, ripple, thermal, bias startup
- [ ] Optical eye/step/saturation test across the bias range and both TIA gains at the fixed post-amp gain (decision 12)
- [ ] Post-amp clip test: 2x and 10x over the 9 uA (20k) clip point with a 5-UI pattern; measure recovery and zero-crossing shift against the 3 ns datasheet figure. The simulation (OPA855 model, recovery under 1 ns, limit cycle at its 0.8 V floor) is not a prediction for the real part: look for any oscillation on OUT while overdriven and for the real clip level near 1.05-1.15 V
- [ ] OPA855 stability at RF 301 / RG 49.9 as built: closed-loop frequency response or a fast step at PA_OUT, compare with the simulated 0.1 dB peaking, 2.13 GHz -3 dB, about 1 % overshoot on 2 ns edges; also check the idle level at OUT against both the model (1.578 V) and the derived 1.73 V
- [ ] OPA857 at 6 pF in both CTRL modes: -3 dB bandwidth, peaking and the eye at 50 Mb/s; compare with the simulated 20k 13.8 % overshoot / 12.6 ns to 2 % and 5k 1.7 % / 4.7 ns. The 20k eye at 6 pF is the key measurement (ISI risk); the 5k eye shows whether 5k can be the preferred mode
- [ ] VCM_REF buffer: step the load or the divider and look for ringing at VCM_REF with C101 1 uF and R102 10 ohm; compare with the simulated 87.6 deg PM and 0.96 mV shift per 100 mV via 1 k
- [ ] Comparator small-signal test: 5-30 mV pulses at VCM 1.65 V; delay, jitter, effective input noise; bias-current offset through the 1 k returns
- [ ] Chain noise at the comparator input with the APD (6 pF) connected, 20k and 5k
- [ ] Measure AC-coupling response to training, gaps and abrupt light changes (baseline wander with 8b/10b)
- [ ] CTRL (20k/5k) and bias-step switching transients: how long until the slicer is valid again
- [ ] eFuse U5 TPS259631 (decision 14): measure OV cut-off (calculated 5.76-6.20 V), UVLO rising/falling (4.06-4.32 V / 3.72-4.00 V), ILIM (0.68-0.84 A) and first-plug inrush with C32 47 nF and the estimated 25 uF on +5V (calculated ramp about 5.3 ms, about 23 mA); check FLT and the IMON test point
- [ ] Fan-out U50 (SN65LVDS104): LVDS eye at the receptacle on both TX pairs through a 2 m certified cable at 50 Mb/s, VOD and common mode against the ECP5 +-100 mV threshold, 3V3 current with outputs 1-3 enabled; J51 output 3 scope eye
- [ ] USB auto-reset and download through the 22 ohm R193/R194 and the USBLC6: esptool/browser flashing of an empty-flash module from a laptop root port, RESET/BOOT recovery, 3V3_D rise versus the EN RC
- [ ] USB-alone self-test current: total +5V input current at dark, with HV at 220 V and 0.5-1 mA load, and at ESP32 boot/flash-write peaks, against the 0.19 A (0.24 A margin) estimate and the 0.5 A USB default; measure the CC1/CC2 voltages at the pins and at the ADC (CC1_SENSE/CC2_SENSE) with a real source port and with 2-3 laptops/hubs; confirm class and orientation classification

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

- Pre-order (decision 14 / fab settings): order the receiver module at JLCPCB with "Min via hole size/diameter" = 0.25 mm/(0.35/0.4 mm) (the high-precision tier; JLCPCB then auto-selects "4-Wire Kelvin Test" and "FR4 Tg155", extra cost), 6 layers, JLC06161H-3313, ENIG, impedance control; confirm the 90/100 ohm trace geometries in JLCPCB's impedance calculator (ours are computed, PROPOSED); the J50 hole waiver in `receiver-module.kicad_dru` relies on the DFM pass with that option on 2026-10-09 (`hardware/pcb/j50-dfm-test`). PROPOSED.

Acceptance: BER measured against known transmitted truth meets the approved target (BER <= 1e-9 is a provisional goal); redundancy works; CAD checks pass before any board order.

- [ ] BER vs known transmitted truth
- [ ] Redundancy tests: skew, missing lane, conflicting frames, CRC errors, rejoin
- [ ] Pre-order CAD checks: symbols/footprints/pin maps, ERC, DRC, stackup, independent review
- [ ] Laptop foreign-host test (decision 14): plug a module into two different laptops (ideally two OSes/vendors, USB 3 Type-C), scope the CAN pins and the LVDS pair: does the host treat the 10-25 kohm per pin CAN load as a termination, SS receiver-detect, SBU handling; module stays harmless and the CAN is silent; decide the foreign-host mitigations (draft open item 3) afterwards
- [ ] 3 m cable check (decision 14): for a specific candidate passive cable, DC continuity of the SS wires (A2 to B11 etc.: a few ohms for passive full-featured), then scope LVDS and CAN through it; accept 3 m only for that cable
- [ ] CAN with 14 stubs (decision 14): bus with one split termination at the breakout, 125 kbit/s, R199 100 k, stubs up to 3 m: error counters, edges
- [ ] CAN-to-LVDS crosstalk inside the cable (decision 14): CAN edges (about 2 V) against the adjacent LVDS pair (about 350 mV); BER with CAN traffic on versus off
- [ ] USB-PD charger or hub plugged into a module (decision 14): stays at 5 V, hard-reset VBUS dip tolerated; hub-powered current behaviour
