# Rev A design review, 2026-10-22 (schematic, PCB, approach)

Consolidated by Claude Fable from six independent Sonnet reviews (three schematic, two PCB, one approach),
run after routing was completed (commit 34168c3, 0 unconnected pads, ERC 0/0, 52 DRC items). The six
detailed reports are in this folder; the DRC report they used is `drc-2026-10-22.rpt`. Nothing in this
review was measured or simulated; every number is from a datasheet, the netlist, the board file, or
hand arithmetic, and is labelled VERIFIED (checked against the cited source), PROPOSED or UNRESOLVED.
"Orchestrator-verified" means Fable re-checked the reviewer's claim directly against the source.

Coordinates in the PCB items are board coordinates (mm from the top-left corner, back edge y = 0), i.e.
the KiCad file coordinates minus (50, 50).

## Verdict

Do not order Rev A yet. One BLOCKER (the APD symbol has the cathode and anode on the wrong pins) must be
fixed on the schematic, the lab library and the board. Beyond that the design is coherent and the layout is
clean in the places that matter most (fast chain all on F.Cu with no vias, solid GND1 under every fast and
HV net, live HV clearance rules at their floors). The MAJOR items below are each a day or less of work; the
approach-level items (link budget, "decodes unprogrammed" wording, missing link interface spec) do not block
the board but should be settled before the headstage emitter is frozen.

## BLOCKER

### B1. S12023-10 symbol pin mapping is reversed: the APD is forward-biased by the HV rail (orchestrator-verified)

- Where: Front End D10, lab-library symbol `AharoniLab_Passive:S12023-10` (pin 1 = K, pin 3 = A, pin 2 = CASE);
  netlist: D10 pin 1 = `/Front End/HV_K`, pin 3 = `/Front End/TIA_IN`, pin 2 = GND.
- Evidence: Hamamatsu KAPD1007E19 p.4, outline (1) "S12023-02/-05/-10/-10A", drawing KAPDA0136EC. The pin diagram
  (rendered at 1200 dpi, `s12023-outline1-pin-diagram-1200dpi.png` in this folder) shows terminal 3 on the
  bar side of the diode symbol and the triangle pointing from 1 toward 3: **pin 1 = anode, pin 3 = cathode**.
  The symbol's own Source property says the opposite ("pin 1 cathode, pin 3 anode") and cites the same page.
  The FDS010 note in decision-log entry 3 (pin 1 anode, pin 2 case, pin 3 cathode) uses the same convention.
  VERIFIED (datasheet drawing + netlist + symbol file).
- Consequence: with HV on physical pin 1 (anode) and the TIA on pin 3 (cathode) the APD conducts forward
  through R19 27k + R50 10k: about 5.9 mA at 220 V into the OPA857 IN pin (abs max 10 mA) and about 0.9 W in
  R19. No signal, overheated parts. ERC and DRC cannot see it.
- Fix (PROPOSED):
  1. Diode-test one real S12023-10 (tab beside lead 1) to make the drawing reading certain before editing.
  2. Lab-library PR: swap the pin names in the symbol (pin 1 = A, pin 3 = K), fix the Source text; apply the
     identical edit to the embedded `lib_symbols` copy in `frontend.kicad_sch` (generators are frozen).
  3. Board: rotate D10 by 180 degrees about the can axis (10.27, 25.0) so the anode pad stays at the right-hand
     position next to U10 and the cathode pad at the left-hand position; the existing HV_K and TIA_IN track
     ends then land on the correct pads after the netlist update, and the TIA_IN_WINDOW stays valid. Re-run DRC
     and re-check the HV clearances (item P1 below still applies).
  4. Update docs/schematic/frontend.md, rev-a-sheet-specs.md, the PCB README ("can sits 1.3 mm right of pin 1")
     and the receiver guide in the same commit.

## MAJOR

### Schematic

- **S1. R7 (20 ohm) is in series with D1, not in the pump-charge branch (orchestrator-verified).** LT8365 Rev. A p.30
  and the DC2838A REV02 schematic both put the 20 ohm in series with the pump diode (V1 to D3); here it carries
  the full stage-1 inductor current, costing about 7 V of SW-pin margin to the 150 V abs max and leaving the
  pump branch undamped. apd-bias-design.md 3.2 itself says "Pump R (R8) 20 ohm as DC2838A R10", so this is a
  wiring slip. Fix: D1 cathode straight to HV_V1, R7 between HV_V1 and the D3 anode. One trace on the board.
  [power-connector M1]
- **S2. Production bias range is about 106 to 167 V, not 100 to 220 V (orchestrator-verified arithmetic).** RV1 and R15
  are DNP, so only the DAC leg (R13 10k + R14 442k) trims: Vout = 1.6(1 + 8.2M/96.6k) + (1.6 - Vdac) 8.2M/452k gives
  166.5 V at 0 V and 106.6 V at 3.3 V (25 C). The "215 V hardware maximum" in the docs needs the pot leg fitted. A
  unit with VBR near 200 V cannot be biased. Decide the range requirement against the VBR bins, then either fit
  R15 plus a fixed divider or lower R14 and re-centre Rb, and re-run tools/apd_bias_design.py. [power-connector M2]
- **S3. MCP4728 powers up at 0 V on every channel, which is the maximum-bias end (orchestrator-verified).** DS22187E
  Table 4-2 p.24: factory EEPROM is code 0, internal 2.048 V ref, normal mode, so DAC_HV = 0 V and DAC_TH = 0 V
  at power-up. apd-bias-design.md line 82 ("DAC pin Hi-Z at reset -> 135.9 V") is wrong for this part: a blank
  DAC gives about 167 V (pot DNP) or 215 V (pot fitted). The firmware already provisions the EEPROM before
  releasing HV_DIS, but J1 "HV FORCE ON" with a blank DAC, or a DAC brown-out while HV is on, bypasses that.
  DAC_TH = 0 V also puts the comparator threshold about 16 mV below the baseline, about the half-amplitude at
  the Q = 6 sensitivity point. Fix: make EEPROM provisioning (C = 0xFFF, B = 0x800) a mandatory first-article
  step in gates.md; correct the two docs; consider a DNP-able 0R in the DAC leg so a no-firmware bench build can
  use the pot leg alone; firmware should treat the MCP4728 POR bit as a fault. [controller M1, frontend M1]
- **S4. "Decodes with the ESP32 unprogrammed" is not true as built.** R33 pulls HV_DIS up (HV off, correct safety
  choice) and J1 is DNP, so an unprogrammed module has no APD bias. Either reword hard rule 1 / decision 12 /
  architecture.md ("slicing is analog; APD bias needs a provisioned ESP32 or J1 plus the pot leg") or implement
  S3's pot-leg option and fit J1 on first-article boards, and add a G1 item that proves the analog-only mode.
  Daniel's call. [controller M2, approach A4]
- **S5. 4.99 M 0603 resistors see 110 V each (R17, R18, R20, R32), and the Q1 clamp is base-starved.** Typical 0603
  thick-film working voltage is 75 V (no MPN on the schematic; UNRESOLVED until an MPN is chosen). Q1's base is
  fed only through 10 M, so the APD bias drops by Ic x 10 M / hFE (about 1 V per 10 uA at hFE 100), which the
  calc doc's "about 1.2 V clamp" ignores; at 7 %/V of gain that is several percent of M per few uA of mean
  photocurrent. Fix: HV-rated 0805/1206 or series parts with a cited rating; rethink the base feed (lower total
  resistance, or a FET pass device), and add a G1 sweep that measures bias at the APD side vs injected current.
  [power-connector M3]
- **S6. No hardware over-voltage limit on the HV chain.** One open resistor in the 8.2 M FBX ladder lets the converter
  run past the 150 V SW/diode ratings; only firmware polling HV_MON protects, and not at all with J1 fitted.
  Cheap option: a Zener string from HV_OUT to FBX. Layout change, so decide before the order. [power-connector M4]

### PCB

- **P1. D10 pad geometry: HV pad 0.35 mm from the case (GND) pad and 1.34 mm from the TIA_IN pad; hidden by the
  same-footprint DRC exception.** Below the project's own 0.4 mm coated and 2 mm HV-to-TIA-input figures, and a
  surface-leakage path into the TIA input. Fix (lab-library footprint PR): 1.0 mm round pads 1 and 2 (0.80 mm and
  1.54 mm gaps), keep the mask web, conformal-coat the HV end, record the waiver in the .kicad_dru. [fastpath M1]
- **P2. C50 is 6.8 mm of trace from the cathode pin (rule says <= 3 mm), and 1.65 mm of the 220 V HV_K trace runs
  under the grounded can flange with only solder mask between.** Move C50 next to the cathode pad and keep HV_K
  copper outside the 2.7 mm flange radius or specify an insulating spacer; this moves anyway with B1. [fastpath M2]
- **P3. OPA855 has no plane window under IN-, FB and OUT (SBOS622D 9.4.1, Fig. 9-12), the feedback parts sit 2.5 to
  4.5 mm from the pins, and TP10 hangs a 2.5 mm stub plus a 1 mm pad on OUT ahead of R56.** Hand estimate: 0.3 to
  0.5 pF on IN- and OUT, maybe 10 to 15 degrees of the 77 degrees simulated phase margin (not simulated). Fix:
  small no-fill rule area under pins 1-4 and 6, R53/R54 within 1.5 mm, TP10 moved behind R56; re-run the OPA855
  stability sim with 0.5 pF added. [fastpath M3]
- **P4. Net-(Q1-B) (clamp base, within about 1 V of APD_BIAS) has 3 vias and 10.1 mm on In2**, contradicting the
  README "no HV-class net has a via". Re-route on F.Cu (room along y 3.4 to 5.8) or record the exception.
  [fastpath M4]
- **P5. LT8365 boost loop return: C5's GND reaches the plane through one via on a 0.15 mm neck about 16 mm from U3,
  and the U3 exposed pad has only 2 vias.** Add 2-3 vias at C5, widen the neck, 4-6 vias in the U3 pad, consider
  moving C5 closer to D1. This is the ripple/EMI path to the 10 uV cathode target. [fastpath M5]
- **P6. Via-in-pad on 155 of 209 vias (ESP32 thermal pad, every EP, 12 0402 caps, most 0603 GND pads) with no
  fill/cap specified anywhere.** "Vias tented" cannot apply inside a pad. Either specify epoxy-filled-and-capped
  for all vias at order time (confirm JLCPCB accepts 0.25/0.45 with it, and the price) or move the cap and
  signal vias 0.6 to 0.8 mm off the pads; a 0.45 mm via leaves almost no solderable area on a 0402 pad even
  when filled. Add to the G4 pre-order checklist. [pi-dfm M1]
- **P7. J50 shell posts have no GND vias and thermal-relief connections (4 of the 5 starved_thermal items)**, against
  decision 16 ("several vias each"). Set the 8 S1 pads to solid connection and add 2-3 GND vias beside each large
  post, outside the B-row antipad. [pi-dfm M2]
- **P8. Ground returns far from vias: U50 SN65LVDS104 GND pins 3.0 and 4.7 mm from the nearest GND via, its caps
  C184/C185 3.0 to 3.2 mm, U51 pin 5 2.3 mm, U4 output caps 4.5 to 5.2 mm.** Add one via at each. [pi-dfm M3]

### Approach

- **A1. The link budget's APD sweep has an energy error and assumes a 35 MHz noise bandwidth the chain does not have.**
  "30 mW/sr over 140 degrees from 25 mW average" implies 229 % wall-plug efficiency (the 0.9 mW/sr/mA figure is a
  +-45 degree part). Independent redo: Q = 6 at 35 cm lateral needs about 6 to 12 mW/sr, roughly 40 to 180 mW
  average electrical per emitter against the ~200 mW headstage budget, with the Q-optimal M at 86 to 114 (the
  S12023-10 M max is 100), not 35 to 60. The built noise bandwidth is about 70 MHz (OPA857 ~100 MHz, 68 MHz
  low-pass), about 1.5 dB optical worse than the budget. "Modestly brighter emitter" (decision 8) is overstated.
  Decision 8 itself (APD) still stands. [approach A1, A2; frontend m5]
- **A2. Range figures are electrical dB.** "39 dB single-setting + 32 dB firmware" is about 16 to 25 dB and 16 dB in
  optical power, and every firmware knob lowers gain: the weak-light end has no remedy, so fade margin equals
  emitter margin. Restate in optical dB with an explicit weak-end margin row. [approach A3]
- **A3. No headstage-to-receiver interface specification.** Two 100 us AC couplings require continuous idle with no
  dark gaps; LED rise times of 11 to 14 ns and the 4x blind-oversampling CDR (+-0.125 UI) are not budgeted; no
  jitter or eye budget exists. Write one interface page and reference it from requirements.md. [approach A5]
- **A4. Biggest uncertainty is the optical power actually delivered to the APD; it needs no Rev A board to measure.**
  Candidate emitter at the real geometry through the real filter onto a calibrated photodiode or the APD at
  M = 1, DC or lock-in photocurrent, plus an ambient reading with the emitter off. Do it before freezing the
  emitter. [approach, "single biggest uncertainty"]

## MINOR (condensed; details and page citations in the reports)

Schematic: OPA855 gain 7.03 at the minimum stable gain of 7 with 1 % parts (use 0.1 % or ~7.6); 3V3 rail window
3.25 to 3.38 V dips below the OPA855 3.3 V minimum (retarget ~3.45 V); TIA_CTRL is a bare GPIO tie with a
solder jumper on the net (add 1 to 4.7k); OPA857 10 nF HF bypass from the datasheet layout example absent;
dielectric/voltage/tolerance fields missing from all passives (C50 >= 400 V C0G, R50 200 V, C54/C87 C0G);
TLV3605 LE/HYS floating; C200 has both pins on GND (orchestrator-verified; ADC_AIN3 has only R209 and U63.7);
TPS7A2033 300 mA vs the ESP32-C6 0.5 A supply requirement (radio must stay off, enforce in firmware config);
R199 100k at the SN65HVD230 Rs maximum (use 82 to 91k); RS has no GPIO so "RS high standby" in the docs is not
available; VBUS has no TVS ahead of the eFuse; R33 pulls HV_DIS up to 3V3_D, so the gate floats if that rail is
absent (pull up to +5V instead); HV_MON loads the ADS1115 by ~1.7 % (calibratable); D2 (DNP) is the SW-to-GND
clamp of the p.30 reference, fit it for the first bench build; eFuse FLT not routed to the ESP32 (documented).

PCB: TIA_IN_WINDOW is L-shaped and leaves inner planes 0.13 mm from the IN pad under pins 13/14 (make it a
rectangle); SYNC pin has a 7.9 mm stub to DNP parts 0.7 mm from the SW pad (cut back); D2 DNP branch hangs 3.1 mm
of SW copper; the 51 mm NTC/FBX node on In2 runs 7.1 mm within 0.6 mm of SDA/SCL; TH1 has no thermal link to the
can (1 mm F.Cu strip to the case pad, or move TH1 within 3 mm of the flange); swap R87/C87 positions so the
hysteresis resistor sits at U20 pin 12; the 4 LVDS_P/N diff-gap items and the 11.7 mm uncoupled item are R180 pad
jogs and the R87 stub, not a routing fault (accept or relax the diff100 rule; through-path skew 0.24 mm, R180 is
correctly at the load end); EN net is ~50 mm long (move C190 to U60 pin 8); VBUS and +5V trunks each pass through
a single via with 0.15 mm necks (add a second via, widen); GND stitching absent on the left edge and sparse
(8 to 19 mm gaps) in four regions; USB_DN changes layer alone without a return via (harmless at 12 Mbps); no
fiducials, no panel plan, J50 overhang and the ESP32 0.25 mm from the edge constrain process rails; J50 shell
slots 0.2 mm vs the 0.35 mm plated-slot minimum (confirm at upload); mounting-hole via rings 0.35 mm wall-to-wall
(move to r = 1.8 mm or use the `_Pad` variant, clears all 32 hole_to_hole items); duplicate GND via at
(52.65, 11.7); dangling vias on VCM_REF and TIA_CTRL and a 0.05 mm EN nub (delete); no test points for VBUS or
+5V; no silkscreen text at all (no HV warning, no TP names, no K/A mark at D10); ESP32 antenna keep-out matches
Espressif Fig. 25 margins but the module is mid-edge (radio unused; README fix). Optical window: a filter holder
over about 8.6 mm OD collides with C50 (moving C50 for P2 helps).

Docs: CLAUDE.md, the PCB README, architecture.md and receiver-guide.html still say "nothing routed";
requirements.md still calls the 3.3 V-bank LVDS input UNVERIFIED (decision 3 says VERIFIED); decision 9's
"external HV module pads" are not in the netlist; architecture.md "Q(M) peaks at M 35-60"; module-controller.md
line 69 has the old HV_EN polarity; firmware/esp32 README quotes the trimmer-fitted DAC span.

## DRC disposition (52 items)

| Item class (count) | Disposition |
|---|---|
| hole_to_hole (32), H1-H4 via rings 0.35 mm | fix: ring radius 1.8 mm or the `_Pad` footprint |
| starved_thermal (5): 4 J50 shell pads, U20 pad 9 | fix: solid connection + vias (P7); U20.9 solid + adjacent via |
| diff_pair_gap (4) and diff_pair_uncoupled (1) on LVDS_P/N | accept with an exclusion, or relax the diff100 rule; not a routing fault |
| via_dangling (2) VCM_REF, TIA_CTRL; track_dangling (1) EN; holes_co_located (1) | fix: delete the stubs and the duplicate via |
| silk_edge_clearance (5), silk_overlap (1) | accept (J50 silk is on the overhang; U60/U51 outlines cosmetic) |

## Verified correct (coverage, so the reader knows what was checked)

Pin maps against datasheet pin tables for U3, U5, U1, U4, Q1-Q3, U50, U51/U52, J50 (A/B rows, CC Rd 5.1k on
both, D+/D- both rows, SBU tied, LVDS N/P flip consistent on both TX pairs), U10, U11, U20, U30, U60 (all 31
signal pads vs MINI-1 Table 3-1), U61, U62, U63, U64; strapping and boot (GPIO8/9, EN RC), native USB on
GPIO12/13 with 22 ohm; I2C addresses 0x60/0x48; HV_DIS polarity gives HV off for high, Hi-Z or unprogrammed;
TIA_CTRL defaults to 20k; SHDN defaults enabled; eFuse ILIM/UVLO/OVLO/dVdt reproduce the documented numbers;
LT8365 EN/UVLO, RT, SS, VC, BIAS, INTVCC, doubler orientation and ratings; AC-coupling corners (1.6 kHz each, fine
for 8b/10b); hysteresis 3.0 mV with the correct sign; polarity chain (light on -> LVDS_P low -> SSTXp high; the
gateware auto-detects polarity); fast chain ~20 mm on F.Cu with zero signal vias; TIA_IN 3.91 mm inside a window
that is empty on all six layers; HV rules live and every HV clearance at or above 1.0 mm (1.25 mm pads, 1.0 mm
edge lane); GND1/GND2 solid under every HV and fast net; no tracks on In1/In3/In4; all three rail pours
connected; LVDS_OUT1/OUT2 on F.Cu with no vias, skew 1.20/0.06 mm; USB end to end balanced to 0.4 mm; both CAN
branches 24 to 25 mm; decoupling within datasheet distances for U10/U11/U20; stackup in the file matches the
README; via 0.45/0.25 everywhere; courtyards clean; nothing under the J50 overhang.

## Recommended order of work before ordering

1. B1: diode-test a real APD, fix the library symbol, rotate D10, re-import, re-run DRC.
2. S1 (R7 branch), P1/P2 (APD pads, C50 placement), P3 (OPA855 window, TP10, feedback parts), P4, P5.
3. Decide S2 (range) and S6 (OVP); both change the board if adopted. Decide S5's base feed.
4. S3 provisioning step and doc corrections; S4 wording or pot-leg option (Daniel's decision).
5. PCB cleanups: P6 via fill decision, P7, P8, mounting-hole rings, stubs/duplicate via, stitching, silk text,
   VBUS/+5V test points, fiducials question to JLCPCB.
6. G4 pre-order: JLCPCB impedance calculator run, DFM on the final board, DRC dispositioned in writing.
7. In parallel and independent of the board: A4 photocurrent measurement; A1-A3 doc corrections; the link
   interface page; the FPGA-end USB-C breakout and an optical test source for G1.
