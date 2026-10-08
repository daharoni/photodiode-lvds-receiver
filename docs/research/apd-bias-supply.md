# APD bias supply for S12023-10: 100-220 V from 5 V, <1 mA, low noise

Research date: 2026-10-08. Companion to docs/research/apd-selection.md (read-only). Labels: DATASHEET = read in a manufacturer document
or manufacturer/distributor page I opened; SEARCH-SUMMARY = web-search extract, PDF not opened (analog.com/mouser/matsusada timed out or 403);
GRAPH-READ = by eye from a plot; DERIVED = my arithmetic from labeled inputs; NOT FOUND = not obtained. Nothing here is recalled from memory
unless stated. Scratchpad copies (untrusted, not executed): scratchpad/hv/misc/xp_a.pdf (EMCO A series), c12702.pdf (Hamamatsu).
Live prices/stock are as of the fetch date only.

## Headline findings

1. **LT8365 (150 V, 1.5 A switch, 2.8-60 V in) is the only single-IC route with a datasheet-family demo above 200 V**: DC2838A does 9-30 V -> 250 V @ 10 mA
   (+250 V boost with charge-pump stages; the -250 V inverting twin is DC2840A). Analog Dialogue 53-03 shows 3 V -> 125 V @ 3 mA single stage ("could drive APDs") and 12 V -> 250 V two-stage. (SEARCH-SUMMARY, ADI pages)
2. The 250 V is reached with a diode-capacitor charge-pump stage driven from the switch node, not with a 250 V switch, so output current falls per stage ("single stage for 20 mA gives ~10 mA with a second stage"). At microamps this is irrelevant.
3. **Cathode noise at 6.63 MHz matters far more than ripple at the switching frequency**: a voltage v on the cathode injects i = 2*pi*f*Cj*v (DERIVED). With Cj = 6 pF (S12023-10) at 6.63 MHz, 1 mV rms gives 250 nA rms, comparable to the whole OPA857 noise (~28 nA, apd-selection.md). Budget <~10 uV rms at 6.63 MHz and across 1-50 MHz at the cathode; this is a filter/layout requirement, not a converter choice.
4. Purchased modules that fit 5 V in: **Matsusada TP-0.2P (<10 mVp-p)** and **XP Power EMCO A02P-5 (ripple <1 % = up to 2 V p-p, unregulated)**. Hamamatsu's own C12702 contains a +5 V -> +200 V temperature-compensated generator, which proves the concept (gain +/-2.5 % typ, +/-5 % max over 25 +/-10 C at M=30).
5. IPC-2221B 171-250 V row: 0.2 mm internal, 1.25 mm external uncoated, 0.4 mm external coated (secondary reproduction, see E).

## A. Single-IC / controller candidates (>=150 V class)

| Part | Vin | Max Vout (how) | Iout at ~200 V | fsw | Control | Switch | Iq | Package | Noise note | Label |
|---|---|---|---|---|---|---|---|---|---|---|
| **LT8365** (Rev 0, Feb 2020, 28 pp) | 2.8-60 V | 150 V switch; 250 V @10 mA with charge-pump stages (DC2838A, 9-30 V in, 400 kHz, 77 % eff., optional 3rd stage for more) | 10 mA @250 V (12 V in); 3 mA @125 V single stage (3 V in) | 100-500 kHz resistor-set, SYNC, spread spectrum | single FBX resistor divider (no DAC pin); EN/UVLO, COMP external | integrated 1.5 A / 150 V | 9 uA | 16-lead MSOP-E | Burst Mode "typically <15 mV" output ripple (single stage); ripple with pump stages NOT FOUND | DATASHEET summary via rlocman.es/datasheet/data.html?di=609109 and /pdf.html?di=167777; demo via SEARCH-SUMMARY (analog.com DC2838A) |
| LT8331 (Rev C, May 2020, 30 pp) | 4.5-100 V | 140 V switch, 0.5 A; nothing >140 V found | n/a | 100-500 kHz | single FB pin, + or - | integrated | 6 uA | MSOP-16E | "<20 mV" Burst ripple | SEARCH-SUMMARY (analog.com/en/products/lt8331.html) |
| LT3757 / LT3757A | 2.9-40 V | external FET; 350 V switch rating listed in a parametric table; no typical application >24 V found | n/a | 100 kHz-1 MHz | FBX, boost/flyback/SEPIC/inv | external N-FET, 7.2 V gate drive | <1 uA shutdown | 10-DFN / MSOP | flyback at 5 V -> 200 V needs ~1:8 transformer; leakage spikes; large | DATASHEET page 1 (rlocman di=166801); "200 V application" NOT FOUND |
| LT3758 / LT3758A | **5.5-100 V** | external FET | n/a | 100 kHz-1 MHz | FBX | external | NOT FOUND | | Vin min 5.5 V is above a 5 V rail (-5 % tolerance) so unsuitable | SEARCH-SUMMARY |
| LM5156 / LM51561 (SNVSBI6, Jan 2021); LM5155 (SNVSB75E) | 1.5-60 V (LM5156) | external FET, so set by FET; max Vout figure NOT FOUND | n/a | up to 2.2 MHz | FB | external | NOT FOUND | | no APD or >100 V application seen | SEARCH-SUMMARY (TI document-viewer) |
| LT8362 | NOT FOUND | NOT FOUND (not retrieved; ADI lists as boost, 2 A/60 V class, unverified) | | | | | | | skip | NOT FOUND |
| TPS61390 / **TPS61391** (Jul 2019) | 2.5-5.5 V | **84 V** table (85 V marketed) | n/a | 700 kHz fixed | FB + current mirror 1:5 / 4:5 | integrated 1 A | NOT FOUND | 3x3 16-WQFN | low-ripple APD part but cannot reach 100 V | DATASHEET page (ti.com/product/TPS61391) |
| MAX1932 | 2.7-5.5 V | 4.5-90 V; has GATE and CS pins, so an external N-FET | NOT FOUND | NOT FOUND | 8-bit SPI DAC, current limit flag | external FET | NOT FOUND | 4x4 TQFN-12 | ripple/noise <1 mV; LX/CS+ abs max NOT FOUND, so >90 V is not licensed | SEARCH-SUMMARY (rlocman di=165701) |
| MAX15031 / SGM41283 / SGM41285 | 2.7-11 V / 2.7-5.5 V | 76 V / 70 V | | | | | | | too low | SEARCH-SUMMARY |
| MIC2605/2606, MP3910, MP9486 | | NOT FOUND (search returned nothing for these parts) | | | | | | | | NOT FOUND |

Notes: (a) LT8365 control is a plain resistor divider; DAC trim must be injected into FBX through a resistor (formula in D). FBX reference voltage: NOT FOUND (not in the pages I could read), so no resistor values are given. (b) A 5 V input is within every LT8365 spec but all ADI demos start at 9 V or 3 V, so a 5 V -> ~190 V board is an interpolation, needs a bench check of current limit and stage count. (c) Burst Mode at microamp load will produce bursts at low repetition rate; filter handles it, but test with the 6.63 MHz field on and consider SYNC at a fixed f (spread spectrum OFF for a clean line spectrum, my suggestion). (d) A flyback/boost controller + external FET + transformer is possible (LT3757) but is bigger, noisier, and no APD application exists; not recommended for a small 4-layer board.

## B. Two-stage: 90 V APD IC + multiplier, or boost + charge pump

- **Evidence that the 90 V ICs cannot simply be extended**: ADI HFAN-03.1.1 (MAX-family boost with external doubler) gives 25-71 V from 5 V because the internal lateral DMOS switch is 40 V abs max; ripple "<100 mV at 71 V and 1 mA" with ceramics and slowed switching (SEARCH-SUMMARY). The doubler is driven from the switch node and is limited by the switch rating, so stacking another stage on LT3482/MAX1932 (switch/LX far below 90 V, LX/Vout abs max NOT FOUND) is not licensed by those datasheets. LT3482's own 90 V already uses its on-chip doubler (apd-selection.md). I found no app note extending them past 90 V.
- **Boost + Dickson/Cockcroft-Walton on a 150 V-switch part (LT8365)** is the documented way (DC2838A, Analog Dialogue Vol. 53 No. 3, July 2019 by J. Rosales: "double the switch voltage"; loop closed through FBX on the final output, polarity independent). Efficiency ~80 % at 10 mA (SEARCH-SUMMARY).
- Tradeoffs (DERIVED unless noted):
  - Output impedance of an N-stage switched-capacitor multiplier in the slow-switching limit ~ N/(f*C). 2 stages, 400 kHz, 100 nF: ~10 ohm. At 1 uA load the droop is nanovolts, so impedance is irrelevant; only transients matter.
  - Regulation: with the divider on the final node the loop regulates including diode drops and temperature. Line/load error is dominated by the divider and the DAC, not the pump.
  - Ripple is a pulse train at fsw (large dV/dt edges through diode capacitance), more spectrally rich than a plain boost. Mitigate with RC at the cathode (E).
  - Diode leakage rises with temperature; use small-signal HV silicon diodes (e.g. 200-250 V fast types); the loop absorbs microamp leakage but a divider/bleeder current of ~10-20 uA sets minimum load.
  - Stability: extra pole from the pump; LT8365 has external COMP, verify in LTspice (ADI provides model) and on the bench.
  - Capacitor stress: every pump capacitor needs a rating over one stage voltage (~100 V) and HV ones >=250 V; use C0G/film in the filtered output path (X7R is piezoelectric/microphonic and loses capacitance with DC bias).

## C. Purchased HV modules

| Module | Input | Output | Current | Ripple | Control | Size / mass | Price / lead | Photodetector pedigree | Label |
|---|---|---|---|---|---|---|---|---|---|
| **Matsusada TP-0.2P** (TP series 50-300 V) | 5 V +/-5 %, ~100 mA typ | 0-200 V | 200 kohm rated load (1 mA at 200 V) | **<10 mVp-p** | 0-3 V, 10 kohm in; setting accuracy -1/+3 %; tempco 0.08 %/C typ (0.12 V/C at 150 V); -10..+50 C | 50.8 x 25.4 x 12.7 mm | NOT FOUND, request quote | "ideally suited for biasing APDs" (vendor text) | SEARCH-SUMMARY (matsusada.com/product/high-voltage-modules/board-mount/tp); datasheet behind login |
| Matsusada TY-0.15P | 10-18 V | 0-150 V | 10 mA | 75 mVp-p (one page says 0.05 %) | 5 kohm pot or 0-5 V | NOT FOUND | NOT FOUND | APD | SEARCH-SUMMARY; needs >=10 V in, so no |
| **XP Power / EMCO A02P-5** (A series, "SF_A_Series.pdf", www.xppower.com/portals/0/pdfs/SF_A_Series.pdf) | 0.7-5 V (5 V model) | 0-200 V proportional, **unregulated**, +/-10 % tol at max, isolated (500 V) | 5 mA | **<1 %** (= <=2 V p-p at 200 V); osc 50-350 kHz | high-Z control pin 0-100 %, tie to Vin or drive from error amp/DAC | 23.37 x 11.43 x 6.35 mm, 5.66 g (for 100 V-2 kV length per drawing note) | US$112.13 (1 pc), 24 in stock, 19 wk factory lead (DigiKey 1470-3179-ND, 2026-10-08) | datasheet lists "avalanche photo diodes" as application; "low noise quasi-sinewave resonant oscillator" | DATASHEET + distributor page |
| A025P-5 (0-250 V, 4 mA, ripple <0.9 %) | 5 V | | | | | same | | | DATASHEET |
| SDS Micro APD series | 5/12 V | 0-100 V (only) ; 200-500 V family needs 4.5-15.5 V | 100 mW | <25 mVp-p, <5 mVp-p with 100 nF | | NOT FOUND | request pricing (AMS Technologies) | APD | SEARCH-SUMMARY; 100 V model too low |
| UltraVolt V series | 5-24 V | 0-600 V up to 3 kV | | 0.01 % p-p | | | | APD listed | SEARCH-SUMMARY; 200 V model not listed; "AA series" NOT FOUND |
| HVM SMHV, Pico Electronics 5 V -> 200 V | | | | | | | | | NOT FOUND |
| Hamamatsu C12702-03/-04 (KACC1214E, 100 MHz, phi 1.0/3.0) | +5 V single | internal +200 V generator + thermosensor | | "ripple noise minimized" | M preset 30 at factory | business-card size, 37 g | NOT FOUND | the manufacturer's own module | DATASHEET (c12702 pdf fetched) |

EMCO A02P-5 caveats (DATASHEET): 5 V input current <300 mA no load / <500 mA full load (up to 1.5-2.5 W of heat on a small board, though the data may be at max output; at 150 V output current is lower, unquantified); isolated 500 V output return; output depends on load; specs after 30 min warm-up at 25 C. With 1 % ripple at ~50-350 kHz the post-filter must give >~100 dB at the converter frequency to reach tens of uV: two 2-pole RC sections (E) can do ~96 dB at 400 kHz, so feasible but with little margin; its quasi-sinewave oscillator keeps harmonics low.

Hamamatsu C4900 bias module: NOT FOUND (search returned only C12702/C12703; C12703 is +/-12 V).

## D. Temperature compensation (S12023: dVBR/dT 0.65 V/C DATASHEET, apd-selection.md)

Sensitivities taken from apd-selection.md (DERIVED there): at M~100 gain changes ~7 %/V of bias, so ~4.5 %/C uncompensated; M=50 about half. Over 25 +/-10 C the bias would be 6.5 V off, giving M roughly x0.63 .. x1.58 (DERIVED exp(+/-0.07*6.5)). Below ~15 C with a fixed bias the APD walks toward breakdown (VBR falls 0.65 V/C): a hard reason to compensate at least coarsely.

1. **NTC in divider bottom leg** (positive slope needs the NTC in the *lower* resistor so Vout rises with T). Vout = Vref(1 + Rt/Rb), dVout/dT = (Vout - Vref)(-alpha_Rb), alpha = (1/Rb)dRb/dT.
   Required alpha_Rb = -0.65/(150 - Vref) ~ -0.436 %/C for Vref ~1.2 V (Vref unknown for LT8365: FBX NOT FOUND; 1.2 V is a placeholder).
   NTC beta 3950 K at 25 C: alpha_ntc = -beta/T^2 = -4.45 %/C (DERIVED). Dilute with a series fixed resistor: Rb = Rntc + Rfix with Rntc/Rb = 0.436/4.45 = 0.098.
   Example (DERIVED, unvalidated): Rntc = 10 kohm @25 C, Rfix = 92 kohm, Rb ~ 102 kohm, Rt = Rb(150/1.2 - 1) ~ 12.6 Mohm (use 2-3 series 0603/0805 HV resistors, each <=100-200 V). Divider current ~12 uA (also the bleeder). Trim Rfix per unit for VBR (150-200 V spread).
   Residual: NTC curvature gives ~1.4 V peak bow over +/-10 C if linear at 25 C, ~+/-0.7 V when the slope is centered (DERIVED, 2nd-order exp term x 0.098 x Vout); plus VBR tempco unit spread (assume +/-0.05 V/C, not from datasheet) = +/-0.5 V. Total ~+/-1.2 V -> **~+/-8 % gain at M~100, ~+/-4 % at M=50** (DERIVED, rough). Needs good thermal coupling to the APD can; per-unit trim.
2. **Sensor + DAC loop (MCU)**: TMP sensor on the APD can ground, MCU computes Vbias = VBR_unit(25) + 0.65 (T-25) - dV with stored per-unit M-vs-V calibration. DAC injection into an FB divider: Vout = Vfb(1+Rt/Rb) - (Vdac - Vfb) Rt/Rdac. 12-bit DAC over 220 V ~54 mV/step = 0.4 % gain at M~100 (DERIVED). Sensor error +/-0.5 C -> +/-0.33 V -> **~+/-2.3 % at M~100** (DERIVED); with gradient/lag budget ~+/-3 %. Same class as Hamamatsu C12702 (+/-2.5 % typ at M=30, DATASHEET). Needs firmware, but board has a SAMD51 coming.
3. **Rely on slow AGC only**: bias fixed or 1-point trimmed; gain varies x0.63..x1.58 (+/-10 C) at M~100 uncompensated (see above), and below ~15 C the APD can run into excess-noise/near-breakdown. SNR drifts with M even if amplitude is held (excess noise F=M^0.3). Acceptable only with M~30-50 and a wide AGC range; not recommended as the primary method.
4. **Hamamatsu's method**: C12702 uses "a thermosensor [that] controls the bias voltage" through a "voltage controller" (block diagram, DATASHEET), i.e. option 2 in analog form; no APD technical-note equations found (NOT FOUND, search returned only patents). A patent family (SEARCH-SUMMARY, uspto 11513002) describes holding (VBR - Vbias) constant using reference diodes or a stored regression: equivalent to option 2.

Recommended: option 2 for production, option 1 as a hardware-only Rev A fallback or as a coarse pre-bias with option 2 trimming on top. Place the sensor on the APD can/ground tab (apd-selection.md).

## E. Protection and layout

- **IPC-2221B Table 6-1** (secondary reproduction: Altair Pollex help page help.altair.com/pollex/topics/pollex/verification/dfe_ipc_material_r.htm, fetched 2026-10-08; the original standard was not opened). Bare board minimum spacing, mm:

| V (DC/AC peak) | B1 | B2 | B3 | B4 |
|---|---|---|---|---|
| 101-150 | 0.2 | 0.6 | 3.2 | 0.4 |
| 151-170 | 0.2 | 1.25 | 3.2 | 0.4 |
| 171-250 | 0.2 | 1.25 | 6.4 | 0.4 |
| 251-300 | 0.2 | 1.25 | 12.5 | 0.4 |
| 301-500 | 0.25 | 2.5 | 12.5 | 0.8 |

  Column meanings (B1 internal conductors, B2 external uncoated sea level to 3050 m, B3 external uncoated above 3050 m, B4 external with permanent polymer coating) are NOT confirmed by the page I read (a search showed B3 is the altitude case; B4 coating label unconfirmed), so verify against the standard. IPC-2221C (2023) reportedly changes altitude/coating guidance (SEARCH-SUMMARY). IPC-2221 is not a safety standard; IEC creepage tables NOT FOUND. For a 200-220 V rail (row 171-250): internal 0.2 mm, external uncoated 1.25 mm, coated 0.4 mm. Design suggestion (mine): >=1.5 mm clearance externally, >=0.5 mm on inner layers, no HV trace on the top layer under the TIA, solder-mask openings away from HV, slot the board if the HV pad sits near ground.
- **Series resistance and current limit**: S12023 Ir max 200 uA; OPA857 input abs max 10 mA and linear range 60 uA (20k) (apd-selection.md). Photocurrent through R lowers bias: 60 uA x 10 kohm = 0.6 V (~4 % gain at M~100); 100 kohm would drop 6 V (~40 %), so use <=10-22 kohm per stage. Converter/pump short-circuit current is the real limit (module or IC current limit). Fault case: a hard short of the HV node to the TIA input through the filter gives 200 V / 10 kohm = 20 mA, above the OPA857 10 mA abs max, so total series R should be >=22 kohm (22+10 = 32 kohm gives ~6 mA, DERIVED).
- **RC filter at the cathode** (2 stages): R1 22 kohm, C1 10 nF/250 V C0G; R2 10 kohm, C2 1-10 nF/250 V C0G placed within 3 mm of the APD cathode pad with its return to the TIA-side ground (small loop). Attenuation per stage ~fc/f: fc 0.7 kHz and 1.6 kHz -> at 400 kHz about -55 dB and -48 dB (-103 dB total, DERIVED); at 6.63 MHz the C2 impedance is 2.4 ohm for 10 nF, so v_cathode ~ v_in x 2.4/10k = -72 dB for the last stage alone. C0G 250 V in 1206 or film; availability of 10 nF/250 V C0G NOT VERIFIED (check DigiKey: C0G >=10 nF at 250 V typically needs 1206/1210). Avoid X7R (DC-bias loss, piezo noise). 0402/0603 high-voltage parts >=250 V are rarer.
- **Stored energy**: E = 0.5CV^2: 10 nF at 200 V = 0.2 mJ, 100 nF = 2 mJ (DERIVED). Painful pinch, not hazardous; the 12 uA divider bleeds a 10 nF in ~0.15 s (DERIVED). Add a bleeder (1-5 Mohm) across the final cap and a TVS-style clamp to ground at the cathode is NOT recommended (adds leakage). If using the XP A02P-5 note it is isolated, so ground the output return deliberately (and watch its 500 V isolation).
- **Keep-out**: no HV trace/copper within 2 mm of the TIA input node/anode; guard ring tied to the TIA input reference around IN; HV net stays on one inner/bottom side with ground pour under the supply, solid ground under the filter; route the cathode from the filter cap straight to the APD pin. The HV converter and its inductor/charge pump sit at the opposite end of the board from the OPA857; shield can over the supply for 6.63 MHz coupling; filter the 5 V feeding it (ferrite + 10 uF).
- **ESD/handling**: APD anode sits at TIA input (internal clamps ~30 mA, apd-selection.md). Do not hot-plug the APD with bias up; bring the bias up only after the TIA rail (soft-start or sequencer) and ramp the DAC slowly so the cathode step does not pulse 6 pF x dV/dt into the input.

## Recommendation for Rev A

**Primary: LT8365 boost + one extra charge-pump stage (DC2838A topology) for ~100-220 V, loop closed on the final node, trimmed by a 12-bit DAC into the FBX divider, with the two-stage RC cathode filter.** Reasons: only IC family with a 150 V switch, demonstrated 250 V @10 mA (150x our load), 5 V is in its input range, tiny MSOP-16E, Iq 9 uA, burst ripple <15 mV pre-filter, resistor-only control means the DAC and temperature sensor (SAMD51) can do per-unit VBR and tempco compensation (option D2). Pre-layout steps: LTspice from ADI model for 5 V in; bench ripple/spectrum with the 6.63 MHz field on; ensure 5 V in startup current limit.
Also add: (1) footprints for the NTC leg (D1) so the board works with no firmware; (2) a pad/0-ohm option to feed an external HV (from a module) into the filter.

**Fallback: Matsusada TP-0.2P** (5 V in, 0-200 V, <10 mVp-p, 0-3 V control, APD-targeted) on a pin header; the same RC filter and DAC drive. Reasons: lowest-risk noise and proven in APD use; costs: 50.8 x 25.4 x 12.7 mm, 0.12 V/C own tempco at 150 V (0.08 %/C) to be compensated, price/lead NOT FOUND (quote). Second fallback: **EMCO A02P-5** (in stock, ~US$112, 23 x 11 x 6 mm) with an external error amp (it is unregulated, ripple <1 %): choose only if size matters more than noise margin.

## Gaps

- LT8365 datasheet PDF could not be opened (analog.com time-outs): FBX reference, SW abs max, current limit, SYNC/burst behaviour, Vin vs. stage-count curves, and the DC2838A schematic (number of stages, diode/capacitor values, output ripple) are NOT FOUND. Obtain DC2838A user guide/schematic first.
- No LT8365 ripple/noise data with charge-pump stages; no 5 V-input example.
- LT3757/LT3758/LM5156 typical applications and max Vout: NOT FOUND. LT8362, MIC2605/2606, MP3910/MP9486: NOT FOUND.
- Matsusada TP datasheet (behind login), TP price and lead time: NOT FOUND; TP-0.2P noise/tempco from search extracts only.
- EMCO A-series output tempco and low-frequency noise: NOT FOUND (ripple only).
- Hamamatsu Si APD technical note on temperature compensation: NOT FOUND; C4900 bias module NOT FOUND.
- IPC-2221B table was read from a third-party page; B-column meanings and the original standard unverified. IEC 60664/62368 creepage: NOT FOUND.
- NTC design example values assume Vref 1.2 V and beta 3950; residual-error numbers are rough DERIVED estimates; per-unit VBR spread (150-200 V) and tempco spread not measured.
- 10 nF/250 V C0G (and 1-10 nF 0603) availability and price: NOT VERIFIED.
- UltraVolt AA series, HVM SMHV, Pico Electronics 5 V -> 200 V: NOT FOUND.
