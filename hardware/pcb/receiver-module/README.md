# receiver-module (KiCad 10 project, Rev A schematic)

Photodiode LVDS Receiver, Rev A0, Aharoni Lab, UCLA.

**Nothing in this project is fabrication-approved.** The six hierarchical sheets are populated
with lab-library parts, values and footprints per `docs/schematic/rev-a-sheet-specs.md`; project ERC on the root
reports 0 errors and 0 warnings (kicad-cli 10.0.5, 2026-10-09, revision 4 after decision 14). The netlist has 223 components (Power 79, Controller 55, Connector 33 including mounting holes H1-H4 added 2026-10-09, Front End 26, Slicer 17, Monitor 13) on 144 nets. The PCB carries all 223 footprints (H1-H4 included), placed by the first-pass placement script; nothing is routed (see Board below). H1-H4 need lab-library PR #62 (branch `add-mounting-holes`, symbol and footprint `MountingHole_2.2mm_M2_Pad_Via`) merged or checked out so the symbol resolves. Status labels used
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
| `connector.kicad_sch` | single 24-pin USB-C J50: VBUS out, USB_DP/USB_DM, CC1_SENSE/CC2_SENSE, AUX (SBU tie), LVDS fan-out U50 to both SuperSpeed TX pairs, CAN on both RX pairs, ESD arrays U51/U52, scope header J51, test points |
| `controller.kicad_sch` | ESP32-C6-MINI-1, MCP4728 DAC, ADS1115 ADC, SN65HVD230 CAN, USBLC6 and 22R D+/D- (USB from the Connector sheet), RESET/BOOT switches, CC1_SENSE/CC2_SENSE inputs on IO4/IO5 |

`GND` is a global net (global label in every sub-sheet). Other power nets are sheet pins. Nets at or above 50 V are prefixed `HV_` and, with `APD_BIAS`, belong to net class `HV` (1.0 mm clearance).

## Board

`receiver-module.kicad_pcb`: 6-layer board (stackup below), 75 x 50 mm placeholder outline on Edge.Cuts, all 223 footprints placed by the first-pass placement script (below; layout in progress, nothing routed). Rules and fabrication settings follow `docs/pcb/jlcpcb-fab-settings.md` (research, PROPOSED values, nothing measured).

### First-pass placement (2026-10-09, PROPOSED)

`tools/pcb_place.py` (runs under KiCad's bundled Python, which has `pcbnew`) applies `placement/placement-spec.json`: board outline, per-block side and region, fixed anchor parts (ICs, connectors, APD, switches, mounting holes) and a `near` pad target for each passive. Passives are packed on a 0.25 mm grid at the nearest free spot to their target, with courtyard-plus-margin collision checks (0.15 mm, 0.65 mm for HV-class parts, 0.3 mm for HV_LADDER), through-hole parts blocking both sides, an ESP32 antenna keep-out, and region growth when a block is full. Blocks are packed in spec order. Result: 223 placed, 0 courtyard overlaps, 0 clearance violations (kicad-cli DRC); remaining DRC items are silk overlaps (reference labels not yet cleaned up), silk near the edge, and the 32 hole-to-hole hits from the via rings of the `MountingHole_2.2mm_M2_Pad_Via` footprints (0.35 mm between the via holes and the 2.2 mm hole, constraint 0.45 mm; swap H1-H4 to the `_Pad` variant without vias or accept it on the high-precision tier).

Run from this directory, with KiCad closed:

```
PYTHONPATH=../../../tools /Users/daharoni/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
  ../../../tools/pcb_place.py receiver-module.kicad_pcb placement/placement-spec.json --out receiver-module.kicad_pcb --report /tmp/report.json
```

It re-places EVERY footprint from the spec, so do not run it on a board with hand placement you want to keep. Floor plan (y down, optical end left): fast chain on the top centre line (D10 at x 9 mm, OPA857, OPA855, filter, TLV3605, SN65LVDS104, ESD arrays, J50 at the right edge with the mouth overhanging 0.95 mm); HV island along the back edge on top (HV_MON, HV_OUT, FB ladder, LT8365 boost, HV_DIS); J51 at the front left; status LED, test points and the RESET/BOOT switches at the front right. Bottom: ESP32-C6 with its antenna over the front edge (keep-out 41-57 x 44-50 mm, both sides), USB ESD and CAN transceiver under J50, CC dividers and eFuse under the connector end, 3V3/3V3_D regulators and DAC/ADC under the HV island, VCM_REF buffer and RSSI detector under the post-amp. The optical window must be centred on the APD can, which sits about 1.3 mm right of the D10 footprint origin (pin 1). The renders used for review are not committed; `kicad-cli pcb render --side top|bottom` regenerates them.

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

Design rules (Board Setup > Constraints): min clearance 0.10, track 0.10, connection 0.10, annular 0.15, via diameter 0.45, through hole 0.20, hole to hole 0.45, copper to hole 0.30, copper to edge 0.30, mask expansion 0, mask min web 0.10, mask to copper 0.09, silk text 1.0 / 0.15 mm, silk to pad 0.15, courtyard overlap = error, vias tented.

| Class | Track | Clearance | Via | Diff width / gap | Nets |
|---|---|---|---|---|---|
| Default | 0.15 | 0.15 | 0.6 / 0.3 | - | all others (LVDS_DBG_P/N included) |
| HV | 0.30 | 1.0 | 0.6 / 0.3 | - | /APD_BIAS, /Front End/HV_K, /Power/HV_OUT, HV_CLAMP, HV_RAW, HV_V1, HV_PUMP, and Net-(Q1-E), Net-(Q1-B), Net-(R17-Pad2) (clamp transistor nodes, within a few volts of HV; added conservatively, UNRESOLVED whether that is wanted). HV_MON, HV_DIS, DAC_HV, 5V_HVIN are low voltage and stay Default |
| HV_LADDER | 0.30 | 0.6 | 0.6 / 0.3 | - | Net-(R20-Pad2) (HV_MON divider midpoint, R20/R32 4.99 M) and Net-(R10-Pad1), Net-(R10-Pad2), Net-(R8-Pad2) (FBX feedback divider R11/R10/R9/R8, 2.05 M each); steps of about 55 V, IPC-2221B 51-100 V band 0.6 mm |
| DIFF90 | 0.145 | 0.15 | 0.6 / 0.3 | 0.145 / 0.15 | /Connector/LVDS_OUT1_P, _N, LVDS_OUT2_P, _N |
| USB90 | 0.145 | 0.15 | 0.6 / 0.3 | 0.145 / 0.15 | /USB_DP, /USB_DM |
| CAN90 | 0.145 | 0.15 | 0.6 / 0.3 | 0.145 / 0.15 | /CAN_H, /CAN_L |
| DIFF100 | 0.11 | 0.15 | 0.6 / 0.3 | 0.11 / 0.15 | /LVDS_P, /LVDS_N (U20 to R180) |

Tuning profiles were not created (their JSON schema is not documented in the KiCad manual and has no example in these projects); create `Z90_diff` / `Z100_diff` in the GUI if wanted. KiCad pairs nets by name only for _P/_N and +/-: USB_DP/USB_DM and CAN_H/CAN_L may not get the interactive diff-pair router (UNRESOLVED); the DRC rules are netclass based so they apply either way.

HV same-footprint exception: `hv same footprint pads` (last rule in the .kicad_dru) lowers the clearance to 0.15 mm between two pads of the same footprint when either is HV or HV_LADDER (identified by `A.Parent == B.Parent`). Everything outside one footprint keeps the full 1.0 mm (HV), 0.6 mm (HV_LADDER), and 1.25 mm for exposed HV pads.

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

