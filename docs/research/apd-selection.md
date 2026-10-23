# APD selection for the OPA857 optical receiver (replacing FDS010)

Research date: 2026-10-08. Labels: DATASHEET = printed in a manufacturer document I opened;
GRAPH-READ = read by eye from a datasheet plot (+/- ~5%, rendered page image);
DERIVED = my arithmetic from labeled inputs; NOT FOUND = could not obtain.
"via search summary" = taken from a web-search extract of the datasheet because the PDF
host blocked download (analog.com, mouser.com, first-sensor.com, excelitas.com product pages
returned 403/timeouts). Live DigiKey/Mouser stock and prices could NOT be retrieved (NOT FOUND for
every part); check live before ordering. Downloads (untrusted, never executed) are in the session scratchpad `apd/`.

## Headline findings

1. Best fit: **Hamamatsu S12023-10** (phi 1.0 mm, same area as FDS010, 6 pF, 600 MHz) with
   **S12023-05** (phi 0.5 mm, 2 pF, 900 MHz) as the low-capacitance fallback.
2. **The existing link_budget.py S12023-10 entry is wrong on capacitance**: it assumes 3 pF, the datasheet says 6 pF
   (and dark current 0.2 nA typ at M=100, not 0.05). See Part 4.
3. **No integrated APD-bias IC makes 100-250 V from 5 V.** LT3905 ~60 V, LT3571 75 V, LT3482 and MAX1932 90 V,
   ADL5317 75 V. The S12023 M=100 point is ~130-135 V (typ part) and VBR may be as high as 200 V (max), so
   a supply reaching ~190-200 V is needed unless a low-VBR bin is ordered. See Part 2.
4. Uncompensated, M=100 changes ~4-5 %/degC (DERIVED) -> temperature compensation is mandatory (or AGC downstream).

## Part 1. Candidate comparison

Sources (all opened unless marked): Hamamatsu "Si APD S12023 series, etc." Cat. No. KAPD1007E19,
https://www.hamamatsu.com/resources/pdf/ssd/s12023-02_etc_kapd1007e.pdf ; Hamamatsu S14645 series KAPD1065E03 (Mar 2021),
https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/ssd/s14645_series_kapd1065e.pdf ;
Hamamatsu S8664 series KAPD1012E08 (Feb 2026), https://www.hamamatsu.com/resources/pdf/ssd/s8664_series_kapd1012e.pdf ;
Hamamatsu S12053/S9075/S5344/S5345 KAPD1001E08 (Sep 2025), https://www.hamamatsu.com/resources/pdf/ssd/s12053-02_etc_kapd1001e.pdf ;
Excelitas "C30902 and C30921 Series" Rev.1.1-2015.01 (Arrow copy: https://www.ickey.cn/static-pf/datasheet/0d/7d/f6c6/0d/c65257078eb3ce16bb54d31a74f0431d.pdf);
TE/First Sensor AD500-9 TO, order 3001380 Rev-A 07/2022 (via search summary; https://www.first-sensor.com/cms//upload/datasheets/AD500-9_TO_3001380.pdf);
AD1500-9 TO order 501208 (via search summary; https://www.mouser.com/datasheet/2/313/AD1500-9_TO_501208-586517.pdf).

| Part | Active (dia / mm2) | Ct at op. bias | fc / rise (conditions) | R at M=1, ~800-850 nm | VBR typ (max) | dVBR/dT | Dark at gain | Excess noise | Gain spec | Package |
|---|---|---|---|---|---|---|---|---|---|---|
| **S12023-10** | 1.0 / 0.78 (area from S8664 doc for same dia; DERIVED pi*r^2) | 6 pF, f=1 MHz (DATASHEET) | 600 MHz, RL=50 ohm, M=100 (DATASHEET) | 0.5 A/W @800 nm, QE 75 % (DATASHEET) | 150 V (200 V max), ID=100 uA (DATASHEET) | 0.65 V/C (DATASHEET) | 0.2 nA typ / 2 nA max at M=100 (DATASHEET) | x=0.3 (F=M^0.3), 800 nm (DATASHEET) | M=100 (DATASHEET) | TO-18, borosilicate window (K) |
| **S12023-05** | 0.5 / 0.19 | 2 pF (DATASHEET) | 900 MHz (DATASHEET) | 0.5 A/W @800 | 150 (200) | 0.65 | 0.1 / 1 nA | x=0.3 | M=100 | TO-18, window K (S12051 lens L, S12086 lens L) |
| S12023-02 | 0.2 / 0.03 | 1 pF | 1000 MHz | 0.5 | 150 (200); bins -01 80-120 V, -02 120-160 V, -03 160-200 V (DATASHEET, listed for -02) | 0.65 | 0.05 / 0.5 nA | 0.3 | 100 | TO-18 |
| S3884 | 1.5 / 1.77 (DERIVED) | 10 pF | 400 MHz | 0.5 | 150 (200) | 0.65 | 0.5 / 5 nA | 0.3 | 100 | TO-5 |
| S2384 / S2385 | 3.0 / 5.0 | 40 / 95 pF | 120 / 40 MHz | 0.5 | same | 0.65 | 1 / 3 nA typ | 0.3 | 60 / 40 | TO-5 / TO-8 (too slow) |
| S14645-02 | 0.2 / 0.03 | 0.5 pF, M=100, 1 MHz | 600 MHz, M=100, RL=50, 900 nm | 0.5 A/W @900 nm (800 nm: NOT FOUND) | 175 (155-195) | 1.1 V/C | 40 pA typ / 400 max, M=100 | x=0.3, 900 nm | M=100 | SMD 3.1x1.8x1.0 mm, glass-epoxy + silicone resin (no hermetic window) |
| S14645-05 | 0.5 / 0.19 | 1.0 pF | 600 MHz | 0.5 @900 nm | 175 (155-195) | 1.1 | 80 pA typ / 800 max | 0.3 | 100 | same SMD |
| S8664-05K / -10K / -20K | 0.5 / 1.0 / 2.0 mm | 1.6 / 4 / 11 pF (420 nm table) | 680 / 530 / 280 MHz | 0.24 A/W @420 nm; 800 nm NOT READ | 400 (500) | 0.78 | 0.2 / 0.3 / 0.6 nA | 0.2 (index) | 50 | TO-5 K (borosilicate) |
| S5344 / S5345 (S5343 absent) | 3.0 / 5.0 | 120 / 300 pF | 25 / 8 MHz | 0.42 A/W @620 nm (600 nm band) | 160 (140-180) | 0.15 | 1 / 3 nA | F=1.9 @650 nm | 50 | TO-5 / TO-8 |
| Excelitas C30902EH | 0.5 / 0.2 | 1.6 pF typ (2 max) | rise/fall 0.5 ns typ (0.75 max), RL=50 | 77 A/W @830 nm at M=150 (70 min) -> ~0.51 A/W M=1 (DERIVED, QE 77 %) | 225 (Vop 180-250 V per unit) | 0.7 V/C (0.5-0.9) | 15 nA typ / 30 max at M=150 | k=0.02 (F=0.98(2-1/M)+0.02M) | 150 | TO-18; -2 has 905 nm filter, BH ball lens |
| C30902SH | 0.5 / 0.2 | 1.6 (2) | 0.5 ns | 128 A/W @830 at M=250 | 225 | 0.7 | 15 / 30 nA (selected low noise) | k=0.02 | 250 | TO-18 |
| C30737 family | 0.3 / 0.5 mm variants | NOT FOUND | >1 GHz (bandwidth-optimized) per Excelitas text | e.g. 35 A/W, 0.7 GHz, VBR 110-160 V for one variant (distributor listing, unverified) | variant-dependent 110-260 V | NOT FOUND | NOT FOUND | NOT FOUND | NOT FOUND | LCC / ceramic SMD (C30737MH-500-90N 900 nm-enhanced) |
| TE AD500-9 TO (3001380) | 0.5 / 0.196 | 1.2 pF, M=100, 100 kHz | 0.5 GHz -3 dB; rise 0.55 ns (905 nm, RL=50) (Farnell lists 0.4 GHz/0.9 ns) | 49 A/W typ, 38 min @905 nm M=100 with 905 nm BP filter; QE >80 % 750-910 nm; 800 nm value NOT FOUND | 200 typ (160 min), IR=2 uA | 1.55 V/K (8015 variant; search summary) | 0.8 nA typ / 2 max, M=100 | NOT FOUND | optimum 50-60, max 200 | TO-52 with 905 nm filter; unfiltered 8015 variant exists |
| TE AD1500-9 TO | 1.5 / 1.77 | NOT FOUND (table garbled) | NOT FOUND | ~52 A/W min @905 M=100 (garbled) | NOT FOUND | 1.25-1.55 V/K | NOT FOUND | NOT FOUND | max 200 | TO |
| Broadcom AFBR-S4 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | These are SiPMs (Geiger-mode arrays, e.g. AFBR-S4N44P014M 4.3x4.2 mm SMD). No discrete linear APD found; reject. |

Notes: S8664 and S5344/S5345 are short-wavelength designs (VBR 400 V / big C); S5343 is not in the current S12023/S12053/S8664 documents (NOT FOUND, likely superseded).
S14645 is rated Ir max 0.2 mA, operating -30..+100 C (DATASHEET). S12023: Ir max 200 uA, IF 10 mA, -20..+85 C (DATASHEET). C30902: continuous Ir 200 uA, peak 1 mA 1 s, -40..+70 C (DATASHEET).
Availability/price class (all parts): NOT FOUND (Hamamatsu product page for S12023-10 shows no status and says "contact us"; Edmund Optics lists S12023-05/-10 and S5344/5 as sold items, stock date unknown). Hamamatsu APDs are typically quote/distributor items; confirm with Hamamatsu USA / Edmund / Mouser before committing.

### Ranking for this application (area vs >=50 MHz with OPA857, C <= ~8 pF, M 50-100, NIR, filter-compatible)
1. **S12023-10**: same 1.0 mm area as FDS010 (4x the S12023-05 area), 6 pF is inside the 5-8 pF budget, 600 MHz intrinsic fc, peak at 800 nm, hermetic TO-18 with flat window (filter sits in front or bonded). Cost: OPA857 noise rises with Cs (project GRAPH-READ table: 20k, 135 MHz brickwall, about 17 nA at 2 pF to 28 nA at 6 pF, interpolated from FIG_NOISE_VS_CS; ~1.5x), but 4x collected power wins (DERIVED ~2.6x SNR vs -05 if the spot overfills the die).
2. **S12023-05**: 2 pF, 900 MHz; lowest TIA noise and best phase margin; quarter the area. Fallback.
3. **S3884** (1.5 mm, 10 pF, 400 MHz): 2.3x the area of -10, same VBR/bias; 10 pF is beyond the preferred budget, TIA noise ~33 nA (GRAPH-READ). Stretch option, verify OPA857 stability with 10 pF + layout.
   2026-10-23 update: the OPA857 was simulated at 10 pF (SIMULATED, TI behavioural model characterised at 1.5 pF, so unverified at 10 pF; `docs/simulation/README.md` Sim 2). The 20 k mode rings past one 20 ns UI (21.5 ns settle, 2.2 dB peaking at 52 MHz), so the +3.5 dB optical area gain is cancelled by the TIA noise rise (about 1 dB) and the need to run 5 k mode, net about zero at 50 Mbps (PROPOSED reasoning, not measured). S3884 is therefore NOT adopted for Rev A; it is a Rev B option only with a discrete TIA (OPA855/OPA858 class with chosen feedback) and ideally a lower line rate (PROPOSED).
   A dual TO-18/TO-5 footprint for D10 was considered and rejected 2026-10-23: the TO-5 lead circle (2.54 mm radius, lab footprint Thorlabs_FDS010_TO-5_P5.08mm_Vertical) lies under the TO-18 flange rim (2.35 to 2.7 mm radius), so the unused HV cathode pad would sit under the grounded can with only the 1.5 mm spacer (decision 26) as clearance, and the unused anode pad would add a plated-through stub to the TIA input (PROPOSED, geometry reasoning, not a CAD check).
4. TE AD500-9 TO (1.2 pF, optimized for 905 nm; bias 200 V class; filtered version blocks 765 nm; datasheet access incomplete) and Excelitas C30902EH (1.6 pF, highest M, needs 180-250 V, 15 nA dark at M=150) are good small-area parts but need a higher bias rail and offer 0.2 mm2 only.
5. S14645-05 (SMD, 1 pF, 175 V, 1.1 V/C is a harsh tempco) fits reflow assembly but resin package and 0.19 mm2 limit it; S8664/S5344/S5345/Broadcom rejected.

## Part 2. APD bias supply (5 V in, 100-250 V, <1 mA, low noise)

| Device | Vin | Max Vout | Current | Control | Notes | Package / status |
|---|---|---|---|---|---|---|
| LT3905 | 2.7-12 V (DATASHEET via search) | switch 65 V; Vout up to ~60 V (press release) | NOT FOUND | FB divider, resistor sets max APD current | high-side APD monitor, 3 uA-3 mA, <2 % (datasheet via search) ; cannot reach 130+ V | QFN (EUD suffix; exact pkg NOT CONFIRMED) |
| LT3482 | 2.5-16 V | 90 V (voltage doubler on-chip) | example 85 V @ 2.5 mA; 48 V / 280 mA switch | CTRL pin + FB; 650 kHz / 1.1 MHz | APD monitor 250 nA-2.5 mA, <10 % over 4 decades | 3x3 QFN-16; production |
| LT3571 | 2.7-20 V | 75 V | 0.47 A switch | FB/CTRL, sync 250 kHz-2 MHz | const-V or const-I loop, same monitor | 3x3 QFN-16 |
| MAX1932 | 2.7-5.5 V | 4.5-90 V (EV kit 40-90 V, 2 mA) | ~2 mA | 8-bit SPI DAC, or ext DAC / resistors | ripple <1 mV, 0.5 % accuracy, high-side current limit, avalanche flag; datasheet Rev 3 (10/19), PRODUCTION | 12-pin 4x4 TQFN |
| ADL5317 | needs separate HV supply <=80 V | VAPD 6-75 V (VSET 3 V compatible) | mirror 5 nA-5 mA, 1:5 ratio | analog VSET | current mirror + overcurrent/overtemp; not a supply | 16-LFCSP 3x3 |
| MAX5026 | 3-11 V | 36 V boost | n/a | FB | generic boost, not an APD part (your list); skip | SOT23-6 |
| LT3484 | NOT FOUND | NOT FOUND | | | could not identify as an APD part; skip | |
| Hamamatsu C12702-03 | +5 V (4.75-5.25) | internal ~+200 V generator | | factory-preset M=30 | temperature-compensated: gain +/-2.5 % typ at 25+/-10 C; 100 MHz, phi1.0 mm; KACC1214E05 (Aug 2023) -- reference design/eval board | 80x50x22 mm module |
| Matsusada TP series | 5 V | 50-300 V | NOT FOUND | analog programming (NOT verified) | ripple <10 mVp-p (search summary; datasheet behind login) | board-mount module |
| Matsusada TZ series | 5 or 12 V | 200-500 V | 200-500 uA (min load 130 kohm @200 V) | | ripple 30 mVp-p (APDs named as use) | board-mount module |
| Discrete (LT1172 cascode, 5 V->200 V, LT design note) | 5 V | 200 V | low mA | FB | needs heavy filtering; old part, check status | discrete |

Gap vs requirement: every integrated IC tops out at 60-90 V. Options for S12023 (VBR 150 typ, 200 max):
(a) order a low-VBR bin (suffix scheme -01 80-120 V / -02 120-160 V is documented for -02; availability for -10 NOT FOUND) and use MAX1932 (90 V);
(b) MAX1932 or LT3482 plus an external diode-capacitor doubler/tripler stage (circuit not verified; MAX1932 switch node access NOT verified);
(c) a ready HV module (Matsusada TP, up to 300 V, <10 mVp-p) followed by a 2-stage RC/LC filter and an MCU-trimmed divider;
(d) discrete boost controller with 200+ V FET, DAC-trimmed reference. Option (c)/(d) is the lowest-risk way to cover the VBR spread.

### Temperature compensation
- VBR tempco: S12023 0.65 V/C; C30902 0.7 V/C (0.5-0.9); AD500-9 1.55 V/K; S14645 1.1 V/C (all DATASHEET).
- Gain sensitivity (DERIVED from S12023 gain-vs-V plot, KAPDB0017EC): M doubles over roughly 10 V near M=50-100 -> ~7 %/V; times 0.65 V/C = ~4.5 %/C uncompensated at M~100. A 20 C swing = 13 V, so the bias must track ~13 V per 20 C to hold M.
- Gain curves at 0/20/40 C are separated by ~13 V per 20 C (GRAPH-READ) = 0.65 V/C, consistent.
- Approaches: (1) NTC/thermistor network in the FB divider: simple, tracks within a few percent over narrow range, needs per-lot trimming because VBR varies 150-200 V; (2) MCU/DAC loop with a TMP sensor on the APD can (best: slope + per-unit VBR offset stored; MAX1932 SPI DAC gives 8 bits, step ~0.35 V at 90 V FS, about +/-2 %/step gain on a 130 V rail needs finer DAC: use 12-bit external DAC); (3) closed loop on received amplitude (AGC) -- VGA absorbs slow drift, but SNR still shifts with M; do (2) + (3). Running M=50 rather than 100 halves the gain-slope sensitivity.
- Keep thermal coupling: put the temperature sensor on the APD TO-can ground tab; allow the board 6.63 MHz field heating to settle.

### Safety, creepage, current limit
- IPC-2221 Table 6-1 spacing (recalled, NOT re-verified against the standard here): 171-250 V: ~0.2 mm internal layers, ~1.25 mm external uncoated (sea level), ~0.4 mm external with conformal coat; plan 2 mm+ for HV net to anything, add silkscreen/board slots, cut ground pour clear of the HV node and the filter parts.
- HV filter cap (e.g. 10 nF-100 nF, >=250-500 V X7R/C0G, and put a bleeder) stores energy; fine for handling safety but still a pinch/shock hazard to a bare finger and kills the TIA if released into its input.
- Limit supply to <= 0.2 mA continuous (S12023/C30902 Ir max 200 uA; peak 1 mA for 1 s C30902) via the IC current limit plus a series resistor (e.g. 100 kohm - 1 Mohm) in the RC filter; each 10 uA of photocurrent drops 1 V per 100 kohm, which also shifts M (~7 %/V near M=100) -- size R for the worst ambient photocurrent.
- Fault: a shorted/leaky HV path puts >10 mA on IN -> abs max (below).

## Part 3. Interface to OPA857 (SBOS630D, Aug 2016; /docs/datasheets/opa857.pdf)

- Absolute max input current, VIN pin: **10 mA** (DATASHEET, 6.1). Input/output voltage -0.7 V to Vs+ + 0.7 V; supply max 3.8 V; differential input 1 V.
- Linear range: output swing 0.6-1.9 V (1.2 V window, class-A output from VICR 1.83 V down) -> max input current **60 uA at 20k (CTRL=1)** and **240 uA at 5k (CTRL=0)** (DATASHEET, 7.3.1).
- Effective gain into 500 ohm differential load: 18.2 kohm / 4.5 kohm (DATASHEET). Input pin capacitance 2 pF; small-signal BW 105 MHz (CTRL=1) / 125 MHz (CTRL=0) at Cs=1.5 pF (DATASHEET).
- Input-referred noise 135 MHz brickwall at Cs=1.5 pF: 15 nA rms (20k) / 25 nA rms (5k) (DATASHEET). Noise vs source capacitance (Fig. 9/10, your tool's table, GRAPH-READ +/-2 nA): 20k: 12(0 pF), 24(5), 33(10), 38(15) nA; 5k: 21(0), 40(5), 58(10), 68(15) nA.
- The datasheet design target is Cs=1.5 pF in total (APD 0.5-0.7 pF + parasitic 0.8-1 pF): a 6 pF APD departs far from this; bandwidth and peaking at 6-8 pF must be checked in SPICE/bench (OPA857 SPICE model available).
- Protection: internal ESD/clamp (overdrive recovery 25 ns at 2x overload); diodes typically support 30 mA continuous; "use additional external low-capacitance protection where higher currents are possible" (DATASHEET 7.3.4). With a 200 V net nearby, a HV-to-IN fault is real: keep APD anode lead short, route IN guard-ringed, and a series resistor at IN would add noise and cut bandwidth, so rely on the HV-side current limit (<=0.2 mA, well under the 10 mA abs max) plus the HV filter cap's small stored energy.
- Polarity: **cathode to +HV through the RC filter, anode to OPA857 IN**, photocurrent flows into IN, TIA output goes down from 1.83 V (the same as FDS010). The anode rests at ~1.83 V, so reverse bias = HV - 1.83 V; the bias formulas and VBR tempco include that 1.83 V offset (small, but add to the DAC calibration).
- Ambient-light saturation: DC photocurrent is multiplied by M. 60 uA / (M=50) = 1.2 uA of primary photocurrent saturates the 20k range; at R=0.5 A/W that is only ~2.4 uW of in-band light on the die (DERIVED); on 5k 240 uA -> 4.8 uA -> ~10 uW. Also shot noise from background adds F*M*Ibg. The OPA857 is DC coupled (no ambient rejection); either AC-couple/servo the dc or keep in-band ambient << 100 nW. The 6.63 MHz field also induces pickup: shielding, differential output.
- Optical filter must give OD such that out-of-band (visible/IR sunlight, LED, WPT lighting) is cut > 60 dB while passing 765-850 nm; the filter must cover the emitter wavelengths actually used (765 and/or 850 nm per link_budget.py), so size its passband to those; the hermetic flat window leaves room for an interference filter in front. The S12023-10A variant (chip light-shielded by aluminum outside the photosensitive area, DATASHEET note *4) reduces stray light on the die edges.

## Part 4. link_budget.py parameter blocks

Tool keys: diam_mm, c_pf, resp{625,765,850} (note tool wavelength keys are 625/765/850), dark_nA, apd=True, M, k.
Responsivity at 625/765/850 for S12023: only 800 nm is printed (0.5 A/W, QE 75 %, DATASHEET); the QE-vs-wavelength curve (KAPDB0021EC) reads ~66 % @630, ~85 % @765, ~79 % @850 (GRAPH-READ) but the curve shows ~84 % at 800 whereas the table says 75 %; values below are curve shape scaled by 75/84 (DERIVED): R = QE*lambda/1240.
dark_nA: Hamamatsu lists dark current at M=100 (total). The tool uses primary (pre-gain) dark; total/M is the DERIVED lower bound if all bulk; the pessimistic value is the total itself. Both negligible against TIA noise (~nA).

```python
# S12023-10: DATASHEET KAPD1007E19 (diam 1.0, Ct 6 pF @M=100, id 0.2 nA typ M=100, x=0.3, S=0.5 A/W @800 nm)
"S12023-10": dict(diam_mm=1.0, c_pf=6.0,
                  resp={625: 0.30, 765: 0.47, 850: 0.48},   # R(M=1): 625/765/850 GRAPH-READ scaled, DERIVED
                  dark_nA=0.2,                              # DATASHEET total at M=100 (pessimistic); ~0.002 if all bulk
                  apd=True, M=50.0,                         # M=100 max (DATASHEET); 50 = recommended low-noise point (assumption)
                  k=0.02),                                  # DERIVED: F=M^0.3 matches McIntyre k~0.02 at M=50-100; Excelitas states k=0.02
# S12023-05: DATASHEET (diam 0.5, Ct 2 pF, id 0.1 nA typ M=100, 900 MHz)
"S12023-05": dict(diam_mm=0.5, c_pf=2.0,
                  resp={625: 0.30, 765: 0.47, 850: 0.48},   # same die structure as -10, DERIVED
                  dark_nA=0.1, apd=True, M=50.0, k=0.02),
# S3884 (stretch): DATASHEET (diam 1.5, Ct 10 pF, id 0.5 nA typ, 400 MHz)
"S3884":     dict(diam_mm=1.5, c_pf=10.0,
                  resp={625: 0.30, 765: 0.47, 850: 0.48},
                  dark_nA=0.5, apd=True, M=50.0, k=0.02),
# C30902EH (alt, 180-250 V): DATASHEET (diam 0.5, Ct 1.6 pF typ, 15 nA @M=150, k=0.02, 77 A/W @830 M=150)
"C30902EH":  dict(diam_mm=0.5, c_pf=1.6,
                  resp={625: NOT FOUND, 765: NOT FOUND, 850: 0.51},  # 850: DERIVED from 77 A/W / 150 at 830 nm; others not read
                  dark_nA=15.0, apd=True, M=100.0, k=0.02),
```
The tool's existing S12023-10 entry should change c_pf 3.0 -> 6.0 and resp 625 0.30 / 765 0.50 / 850 0.50 -> 0.30 / 0.47 / 0.48 (conservative). M recommended range 50-100.

## Recommendation

- **Primary APD: Hamamatsu S12023-10 (TO-18, phi 1.0 mm)**. Same active area as FDS010, 6 pF / 600 MHz, 0.5 A/W at 800 nm, x=0.3, low dark current, hermetic flat window for the filter, 0.65 V/C tempco (gentlest of the candidates). Risks: 6 pF on OPA857 raises noise ~1.5x and needs a stability/bandwidth check; VBR spread 150-200 V.
- **Fallback APD: S12023-05** (0.5 mm, 2 pF, 900 MHz): lowest TIA noise, near the OPA857 design Cs; 4x less area. Excelitas C30902EH is the alternative if more gain (M 150) is wanted at the cost of 180-250 V bias.
- **Primary bias-supply IC: MAX1932** (SPI DAC, <1 mV ripple, 0.5 % accuracy, high-side current limit, avalanche flag, 2.7-5.5 V in) because it is the only IC option with digital trim for temperature compensation and VBR calibration. It stops at 90 V, so it directly serves only a low-VBR bin (~80-115 V). For standard S12023 parts add a doubling stage or use the Matsusada TP module; LT3482 (monitor + 90 V) is the second choice. Neither route is verified in this research.
- 2026-10-23: S3884 (10 pF) is not adopted for Rev A. The OPA857 simulated at 10 pF rings past one UI in 20 k mode (SIMULATED, model unverified at 10 pF; `docs/simulation/README.md` Sim 2); the area gain is cancelled by the noise rise and 5 k mode. Rev B option only with a discrete TIA (OPA855/OPA858 class), ideally at a lower line rate. A dual TO-18/TO-5 D10 footprint was rejected the same day (see item 3 above). PROPOSED.
- Run M=50 initially (0.5x the gain slope), closed-loop with a TMP sensor on the can plus downstream AGC.

## Gaps

- Live DigiKey/Mouser/Edmund stock and prices for every part: NOT FOUND.
- S12023-10 operating voltage for M=50/100 is GRAPH-READ only (~130-135 V at 20 C for M=100, roughly 5-10 V lower for M=50); per-device Vop is not printed.
- QE/responsivity at 625/765/850 nm are GRAPH-READ+scaled; the plot (~84 % at 800) disagrees with the table (75 %).
- OPA857 bandwidth and stability with 6-10 pF source capacitance (datasheet gives noise plot only; SIMULATED at 6 and 10 pF 2026-10-23, `docs/simulation/README.md` Sim 2, nothing measured).
- AD500-9/AD1500-9, C30737: PDF hosts blocked; AD1500-9 capacitance/rise time and C30737 table NOT FOUND; AD500-9 800 nm responsivity NOT FOUND.
- LT3905/LT3482/LT3571/ADL5317 datasheets (analog.com) could not be opened; figures come from search extracts and distributor pages.
- Whether S12023-10 low-VBR suffix bins exist; Matsusada TP/TZ datasheets are behind login.
- IPC-2221 spacing values are recalled and need confirming against the standard (IPC-2221B Table 6-1).
- 800 nm responsivity of S14645 and S8664 not read.
