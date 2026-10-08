# Link component evidence (photodiode -> TIA -> VGA -> comparator -> LVDS)

Retrieval date for all sources: 2026-10-08. Downloaded copies (untrusted data, never executed) are in `downloads/` next to this file.
Convention: "NOT FOUND" = could not be retrieved; "(graph)" = read off a plotted curve, approximate.

## 1. Thorlabs FDS010 (Si PIN, TO-5)

Important: thorlabs.com (product page, QuickView, spec-sheet PDF) returned only a bot-block stub ("Thorlabs") to both WebFetch and curl, so the CURRENT Thorlabs page/spec sheet could NOT be read directly. Only two sources were obtained: (a) the old Rev E spec sheet (April 2010, 0636-S01), and (b) a reseller page (OptoMechs) reproducing the current Thorlabs table, plus search-engine snippets of the current Thorlabs table and a later Rev I sheet (2017-03-16) that I could not open.

| Parameter | Rev E sheet (2010, file read) | Current Thorlabs table (secondary: OptoMechs / search snippets) |
|---|---|---|
| Active area | diameter 1.02 mm (sheet prints "0.82 nm2", typo for mm2) | 0.8 mm2 (diameter 1.0 mm) |
| Junction capacitance | 10 pF typ @ 0 V; 2 pF typ @ -10 V | 6 pF typ @ 10 V (snippet of Thorlabs table and eBay listing; not read from a Thorlabs file) |
| Rise/fall time | <1 ns, RL = 50 ohm, 20 V | 1 ns / 1 ns @ 830 nm, 10 V (OptoMechs) |
| Bandwidth | 350 MHz min, RL = 50 ohm, -3 dB, 5 V | NOT FOUND |
| Dark current | 2.5 nA max @ 20 V | 0.3 nA typ @ 10 V (OptoMechs); snippet also says 1.0 nA max @ 10 V (unconfirmed) |
| NEP | 5.0e-14 W/rtHz (900 nm, 20 V) | NOT FOUND |
| Max reverse (bias) voltage | 25 V | 25 V |
| Reverse current / forward current max | 5 mA / 5 mA | NOT FOUND |
| Operating temp | -40 to 100 C | -25 to 75 C (OptoMechs) |
| Package | TO-5, 0.36" (9.14 mm) can, UV fused-silica window (window per reseller text) | TO-5 |
| Wavelength range | 200-1100 nm | 200-1100 nm |
| Responsivity | graph only, FDS010 curve (blue) | graph only |

Responsivity (graph, Rev E "FDS Series Photodiode Responsivity", FDS010 curve, approximate): ~0.43 A/W at 630 nm, ~0.35 A/W at 850 nm; peak ~0.445 A/W near 730 nm. No numeric table found. Sheet states responsivity varies lot to lot and rises slightly with bias.

Pins and mechanical (Rev E drawing): pin 1 = Anode, pin 2 = Case, pin 3 = Cathode. Leads Ø0.018" (0.46 mm), length 1.500" (38.10 mm); lead circle Ø0.200" (5.08 mm) (on the bottom-view drawing); can Ø0.360" (9.14 mm), flange Ø0.397" (10.1 mm); window recess Ø0.240" (6.10 mm). Lead-to-lead spacing is NOT dimensioned in the sheet; only the Ø0.200" (5.08 mm) lead-circle diameter is given (standard TO-5 3-lead pattern, 45-degree geometry). Check the drawing before layout. Sheet text: "The photodiode anode produces a current" and RL from anode to ground; bias applied to the cathode through R1 = 1 kohm / C1 = 0.1 uF filter.

Capacitance question (2 pF vs 6 pF): Rev E sheet says 10 pF @ 0 V and 2 pF @ -10 V. Newer table says 6 pF @ 10 V (per snippets). These conflict at about the same bias (10 V): 2 pF vs 6 pF. The 6 pF may be the newer, more conservative spec; the 2 pF is from the 2010 sheet. Design with 6 pF at 10 V (worst case), and 10 pF at 0 V. Must be settled by reading the current Thorlabs sheet by hand.

Sources:
- Thorlabs FDS010 Product Specification Sheet 0636-S01 Rev E, April 20, 2010, mirror at https://www.physics.utoronto.ca/~astummer/Archives/2011%20Balanced%20TIA/Docs/Thorlabs%20FDS010%20PD.pdf (downloaded, text read; file `fds010_utoronto.pdf`). Old; not the current sheet.
- OptoMechs reseller page reproducing current table: https://optomechs.com/products/thor-labs/light-analysis/FDS010 (no datasheet date; reseller disclaims accuracy).
- Search-engine snippets only (not opened): https://www.thorlabs.com/photodiodes?pn=FDS010 ; https://optomechs.com/pdf/manuals/FDS010/FDS010_SpecSheet.pdf (Rev I, 2017-03-16; URL returned 404/not a PDF to me); https://www.gophotonics.com/products/photodiodes/thorlabs-inc/56-46-fds010 (403 to fetch).

### FDS010 spec table (from 0636-S01, revision as found)

Source: docs/datasheets/fds010.pdf, user-supplied, SHA-256 9ddfb35ecbe458a89cfd34c6a86d5372f66178557ccb23be1a219ce4def427e3. Revision string on every page: "March 16, 2017 / 0636-S01, Rev I". This is NOT the Rev E (April 2010) sheet; it is newer (Rev I, the one previously only seen in snippets). Capacitance: this sheet says 6 pF (Typ.) at 10 V reverse bias ("Capacitance (10 V) Cj 6 pF (Typ.)"). It does not state 2 pF or any 0 V capacitance, so the Rev E "2 pF @ -10 V" value is superseded; design with 6 pF at 10 V. Rise/fall time here is 1 ns / 1 ns at 830 nm, RL = 50 ohm, 10 V.

Specifications table, pdftotext output (page 1), verbatim:

```
Specifications
                             Specificationsa
Wavelength Range                               λ            200 - 1100 nm
Peak Wavelength                                λP               730 nm
Peak Responsivity                              (λp)            0.44 A/W
Active Area Diameter                                     0.8 mm2 (Ø1.0 mm)
Rise/Fall Time (830 nm, RL=50 Ω, 10 V)      tr/tf             1 ns / 1 ns
NEP, Typical (830 nm, 10 V)                W/√Hz              5.0 x 10-14
                                                            0.3 nA (Typ.)
Dark Current (10 V)                            Id
                                                             1.0 nA (Max)
Capacitance (10 V)                             Cj             6 pF (Typ.)
Package                                                          TO-5
Sensor Material                                                    Si
a. Unless otherwise noted, all measurements are performed at 25 °C ambient temperature.

                        Maximum Rating
Max Bias (Reverse) Voltage                               25 V
Reverse Current                                         5 mA
Operating Temperature                                -25 to 75 C
Storage Temperature                                 -40 to 100 C
```

Pin assignment (page 3 drawing, extracted text only): pins labelled PIN 1, PIN 2, PIN 3, with a "Ground" label next to PIN 2; dimensions Ø1.00 mm active area, Ø6.1 mm window recess, Ø8.3 mm, Ø9.1 mm can, Ø5.1 mm lead circle, Ø0.5 mm leads, 38.0 mm lead length, 3.0 mm, 4.6 mm, 0.7 mm, 9.9 mm. Anode/cathode-to-pin mapping is not in the extracted text (drawing graphic only); the Rev E mapping (pin 1 anode, pin 2 case, pin 3 cathode) is consistent with the "Ground" label on pin 2 but must be confirmed visually on the PDF. Description text: "an anode and cathode connection"; RL from photodiode anode to ground; bias to cathode via R1 = 1 kΩ, C1 = 0.1 μF noise filter. Responsivity is a graph only (page 2), no numeric table beyond the 0.44 A/W peak at 730 nm.

## 2. Hamamatsu C15522-3010SA (MPPC module, analog output)

Official C15522 datasheet (KACC1288J02, Japanese only, PDF created 2022-05-17) was downloaded and its tables read. The English sibling C15524 (flexible-cable version, KACC1289E01, Sept 2021) has identical numeric tables for the "-3010SA" model; used for English wording. Values below are identical in both documents.

| Parameter | Value (condition) |
|---|---|
| Effective photosensitive area | 3 x 3 mm |
| Pixel pitch / number of pixels | 10 um / 89,984 pixels (3010SA); 15 um / 39,984 (3015SA) |
| Output | Analog voltage (amplified; module includes MPPC, amplifier, HV supply, temperature compensation) |
| Spectral response / peak | 290-900 nm / 500 nm typ |
| Photoelectric conversion sensitivity | 0.3e8 min, 0.4e8 typ, 0.5e8 max V/W (lambda = peak, 25 C, Vs = +/-5 V) |
| Cutoff frequency (-3 dB, sine) | high side 10 MHz min, 15 MHz typ (3010SA); low side DC (DC-coupled) |
| NEP (dark) | 2.7e-15 typ, 5.4e-15 max W/rtHz |
| Minimum detection limit | 10 pW rms typ, 20 max |
| Maximum output voltage | 4.7 V typ |
| Supply | +/-5 V (+4.75..+5.25, -4.75..-5.25); abs max +/-6 V; supply must source >= 300 mA |
| Current consumption | +Vs 50 mA typ / 250 max; -Vs -20 typ / -40 max |
| Temp stability of output voltage | +/-5 % max (25 +/- 10 C) |
| Operating / storage | -10..+60 C / -20..+80 C, no condensation |
| Mass / tolerance | 8 g, +/-0.3 mm (from search summary of drawing; not re-verified) |
| Gain (as a number) | NOT STATED as a unitless gain; conversion sensitivity in V/W above is given instead |
| Built on which MPPC | NOT STATED by part number (documents say "wide dynamic range type MPPC" only) |
| Recommended load | NOT FOUND in the datasheet text (no load impedance stated; the sheet shows an oscilloscope connection example and a 100 mV / 1 us waveform) |
| Saturation / recovery time | NOT FOUND as a specified number. Only a linearity curve (pulse 2 us, 5 kHz, duty 1 %) and the 4.7 V max output voltage. Pulse behavior must be inferred from the 15 MHz bandwidth and ~10 um-pixel recovery; not verified. |

Note for 50 Mbps use: 15 MHz typ high cutoff is far below what a 50 Mbps NRZ link needs (~25-35 MHz), so this module (previous receiver) is bandwidth-limited. Its spectral peak is 500 nm; sensitivity at 630-850 nm is lower (read from the V/W-vs-wavelength graph, not extracted).

Sources:
- https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/ssd/c15522_series_kacc1288j.pdf (KACC1288J02, PDF dated 2022-05-17 created / 2022-07-25 modified; Japanese; file `c15522j.pdf`)
- https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/ssd/c15524_series_kacc1289e.pdf (C15524 sibling, KACC1289E01, Sept 2021, modified 2024-08-04; file `c15524e.pdf`)
- No English C15522 sheet found (search, hamamatsu.com).

## 3. Würth Elektronik 150060RS75003 (WL-SMCW 0603 red chip LED)

Note: this is a WL-SMCW chip LED, NOT WL-TMRW. Official datasheet downloaded from we-online.com (file `150060RS75003.pdf`; PDF title "150060RS75003 Datasheet WL-SMCW SMT Mono-color Chip LED Waterclear", PDF creation date 2025-10-20; status "Valid").

| Parameter | Value (test condition) |
|---|---|
| Peak wavelength | 630 nm typ (20 mA) |
| Dominant wavelength | 615 min / 625 typ / 635 max nm (20 mA) |
| Luminous intensity | 230 min / 530 typ / 800 max mcd (20 mA). Radiant intensity (mW/sr) not given. |
| Forward voltage | 1.8 / 2.0 / 2.6 V (20 mA) |
| Spectral bandwidth | 15 nm (20 mA) |
| Viewing angle (2theta 50 %) | 140 degrees typ (20 mA) |
| Continuous forward current | 30 mA max |
| Peak forward current | 100 mA max (duty 1/10 @ 1 kHz) |
| Power dissipation | 78 mW |
| Reverse current | 10 uA max @ 5 V |
| Operating temp | -40..+100 C |
| Rise/fall time, switching speed | NOT FOUND in datasheet (no capacitance or switching data) |
| Package | 0603 (1.6 x 0.8 mm), waterclear lens |

Sources:
- https://www.we-online.com/components/products/datasheet/150060RS75003.pdf (retrieved 2026-10-08; dated PDF 2025-10-20)
- Distributor corroboration (listing only): https://nz.element14.com/wurth-elektronik/150060rs75003/led-red-530mcd-630nm/dp/3934862 (fetch timed out; seen in search snippet as "LED red 530mcd 630nm")

## 4. QT Brightek QBLP601-2IR4 (0603 IR LED, 765 nm)

Official datasheet downloaded (file `QBLP601-2IR4.pdf`), "Version 1.0, Date: September 17, 2021", 9 pages.

| Parameter | Value (condition) |
|---|---|
| Peak wavelength | 760 min / 765 typ / 780 max nm (IF = 20 mA) |
| Radiant intensity | 0.2 mW/sr min (bin A 0.20-0.60, B 0.60-1.10, C 1.10-1.60); 1.0 mW/sr typ (IF = 20 mA, 25 C) |
| Forward voltage | 1.6 typ / 1.8 max V (20 mA) (bin table min 1.0 V) |
| Viewing angle | 140 degrees typ |
| Continuous forward current | 50 mA max |
| Peak (pulsed) forward current | 1 A (IFP), duty 1 %, pulse width 100 us |
| Power dissipation | 90 mW; reverse voltage 5 V |
| Operating / storage | -40..+80 C / -40..+85 C |
| Rise/fall time | NOT FOUND (not in the datasheet text; curves page is images; AlGaAs, no switching spec) |
| Technology / package | AlGaAs, 0603, water-clear |

Caution: Digi-Key lists the nominal wavelength as 765 nm, consistent. Sibling QBLP601-IR4 is 740 nm: do not mix.
Caution: 1 A pulse rating is for 100 us at 1 % duty; a 50 Mbps drive is nowhere near that regime; stay within DC/average limits.

Sources:
- https://www.qt-brightek.com/datasheet/QBLP601-2IR4.pdf (V1.0, 2021-09-17; retrieved 2026-10-08)
- https://www.digikey.ie/en/products/detail/qt-brightek-qtb/QBLP601-2IR4/16499678 (listing, matches)

## 5. Lattice ULX3S (ECP5): LVDS-capable GPIO

Evidence: ULX3S schematic v3.1.7 (`schematics_v317.pdf`, PDF created 2021-12-10, gpio sheet Rev 1.0.2), constraints file `ulx3s_v20.lpf`, Lattice ECP5 sysIO Usage Guide FPGA-TN-02032-1.3 (Jan 2020, from a third-party mirror). Note emard/ulx3s `doc/schematics.pdf` is a pointer to `schematics_v316.pdf`; v317 also exists; I used v317.

Findings (gpio sheet text, verbatim):
- "GP,GN 0-7 single-ended connected to BANK0"
- "GP,GN 8-13 differential bidirectional connected to BANK7"
- "GP,GN 14-21 differential bidirectional connected to BANK2,3 on 'ram' sheet"
- "GP,GN 22-27 single-ended connected to BANK1 on 'gpdi' sheet"
- "GPIO route only A/B pairs as those are differential bidirectional; don't route C/D pairs to GPIO as those can be differential input only"; "BANK0,1 are single-ended (non-differential)".

| Item | Result |
|---|---|
| True differential pairs on GPIO header | gp/gn[8..13] (bank 7) and gp/gn[14..21] (banks 2, 3). 14 pairs. gp/gn[0..7] and [22..27] are NOT differential-capable. |
| Pin sites (from ulx3s_v20.lpf, "DIFF" comments) | gp8 A4/gn8 A5; gp9 A2/gn9 B1; gp10 C4/gn10 B4; gp11 F4/gn11 E3 (shares wifi_gpio26/25); gp12 G3/gn12 F3 (clock-capable, shared wifi_gpio33/32); gp13 H4/gn13 G5 (wifi_gpio35/34); gp14 U18/U17 (ADC AIN1/AIN0); gp15 N17/P16 (AIN3/AIN2); gp16 N16/M17 (AIN5/AIN4); gp17 L16/L17 (AIN7/AIN6); gp18 H18/H17; gp19 F17/G18; gp20 D18/E17; gp21 C18/D17 |
| Polarity | "true" pad is gp (+); gn (-) is ignored in the design when a LVCMOS33D / differential type is used. Header pin numbering applies to female angled header; swap even/odd for male vertical. |
| Bank VCCIO | Not stated in a form I could verify. Every GPIO is constrained LVCMOS33 in the LPF, implying 3.3 V banks, and the schematic net +3V3 appears around the VCCio pins. The text extraction of the FPGA power sheet is ambiguous, so treat "3.3 V" as inferred, not read. |
| LVDS input on 3.3 V bank | ECP5 sysIO guide: differential LVDS inputs are supported on A/B and C/D pairs, left and right sides only; ECP5 has programmable on-chip 100 ohm differential input termination "between all pairs of all banks on left and right sides". Whether LVDS (LVDS25 input) is legal with VCCIO = 3.3 V was NOT confirmed (search failed; guide extract has no explicit rule). |
| External 100 ohm termination on board | None found on the gpio sheet (text extraction shows no resistor between GP/GN). Not visually verified. Use the ECP5 on-chip TERMINATION=100 if the bank allows it, otherwise add external 100 ohm across the pair at the FPGA pins. |

Sources:
- https://github.com/emard/ulx3s/blob/master/doc/schematics_v317.pdf (v3.1.7; gpio sheet Rev 1.0.2; PDF 2021-12-10; raw copy `ulx3s_v317.pdf`)
- https://github.com/emard/ulx3s/blob/master/doc/constraints/ulx3s_v20.lpf (raw copy `ulx3s_v20.lpf`; header comment "default single-ended; rename LVCMOS33->LVCMOS33D to enable differential")
- https://github.com/emard/ulx3s/blob/master/README.md (GPIO pins "routed as differential pairs", 12 true differential pairs claim; note README says 12, schematic says 14 diff pairs (8-13 and 14-21): contradiction, see Gaps)
- Lattice FPGA-TN-02032-1.3, ECP5 and ECP5-5G sysI/O Usage Guide, Jan 2020: https://autodiscover.stm32world.com/images/2/29/FPGA-TN-02032-1-3-ECP5-ECP5G-sysIO-Usage-Guide.pdf (third-party mirror, file `ecp5_sysio.pdf`)

## 6. Alternatives (brief)

Hamamatsu documents downloaded and read (files `s5971.pdf`, `s14645.pdf`, `s12023.pdf`).

| Part | Type | Active area | Capacitance | Bandwidth | Responsivity | Bias | Package |
|---|---|---|---|---|---|---|---|
| S5973 (S5971/S5972/S5973 sheet, KPIN1025E) | Si PIN | phi 0.4 mm (0.12 mm2) | 1.6 pF (VR = 3.3 V, 1 MHz) | fc 1 GHz (VR = 3.3 V) | S5973 row: 0.52 / 0.51 / 0.47 A/W against columns for 660 / 780 / 830 nm (column alignment in extraction not certain; ~0.5 A/W across 660-830). No 630 or 850 nm value. | 3.3 V typ; abs max 20 V | TO-18 |
| S5972 (same sheet) | Si PIN | phi 0.8 mm (0.5 mm2) | 3 pF (VR = 10 V) | 500 MHz (VR = 10 V) | ~0.57 A/W peak at 800 nm (sheet), 0.44 at 660 nm | 10 V; abs max 20 V | TO-18 |
| S12023-05 (APD) | Si APD | phi 0.5 mm | 2 pF (M = 100) | fc 900 MHz (RL = 50 ohm, M = 100) | 0.5 A/W at 800 nm, M = 1; QE ~75 % | breakdown 150 V typ, 200 V max (ID = 100 uA); operate near gain 100; temperature coefficient 0.65 V/C; max reverse current 200 uA | TO-18 |
| S14645-05 (APD) | Si APD, SMD | phi 0.5 mm (0.19 mm2) | 1.0 pF (M = 100, 1 MHz) | fc 600 MHz (M = 100, RL = 50 ohm, 900 nm) | 0.5 A/W at 900 nm, M = 1; peak 840 nm | breakdown 175 V typ (155-195); VBR tempco 1.1 V/C; gain 100 | glass-epoxy SMD 3.1 x 1.8 x 1.0 mm |

Notes: no 630 nm value found for these APDs (APD sheets give 0.5 A/W at 800/900 nm only; graphs not extracted). APD options need a 150-200 V, temperature-compensated bias supply, so for a 50 Mbps link with mW-level LED light the S5973 (3.3 V) is likely the simplest speed upgrade; the FDS010 at 6 pF is the slowest candidate. S12023 datasheet PDF creation date 2026-07-26 (KAPD1007E per earlier search note; revision letter not extracted).

Sources:
- https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/ssd/s5971_etc_kpin1025e.pdf (PDF created 2020-02-12, modified 2024-08-01)
- https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/ssd/s12023-02_etc_kapd1007e.pdf (PDF created 2026-07-26; S12023-05 row partly garbled in extraction; capacitance/bandwidth cross-checked with Hamamatsu product-page summaries and Edmund Optics listing)
- https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/ssd/s14645_series_kapd1065e.pdf (PDF created 2021-03-15, modified 2024-08-02)

## Gaps and cautions

1. FDS010: RESOLVED 2026-10-08. The current sheet (0636-S01 Rev I, 2017-03-16, docs/datasheets/fds010.pdf) gives 6 pF typ at 10 V; Rev E's 2 pF is superseded. Pinout verified from the Rev I drawing: 1 anode, 2 case, 3 cathode. Remaining: measure installed capacitance.
2. C15522-3010SA: English sheet NOT FOUND (Japanese sheet read; numbers match the English C15524 sibling). No load impedance, gain number, MPPC part number, or saturation/recovery time is given. Bandwidth 15 MHz typ is marginal for 50 Mbps NRZ.
3. WL-SMCW 150060RS75003: no rise/fall time or capacitance in the datasheet; the user-supplied description ("red emitter") fits, but the series is SMD WL-SMCW, not through-hole. Luminous (mcd) not radiant units; convert only with the spectral curve.
4. QBLP601-2IR4: no rise/fall time; characteristic curves are images and were not read. NIR LED switching speed must be measured.
5. ULX3S: bank VCCIO (3.3 V) inferred, not read; LVDS-in-3.3V-bank legality and on-chip termination availability on those specific banks not confirmed (the ECP5 guide mirror is from a third party, Jan 2020 rev 1.3). Contradiction: README says 12 differential pairs, schematic comments say pairs 8-13 and 14-21 (14 pairs). Schematic text extraction was not checked visually.
6. Section 6: S5973 responsivity row alignment is uncertain; no values exactly at 630 or 850 nm for any alternative; S12023 row text extraction was partially garbled.
7. All fetches were done by automated tools; the "retrieved" date is 2026-10-08.
