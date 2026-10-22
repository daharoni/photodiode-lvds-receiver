# PCB layout review: fast analog path, HV bias island, APD/TIA input, LVDS to fan-out (Rev A, 2026-10-22)

Reviewer scope: placement and routing of the fast chain, the LT8365 HV island, the APD/TIA input region and the comparator LVDS output up to the fan-out. Read-only. All coordinates are doc coordinates (file minus 50,50). Measurements come from a COPY of the board (`work-fastpath/receiver-module.kicad_pcb`, zones refilled in `work-fastpath/filled.kicad_pcb`) queried with KiCad 10.0.5 pcbnew Python; scripts are in `.../scratchpad/work-fastpath/` (dump.py, clr.py, pair.py, par.py, refpl.py). Distances quoted as "gap" are copper-to-copper edge distances computed from the shapes (bisection on `SHAPE::Collide`), not centre distances.

## Executive summary

1. The fast chain is compact and clean: about 20 mm from D10 pad 3 to U20 pin 4, all on F.Cu, zero vias on any signal node of the chain (the only vias are decoupling GND/3V3), solid GND1 under every fast segment except the intentional TIA window. TIA_IN is 3.91 mm, 0.15 mm wide, one segment pair, no via, and no copper exists on any layer inside the TIA_IN_WINDOW. The HV island has 0 DRC violations against live HV rules and the nearest HV-to-other-net copper everywhere is at or above 1.0 mm (1.25 mm pad rule respected).
2. MAJOR: D10 pad 1 (HV_K, up to 220 V) is only 0.35 mm from pad 2 (case, GND) on F.Cu; the DRC rule "hv same footprint pads" (0.15 mm) hides it, and it is below even the project's own "0.4 mm external coated" figure. HV_K to the TIA_IN pad is 1.34 mm (calc doc rule says >= 2 mm). The 1.65 mm of HV_K trace also passes under the grounded can flange.
3. MAJOR: the cathode filter cap C50 is 6.78 mm of trace from the D10 K pin (calc doc 7 rule 6 asks <= 3 mm); the OPA855 has no plane cut-out under IN-/FB/OUT although SBOS622D 9.4.1 and Fig. 9-12 (p.29) ask for it, and TP10 hangs a 2.5 mm stub plus 1 mm pad on the OPA855 OUT pin ahead of R56.
4. MAJOR: the README claim "no HV-class net has a via" is false: net Net-(Q1-B) (clamp base node, within about 1 V of APD_BIAS) has 3 vias and 10.1 mm on In2. The SW-to-C5 loop returns to the U3 exposed pad through a single via and a 0.15 mm neck at C5 about 16 mm away; the U3 exposed pad has only 2 vias.
5. Silkscreen: the board carries NO silkscreen text at all (0 text items): no HV warning (calc doc 7 rule 8 asks for one), no test-point names, no D10 K/A marks (only a pin-1 triangle and the can circle). Test-point names exist on Fab layers only.

## Measured net table (fast chain and HV nets)

Layers: F = F.Cu, In2 = SIG_IN, B = B.Cu. "Stub" = branch off the through path. Lengths are track lengths summed from the file; widths in mm.

| Net | Endpoints / path | Total track length (mm) | Layer, width | Vias | Notes |
|---|---|---|---|---|---|
| /Front End/TIA_IN | D10.3 (11.54,25.00) -> U10.15 (15.35,25.25) | 3.91 | F, 0.15 | 0 | no stubs; no copper on any other layer in the window |
| /Front End/HV_K | R50.2 (7.01,15.56) -> C50.1 (6.98,19.05) -> D10.1 (9.00,25.00) | 10.29 (R50 to C50 3.46; C50 to D10.1 6.78) | F, 0.30 | 0 | C50 in series path, not a stub |
| /APD_BIAS | R19.2 (8.65,3.60) -> C8.1 (10.05,12.07) -> R50.1 (9.93,15.56) | 13.37 | F, 0.30 | 0 | R19 to C8 stage-1 filter 13 mm from can |
| Net-(U10-OUT) | U10.8 (18.15,24.25) -> C51.1 (21.03,24.80); stub to R58.1 | 4.65 (through 3.11, stub 1.55) | F, 0.15 | 0 | TIA_TAP take-off is the 1.55 mm stub to R58 (1k) |
| Net-(U10-OUTN) | U10.5 (18.15,25.75) -> TP12 (20.10,28.85) | 3.95 | F, 0.15 | 0 | stub to a 1 mm test pad |
| /Front End/PA_IN | C51.2 (22.58,24.80) -> U11.4 (25.17,25.75); stub to R51.1 | 4.54 (through 2.99, stub 1.55) | F, 0.15 | 0 | R51 stub right at C51 |
| Net-(U11-IN-) | U11.3 (25.17,25.25) -> R53.1 (25.35,22.67) -> R54.2 (25.35,21.12) | 4.97 | F, 0.15 | 0 | high-sensitivity node; RF/RG 2.5-5 mm from pins |
| Net-(U11-FB) | U11.1 (25.17,24.25) -> R53.2 (27.00,22.67) | 2.48 | F, 0.15 | 0 | feedback loop FB->R53->IN- about 5.9 mm |
| Net-(U11-OUT) | U11.6 (27.08,25.25) -> R56.1 (28.45,25.28); stub to TP10 (26.95,27.12) | 3.86 (through 1.39, stub 2.47) | F, 0.15 | 0 | TP10 stub is ahead of R56 |
| /Front End/LPF_OUT | R56.2 (30.10,25.28) -> C55.1 (31.58,25.28); stub to C54.1 | 3.06 | F, 0.15 | 0 | |
| /SDET_P | C55.2 (33.12,25.28) -> R59.1 (33.15,23.72) -> U20.4 (38.38,24.50) | 11.67 (through about 7.1) | F, 0.15 | 0 | stubs: TP11 1.6 mm, TP21 (DNP) 0.25 mm, C87 2.9 mm |
| Net-(C87-Pad2) | C87.2 (36.22,21.83) -> R87.1 (41.17,20.78) | 5.38 | F, 0.15 | 0 | hysteresis mid node |
| /LVDS_P | U20.12 (41.32,24.50) -> R180.1 (45.69,25.42) -> U50.6 (48.06,25.97); stub to R87.2 (42.83,20.78) | 11.69 (through 7.35, R87 stub 4.34) | F, 0.11 | 0 | |
| /LVDS_N | U20.10 (41.32,25.50) -> R180.2 (45.69,27.08) -> U50.7 (48.06,26.62) | 7.58 | F, 0.11 | 0 | through-path skew P-N 0.24 mm |
| /Connector/LVDS_OUT1_P | U50.16 (53.79,22.72) -> U52.1/14 -> J50.B3 (66.37,23.40) | 20.98 | F, 0.145 | 0 | no vias |
| /Connector/LVDS_OUT1_N | U50.15 (53.79,23.38) -> U52.2/13 -> J50.B2 (66.37,22.60) | 19.78 | F, 0.145 | 0 | pair skew 1.20 mm |
| /Connector/LVDS_OUT2_P | U50.14 (53.79,24.03) -> U51.3/12 -> J50.A3 (64.42,26.75) | 11.84 | F, 0.145 | 0 | |
| /Connector/LVDS_OUT2_N | U50.13 (53.79,24.67) -> U51.4/11 -> J50.A2 (64.42,27.25) | 11.90 | F, 0.145 | 0 | pair skew 0.06 mm |
| /Power/HV_OUT | R30.2 (67.26,10.40) -> back-edge lane y=1.15 (x 63.50 to 22.09) -> R17/Q1/R20, plus R11.2 and C25.1 | 72.74 | F, 0.30 | 0 | lane copper edge 1.0 mm from board edge |
| /Power/HV_RAW, HV_V1, HV_PUMP, HV_CLAMP | doubler and stage-1 | 6.83 / 7.17 / 5.43 / 4.99 | F, 0.30 | 0 | |
| Net-(D1-A) (SW) | U3.14/16 -> L1.2, D1.2, C6.1, D2.1 (DNP) | 11.57 | F, 0.30 | 0 | D2 branch about 3.1 mm of live SW copper to a DNP pad |
| Net-(D1-K) | D1.1 -> R7.1 | 2.34 | F, 0.30 | 0 | |
| Net-(Q1-B) | Q2.3, Q1.1, R18.2 | 1.04 on F + 10.11 on In2 | F/In2, 0.30 | 3 | violates "no HV via" |
| /Power/FBX | U3.9 -> R8, R12, R14, R15, C26 (DNP) | 9.21 | F, 0.15 | 0 | |
| Net-(R12-Pad2) (NTC node) | TH1.1 (9.48,31.62) -> R12.2 (52.50,16.53) | 51.31 on In2 | In2, 0.15 | 2 | 7.1 mm within 0.6 mm of SDA/SCL |
| /VCM_REF | R51, R60, R59, R84, buffer | 40.17 on B | B, 0.15 | 5 | daisy tree under the chain, GND2 reference |

## BLOCKER

None found in this scope. (I checked for shorts and HV clearance failures by measurement; see "Checked and found correct".)

## MAJOR

### M1. D10 pad 1 (K, HV_K) is 0.35 mm from pad 2 (case, GND) and 1.34 mm from pad 3 (TIA_IN); the same-footprint rule hides it
- Location: D10 (9.00,25.00) pad 1 square 1.2 mm; pad 2 round 1.2 mm at (10.27,26.27); pad 3 round 1.2 mm at (11.54,25.00).
- Seen: measured copper gap pad1-pad2 = 0.35 mm, pad1-pad3 = 1.34 mm, pad2-pad3 = 0.60 mm. The .kicad_dru rule `hv same footprint pads` sets 0.15 mm between pads of one footprint, so DRC cannot see this; `hv pad clearance` (1.25 mm) does not apply to same-footprint pads. The three leads of the TO-18 sit on a 2.54 mm circle (1.80 mm centre to centre; footprint description cites KAPD1007E19 outline KAPDA0136EC, not re-checked by me), so the footprint's 1.2 mm pads (0.7 mm drill) take most of the pitch.
- Why it matters: APD_BIAS goes to 220 V (CLAUDE.md, decision log 9). docs/calculations/apd-bias-design.md section 7 rule 1 gives 1.25 mm external uncoated or 0.4 mm external coated for 171-250 V (secondary source, cited in that doc), rule 1 also asks >= 2 mm from the TIA input node. Pad-to-pad 0.35 mm K to GND is below the 0.4 mm coated figure; K to anode 1.34 mm is below the 2 mm project rule and is also a surface-leakage path into the TIA input (220 V across 1.34 mm; a 10 GOhm surface film gives 22 nA, comparable to or larger than APD dark current; PROPOSED estimate, not measured).
- Fix (PROPOSED): reduce pad 1 and pad 2 to round 1.0 mm (minimum for 0.7 mm drill with 0.15 mm annular), which gives 0.80 mm K-to-case and 1.54 mm K-to-anode; that is a lab-library footprint change (PR), not a project-local footprint. Mask web between pads should stay (do not open the mask as one slot). Keep the area clean and conformal-coat the HV end; add an explicit note to the HV waiver in the .kicad_dru so the exception is a recorded decision. Optionally put a grounded guard track from pad 2 between pad 1 and pad 3 only if the capacitance on IN is simulated first (it adds C to the input; PROPOSED, UNRESOLVED).
- Confidence: HIGH on the measured numbers; MED on the severity (inherent to the can, but pad size is a choice).

### M2. HV_K trace to D10 passes under the grounded can flange, and C50 is 6.8 mm from the K pin
- Location: HV_K (6.98,22.97)-(9.00,25.00) and (6.98,19.05)-(6.98,22.97); can axis (10.27,25.00).
- Seen: the can axis is the centre of the pin circle (10.27,25.00); the D10 footprint's courtyard radius is 3.45 mm and the descr says a 5.4 mm flange (radius 2.7 mm; from the library description, not checked against KAPD1007E19 by me). 1.65 mm of the 0.3 mm HV_K diagonal lies inside radius 2.7 mm, i.e. under the flange, which is on the case lead (GND). Separately the path C50 pad 1 (6.98,19.05) to D10 pad 1 is 3.92 + 2.86 = 6.78 mm of 0.30 mm trace in series with the cathode.
- Why it matters: (a) apd-bias-design.md section 7 rule 6: "C2 at the cathode pad (<= 3 mm), cathode trace from C2 to the pin as short as possible". Measured 6.78 mm, 2.3x the limit. The photocurrent AC return runs cathode -> C50 -> GND, so the 6.8 mm adds about 5-7 nH of series inductance (PROPOSED estimate, over 0.1 mm of GND1 where present) into that return; this is 4-5 ohm at 100 MHz, small against Cj 6 pF (265 ohm at 100 MHz) but it is exactly the ripple/ground-noise coupling path the rule exists for. (b) 220 V trace under a grounded metal flange: the only insulation is 0.03 mm of solder mask unless the can stands off the board (standoff height is not specified in the footprint; UNRESOLVED).
- Fix (PROPOSED): move C50 (1210) to the left/below of D10 pad 1 so the pad-to-pad distance is <= 3 mm and route the cathode pad directly to C50; if that is not possible add a 100 pF C0G 0603 at the K pin (rated 250 V or more; derate per rule 9). Keep the HV_K copper outside radius 2.7 mm of the can axis, or specify an insulating spacer/Kapton under the flange.
- Confidence: HIGH on geometry, MED on the electrical impact (not simulated).

### M3. OPA855 signal pins have no plane window; TP10 loads OUT ahead of R56
- Location: U11 (26.12,25.00): IN- pin 3, FB pin 1, OUT pin 6; TP10 (26.95,27.12); R53/R54 at (26.17,22.67)/(26.17,21.12).
- Seen: only two rule areas exist (ANT_KEEPOUT, TIA_IN_WINDOW). GND1/GND2/PWR planes and the F.Cu GND pour run straight under U11 and up to the pins (zone refill map: F.Cu pour adjacent to the pad rows). OUT net has a 2.47 mm stub (0.35 + 2.12) ending in the 1 mm test pad TP10, connected before R56 49.9 ohm (through path is only 1.39 mm).
- Why it matters: OPA855 SBOS622D 9.4.1 (p.29): "Minimize parasitic capacitance from the signal I/O pins to ac ground. Parasitic capacitance on the output and inverting input pins can cause instability... cut out the power and ground traces under the signal input and output pins" and Fig. 9-12 shows plane removed on inner layers and outer ground fill removed (VERIFIED against p.29 text). 9.4.1 also says to place the feedback resistor as close to the output pin as possible; the board has RF (R53) 2.5 mm away on FB and the IN- node 4.97 mm long (feedback loop about 5.9 mm). My own estimates (PROPOSED, hand calculation, not simulated): IN- trace over GND1 about 0.09 pF/mm gives about 0.3-0.4 pF with pads; with RF||RG = 43 ohm the pole is near 9-12 GHz, which at the 2 GHz closed-loop crossover costs on the order of 10-15 degrees of phase margin against the ngspice 77 degrees (SIMULATED in docs/schematic/frontend.md without parasitics). TP10 stub plus pad on OUT adds about 0.4-0.5 pF (PROPOSED).
- Fix (PROPOSED): add a no-fill/no-plane rule area (all six layers) under U11 pins 1-4 and 6 and R53/R54 (a small L-shaped window like the OPA857 one), keep pour and planes beyond 0.5 mm; move TP10 behind R56 (to LPF_OUT) or remove its stub; move R53 and R54 to within 1.5 mm of the pins (they currently sit 2.5-4.5 mm above U11). Re-run the OPA855 stability sim with 0.5 pF at IN- and OUT before committing.
- Confidence: MED-HIGH (the guidance is explicit; the size of the effect is estimated).

### M4. "No HV-class net has a via" is not true: Net-(Q1-B) has 3 vias and 10.1 mm on In2
- Location: Q1.1 (17.80,5.78) via (17.53,5.60), via (14.05,3.40) at R18.2, via (9.76,6.88) at Q2.3; In2 tracks (17.53,5.60)-(15.33,3.40)-(13.24,3.40)-(9.76,6.88).
- Seen: net is in class HV (README table) and carries a clamp base node that sits within about one Vbe of HV_CLAMP/APD_BIAS in normal operation (circuit per docs/schematic/power.md line 41: Q1 base = R18/Q2 collector, Q1 emitter = R16/Q2 base; PROPOSED reading of the netlist). README (2026-10-22) says "no HV-class net has a via". DRC passes (1.0 mm clearance to other In2 copper is respected) but the route sits 0.1088 mm above In3 pours and 0.55 mm over a core to GND1 (stackup).
- Why it matters: calc doc 7 rule 2 ("no HV via under a pad"; planes solid under HV on purpose, README 2026-10-14) and the README claim are inconsistent with the file; 220 V over 0.1088 mm prepreg is about 2 kV/mm, well within FR4 capability (PROPOSED, no JLC dielectric strength figure read) but it is the one HV net that leaves the top layer.
- Fix (PROPOSED): either re-route Net-(Q1-B) on F.Cu (there is room along y=3.4-5.8 between R17/R18 and Q1) or correct the README/fab doc to say Q1-B is the exception and record the intent. Vias are tented and 0.45/0.25, so electrical risk is low; this is mostly a consistency/doc issue plus avoiding HV vias near the tiny prepreg.
- Confidence: HIGH on the facts; MED on whether you care.

### M5. Boost output loop returns to U3 through one via and a 0.15 mm neck about 16 mm away; U3 exposed pad has only 2 vias
- Location: C5 pad 2 GND (62.40,6.05) -> 0.15 mm track 0.42 + 0.78 mm -> single via (62.10,4.98); U3 exposed pad (47.03,11.05) vias at (47.05,10.10) and (47.03,12.00) with 0.15 mm tracks 0.93-0.95 mm from the pad centre; loop path SW (49.14,9.30/10.30) -> C6 -> D1.2 (51.15,6.05) -> D1.1 (53.53,6.05) -> R7 (56.78,6.05) -> C5 (59.45,6.05).
- Seen: the current path SW -> D1 -> R7 -> C5 -> GND is about 11 mm of 0.30 mm trace on F.Cu with the GND1 plane 0.0994 mm below (good), but the return enters the plane through ONE 0.45 mm via at the end of a 1.2 mm, 0.15 mm neck and then travels about 16 mm in the plane back to the U3 pad, which itself has only 2 vias. Only 2 of the GND vias are within 4 mm of the exposed pad (also 2 vias (52.65,11.70) sit at the same coordinates, the known holes_co_located item).
- Why it matters: LT8365 Rev. A p.16, Fig. 5 and the layout hints text: "Note the vias under the exposed pad. These should connect to a local ground plane for better thermal performance" and Pin Functions (p.7): the input cap and exposed-pad power ground copper at the EN/SW end (VERIFIED against lt8365.pdf text). Loop inductance estimate over 0.0994 mm: about 0.4 nH/mm for a 0.3 mm trace, so about 7 nH for 17 mm plus the neck (PROPOSED hand calculation); R7 (20 ohm) damps it, so this is a ripple/EMI risk against the 10 uV cathode target (apd-bias-design.md section 4/7, 6.63 MHz), not a function risk.
- Fix (PROPOSED): 2-3 vias in C5's pad (via-in-pad is not needed; use 3 vias within 0.5 mm of the pad) and widen the neck to the pad width; add 4-6 vias in the U3 exposed pad (pad is 1.65 x 2.85 mm; with the 0.45 mm via size, 4 vias fit on a 0.8 mm grid); consider moving C5 closer to D1 (C5 is 8.7 mm from D1.1). Measure SW ringing and cathode ripple at G1 as already planned.
- Confidence: MED (layout geometry HIGH, effect size not measured).

## MINOR

### m1. Plane window under the OPA857 is L-shaped and leaves planes under pins 13/14 next to IN
- Location: TIA_IN_WINDOW polygon (10.5,24.0) (14.6,24.0) (14.6,25.0) (15.9,25.0) (15.9,26.1) (10.5,26.1) (confirmed in the .kicad_pcb zone polygon, all six layers, copperpour not_allowed).
- Seen (refilled zones): on F.Cu, GND1, PWR, GND2 and B.Cu no fill at all inside the window for x 10.5-14.6, y 24.0-26.1 and for x 14.6-15.9, y 25.0-26.1; but for x 14.6-16.0, y 24.0-25.0 (under Test_SD pin 13 and Test_IN pin 14, 3V3 and GND pads) the inner planes are present with the fill edge at y = 25.00, i.e. 0.13 mm from the edge of the IN pad (pad 15 spans y 25.13-25.37, x 15.05-15.65) and 0.25 mm from the IN trace centreline. U10 pad 17 is outside the window (x >= 16.03) with the per-pad solid connection described in the README.
- Why: OPA857 SBOS630D 10.1(a) p.23: "open a window around the signal I/O pins in all ground and power planes around those pins" and Fig. 48 p.24 "Open Planes to Minimize Parasitic Input Capacitance" (VERIFIED). Pins 13 and 14 are AC grounds (3V3, GND per p.4 pin table: Test_IN to +VS, Test_SD to GND), so this is a small effect; the IN pad sees inner plane within 0.13 mm laterally. My estimate of total TIA_IN stray C with the window as built is about 0.3-0.5 pF (0.05 pF/mm coplanar-to-pour times 3.9 mm, pads 0.1-0.2 pF; PROPOSED, not simulated); without any window the trace over GND1 (0.0994 mm) would add roughly 0.35 pF (0.09 pF/mm) plus about 0.3 pF for the 1.2 mm D10 pad (PROPOSED).
- Fix (PROPOSED): extend the window polygon to cover y 24.0-25.0 for x 14.6-15.9 as well (a plain rectangle x 10.5-15.9, y 24.0-26.1); pins 13/14 connect on F.Cu so they do not need the planes there.
- Confidence: MED.

### m2. OPA857 IN pad has two live neighbours and no guard; 3V3 route into the window
- Seen: IN pad 15 has pin 14 (3V3, Test_IN) 0.26 mm away and pin 16 (NC) 0.26 mm away; the 3V3 track from pin 14 runs (15.35,24.75)-(15.08,24.75)-(14.38,24.05)-via (14.38,23.62), which crosses into the window region (inside y >= 24.0) for about 0.4 mm and passes 0.35 mm from the TIA_IN trace. The nearest GND pour is 0.25 mm from pad 15 and 0.48 mm from the trace (F.Cu).
- Why: leakage and cap on a node with 6 pF source; pin-pitch limits this (0.5 mm QFN). Not a violation. Option: pull pin 14's 3V3 tie straight back along y=24.75 to x 14.6 instead of the diagonal. PROPOSED, low value.
- Confidence: LOW-MED.

### m3. SYNC pin has a 7.9 mm stub to DNP parts, 0.7 mm from the SW pad
- Location: /Power/SYNC U3.12 (49.14,11.30) -> R27.1 (46.35,14.58), R26.1 (46.35,16.17), TP2 (46.40,17.75); 7.86 mm total, 0.2 mm wide near the pin.
- Seen: measured clearance SYNC pad to SW pad U3.14 0.69 mm, SYNC trace to SW pad 0.75 mm. R26/R27/TP2 are DNP; the mode is "SYNC floating = pulse-skip" (power.md line 20).
- Why: LT8365 Rev. A p.7: SYNC/MODE (1) GND/<0.14 V Burst, (4) float = pulse-skipping, (5) INTVCC/>1.7 V pulse-skip/SSFM, thresholds 1.3-1.7 V (p.4 table, VERIFIED). A floating mode pin with an 8 mm antenna next to a 130 V swinging node can be pulled across a threshold, changing the mode (UNRESOLVED; no measurement).
- Fix (PROPOSED): cut the stub back so only the DNP pads nearest the pin remain (R27 at <= 2 mm), or add a 100 pF to GND at the pin (changes the mode input impedance: check LT8365 p.7 before adding). At G1 check f_sw is stable over 465-535 kHz as already planned.
- Confidence: LOW-MED.

### m4. D2 (DNP) hangs 3.1 mm of live SW copper plus a pad
- Location: Net-(D1-A) tracks (50.92,4.17)-(50.92,6.05) and (51.80,3.30)-(50.92,4.17), pad D2.1 (51.80,3.30), which is DNP (purpose UNRESOLVED per README).
- Why: unneeded antenna on the SW node. Fix: remove that branch and keep D2 pads off the SW copper until the part is decided. PROPOSED.
- Confidence: MED.

### m5. 51 mm thermistor/FBX node on In2 runs 7.1 mm within 0.6 mm of SDA/SCL
- Location: Net-(R12-Pad2) (10 k NTC end of the FBX bottom leg: TH1 pad 1 via (9.52,31.60) -> In2 -> via (52.50,16.53) at R12.2); SDA nearest edge distance 0.36 mm, SCL 0.80 mm.
- Seen: `par.py` result: 7.1 mm of the net is within 0.6 mm (edge) of SDA/SCL, 8.2 mm within 1.0 mm. README says the 45 mm run is acceptable because the node is low impedance; the node is the NTC top (10 kohm nominal, R12 86.6 kohm in series to FBX), so the injected digital edge is attenuated by R12 into FBX but the FBX node is the converter's set-point and is the one called "sensitive" in the calc doc rule 5.
- Fix (PROPOSED): re-route away from SDA/SCL (>= 1 mm or a GND neighbour), and add 100 nF across the NTC end (check C27/C28 first, one cap already sits on a DAC leg; that changes the thermal response by only tau = 10k x 100n = 1 ms). 
- Confidence: MED.

### m6. TH1 is not thermally linked to the can
- Location: TH1 (8.65,31.62), can axis (10.27,25.00): 6.8 mm centre to centre; flange edge to TH1 courtyard roughly 3.5 mm; D10 pad 2 (case) to TH1 pad 2 (GND) 5.9 mm. TH1 GND pad 2 and D10 pad 2 are only joined by the F.Cu pour and planes.
- Why: README 2026-10-13 says "per apd-bias-design.md section 7 'on APD can ground tab / thermal link'". There is no dedicated copper link and the three can leads dissipate into four GND planes, so the NTC tracks board temperature near the can, not the die. Whether that meets the 0.65 V/C compensation accuracy (apd-bias-design.md G1 test 2, +/-0.75 V span) is UNRESOLVED until the chamber test. Fix (PROPOSED): a 1 mm F.Cu strip from D10 pad 2 to TH1 pad 2 (no plane cut), or move TH1 within 3 mm of the flange, e.g. at (8.0,28.8). Confidence: MED.

### m7. R87/C87 hysteresis geometry and SDET_P stubs
- Location: R87 (42.00,20.78), C87 (37.00,21.83); stub from U20.12 (41.32,24.50) up to R87.2 (42.83,20.78) is 4.34 mm of 0.11 mm trace; C87.2 to R87.1 is 5.38 mm of 0.15 mm trace; SDET_P branch to C87.1 is 2.9 mm; TP11 1.6 mm stub, TP21 pad (DNP) 0.25 mm from the node, 1 mm pad.
- Seen/why: the hysteresis network needs only 3.0 mV (slicer.md line 10) and the loop is slow; the 4.3 mm stub on OUT+ is electrically short for an LVDS edge (round trip about 60 ps; edge >= 200 ps typical, PROPOSED), the bigger concern is that the 5.38 mm mid node sits at ~5 kohm impedance beside digital edges. TLV3605 SNOSDA2F 7.4.1 (p.19) item 3 says minimise trace lengths on inputs, and item 5 allows a <= 1 nF capacitor between inputs if needed (VERIFIED).
- Fix (PROPOSED): put R87 within 1.5 mm of U20 pin 12 and run only the short mid node to C87, i.e. swap the positions of R87 and C87 (R87 to pin side, C87 next to IN+). Remove the TP11 stub or move it behind R59 away from pin 4 side. VCM_REF reaches the comparator via R59 pad 2 (31.50,23.72) through a via at (31.47,23.65) and B.Cu; that is fine.
- Confidence: LOW-MED.

### m8. LVDS_P/N (DIFF100) DRC items are pin-escape and R87-stub artifacts, not a routing problem
- The 4 diff_pair_gap items: (a) P segment (46.24,25.97)-(45.69,25.42) 0.78 mm vs N segment (44.39,25.78)-(45.69,27.08) 1.84 mm: reported gap 1.057 mm, (b) P segment (45.69,25.42)-(42.75,25.42) 2.94 mm (at y=25.42) vs N (42.60,25.78)-(44.39,25.78) 1.79 mm (at y=25.78): reported 0.24 mm against max 0.20. The pair is loosely coupled: gap 0.24 mm for 1.8 mm, then 0.36-1.06 mm approaching R180 (pads 1.66 mm apart) and 0.54 mm at the U50 pins (0.65 mm pitch). The "11.69 mm uncoupled" for LVDS_P is the entire P net: 7.35 mm of through path plus the 4.34 mm R87 hysteresis stub, which KiCad counts as uncoupled. The through-path lengths are P 7.35 mm and N 7.59 mm (skew 0.24 mm, about 1.7 ps at 7 ps/mm, PROPOSED).
- Why it is not a real problem (PROPOSED): total line length 7.4 mm and edge rates of the order of 0.2-1 ns give a line below 1/10 of the rise-time length (about 15-70 mm); differential impedance by Hammerstad/IPC estimate with 0.11 mm over 0.0994 mm prepreg Er 4.1 is about 58 ohm single-ended, 100-115 ohm differential for gaps 0.15-1.06 mm (formula estimate, not a solver result and not the repo's field-solver value). Termination: R180 sits at the load end of the line (2.4 mm before U50 pins) which is correct for a source-driven, receiver-terminated LVDS link (SN65LVDS104 has no on-chip termination, slicer.md line 14); the TLV3605 datasheet 7.4.1 item 6 asks for 100 ohm across the outputs, which this satisfies after 4.4 mm of trace (VERIFIED against p.19 text).
- Recommendation: either leave and mark the 4 DRC items accepted, or relax rule "diff100 gap" to max 1.2 mm and the "diff100 uncoupled" limit to 8 mm and exclude the R87 stub with a courtyard condition (the rule file already notes that the R87 tap inflates the net length). The `pair gap at pins` rule intersects U20's courtyard but the failing segments are around R180, which the rule file deliberately left out. Confidence: HIGH.

### m9. LVDS_OUT1/OUT2 (DIFF90) U50 -> ESD -> J50: lengths and planes
- OUT1 P/N 20.98/19.78 mm (skew 1.20 mm, about 8 ps at 7 ps/mm, PROPOSED; rule max 2.5 mm), OUT2 P/N 11.84/11.90 mm (skew 0.06 mm); all F.Cu, 0.145 mm, no vias; reference plane GND1 continuous under both pairs except 6-8 samples around the J50 B2/B3 through-hole pads (66.4-66.9, 22.5-23.2), the expected pad voids; the ESD arrays U51/U52 pass the pair straight through their pads (pad 1 to pad 14, 2 to 13) so there is no ESD stub. U50.13 (OUT2_N) to U50.12 (DBG_P) is 0.25 mm pad gap (pin pitch). OUT1 vs OUT2 minimum approach 0.90 mm (at U50 pins).
- Why it is acceptable: 50 Mb/s, UI 20 ns, 90 ohm pair; skew is 0.04% of the UI. OUT1 is 9 mm longer than OUT2 because it goes up and over to the B-row; no inter-pair match needed (rule file says so). Confidence: HIGH on measured lengths.

### m10. Silkscreen and test points
- Seen: the board has 0 silkscreen text items (all reference designators are on F.Fab/B.Fab, README 2026-10-14). There is no HV warning, no K/A or polarity text at D10 (only the pin-1 triangle at (7.6-8.0,25.0) and a can circle radius 2.85 mm centred (10.27,25.0)), no "+"/"-" marks, and none of TP10 PA_OUT (26.95,27.12), TP11 SDET_P (33.17,22.10), TP12 TIA_REF (20.10,28.85), TP20 SDET_N (36.72,26.45), TP21 SDET_P (36.65,24.33, DNP), TP30 VCM_REF (B.Cu) is named on the board.
- Why: apd-bias-design.md section 7 rule 8: "label the HV area and test points"; G1 bring-up (docs/bringup/gates.md) probes these nodes. There is no test point on TIA_OUT (probe C51 pad 1) and, by decision 9, no bare APD_BIAS pad (HV_MON only).
- Fix (PROPOSED): add F.SilkS text "HV 220 V" near R19/C8/R50/C50/D10 and the SW cell, and net names next to each TP; keep silk text out of the TIA window. Confidence: HIGH on the facts.

### m11. Optical window: what is tall near the can
- Seen: can axis (10.27,25.00), 3.7 mm overall height and 5.4 mm flange (library descr). Nearest courtyards: C50 1210 (8.5,19.0) is 4.3 mm from the axis (1.6 mm beyond the flange); U10 4.5 mm; TH1 5.9 mm; C57 5.7 mm; JP10 4.6 mm; the board left edge is 10.27 mm from the axis. A filter holder or window ring with diameter up to about 8.6 mm clears C50; anything larger, or any holder that sits at the board edge side only, would collide with C50 (about 2.5 mm tall as 1210, PROPOSED) or U10. The housing/filter holder dimensions are not in the repo (hardware/mechanical is TBD), so this is UNRESOLVED.
- Fix: decide the holder OD now; if it is > 8.6 mm move C50 (see M2, which wants it close to the K pin anyway). Confidence: MED.

## Checked and found correct (coverage)

- TIA_IN_WINDOW is live (zone polygon present on all six copper layers, copperpour not_allowed) and removes all fill on every layer for x 10.5-14.6, y 24.0-26.1 and x 14.6-15.9, y 25.0-26.1; TIA_IN (D10.3 to U10.15) lies entirely inside it; no track or via of any net on any other layer enters the box x 9-17, y 22.5-27.5 other than F.Cu items (checked on all layers).
- TIA_IN measured clearance to other nets: 0.6 mm to D10.2 (GND), 1.34 mm to HV_K pad, 1.79-1.87 mm to the HV_K trace, 0.26 mm to U10 pins 14/16, GND F.Cu pour 0.25-0.78 mm. No via on the node. HV_OUT, SW (Net-(D1-A)) and APD_BIAS are >= 6 mm from the TIA_IN, PA_IN and OPA855 nodes (pair distance query capped at 6 mm); the switching cell is 30 mm from U10.
- DRC HV rules are live: the .kicad_dru parses (rule names such as "diff100 gap" appear in drc.rpt) and measured HV copper clearances sit exactly at the rule floors (1.00 mm to GND pour, 1.0-1.25 mm pad to pad, 1.0 mm HV_OUT lane to the board edge), which a non-enforcing rule set would not produce; HV_OUT lane y=1.15, 0.3 mm wide gives copper-to-edge 1.0 mm (rule `hv edge` 1.0 mm).
- HV trace over plane voids: GND1 and GND2 are solid under every HV net on F.Cu (APD_BIAS, HV_OUT 734 samples, SW, HV_V1, HV_RAW, HV_PUMP: 0 samples without plane), except the PTH anti-pad voids around D10 pad 1 (about 1.6 mm radius, from the 1.0 mm HV class clearance) which is the intended behaviour. No HV net crosses a plane cut.
- OPA857 decoupling: C57 and C56 (100 nF) are 1.2 and 2.5 mm of 0.15 mm trace from the VS+ pins 9-11 (limit 6.35 mm = 0.25 in, SBOS630D 10.1(b), VERIFIED), GND returns go to pin 12 and via the F.Cu GND pour; C59 1 uF at 4.0 mm; exposed pad U10.17 has 2 vias (16.35,24.62), (17.15,25.42) and per-pad solid connection. OPA855: C52 100 nF 1.1 mm from VS+ pins 7/8 (0.15 mm tracks), C58 1 uF 2 mm, EP U11.9 has 1 via at (26.28,25.00); C52's GND return reaches the plane through a 1.66 mm 0.15 mm neck to the via at C58.2 (30.03,22.65) and the F.Cu pour, which is acceptable but weak (add a via at C52.2 (29.18,23.95) if room; PROPOSED).
- TLV3605: C80 100 nF 1.5 mm from VCCI, C82 100 nF 1.5 mm from VCCO (C83 1 uF 10.8 mm of VCCO net), U20 EP has 1 via (39.83,25.00) plus GND returns on the pour; decoupling placement matches SNOSDA2F 7.4.1 item 2 (VERIFIED).
- TIA_TAP: the take-off is a 1.55 mm stub off the OPA857 OUT trace to R58 1k, then 0.9 mm and a via to D30 (BAS70 on B.Cu): the stub is short and isolated by 1 kohm; it does not interrupt the fast path (C51 sits at the end of the through route). TP12 hangs 3.95 mm on OUTN.
- VCM_REF into the comparator baseline: B.Cu daisy tree of 40.17 mm referenced to GND2, 5 vias; each branch ends on a 1 kohm (R51, R59, R84, R60 10 ohm) so no signal current flows in the long trace; acceptable (the two dangling-via DRC items belong to the DRC triage reviewer).
- LVDS_P/N and LVDS_OUT pairs are on F.Cu over solid GND1 with no vias; DRC 0 unconnected pads.
- FBX: U3.9 to the divider 9.21 mm of 0.15 mm trace, closest SW copper (U3.14) 2.19 mm away, no HV or SW trace nearer than 4.6 mm to the ladder pad R8.1; VC 4.05 mm from SW. Clamp Q1/Q2/R16/R17/R18: all HV clearances >= 1.1 mm (pad pairs inside the footprints use the same-footprint exception, 0.65-0.85 mm).
- Doubler D3/D4/C6/C7: HV_RAW/HV_V1/HV_PUMP separations 1.0-1.3 mm; no HV copper under or near the TIA.

## QUESTIONS / UNRESOLVED

1. Can stand-off: does the S12023-10 sit on the board (flange against mask) or on a spacer? This decides how serious M2(b) is. Not in the repo; KAPD1007E19 outline not re-read in this review.
2. Is the 2.0 mm HV-to-TIA-input rule in apd-bias-design.md section 7 intended to apply at D10? At the can it is geometrically impossible (1.34 mm with the present pads, 1.54 mm best case with 1.0 mm pads). The rule or the footprint pads need an explicit decision.
3. Flange diameter and can height come from the lab library footprint description (not re-verified against the Hamamatsu datasheet here).
4. OPA855 and OPA857 stability with these parasitics (IN-/OUT extra capacitance, TP10 stub) has not been simulated; all capacitance and phase-margin numbers above are hand estimates.
5. Q1-B net class: README says it was added to class HV "conservatively, UNRESOLVED whether wanted". The measurements say it is within about 1 V of APD_BIAS, so keep it HV.
