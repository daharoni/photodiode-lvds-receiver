# receiver-module (KiCad 10 project, Rev A schematic)

Photodiode LVDS Receiver, Rev A0, Aharoni Lab, UCLA.

**Nothing in this project is fabrication-approved.** The six hierarchical sheets are populated
with lab-library parts, values and footprints per `docs/schematic/rev-a-sheet-specs.md`; project ERC on the root
reports 0 errors and 0 warnings (kicad-cli 10.0.5, 2026-10-09, revision 4 after decision 14). The netlist had 223 components on that date; since 2026-10-22 it has 221 (C181 and R170 removed, Connector 33 -> 31; Power 79, Controller 55, Connector 31 including mounting holes H1-H4 added 2026-10-09, Front End 26, Slicer 17, Monitor 13) on 144 nets. The PCB carries all 221 footprints (H1-H4 included), placed by the first-pass placement script; nothing is routed (see Board below). H1-H4 need lab-library PR #62 (branch `add-mounting-holes`, symbol and footprint `MountingHole_2.2mm_M2_Pad_Via`) merged or checked out so the symbol resolves. The S12023 pinout fix (lab-library PR #63) is merged into main. U6 (TLV431, decision 23) needs lab-library branch `add-tlv431` checked out or merged. Status labels used
in notes: VERIFIED / PROPOSED / UNRESOLVED.

## Generated sheets

**FROZEN since 2026-10-09 (PCB layout started).** The generators exit with status 2 while `gen/FROZEN` exists, because regeneration would rewrite the `.kicad_sch` files with new UUIDs and break the schematic-to-board link. Schematic changes now go through the KiCad GUI, with the spec and as-built docs updated by hand. To unfreeze, see `gen/FROZEN` (delete it deliberately, regenerate all sheets in order, re-import to the PCB, re-annotate/re-link footprints). The text below is historical until then.

Each sub-sheet and the root are produced by `gen/<sheet>.py` using the `tools/kicad_sch` package
(`cd tools && python3 gen/...` from the project root; see `tools/kicad_sch/README.md`). Regenerate in
the order power, frontend, slicer, control, connector, controller, root. Each sheet keeps its uuid, so
instance paths stay stable. KiCad's bundled `power:PWR_FLAG` / `power:GND` symbols are used alongside
the lab library. Reference designator ranges per sheet are listed in the spec document.

Validation: `kicad-cli sch erc` and `kicad-cli sch export netlist` on `receiver-module.kicad_sch`
(kicad-cli path in CLAUDE.md). Revision 4 (decision 14) needs lab-library PR #61 (branch `add-usbc-fanout-efuse-esd`: symbols `AharoniLab_Connector:632723300011`, `AharoniLab_Power:TPS259631DDAR`, `AharoniLab_Interface:SN65LVDS104PW`, `AharoniLab_Misc:TPD6E05U06` and their footprints) to be merged before this project is opened on another machine; the generators embed the library symbols, so regenerate after any library change. Revision 3 parts (AharoniLab_Switch / AharoniLab_Switch_SMD for SW60/SW61, lab-library PR #60) are still used: the global sym-lib-table and fp-lib-table must carry those rows.

## How to open

Open `receiver-module.kicad_pro` in KiCad 10. Symbol and footprint libraries come from the global
tables (the lab library is global via `${AHARONI_LAB_KICAD_LIB}`); this project has no
`sym-lib-table` or `fp-lib-table` on purpose. Project text variables: TITLE, REV, COMPANY.

## Sheets

| File | Purpose |
|---|---|
| `receiver-module.kicad_sch` | Root: hierarchical sheet symbols only, in signal-flow order |
| `power.kicad_sch` | VBUS in, TPS259631 eFuse U5 to the internal +5V rail; 3V3 and 3V3_D rails; LT8365 boost + doubler APD bias (HV_ nets, clamp, stage-1 RC filter) -> APD_BIAS, HV_MON divider, DAC_HV trim input, HV_DIS gate |
| `frontend.kicad_sch` | APD, OPA857 TIA with 20k/5k CTRL, AC coupling, OPA855 x7 post-amp, 68 MHz low-pass, AC coupling to SDET_P (TIA_TAP out, VCM_REF in) |
| `slicer.kicad_sch` | TLV3605 sliced at VCM_REF baseline with DAC_TH trim and ~3 mV hysteresis, LVDS out |
| `control.kicad_sch` | Monitor: OPA2320 VCM_REF 1.65 V buffer and BAS70 RSSI minimum detector from TIA_TAP |
| `connector.kicad_sch` | single 24-pin USB-C J50: VBUS out, USB_DP/USB_DN, CC1_SENSE/CC2_SENSE, AUX (SBU tie), LVDS fan-out U50 to both SuperSpeed TX pairs, CAN on both RX pairs (nets CAN_P/CAN_N (CANH/CANL; renamed from CAN_H/CAN_L 2026-10-16 so the KiCad diff-pair router pairs them)), ESD arrays U51/U52, scope header J51, test points |
| `controller.kicad_sch` | ESP32-C6-MINI-1, MCP4728 DAC, ADS1115 ADC, SN65HVD230 CAN, USBLC6 and 22R D+/D- (USB from the Connector sheet), RESET/BOOT switches, CC1_SENSE/CC2_SENSE inputs on IO4/IO5 |

`GND` is a global net (global label in every sub-sheet). Other power nets are sheet pins. Nets at or above 50 V are prefixed `HV_` and, with `APD_BIAS`, belong to net class `HV` (1.0 mm clearance).

## Board

`receiver-module.kicad_pcb`: 6-layer board (stackup below), 75 x 50 mm placeholder outline on Edge.Cuts, all 221 footprints placed by the first-pass placement script (was 223 before the shield RC removal, 2026-10-22) (below; layout in progress, nothing routed). Rules and fabrication settings follow `docs/pcb/jlcpcb-fab-settings.md` (research, PROPOSED values, nothing measured).

### First-pass placement (2026-10-09, PROPOSED)

`tools/pcb_place.py` (runs under KiCad's bundled Python, which has `pcbnew`) applies `placement/placement-spec.json`: board outline, per-block side and region, fixed anchor parts (ICs, connectors, APD, switches, mounting holes) and a `near` pad target for each passive. Passives are packed on a 0.25 mm grid at the nearest free spot to their target, with courtyard-plus-margin collision checks (0.15 mm, 0.65 mm for HV-class parts, 0.3 mm for HV_LADDER), through-hole parts blocking both sides, an ESP32 antenna keep-out, and region growth when a block is full. Blocks are packed in spec order. Result: 223 placed, 0 courtyard overlaps, 0 clearance violations (kicad-cli DRC); remaining DRC items are silk overlaps (reference labels not yet cleaned up), silk near the edge, and the 32 hole-to-hole hits from the via rings of the `MountingHole_2.2mm_M2_Pad_Via` footprints (0.35 mm between the via holes and the 2.2 mm hole, constraint 0.45 mm; swap H1-H4 to the `_Pad` variant without vias or accept it on the high-precision tier).

Run from this directory, with KiCad closed:

```
PYTHONPATH=../../../tools /Users/daharoni/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
  ../../../tools/pcb_place.py receiver-module.kicad_pcb placement/placement-spec.json --out receiver-module.kicad_pcb --report /tmp/report.json
```

It re-places EVERY footprint from the spec, so do not run it on a board with hand placement you want to keep. Floor plan (y down, optical end left): fast chain on the top centre line (D10 at x 9 mm, OPA857, OPA855, filter, TLV3605, SN65LVDS104, ESD arrays, J50 at the right edge with the mouth overhanging 0.95 mm); HV island along the back edge on top (HV_MON, HV_OUT, FB ladder, LT8365 boost, HV_DIS); J51 at the front left; status LED, test points and the RESET/BOOT switches at the front right. Bottom: ESP32-C6 with its antenna over the front edge (keep-out 41-57 x 44-50 mm, both sides), USB ESD and CAN transceiver under J50, CC dividers and eFuse under the connector end, 3V3/3V3_D regulators and DAC/ADC under the HV island, VCM_REF buffer and RSSI detector under the post-amp. The optical window must be centred on the APD can, which sits 1.27 mm from the D10 footprint origin (pad 1, the anode): to the left of it since the 180-degree rotation of 2026-10-22 (see below). The renders used for review are not committed; `kicad-cli pcb render --side top|bottom` regenerates them.

### Hand placement and HV island rearrangement (2026-10-13, PROPOSED)

Daniel re-placed most of the board by hand after the first pass (commit f10238c). The LT8365 island was then rearranged by script (`tools`-free pcbnew snippet, not kept) on the following plan; coordinates are mm from the board's top-left corner, back edge at y = 0. Nothing is routed and nothing was measured.

- U3 is at (48.3, 9.6), rotation 0, so pins 9-16 are on its right side: SW (14, 16) at the top-right corner, FBX (9) at the bottom-right. Power ground leaves the exposed pad at the EN/SW corners, signal ground at the VC/FBX corners (LT8365 Rev. A p.7 pin descriptions, Figure 5 p.16).
- Switching cell along the back edge, right of L1: L1 above U3 with its SW pad 2.4 mm above pin 16, D1 anode 0.6 mm from the L1 SW pad, then R7 and C5 in a row (C5 GND pad to be stitched to GND1 at the pad). C6 (pump) hangs on the same SW blob below D1; D3, D4, C7, R30 continue to the right; C25 sits under the R30 HV_OUT pad. HV_OUT leaves R30 at x 67.3 and is meant to run up to a 0.3 mm lane along the back edge at y about 1.2 (1.0 mm from the edge), then left to the clamp at R17/Q1. Every pad under that lane was placed with its top edge at y >= 2.5 so the 1.0/1.25 mm HV clearances hold.
- FBX island at pin 9: C22 (SS) and R24 (RT) in a column 1.8 mm right of pins 10/11; R8 (ladder end), R12 (bottom resistor) and C26 directly below-right of pin 9 (FBX pads 1.8 mm from the pin); R14 and R15 one column further; the ladder R9, R10, R11 runs right along y 13-15 to the HV_OUT pad of R11 at (63.2, 14.7), 4 mm below D4. R13/C27 (DAC leg) sit beside R14. SYNC parts R26/R27/TP2 (DNP) are in a row at y 17.9: route them only if fitted. C26 (10 pF, DNP in the schematic) is worth fitting as an FBX noise shunt: PROPOSED, not simulated.
- TH1 (NTC in the FBX bottom leg) moved to (10.0, 30.2) just below the APD can, per docs/calculations/apd-bias-design.md section 7 ("on APD can ground tab / thermal link"); its node is the low-impedance end of R12, so the 45 mm run is acceptable.
- LT8365 low-voltage passives in two columns left of U3 (x 40-45): R22/R23 (EN) at the top, C19/C20 at VIN, C21 at INTVCC, R28/R29 at BIAS, R25/C23/C24 at VC; L2 and C18 further left at y 9.9; RV1 at (31, 10.5). J1 moved to x 70.3 and Q3 to (70.5, 15.8) to clear the HV_OUT riser.
- D2 (DNP, purpose not stated in the datasheet) is parked at (66.0, 17.6) off the SW node; if it is ever fitted it must move onto the SW blob.
- Clamp, monitor, stage-1 filter, APD and the whole fast chain are unchanged. DRC (kicad-cli 10.0.5): no clearance, courtyard or hole violations; only silk overlaps (reference labels not yet cleaned up), silk near the edge, and the 32 known mounting-hole via-ring hits.

Distances after the move (centre to centre): C6 pump cap to C87 19 mm (was 10.5), L1 to U20 22.5 mm (was 17.6), FBX end of the ladder (R8) to U3 pin 9 about 2.5 mm (was 16). The D1-R7-C5 path is about 15 mm of trace; with GND1 0.1 mm below F.Cu the loop area stays small provided C5's GND pad and the U3 pad are via-stitched.

Files for the board:

| File | Purpose |
|---|---|
| `receiver-module.kicad_pcb` | board, stackup, plot parameters (`pcbplotparams`) |
| `receiver-module.kicad_pro` | design-rule constraints, net classes and net-class patterns |
| `receiver-module.kicad_dru` | custom DRC rules: diff-pair gap/uncoupled/skew/keep-out, HV edge and pad clearance, same-footprint HV exception. A syntax error makes KiCad ignore the WHOLE file silently (kicad-cli reports no error), so after editing it confirm a rule is live, e.g. delete the last rule and check that DRC messages change |
| `../../../tools/netclass_membership.py` | prints which nets each class pattern catches (run from the repo root) |

### Second placement pass, copper pours and rule areas (2026-10-14, PROPOSED)

Daniel's second hand pass (commit b9dc777) rebuilt the LT8365 cell with D2 (the GND-to-SW clamp of the LT8365 Rev. A p.30 3 V to 6 V reference circuit; purpose still UNRESOLVED in `docs/schematic/power.md`) on the SW node, regrouped the FBX, DAC and pot legs under U3, moved U1/U4 beside the eFuse and Q3/R33/R34/J1 next to the EN divider. Script changes after it (coordinates in mm from the top-left corner):

- Netclass: `Net-(D1-A)` (SW) and `Net-(D1-K)` (replaced by `Net-(D3-A)` on 2026-10-22, see below) added to HV; C22/R24 moved to (51.85, 11.65)/(51.85, 13.25) to clear the 1.25 mm pad rule.
- Hysteresis network: C87 (100 pF) at (37.0, 21.8) on the input side, 2.75 mm from U20 pin 4; R87 swapped with C83 so R87 sits at (42.0, 20.78) on the output side (LVDS_P pad 4 mm from pin 12) and C83 (VCCO 1 uF) moved to (37.0, 17.15).
- ESP32 U60 moved 6 mm left to (43.0, 38.7) with C191/C192 and the ADS1115 cluster (U63 at (28.75, 46.38), R206/R207/C197/C198/C200 at x 23.8, C195 at (29.0, 48.75), R208/C199/R209 at x 33.75). TP62/TP63/R203/D60 moved out of the antenna end to x 51 to 54, y 36 to 40.
- J51 (debug header) now lies along the front edge at (54.31, 47.6), rotation 90, pins at y 47.6 from x 54.3 to 67.0, 2.9 mm right of the antenna keep-out and clear of H4. The USB-C CC network (C182, C183, R181, R184, R185, R187, R188, R189) that was under it moved to B.Cu columns x 52.5 and 55.5, y 35.0 to 39.8, between the module and U64.
- Zones (all `thermal relief` pad connection, clearance 0.2 mm, min width 0.2 mm, spoke 0.4 mm, gap 0.25 mm, islands removed): `GND_F` (F.Cu), `GND1` (In1.Cu), `GND_In3` (In3.Cu, priority 0), `GND2` (In4.Cu), `GND_B` (B.Cu), each the full outline. Rail pours on In3.Cu with higher priority (reshaped 2026-10-15 against the pad list, PROPOSED): `PWR_3V3` (priority 1: U1-output corner x 54-72, y 1.5-9.5, neck x 52-58.8 down to y 20.4, front-end band x 6-49, y 17.5-31.8), `PWR_3V3_D` (priority 2: x 49.4-72 from y 20.8, so the DAC cluster U62/C194/R192 at x 50.8-51.8 is inside, and the front band x 18-72, y 32.3-49.5), `PWR_5V` (priority 3: U1-input column x 57.5-62.3, y 3.3-18 plus the eFuse/U4-input block x 62.3-72, y 9.9-18; it cuts the 3V3 pour, which keeps a 1.8 mm strip along y 1.5-3.3). Rail pads that stay outside their pour and need a trace: 3V3 TP50; 3V3_D R33 (EN divider), R39 (at J50) and the U4 output group U4.5/C30/C31 (link on B.Cu plus one In2 track down to the 3V3_D pour); +5V C18/L2 (LT8365 input, In2 track from the 5V pour, about 21 mm) and C29. The user's first-pass 3V3/3V3_D/+5V outer-layer tracks can be replaced by vias into these pours. In2.Cu has no pour (signal layer). The three rail zones report `isolated_copper` until their vias exist. U10 pad 17 (OPA857 exposed pad) has a per-pad solid zone connection because the input window below leaves it one spoke.
- Rule areas (all six copper layers): `ANT_KEEPOUT` x 35.35-50.65, y 44.2-50 (no fills, tracks, vias or pads; the module body is 13.2 x 16.6 mm with the antenna at the front end, MINI-1 datasheet v1.5 Fig. 10-1; the lateral/forward clearance Espressif recommends was not read, so the 1 mm side margin and the 2.9 mm gap to J51 are UNRESOLVED, check `docs/datasheets/esp32-c6-hw-design-guidelines.pdf`). `TIA_IN_WINDOW` x 10.5-15.9, y 24.0-26.1 (no fills only): the plane window under the APD anode pad, the TIA_IN trace and OPA857 pins 15/16, per SBOS630D section 10.1 (a) and Figure 48 p.24 (VERIFIED guidance, PROPOSED size). No plane cut-outs under the HV copper: planes stay solid there on purpose (0.0994 mm prepreg, 220 V, see the HV routing notes above); the earlier idea of an all-layer keep-out around the HV island in `docs/pcb/jlcpcb-fab-settings.md` section 3 is withdrawn.
- DRC after this: no clearance, courtyard or keep-out violations; remaining items are 3 `isolated_copper` (rail zones, unrouted), silk, and the 32 hole-ring warnings.
- Reference designators (2026-10-14): all 223 (then; 221 now) moved off the silkscreen to F.Fab/B.Fab, 0.5 mm text centred on each courtyard, so the silk carries only footprint graphics (outlines, pin-1/polarity marks) and the Fab layers are the assembly drawing. The footprints' own `${REFERENCE}` Fab texts are hidden on the board to avoid doubles. Silk DRC items dropped from 320 to 7 (J50/U60 outlines at the edge, U62 polygon under mask, U51/U52 outlines touching). Fab layers are not in the Gerber set; plot them to PDF for assembly.
- J50 shield (2026-10-22, Daniel, PROPOSED): C181 (1 nF) and R170 (1 M, DNP) deleted; the eight S1 pads (four shell posts) are on net GND (`/Connector/SHIELD` no longer exists). Each shell post needs several vias to the GND planes, with the housing bonded at the connector end. The zones were not refilled in the saved file: refill them (KiCad Fill All Zones, or `kicad-cli pcb drc --refill-zones` on a copy) before judging DRC; on a refilled copy the S1 pads connect to the GND pours with 0 unconnected S1 items.
- U51 CAN channels swapped (2026-10-22, Daniel, GUI, routing only): pin 9 (and stacked NC pin 6) = CAN_P (J50 B11), pin 8 (and NC pin 7) = CAN_N (J50 B10); electrically neutral, U52 unchanged.
- D10 APD pinout corrected (2026-10-22, design review B1, VERIFIED against KAPD1007E19 p.4 outline KAPDA0136EC): the lab-library S12023-10 symbol had pin 1 = K and pin 3 = A; the Hamamatsu pin diagram (bottom view) draws the diode between terminals 3 and 1 with the bar on the 3 side, so pin 1 = anode, pin 3 = cathode. As wired before the fix, HV_K sat on the physical anode and the APD would have conducted forward through R19 + R50 into the OPA857 IN pin. Fix: symbol pin numbers swapped in the library (branch `fix-s12023-pinout`) and in the embedded copy in frontend.kicad_sch; on the board D10 was rotated 180 degrees about the can axis (footprint origin now at (11.54, 25.0), rotation 180) so pad 1 (anode, TIA_IN) stays at (11.54, 25.0) next to U10 and pad 3 (cathode, HV_K) at (9.0, 25.0); the HV_K and TIA_IN tracks are unchanged and the case pad 2 moved from below to above the can axis. The index tab of the fitted part therefore points to the lower right (toward U10); the F.Fab tab outline shows this. Zones refilled, ERC 0/0, netlist differs from before only at D10 pins 1/3, DRC unchanged (52 items, 0 unconnected). Footprint pad geometry unchanged (its description already mirrors the bottom view correctly); only its description text was corrected.
- D10 pads reduced to 1.0 mm (2026-10-22, design review P1, decision 25; lab-library PR #65, branch `s12023-1mm-pads`, needed checked out or merged for the library to match the board): pad 1 square, pads 2 and 3 round, drill 0.7 mm unchanged, annular ring 0.15 mm (JLCPCB standard-tier minimum, 0.20 recommended). Done by text edit with KiCad closed; the board copy of the footprint carries the new sizes and description. Measured copper gaps from the cathode pad 3 (HV_K, 220 V), pcbnew shape distances: case pad 2 (GND) 0.80 mm (was 0.60), anode pad 1 (TIA_IN) 1.54 mm (was 1.34), anode corner to case 0.59 mm (was 0.35, low voltage); GND/3V3 zones on all six layers 1.00 mm; TIA_IN track 1.97 mm. The `hv same footprint pads` DRC exception hides the first two gaps, so the waiver is written into the .kicad_dru comment and the assembly rule (clean and conformal-coat the solder side at D10) is in gates.md G4. Zones refilled; DRC 52 (unchanged), 0 unconnected, parity clean.
- R7 moved into the pump-charge branch (2026-10-22, design review S1, decision 18): D1 cathode now goes straight to HV_V1 and R7 20R sits between HV_V1 and the D3 anode (net `Net-(D3-A)`, in the HV netclass in place of `Net-(D1-K)`), as LT8365 Rev. A p.30 (R8) and DC2838A REV02 (R10). Board (Daniel, GUI, commit 40262da): R7 vertical at (56.83, 5.83) with pad 2 (HV_V1) at the top, D1 K to C5 pad 1 along y 4.8-6.05, C5 moved to (61.00, 4.90), C7 to (61.38, 10.48) with its HV_V1 feed from C5 pad 1; D3 and D4 unchanged. DRC after the change (56 items, 0 unconnected, parity clean): four new 'hv pad clearance' (1.25 mm) items still to be cleared by a move: +5V via at (60.97, 4.05) to C5 pad 1 0.67 mm; 3V3_D via at (63.25, 13.23) to C7 pad 2 1.08 mm; D3 pad 2 (Net-(D3-A)) to C7 pad 1 1.10 mm; R7 pad 1 to D3 pad 1 (HV_PUMP) 1.05 mm. Side effect undone the same day: the 'Update Symbols from Library' run had reset the 27 test-point Footprint fields to the library default `TestPoint_Plated_Hole_D1.0mm_interconnect`, and Update PCB from Schematic then swapped the 27 SMD test points for 1.0 mm plated holes (0.5 mm drill), adding 85 DRC items (holes against vias, shorts, mask bridges). Fields and footprints are back on `TestPoint_Pad_1.0x1.0mm_interconnect` (the embedded library copy keeps the plated-hole default, as the library does); when updating symbols from the library, untick the Footprint field under 'Update/reset fields' or the test points flip again. Vias were never affected: 209, all 0.45/0.25.
- R17, R18, R20, R32 changed from 0603 to 0805 (2026-10-22, review S5a, decision 22, value text `4.99M 1% 0805 150V`, Yageo RC0805 spec V0 p.3: 150 V working). Done by script with KiCad closed: library footprint `R_0805_2012Metric_N` substituted in place with position, rotation, fields, path and pad nets carried over; the existing track ends fall inside the larger pads, so no track was redrawn. Re-placement to clear courtyards: C28 moved 0.3 mm left (to x 14.98) together with the HV_MON via under its pad 1 and the three track ends on them; R20 moved 0.2 mm right (to x 21.92); R32 moved 0.25 mm up (to y 10.09). R17/R18 top pad edges stay at y 2.70, 1.40 mm below the HV_OUT lane. Zones refilled; DRC 52 (unchanged), 0 unconnected, parity clean; ERC 0/0.
- OVP limiter added (2026-10-22, decision 23, by script with KiCad closed): R21 rotated to 0 so pad 1 (HV_MON) is at (14.43, 11.92) and pad 2 (new net `/Power/OVP_REF`) at (16.08, 11.92); the old GND via and stubs at its pad 2 removed and the HV_MON feed from C28 pad 1 re-drawn to (14.43, 11.92). R45 54.9k 0603 at (15.25, 13.60) rot 180: pad 1 OVP_REF (16.08, 13.60), pad 2 GND (14.43, 13.60) with a new GND via in the pad; tap track vertical at x 16.08. U6 TLV431 SOT-23 at (18.90, 14.50) rot 0: REF (17.96, 13.55) to the tap, anode (19.84, 14.50) to a new GND via at (20.60, 14.50), cathode (17.96, 15.45) to EN on F.Cu: along y 15.45 to x 29.55, to (31.0, 14.0), up x 31.0 to y 10.6, then to the Q3 drain pad at (33.66, 9.37); 0.15 mm, no via, passes 0.9 mm left of the Q3/C18 courtyards. Values R21 45.3k, R22/R23 20k on the footprints. Zones refilled; ERC 0/0, DRC 52 (unchanged), 0 unconnected, parity clean. Lab library branch `add-tlv431` (AharoniLab_Power:TLV431) must be checked out or merged for U6 to resolve.
- Q4 Darlington driver added (2026-10-22, decision 24, by script with KiCad closed): Q4 MMBTA42 SOT-23 at (23.60, 6.73) rot 0 right of Q1 (pads 1 B Net-(Q2-C) at (22.66, 5.78), 2 E Net-(Q1-B) at (22.66, 7.68), 3 C HV_OUT at (24.54, 6.73)). HV_OUT now runs from Q1 pad 3 along y 6.73 through Q4's pad gap to Q4 pad 3, then (25.30, 7.49)-(25.30, 9.30)-(24.22, 10.38) into R20 pad 1; the old diagonal (19.68, 6.73)-(22.55, 9.60) is gone. The 10 M node (R18 pad 2, Q2 collector, now net Net-(Q2-C), added to the HV class) keeps its SIG_IN run from the via at (14.05, 3.40) and continues on SIG_IN via (16.13, 4.20) to a new via at (22.66, 4.20) under Q4's base; the old SIG_IN leg to (17.53, 5.60) was removed. Q4's emitter goes by F.Cu to a new via at (21.30, 8.40), then SIG_IN via (18.50, 5.60) to the existing via at (17.53, 5.60) and the F.Cu stub into Q1's base pad (net Net-(Q1-B), now Q4 E to Q1 B only). Q4 added to the "hv escape inside own courtyard" rule in the .kicad_dru. HV-class vias: Net-(Q2-C) 3, Net-(Q1-B) 2 (review P4 still open). Zones refilled; ERC 0/0, DRC 52 (unchanged), 0 unconnected, parity clean.

## Fabrication settings (JLCPCB, 6 layers) - PROPOSED

**Ordering tier (Daniel, 2026-10-09):** order with the JLCPCB quote option "Min via hole size/diameter" = 0.25 mm/(0.35/0.4 mm) (the high-precision tier; JLCPCB then auto-selects "4-Wire Kelvin Test" and "FR4 Tg155", extra cost). The J50 (Wuerth 632723300011) B-row holes (0.65 mm pad / 0.40 mm drill at 0.8 mm pitch, as drawn by WE) are below the standard-tier minima (annular 0.15 mm, hole-to-hole 0.45 mm, hole-to-copper 0.30 mm); JLCPCB's DFM accepted the test board `hardware/pcb/j50-dfm-test` without error with that option selected (screenshot, Daniel 2026-10-09). `receiver-module.kicad_dru` waives the three hole rules for J50 only (rules `j50 annular`, `j50 hole to hole`, `j50 hole clearance`); every other footprint keeps the standard minima. DRC after the waiver: no hole or clearance violations (only silk-over-copper from unplaced parts).

Full rationale, sources and the UNRESOLVED list: [`docs/pcb/jlcpcb-fab-settings.md`](../../../docs/pcb/jlcpcb-fab-settings.md). The differential geometries below are values computed with a 2D field solver (`tools/impedance_fd/`), labelled PROPOSED; they are NOT JLCPCB calculator output and must be confirmed with the JLCPCB impedance calculator at order time (the stackup lists 1.538 mm of copper and dielectric, about 1.60 mm with mask; confirm 1.6 mm in the calculator).

Stackup: JLC06161H-3313, 1.6 mm, ENIG, outer copper 1 oz (0.035 mm), inner 0.5 oz (0.0152 mm), mask 0.0305 mm Er 3.8; prepreg 3313 0.0994 mm Er 4.1 (F.Cu to In1, In4 to B.Cu), core 0.55 mm Er 4.6 (twice), prepreg 2116 0.1088 mm Er 4.16 (In2 to In3). Loss tangent left at the KiCad default 0.02 (JLCPCB publishes none). Board thickness in the file is 1.5994 mm (sum of the stackup including mask; KiCad recomputes it).

| Layer | KiCad name | User name | Use |
|---|---|---|---|
| L1 | F.Cu | F.Cu | components, fast analog path, USB-C pairs, LVDS, HV outer routing; 90/100 ohm referenced to L2 |
| L2 | In1.Cu | GND1 | solid GND, no routing |
| L3 | In2.Cu | SIG_IN | slow signals and rail routing, no controlled-impedance pairs |
| L4 | In3.Cu | PWR | power pours (VBUS 5 V, 3V3, 3V3_D), remaining area GND, stitched; only 0.1088 mm to L3 |
| L5 | In4.Cu | GND2 | solid GND |
| L6 | B.Cu | B.Cu | bottom components, slow routing |

Vias (Daniel, 2026-10-22): one size on every net, 0.45 mm pad / 0.25 mm drill (standard JLCPCB price for a 0.25 mm drill at >= 0.45 mm pad, capabilities page read 2026-10-22), several in parallel for power; no HV-class net has a via. All 209 board vias resized; netclass defaults set to 0.45/0.25; custom rule "via annular" (0.10 mm, vias only) keeps the 0.15 mm Board Setup minimum for PTH pads.

Design rules (Board Setup > Constraints): min clearance 0.10, track 0.10, connection 0.10, annular 0.15, via diameter 0.45, through hole 0.20, hole to hole 0.45, copper to hole 0.30, copper to edge 0.30, mask expansion 0, mask min web 0.10, mask to copper 0.09, silk text 1.0 / 0.15 mm, silk to pad 0.15, courtyard overlap = error, vias tented.

| Class | Track | Clearance | Via | Diff width / gap | Nets |
|---|---|---|---|---|---|
| Default | 0.15 | 0.15 | 0.45 / 0.25 | - | all others (LVDS_DBG_P/N included) |
| HV | 0.30 | 1.0 | 0.45 / 0.25 | - | /APD_BIAS, /Front End/HV_K, /Power/HV_OUT, HV_CLAMP, HV_RAW, HV_V1, HV_PUMP, Net-(D1-A) (the LT8365 SW node, swings to the stage-1 voltage every cycle) and Net-(D3-A) (R7 to the D3 anode, the pump-charge node at the stage-1 voltage; it replaced Net-(D1-K) on 2026-10-22 when R7 moved; both added 2026-10-14 after the first DRC with the HV class had missed them), and Net-(Q1-E), Net-(Q1-B), Net-(Q2-C) (since decision 24: the 10 M node; Net-(Q1-B) is now the Q4-to-Q1 base link), Net-(R17-Pad2) (clamp transistor nodes, within a few volts of HV; added conservatively, UNRESOLVED whether that is wanted). HV_MON, HV_DIS, DAC_HV, 5V_HVIN are low voltage and stay Default |
| HV_LADDER | 0.30 | 0.6 | 0.45 / 0.25 | - | Net-(R20-Pad2) (HV_MON divider midpoint, R20/R32 4.99 M) and Net-(R10-Pad1), Net-(R10-Pad2), Net-(R8-Pad2) (FBX feedback divider R11/R10/R9/R8, 2.05 M each); steps of about 55 V, IPC-2221B 51-100 V band 0.6 mm |
| DIFF90 | 0.145 | 0.15 | 0.45 / 0.25 | 0.145 / 0.15 | /Connector/LVDS_OUT1_P, _N, LVDS_OUT2_P, _N |
| USB90 | 0.145 | 0.15 | 0.45 / 0.25 | 0.145 / 0.15 | */USB_DP, */USB_DN, */USB_ESD_DP, */USB_ESD_DN, */USB_E_DP, */USB_E_DN (last four added 2026-10-22; U61 -> R193/R194 was unnamed and the ESP32 side was USB_DP_E/USB_DN_E, neither ending in P/N) |
| CAN90 | 0.145 | 0.15 | 0.45 / 0.25 | 0.145 / 0.15 | */CAN_P, */CAN_N |
| DIFF100 | 0.11 | 0.15 | 0.45 / 0.25 | 0.11 / 0.15 | /LVDS_P, /LVDS_N (U20 to R180) |

Tuning profiles were not created (their JSON schema is not documented in the KiCad manual and has no example in these projects); create `Z90_diff` / `Z100_diff` in the GUI if wanted. KiCad pairs nets by name only for _P/_N and +/-. This was UNRESOLVED for CAN_H/CAN_L and USB_DP/USB_DM; resolved 2026-10-16 by renaming to CAN_P/CAN_N and USB_DN (USB_DP unchanged; no electrical change), so the interactive diff-pair router now recognises all of them (netclass patterns `*/CAN_P`, `*/CAN_N`, `*/USB_DP`, `*/USB_DN`; recognition in the router itself not yet exercised on these nets, PROPOSED). The DRC rules are netclass based so they apply either way.

HV same-footprint exception: `hv same footprint pads` (last rule in the .kicad_dru) lowers the clearance to 0.15 mm between two pads of the same footprint when either is HV or HV_LADDER (identified by `A.Parent == B.Parent`). Everything outside one footprint keeps the full 1.0 mm (HV), 0.6 mm (HV_LADDER), and 1.25 mm for exposed HV pads. D10 is the recorded case where the exception hides a real gap (cathode pad 0.80 mm from the case pad, 1.54 mm from the anode pad with the 1.0 mm pads; decision 25); the waiver text sits in the .kicad_dru next to the rule.

Plot settings (in the .kicad_pcb): Gerber, Protel extensions, X2 and netlist attributes on, 4.6 coordinates, layers F.Cu, In1-In4, B.Cu, F/B Mask, F/B Silkscreen, F/B Paste, Edge.Cuts, subtract mask from silk on, drill marks none, output directory `fab/` (git-ignored except under `release/`).

Gerbers and drill (from the repo root; KiCad 10.0.5 CLI, path in CLAUDE.md):

```
K=/Users/daharoni/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
B=hardware/pcb/receiver-module/receiver-module.kicad_pcb
$K pcb export gerbers --board-plot-params -o hardware/pcb/receiver-module/fab/ $B
$K pcb export drill --format excellon --drill-origin absolute --excellon-zeros-format decimal \
   --excellon-oval-format alternate -u mm --excellon-separate-th --generate-map --map-format pdf \
   -o hardware/pcb/receiver-module/fab/ $B
```

Inner layer files are named by user layer name (`-GND1.g1`, `-SIG_IN.g2`, `-PWR.g3`, `-GND2.g4`), which keeps the Protel .G1-.G4 order JLCPCB needs. Excellon settings in the GUI (Fabrication Outputs > Drill Files): Excellon, millimetres, zeros format Decimal, origin Absolute (matches Gerber; leave "use drill/place file origin" off), oval holes Alternate drill mode, PTH and NPTH in separate files (box "single file" unticked), drill map ticked. Run DRC to zero errors first; layout is not done, so this has not been done for a real release.

