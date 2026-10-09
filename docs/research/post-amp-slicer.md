# Post-amplifier + baseline-sliced TLV3605 (replacing VCA821 + AGC + peak detectors)

Research note, 2026-10-08. Labels: VERIFIED (document, revision, page/figure) / PROPOSED / UNRESOLVED. Nothing here is measured or simulated;
numbers marked "derived" are arithmetic on datasheet values. Datasheets: TLV3605 SNOSDA2F (docs/datasheets/tlv3605.pdf), OPA857 SBOS630D, OPA858 SBOS629B,
OPA855 SBOS622D, LMH6629 SNOSB18I, THS4541 SLOS375B (all in docs/datasheets/, MANIFEST rows added). Page numbers are the printed datasheet pages.
Inputs: link budget (docs/calculations/link-budget.md, `tools/link_budget.py --apd-sweep`), architecture.md, decision-log entries 8-11.

## 1. TLV3605 at small signal

- Propagation delay 800 ps typ at 50 mV over/underdrive, 50 MHz square wave: VERIFIED (SNOSDA2F p.7, tPD). Dispersion: overdrive 350 ps (10-250 mV), underdrive 200 ps (10-250 mV), common-mode 200 ps (VEE to VCCI): VERIFIED (p.7).
- TPLH vs overdrive, Fig. 5-19/5-20/5-21 (p.12), read off the rendered plot (axis is labelled V_OD (V) but runs 0-250, i.e. mV): the curves start at about 10 mV, which is the lowest overdrive plotted. At VCC = 3.3 V, 25 C the delay there is about 1040 ps (-40 C about 960 ps, 85 C about 1100, 125 C above 1200 ps), falling to about 750 ps by 50 mV and flat above. VERIFIED that nothing below about 10 mV is plotted; the values are graph reads (+/- 30 ps).
- Fig. 5-22..24 (underdrive) also start at about 10 mV. All characterisation uses a 50 MHz square wave / step with 0.3 ns edges and VCM = 0.3 V (p.7 header), not a 5-10 ns noisy signal at VCM = 1.65 V: VERIFIED.
- Input offset +/-0.5 mV typ, +/-5 mV max; hysteresis 0 mV default: VERIFIED (p.7, VIO, VHYST). Input bias current -1 uA typ, +/-5 uA max (current flows out of the pin), offset current +/-1 uA max: VERIFIED (p.7). Input range VEE-0.2 to VCCI+0.2 V (p.7); RDM 67 kohm, RCM 5 Mohm, CIN 1 pF.
- Bias-current effect (derived): a return resistor R from each input to the 1.65 V reference drops IB*R. Single resistor on one input only: 1 kohm gives 1 mV typ / 5 mV max; 10 kohm gives 10 / 50 mV, which is larger than the whole signal. Matched R on both inputs cancels IB and leaves IOS*R: 1 kohm gives 1 mV max, 10 kohm gives 10 mV max. Rule: R <= 1 kohm, identical on both inputs, and IN- decoupled to ground with the same R. IB is specified only at VCM = 0.3 V; its value at 1.65 V is UNRESOLVED.
- Hysteresis: LE/HYS resistor to VEE: 0 mV floating, 30 mV at 150 kohm, 60 mV at 56 kohm (p.8); Fig. 7-4 (p.16, VCC = 3.3 V) shows about 63 mV at low R, about 20 mV at 300 kohm, about 8 mV at 700 kohm; nothing smaller is characterised. VERIFIED. Consequence: the smallest characterised internal setting (about 8 mV) is a large fraction of a 15-25 mVpp signal; external positive feedback (section 7.2.1) is the only way to get 1-3 mV. LE low latches the output on the same pin.
- Minimum allowed input pulse: 600 ps, PWOUT = 90 % of PWIN, at 50 mV over/underdrive (p.8): VERIFIED. At 20 ns UI this is not a limit; the spec says nothing about low overdrive.
- Input noise or minimum detectable signal: there is none. I searched the full text (noise, sensitivity, minimum signal); the only noise statements are the layout advice "comparators are very sensitive to input noise" and the 7.1.4 text on hysteresis. VERIFIED absence. Section 7.2.2 (p.18, Fig. 7-7) shows OPA855 -> TLV360x as an "optical receiver" with no component values and no performance figure; it is a block diagram, not a characterisation.
- Conclusion: a direct TIA-to-comparator connection at 15-25 mVpp is NOT PROVABLE from the datasheet. Missing: comparator input noise, behaviour below 10 mV overdrive, behaviour with slow noisy edges, bias current at VCM = 1.65 V. Known adverse numbers: offset up to 5 mV (33 % of 15 mVpp), minimum internal hysteresis about 8 mV. Derived timing (linear edge, 60 MHz bandwidth, 10-90 % rise 5.8 ns): slew is about 2.1 mV/ns at 15 mVpp, so a 5 mV offset displaces the crossing by 2.4 ns (12 % UI) and 0.5 mV by 0.24 ns; at G = 7 (105 mVpp) slew is about 14 mV/ns and the same offsets give 0.35 / 0.035 ns. If the comparator's input noise were 1 mV rms (a placeholder, the datasheet gives none), a direct connection would be 3-7x worse than the TIA noise (0.15-0.3 mV rms); behind G = 7 the same comparator noise refers to 0.14 mV at the TIA output, comparable to rather than larger than the TIA noise. Gain ahead of the comparator is therefore the defensible choice. PROPOSED.

## 2. Post-amplifier candidates (3.3 V single supply unless stated)

| | OPA858 | OPA855 | LMH6629 | THS4541 (FDA) |
|---|---|---|---|---|
| Supply | 3.3-5.25 V (p.5) | 3.3-5.25 V | 2.7-5.5 V | 2.7-5.4 V |
| Min stable gain | 7 | 7 | 4 (COMP low) or 10 (COMP high, WSON-8); SOT-23-5 fixed at 10 | 1 |
| GBW / BW at G 5-10 | GBW 5.5 GHz; 1.2 GHz small-signal at G=7 (5 V) | GBW 8 GHz; 2.5 GHz SS at G=7 (5 V) | 820 MHz SS at G=10; 730 MHz at G=4 (3.3 V, p.8) | 200 MHz at G=5, 120 MHz at G=10 (3 V, p.8) |
| Input noise | 2.5 nV/rtHz | 0.98 nV/rtHz, 2.5 pA/rtHz | 0.69 nV/rtHz, 2.6 pA/rtHz | 2.2 nV/rtHz, 1.9 pA/rtHz |
| Input CM at 3.3 V | 0-0.4 V low, 1.7 V min / 1.9 typ high (p.6): 1.83 V NOT guaranteed | 1.3 V max low to 2.7 V min high (p.6): 1.83 V inside | -0.3 to 2.1 V, CMRR > 70 dB (p.9): 1.83 V inside, 0.27 V margin | high limit (Vs+)-1.3 V (p.9, 3 V table) = 2.0 V at 3.3 V (extrapolated) |
| Output on 3.3 V | VOL 1.05-1.15, VOH 2.3 min / 2.4 typ: about 1.15-1.25 Vpp (p.7) | VOL 1.15 max, VOH 2.35 min: about 1.2 Vpp (p.7) | RL 100 ohm: 0.90 to 2.40 V min = 1.5 Vpp; typ 0.79-2.50 (p.9) | (Vs-)+0.25 to (Vs+)-0.25 per side: about 5.6 Vpp differential (p.9) |
| Overload recovery | 200 ns, 2x output overdrive, 0.1 % recovery (p.6); Fig. 6-22 (p.11, +/-2.5 V) shows the output back on the ideal trace within a few ns | 3 ns, 2x output overdrive (p.6) | 2 ns, VIN = 1 Vpp (p.8) | 20 ns, 2x output overdrive (p.8); Fig. 6-30 (p.15, 3 V) shows output limiting at +/-2.8 V and following within a few ns |
| Iq | 20 mA (3.3 V) | 17.8 mA (5 V; 3.3 V not given) | 13.7 mA typ (3.3 V) | 9.7 mA (3 V) |
| Input bias | 0.4 pA (FET) | -12 uA typ (-5 to -18.5) | -15 uA typ (-23 max) | 9 uA typ (12 max) |
| Package | WSON-8 2x2 mm | WSON-8 2x2 mm | SOT-23-5 or WSON-8 3x3 | VQFN-16 3x3 or WQFN-10 2x2 |

All cells are VERIFIED against the cited pages except where marked "extrapolated". Input-bias note: with the bipolar parts an AC-coupling bias resistor of R produces IB*R*G at the output (1 kohm, G = 7, 12 uA: 84 mV of 1.2 V headroom); use about 75-100 ohm or match the inverting side. PROPOSED.

- Added noise (derived, 70 MHz brickwall, 25 ohm OPA857 source, Rg about 75 ohm): OPA855 about 14 uV rms, LMH6629 about 12 uV, OPA858 about 24 uV, THS4541 (Rg 374 ohm each) about 36 uV differential. Against 0.15-0.3 mV TIA output noise this adds 0.1-3 % in quadrature. Amplifier noise is not the limit; the TIA is. PROPOSED (not simulated).
- Recovery versus the 20 ns UI: OPA855 3 ns and LMH6629 2 ns are 10-15 % of a UI and acceptable. OPA858's 200 ns is a 0.1 % settling figure; the plot suggests a few ns to the ideal trace, but the number a designer can cite is 200 ns, so OPA858 is the weakest on this criterion (UNRESOLVED until measured). THS4541's 20 ns spec equals one UI, but at G = 5 it clips only at about 5.6 Vpp differential (about 61 uA at 20k), so it never clips before the TIA does.
- THS4541 fully differential drive of the comparator: OPA857's OUT/OUTN is pseudo-differential (OUTN is the 1.83 V reference, OUT swings down only, OPA857 p.15 section 7.3.1 and p.18). TI's own Fig. 39 (SBOS630D p.18-19) pairs it with a THS4541 at G = 5, RG = 374 ohm, RF = 2 kohm, 5 V supply. Benefits: both inputs are coupled so reference and ground noise on OUTN subtract; no 1.65 V reference or IN- network needed at the comparator (only the common-mode return resistors); outputs centred on Vocm. Costs: 3x3 mm FDA plus 4 resistors, 374 ohm loads reduce OPA857 bandwidth (OPA857 p.19 warning), 5 V or 3.3 V headroom, 120-200 MHz bandwidth at G = 5-10. THS4541 is characterised at 3 V and 5 V, not 3.3 V (VERIFIED p.8); 3.3 V is inside the 2.7-5.4 V operating range. A single-ended stage is simpler and has the best recovery; the FDA is cleaner. PROPOSED, not measured.

## 3. Overload without AGC

Clip level (derived) I_clip = Vswing / (G x Rt_eff), Rt_eff = 18.2 kohm (20k) / 4.5 kohm (5k) into 500 ohm, VERIFIED OPA857 p.6 table note 4 and p.15. Photocurrent here is peak-to-peak (Ipp = Ion for OOK). Vswing: 1.15 V (OPA855/858), 1.5 V (LMH6629), 5.6 V (THS4541). The OPA85x parts cannot do G = 5; G = 7 is the minimum.

| G | OPA855/858 20k / 5k | LMH6629 20k / 5k | THS4541 20k / 5k |
|---|---|---|---|
| 5 | n/a | 16.5 / 66.7 uA | 61.5 / 249 uA |
| 7 | 9.0 / 36.5 uA | 11.8 / 47.6 uA | 44.0 / 178 uA |
| 10 | 6.3 / 25.6 uA | 8.2 / 33.3 uA | 30.8 / 124 uA |

TIA limit regardless of the post-amp: 60 uA at 20k, 240 uA at 5k, 1.2 V swing, VERIFIED (OPA857 p.15, section 7.3.1). TIA overload recovery 25 ns to 1 % at 2x overload: VERIFIED (p.6), i.e. longer than the UI. OPA857 small-signal bandwidth 105 MHz (20k) / 125 MHz (5k) at 1.5 pF: VERIFIED (p.6); at 6 pF UNRESOLVED.

Expected photocurrent (S12023-10, 850 nm, T = 0.9, 50 cm height; derived from `link_budget.py` single-point runs with its cos^0.646 emitter pattern: 0.64 nA per unit M per mW/sr at 35 cm lateral, 1.33 nA at 0 cm; closer receiver scales as 1/d^2; PROPOSED, the 30 and 100 mW/sr emitters are scaled from the 1 mW/sr run):

| Case | M = 10 | M = 30 | M = 50 | M = 100 |
|---|---|---|---|---|
| 30 mW/sr, 35 cm lateral (worst) | 0.19 uA | 0.58 | 0.97 | 1.9 |
| 100 mW/sr, 35 cm lateral | 0.64 | 1.9 | 3.2 | 6.4 |
| 100 mW/sr, on axis | 1.3 | 4.0 | 6.6 | 13.3 |
| 100 mW/sr, on axis, 25 cm height (x4) | 5.3 | 16 | 27 | 53 |

Link budget: Q = 6 needs Ipp of about 90-180 nA (link-budget.md; 1.7-3.3 mVpp at 20k), so the usable window at fixed gain and M is from about 0.1-0.2 uA up to the clip level: 12.6 uA gives 63-126x (36-42 dB) at G = 5, 6.3 uA gives 32-63x (30-36 dB) at G = 10. The 15-25 mVpp operating point (0.8-1.4 uA) sits 16-21 dB under the G = 7, 20k clip (9.0 uA) and 28-33 dB under it at 5k (36.5 uA).
- What firmware covers (PROPOSED): lowering M from 50 to 5 buys 20 dB of input current and 20k -> 5k buys 12 dB (18.2/4.5 = 4.0x), 32 dB together, so the OPA855 G = 7 stage goes from a 9.0 uA clip to 36.5 uA at 5k with M unchanged, and every row of the table above fits at M <= 30 on 5k, and at M = 50 except the 25 cm / 100 mW/sr case (27 uA fits 36.5 uA; 53 uA at M = 100 does not). Cases above 36.5 uA need M below about 50 on top of 5k. The photocurrent spread across the arena (about 2x on axis versus 35 cm lateral at 50 cm, 4x more at 25 cm height, i.e. 6-15 dB) fits inside the 30-36 dB window, so one setting per session plus slow M tracking could work. The M floor (APD gain at 100 V bias) and the M tempco (VBR 0.65 V/C; datasheet figures in docs/research/apd-selection.md) are UNRESOLVED; without temperature compensation M moves by a large factor over a few degrees, so the firmware loop is required, not optional.
- During a switch (M change settles with the HV filter and supply loop, ms-scale, UNRESOLVED; OPA857 CTRL switching transient is not specified): the comparator continues slicing the clipped signal. A clipped signal stays sliceable if the clipping is symmetric about the comparator baseline and the amplifier leaves the rail in less than the time between "input falls below clip level" and "input crosses the baseline", which is about t_rise/(2k) for an input k times the clip amplitude (derived: 1.4 ns at k = 2 with 5.8 ns rise, 0.3 ns at k = 10). With 2-3 ns recovery (LMH6629, OPA855) the zero-crossing is delayed by at most about 1-2 ns, equal on both edges (a fixed delay, not DCD, when clipping is symmetric); with 200 ns (OPA858 spec) the 0.1 % tail is irrelevant to a 50 % slicer but the delay is UNRESOLVED. Symmetry needs AC coupling AFTER the clipping amplifier (or before it with mid-rail bias), because the OPA857 OUT swings only downward from OUTN. Beyond 60 uA at 20k the TIA saturates; its 25 ns recovery to 1 % defeats this argument, so the system must not rely on slicing beyond TIA overload (UNRESOLVED edge timing).

## 4. Recommendation (PROPOSED, all unmeasured)

- Stage: a fixed-gain post-amplifier is justified; the choice is OPA855 at G = 7 (single-ended) or THS4541 at G = 5 (differential). Primary: OPA855 at G = 7: 0.98 nV/rtHz, 3 ns recovery, input CM range includes the 1.83 V OPA857 level on 3.3 V, 2x2 mm. Alternative: THS4541 at G = 5 if a differential feed is preferred (TI reference pairing, no clipping before TIA saturation, but 20 ns recovery spec and BW 200 MHz). OPA858 only if bias current matters (FET input); it is last on recovery and is not guaranteed at 1.83 V CM on 3.3 V. LMH6629 (G = 4/10, 2 ns, 1.5 Vpp) is a strong second single-ended choice if G = 5 is wanted.
- Gain: G = 7 gives 105-175 mVpp at the comparator for 15-25 mVpp from the TIA (G = 10: 150-250 mVpp) with the 0.8-1.4 uA operating point 16-21 dB under the 9.0 uA clip (20k). Use 7, the datasheet minimum, with RF 453 ohm / RG about 75 ohm (the datasheet test values, OPA855 p.6).
- Coupling: AC-couple the OPA857 output into the post-amp (not DC). Reason: a DC-coupled gain stage multiplies ambient photocurrent by G; the one-sided headroom before clipping is about 0.6 V, i.e. 4.7 uA of DC photocurrent at G = 7/20k (derived), which is only about 0.2 uW of in-band ambient at M = 50 (R = 0.48 A/W), much less than the 2.5 uW at the OPA857 limit; and the DC level is not guaranteed in the OPA858 input range. This agrees with standing correction 1. AC time constant at least 10 us (corner at most about 16 kHz) so a 5-UI run (100 ns) droops under 1 %; e.g. 10 nF into 1 kohm. Then AC-couple the post-amp output into the comparator with identical return resistors (about 1 kohm, matched) to a heavily filtered 1.65 V reference on both inputs; hold IN- with the same RC to ground.
- Low-pass: 60-80 MHz single pole between the post-amp and comparator (50 Mbps NRZ needs 0.5 x bitrate = 25 MHz minimum; the TIA is already at 105 MHz). Noise bandwidth drops from about 105 MHz to about 70 MHz (derived). Edge rate falls: 10-90 % rise about 5-6 ns, so comparator overdrive stays above 10 mV for G = 7 and 15 mVpp (about 52 mV peak).
- Hysteresis: external positive feedback sized for 2-4 mV (not the pin option; Fig. 7-4 minimum about 8 mV) with the LE/HYS pin left at its 0 mV setting (open, Table p.8) unless latching is needed. PROPOSED.
- Two-stage alternative: OPA858 at G = 7 then comparator; the FET input removes bias-current offset but adds noise 2.5 nV and has the slowest recovery spec. Two OPA855 stages (G = 7 x 2) would exceed the 5-10 uA window; not recommended.
- G1 must measure: (1) TIA-to-post-amp chain at 6 pF source: bandwidth, output noise at post-amp output; (2) recovery: drive 2x and 10x clip amplitude with 20 ns-wide pulses and a 5-UI pattern and record edge-timing shift on the comparator output; (3) comparator input-referred noise and delay vs a 5-30 mV pulse with 5-10 ns edges at VCM = 1.65 V (the datasheet cannot supply this); (4) IB at 1.65 V CM and the net offset with the chosen R; (5) jitter and BER of a PRBS7 8b/10b stream versus Ipp from 0.1 to 60 uA with M and 20k/5k steps; (6) switching transients of the OPA857 CTRL and APD bias change; (7) APD M versus bias and temperature.

## 5. Compare with VCA821 + AGC (current design)

| | VCA821 + AGC + peak detectors | Fixed post-amp + baseline slicer |
|---|---|---|
| Part count | VCA821, level shift, high/low capture, 2 diodes/buffers, subtractor, integrator, VMID network, LOS comparator, DACs (about 8 active parts) | one amplifier, 2 AC networks, LPF, hysteresis resistors (1 active part) |
| Unresolved | peak-detector accuracy (main risk), integrator anti-windup, VG bound, loop stability, rails +/-3.7 V | comparator small-signal noise, M and 20k/5k scheduling, baseline wander in runs |
| Overload handling | VGA reduces gain in 4.7 ms; fast overload can saturate VCA821 input (RG current limit about 2.6 mA) | amplifier clips; 2-3 ns recovery; firmware lowers M, 20k -> 5k; TIA saturates at 60 uA |
| Startup | gain climbs from max; noise amplified to target (decision 10) | no loop; correct immediately if M and gain were set right |
| Firmware dependence | none required for the loop | required for range (M, 20k/5k) and temperature compensation of M; contradicts the "analog-first" independence unless a slow analog fallback is kept |

Impact on decisions: this proposal makes slow range control firmware-based, which is a contradiction of decision 1 ("AGC is analog; MCU/ADC hooks optional") and needs the user's explicit approval. Keep the VCA821 + AGC as an option on the disconnectable sub-circuit until G1/G2 show the fixed-gain path works.

## Simulation follow-up (2026-10-09)

Three ngspice 47 simulations with TI vendor models now exist: `docs/simulation/README.md` (SIMULATED, not VERIFIED; no parasitics, no tolerances, nothing measured). Headline results:

1. OPA855 at gain 7: RF 301 / RG 49.9 is as stable as the datasheet's 453 / 75 in the model (77 deg phase margin both, no peaking). The phase figure is moderately trustworthy (model AC polarity quirk). The model clips 0.25-0.35 V below the datasheet VOL and limit-cycles when overdriven, so the clip and recovery questions of this note stay UNRESOLVED for the real part (G1).
2. OPA857 at 6 pF: stable, but in 20k mode 13.8 % overshoot and 12.6 ns to settle to 2 % of the 20 ns UI (ISI risk at 50 Mb/s); 5k is clean. Prefer 5k when the signal allows; measure the 20k eye at 6 pF (G1). Model validated only at 1.5 pF.
3. VCM_REF buffer: R102 10 ohm with C101 1 uF gives 87.6 deg phase margin; with no isolation resistor the model is unstable. The value stands.

Not simulated: the end-to-end TIA -> post-amp -> comparator chain, noise or BER, the TLV3605.
