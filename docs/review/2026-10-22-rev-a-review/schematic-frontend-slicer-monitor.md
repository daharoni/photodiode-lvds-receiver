# Rev A review: Front End, Slicer, Monitor sheets (2026-10-22)

Executive summary
1. One probable BLOCKER: the S12023-10 pin mapping in the lab library symbol (pin 1 = K, pin 3 = A) is the opposite of what the Hamamatsu outline drawing shows when read at 900 dpi (pin 1 = anode, pin 3 = cathode). If I am right the APD is forward-biased by the HV rail. Confirm with a diode test on a real part before anything else.
2. One MAJOR: with the ESP32 unprogrammed, DAC_TH is 0 V (MCP4728 factory EEPROM), which puts the comparator threshold 16.3 mV below the baseline. That is about the same size as the signal at the BER 1e-9 sensitivity point, so "decodes with the ESP32 unprogrammed" holds only for strong signals.
3. The rest of the fast path (pin maps of U10/U11/U20/U30, DC bias paths, AC-coupling corners, polarity chain to J50, hysteresis arithmetic, CTRL/SHDN defaults) checks out against the datasheets. Several MINOR items: OPA855 gain at its minimum-stable-gain limit with 1 % parts, 3V3 rail window versus OPA855 3.3 V minimum, direct GPIO-to-CTRL tie with a solder jumper, noise bandwidth versus the link budget.
4. Nothing in this review was measured or simulated by me; all arithmetic is hand-derived from cited datasheet values and is labelled as such.

Sources used: netlist.xml (exact pin to net), frontend/slicer/control.kicad_sch notes, docs/schematic/{frontend,slicer,control,power}.md, rev-a-sheet-specs.md, docs/simulation/README.md, link-budget.md, apd-bias-design.md. Datasheets read: OPA857 SBOS630D, OPA855 SBOS622D, TLV3605 SNOSDA2F (Jun 2024), MCP4728 DS22187E, Hamamatsu S12023 KAPD1007E19 (docs/research/downloads/s12023.pdf, untrusted raw data, but it is the only source for the pinout; the lab library cites the same page).

---

## BLOCKER

### B1. APD D10 pin mapping appears reversed (cathode and anode swapped at the symbol/footprint)
- Location: Front End D10 (S12023-10), symbol in `AharoniLab_Passive.kicad_sym` ("S12023-10"), footprint `Hamamatsu_S12023_TO-18_P2.54mm_Vertical`. Netlist: D10 pin 1 = HV_K (to R50/C50), pin 3 = TIA_IN (to U10.15), pin 2 CASE = GND.
- What I saw: the lab symbol's Source field says "outline KAPDA0136EC: pin 1 cathode, pin 2 case, pin 3 anode". The same drawing (docs/research/downloads/s12023.pdf page 4, view (1) "S12023-02/-05/-10/-10A", the schematic symbol under the bottom view) shows a diode symbol between terminals (3) on the left and (1) on the right. I rendered it at 900 dpi and measured the pixels: the vertical bar is on the LEFT (x=592) and the filled triangle widens toward the RIGHT (height grows from 8 px at x=598 to 64 px at x=646), so the triangle points at the bar on the left. In the standard symbol the bar is the cathode, so (3) = cathode and (1) = anode. This is also the same convention as the project's own FDS010 note (decision log 3: "pin 1 anode, pin 2 case, pin 3 cathode"), and the two packages share the 3-lead TO-18/TO-46 arrangement with the tab beside pin 1.
- Why it matters: with HV on pad 1 (really the anode) and TIA_IN on pad 3 (really the cathode) the APD is forward biased through R19 27k + R50 10k = 37k. Fault current is about (220 - 0.7 - 1.83) / 37k = 5.9 mA (arithmetic) into the OPA857 IN pin (abs max 10 mA, apd-selection.md line 99), about 0.94 W in R19 (1206) and 0.35 W in R50 (1206). The link would not work and parts would overheat at full bias. ERC cannot see this. The documented standing correction "cathode to positive bias, anode to TIA IN" is correct; the error, if any, is in the pin-to-pad assignment in the library.
- Fix: (1) Before anything else, diode-test a real S12023-10: meter on diode mode, red on lead 1 and black on lead 3 should read about 0.5 V if lead 1 is the anode (leads viewed per the drawing; tab beside lead 1). (2) If confirmed, swap in the lab library (PR to ~/Projects/kicad-lab-library) so pin 1 = A and pin 3 = K (or swap the nets at D10), then swap the two traces at D10 in the PCB (HV_K to pad 3, TIA_IN to pad 1) and re-check the HV keep-out. Update lab-library Source text, frontend.md and the generator spec. (3) Do not order boards until resolved. 
- Confidence: MED-HIGH on the drawing reading (pixel measurement, standard symbol convention); the diode test makes it certain. Label: UNRESOLVED until the part is tested.

---

## MAJOR

### M1. DAC_TH default is 0 V, giving a -16.3 mV comparator threshold offset whenever the ESP32/DAC is not programmed
- Location: Slicer R85 (DAC_TH to IN-, 100k), R84 1k, U62 MCP4728 channel B (Controller sheet, DAC_TH through 100R + 100n).
- What I saw: IN- = VCM_REF + (DAC_TH - VCM_REF) x 1k/101k (the sheet's own formula). MCP4728 factory EEPROM defaults are VREF = VDD, gain 1, DAC input code 0 for every channel (MCP4728 DS22187E Table 4-2, p.24; the device loads the EEPROM at power-on reset, section 4.1/4.2). So at power-up DAC_TH = 0 V and IN- sits (0 - 1.65) x 1/101 = -16.3 mV below VCM_REF (arithmetic, VERIFIED values from the datasheet table). Zero offset needs code 0x800. controller.md already lists "DAC_TH safe default direction" as UNRESOLVED.
- Why it matters: slicer.md and CLAUDE.md hard rule 1 say the module decodes with the ESP32 unprogrammed. Sensitivity estimate (PROPOSED, hand-derived, not simulated): link-budget.md Table 7 gives about 26 nA rms at 6 pF/135 MHz for the 20k mode, so roughly 13 nA rms at the 35 MHz budget bandwidth; Q = 6 needs I_pp about 2 x 6 x 13 nA = 160 nA, i.e. 160 nA x 18.2k x 7 = 20 mV peak-to-peak at SDET_P (+-10 mV about baseline); with the 68 MHz low-pass actually in the chain the noise is larger (see Q2). A fixed -16.3 mV threshold shift is of the same size as the half-amplitude, and it is on the light-on side (SDET_P goes below baseline for a one), so ones would be lost first and the duty cycle distorted well before that. Add the TLV3605 VIO of +-5 mV max (TLV3605 p.7 EC table) and 3.0 mV hysteresis.
- Fix (PROPOSED, pick one): (a) program MCP4728 channel B EEPROM to 0x800 once at production through the SDA/SCL test pads TP64/TP65 (needs no firmware; the factory-default risk then only applies to an unprogrammed DAC); (b) add a DNP-able 0R series element so R85 can instead be fed from VCM_REF (true no-ESP32 fallback); (c) accept it and state in the docs that the unprogrammed-ESP32 case needs signal well above sensitivity. Also check the DAC_HV channel default the same way (controller.md already flags it).
- Confidence: HIGH on the default and the 16.3 mV; MED on the sensitivity impact (depends on noise at 6 pF, not measured).

---

## MINOR

### m1. OPA855 gain sits at the datasheet minimum stable gain; 1 % parts can put it below 7
- Location: U11 R53 301, R54 49.9.
- Saw: G = 1 + 301/49.9 = 7.03. OPA855 minimum stable gain is 7 V/V (SBOS622D p.3 Device Comparison Table; GBW 8 GHz). With 1 % resistors (the value strings carry no tolerance) the range is about 6.91 to 7.15. The ngspice run in the repo (Sim 1, Rev A macromodel, no parasitics or tolerances) shows 77 deg PM at 7.03 and 6.1 dB peaking at gain 5, so the real margin at 6.9 is probably fine but is not demonstrated.
- Fix: specify 0.1 % for R53/R54, or move to about 7.6 (R54 45.3 with R53 301, G = 7.64, which also adds clip headroom of about 8 %). PROPOSED. Confidence MED.

### m2. 3V3 rail window versus the OPA855 minimum supply
- Location: Power U1 (TPS79901, R1 17.8k / R2 10.0k), consumed by U11, U10, U20, U30.
- Saw: Vout = VFB x (1 + 17.8/10) with VFB 1.169/1.193/1.217 V (TPS799 SBVS056L p.5) = 3.25 / 3.316 / 3.383 V before resistor tolerance (arithmetic). OPA855 recommended supply minimum is 3.3 V (SBOS622D 6.3, p.5; its VOL/VOH numbers in the table are quoted at 3.3 V). OPA857 allows 2.7 to 3.6 V (SBOS630D p.5). So the low end of the rail window is up to about 80 mV below the OPA855 minimum. The window that satisfies both parts is 3.3 to 3.6 V.
- Fix: retarget the divider near 3.45 V (e.g. R1 = 19.1k gives 3.43 V typ, 3.37 to 3.50 V before resistor tolerance), checking TLV3605 (2.4 to 5.5 V) and OPA320 (to 5.5 V) are happy and that VCM_REF = 3V3/2 then moves to 1.72 V (still inside the OPA855 CM range 1.3 to 2.7 V, p.6). Power-sheet owner should decide; I only flag it. Confidence MED.

### m3. TIA_CTRL is a direct GPIO tie with a three-pad jumper on the same net
- Location: JP10 (A = GND, B = 3V3, C = CTRL), R57 100k pull-up, ESP32 U60.26 (IO20), netlist `/TIA_CTRL`: JP10.2, R57.2, U10.2, U60.26.
- Saw: no series resistor between GPIO20 and CTRL. If a user bridges A-C (force 5k) while firmware drives IO20 high, the pin sources into a short; B-C while firmware drives low does the same toward 3V3. The default is correct: R57 pulls CTRL to 3V3 = 20k mode with the ESP32 unprogrammed (OPA857 pin table p.4; VIH 2 V, VIL 0.8 V, bias current <= 1 uA, p.7, so 100k gives 0.1 V drop at worst, VERIFIED arithmetic).
- Fix: 1k to 4.7k series resistor between the hierarchical TIA_CTRL pin and the CTRL net (JP10 and R57 stay on the CTRL side). PROPOSED. Confidence HIGH.

### m4. Missing 10 nF HF bypass shown in the OPA857 layout example
- Location: U10 supply (C56, C57 100n 0402, C59 1u 0603 on three +VS pins).
- Saw: OPA857 Fig. 48 / section 10.2 (p.24) shows a 10 nF and a 100 nF "as close as possible to +VS and GND", under 0.25 in.; section 9 (p.23) says "use a linear supply with good PSRR". The design has 2 x 100n + 1u. Probably adequate; the single-ended use of OUT (OUTN goes only to TP12) gives up the differential cancellation of supply noise that the datasheet describes for its reference chain (7.3.2), and the datasheet PSRR at 10 MHz is only 15 to 18 dB (p.7). The rail is a plain TPS79901 off the +5V that also feeds the LT8365 stage; there is no bead or RC for the TIA. UNRESOLVED whether supply ripple matters at the TIA output; derive from G1 measurement.
- Fix: footprint for a 10 nF 0402 beside C56 (cheap), and consider a DNP bead footprint in the TIA 3V3 branch. PROPOSED. Confidence LOW-MED.

### m5. Noise bandwidth in the chain is wider than the link budget assumed
- Location: R56/C54 low-pass 68 MHz (R56 49.9 x C54 47 pF = 67.9 MHz, VERIFIED arithmetic) after a TIA of about 54 to 105 MHz.
- Saw: link-budget.md uses B = 35 MHz (0.7 x bit rate) for noise. No 35 MHz filter exists in the chain; the 68 MHz low-pass was chosen for ISI. sqrt(68/35) = 1.39, so rms noise is up to about 1.4x (about 1.5 dB optical) worse than the budget for the same eye, before TIA peaking (the repo's Sim 2 shows 0.97 dB peaking at 54 MHz at 6 pF in 20k mode). The budget shortfall is already 17 to 25 dB for FDS010 without APD gain, so the APD gain M and filter are what matter more; but the 35 MHz assumption should be reconciled.
- Fix: either re-run link-budget with B = 60 to 68 MHz or evaluate a lower corner (C54 about 82p gives 39 MHz) against ISI at G1 (the footprint is already there). PROPOSED. Confidence MED.

### m6. Capacitor and resistor dielectric, voltage and tolerance live only in docs
- Location: all passives; symbols carry values like "10n", "47p", "100p", "100n" with `Validated: No`, no dielectric/voltage/tolerance fields (only C102 says "1n C0G").
- Why: C50 must be C0G/film >= 400 V per apd-bias-design.md line 85, R50 1206 needs >= 200 V rating, C54/C87 must be C0G, R53/R54/R59/R84 matched (the 1k IB-cancelling pair), R87 sets the hysteresis. The BOM needs these fields or the wrong dielectric is the likely failure. Fix: add Dielectric/Voltage/Tolerance fields in the schematic before the BOM export. Confidence HIGH (process point).

### m7. LE/HYS (U20.8) left floating
- Saw: pin open, R82 150k to GND and R83 0R/R205 0R are DNP. TLV3605 p.14 7.1.3: the output latches when the LE/HYS pin is below 800 mV above VEE; p.7 EC table: floating gives 0 mV internal hysteresis, so the pin has an internal pull to the high state (not stated explicitly in the text I read). Floating pin sits within a few mm of OUT+/OUT- and the R87 tap.
- Fix: keep the net short and away from OUT+ and the hysteresis tap; if G1 shows spurious latching, fit a high-value pull-up option. Confidence LOW.

---

## QUESTIONS / UNRESOLVED

Q1. Default TIA gain is 20k with the ESP32 unprogrammed. The repo's Sim 2 (TI OPA857 v1.0 behavioural model, not validated at 6 pF) shows 13.8 % overshoot on a 5-UI run and 12.6 ns settling to 2 % in 20k mode at 6 pF, versus clean 5k behaviour, and the clip level at 20k is only about 9 uA pp (derived). Is the sensitivity-first default what you want when no firmware is running? (Does not contradict a decision; decision 12 puts the trim in firmware.)

Q2. Post-amp input excursions at strong signal: at 20k with 9 uA pp or more the OPA855 IN+ swings below its CM range (VIL 1.1 to 1.3 V typ/max at 3.3 V, p.6) because TIA output swings down up to 1.2 V. The datasheet shows input clamps (line 1272 mentions them) but I found no statement about phase reversal or recovery for CM overrange; the repo sim does not model this and itself says clipping/recovery is UNRESOLVED. G1 clip test should include recovery after a CM-range excursion, not only output clipping.

Q3. RSSI semantics (Monitor): D30 (cathode TIA_TAP, anode RSSI_HOLD) is a negative-peak detector, VERIFIED polarity against the TIA output swinging DOWN (OPA857 p.19) and BAS70 single SOT-23 pin 1 anode / pin 3 cathode (standard; not read from a BAS70 datasheet here). Attack time constant is about R58 x C102 = 1k x 1 nF = 1 us, release 1 ms (R103 1M, derived). The equilibrium level is about L + Vf (a few mV above, hand-derived) so it does capture the light-on (low) level, and it includes ambient DC photocurrent (DC-coupled TIA tap). It cannot separate ambient from modulated signal; the dark reference must be taken by the ESP32 with the emitter off. The docs already call it relative. Fine as is; flagging only so the firmware loop is not designed around it as an amplitude meter.

Q4. TIA_TAP loading of the fast path: R58 1k plus D30 (reverse-biased BAS70, about 2 pF at 0 V, typical Schottky value, not looked up) is a 1k stub on the OPA857 OUT pin; at AC the OPA857 sees R51 1k (via the 100n) as load, within the 500 ohm to 1 kohm range the datasheet characterises (p.6, p.19). I judge it harmless; not simulated (repo sim says the tap is not modelled).

Q5. Polarity and 8b/10b (checked, no defect, for the record): light on lowers OUT (OPA857 p.19) -> non-inverting OPA855 -> SDET_P below baseline -> U20 IN+ below IN- -> OUT+ low -> LVDS_P low -> U50 A (non-inverting buffer, inputs A/B pins 6/7) -> 1Y/1Z -> J50 B3/B2 and 2Y/2Z -> A3/A2; J50 is wired N to SSTXp and P to SSTXn on both pairs (connector.md hand edit), so SSTXp = high for a one on the cable. Net effect: one inversion overall (cathode-on-positive polarity) plus the flip at J50; whether the ECP5 breakout inverts again is the gateware constant in firmware/ecp5 (I did not read it). For 8b/10b this is not a link-layer problem: an inverted stream is still a valid comma with opposite disparity, but decoding fails unless inverted; a polarity bit in the gateware (or auto-detect on K28.5 vs its complement) removes the question. Recommend the FPGA side keep a polarity-select register rather than a compile-time constant. PROPOSED.

---

## What I checked and found correct

Pin maps (exact, from netlist.xml, against datasheet pin tables):
- U10 OPA857 RGT-16: IN 15 = TIA_IN, OUT 8 -> C51/R58, OUTN 5 -> TP12 only, CTRL 2 = TIA_CTRL net, VS+ 9/10/11 = 3V3, GND 1/3/4/6/7/12/13 and PAD 17, Test_IN 14 = 3V3, Test_SD 13 = GND, NC 16 open (OPA857 SBOS630D p.4 pin table).
- U11 OPA855 DSG-8: FB 1 -> R53 -> IN- 3, NC 2 open, IN+ 4 = PA_IN, VS- 5 GND, OUT 6, VS+ 7 = 3V3, PD 8 = 3V3 (PD enable <= 1.8 V, bias 70/140 uA, SBOS622D p.7 so no series R is right), EP 9 GND (SBOS622D p.3).
- U20 TLV3605 RVK-12: OUT+ 12 = LVDS_P, OUT- 10 = LVDS_N, IN+ 4 = SDET_P, IN- 6 = SDET_N node, SHDN 7, LE/HYS 8, VCCI 2, VCCO 1 via R80, VEE 3/5/9/11 and EP 13 GND (TLV3605 Table 4-1 p.3-4).
- U30 OPA2320 SOIC-8: 1 out / 2 - / 3 + (A), 5 + / 6 - / 7 out (B), 8 V+, 4 V-.

DC bias paths, no floating inputs: OPA855 IN+ returns to VCM_REF through R51 1k (IB -12 uA typ gives about +12 mV, derived), IN- through R53 || R54; TLV3605 IN+ via R59 1k and IN- via R84 1k to VCM_REF (IB -1 uA typ, matched pair, IOS +-1 uA gives +-1 mV); the OPA2320 B buffer is a unity follower with R103 pull-up on the hold node.

Coupling corners vs 8b/10b (50 Mbps, UI 20 ns, max run 5 = 100 ns): C51 100n x R51 1k and C55 100n x R59 1k = 100 us, 1.6 kHz each (arithmetic); droop across a 100 ns run is about 0.1 % per stage. Baseline wander is therefore negligible for DC-balanced 8b/10b; the corner is not too high. (The corner is low enough that recovery from a large overload takes about 4 x 100 us, which is a robustness point for G3, not a design error.)

OPA855 gain network, PA_REF/R60/C53 arrangement: at AC R54 is grounded directly by C53 (R60 only isolates from VCM_REF), so AC gain is 1 + 301/49.9 = 7.03 as documented; DC gain is 6.03 (R60 in series) and only affects offset. FB/OUT separation per SBOS622D p.17.

Comparator network: hysteresis window 350 mV x 47.5/(5490 + 47.5) = 3.0 mV (arithmetic from TLV3605 VOD 350 mV p.7; positive feedback sign is correct because OUT+ is in phase with IN+ per Table 4-1; C87 blocks the -69 mV static shift as stated). Trim authority +-16.3 mV, 8 uV/LSB (arithmetic). SHDN: R81 10k pull-up to 3V3 means enabled with the ESP32 unprogrammed (VIH 1.5 V, IIL 30 uA max p.7; IO1 is not a strapping pin per MINI-1 note quoted in controller.md); VCCI/VCCO 2.4 to 5.5 V OK.

VCM_REF: R100/R101 10k/10k from 3V3 = about 1.658 V, C100 100n filter (corner 318 Hz), R102 10 ohm + C101 1u after the feedback tap, loads are 3 x 1k returns plus R60 (all microamp DC); sim claims (87.6 deg PM, one channel, ideal) are in the repo only and I did not re-run them; datasheet cap-load statement (OPA320 about 1 nF direct, resistor for more) is as cited in control.md.

APD/HV side of the schematic: R19 27k + R50 10k limit steady fault current to about 5.9 mA at 220 V (arithmetic, below the OPA857 IN 10 mA abs max), C50 sits at the cathode with no series R after it (correct, per apd-bias-design.md line 85); anode to IN, cathode to bias is the OPA857 reference arrangement (p.19). Layout: D10 at (9.0, 25.0), R50 (8.5, 15.6), C50 (8.5, 19.1) put the HV stage upstream of the APD and the TIA_IN trace is 3.9 mm on F.Cu (from the board file). HV keep-out and TIA_IN window were not evaluated here.

Footprints vs values: RGT0016A, DSG0008A, RVK0012A, SOIC-8, SOT-23, TO-18 footprint for the S12023 (package confirmed TO-18 in the Hamamatsu table), 1206/1210 on the HV parts, 0603 on the signal path, consistent with the specs; C54/C51/C55/R-values are plausible for those sizes.

Not checked: PCB routing, HV creepage, the FPGA-end polarity constant, ECP5/ULX3S behaviour, the LT8365 stage, the ESP32 firmware, anything that needs measurement.
