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
- [ ] Manual-gain optical eye/step/saturation test across bias range and both TIA gains
- [ ] Measure TIA->VGA common-mode, differential input and RG overload
- [ ] Measure AC-coupling response to training, gaps and abrupt light changes

## G2: detector proof

Acceptance: held levels track eye centers; midpoint/span error <= 5% of span at 1 V (goal); detector adds <= 0.05 UI jitter (goal).

- [ ] Compare held levels to center-eye histograms with 0101, isolated one/zero, max runs, commas, PRBS payload
- [ ] Sweep hold C/R, temperature, noise, diode current; bound midpoint/span error, settling, droop, loading
- [ ] Eye with detector connected vs disconnected (added jitter <= 0.05 UI goal)

## G3: closed-loop proof

Acceptance: stable loop with >= 60 degrees phase margin, correct sign, working clamps and anti-windup, defined behavior through all startup and fade cases.

- [ ] Measure gain slope and detector pole; verify sign
- [ ] Verify >= 60 degrees phase margin, clamps, anti-windup
- [ ] Dark start, weak light, sudden strong light, interruption and return (includes the SEARCH-at-max-gain behaviour: LOS no longer freezes the integrator, decision 10)
- [ ] Verify VINT upper bound against the VCA821 VG range; decide whether the DNP BAS70 clamps or a hard limiter are needed
- [ ] Latch/shutdown/independent-clock timeout behavior

## G4: system proof

Acceptance: BER measured against known transmitted truth meets the approved target (BER <= 1e-9 is a provisional goal); redundancy works; CAD checks pass before any board order.

- [ ] BER vs known transmitted truth
- [ ] Redundancy tests: skew, missing lane, conflicting frames, CRC errors, rejoin
- [ ] Pre-order CAD checks: symbols/footprints/pin maps, ERC, DRC, stackup, independent review
