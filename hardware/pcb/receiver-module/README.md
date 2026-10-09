# receiver-module (KiCad 10 project, Rev A schematic)

Photodiode LVDS Receiver, Rev A0, Aharoni Lab, UCLA.

**Nothing in this project is fabrication-approved.** The six hierarchical sheets are populated
with lab-library parts, values and footprints per `docs/schematic/rev-a-sheet-specs.md`; project ERC on the root
reports 0 errors and 0 warnings (kicad-cli 10.0.5, 2026-10-09, revision 4 after decision 14). The netlist has 224 components (Power 79, Controller 55, Connector 33 including mounting holes H1-H4 added 2026-10-09, Front End 27, Slicer 17, Monitor 13) on 144 nets. The PCB has the 220 imported footprints, unplaced; run "Update PCB from Schematic" to pull in H1-H4 (224 in total). H1-H4 need lab-library PR #62 (branch `add-mounting-holes`, symbol and footprint `MountingHole_2.2mm_M2_Pad_Via`) merged or checked out so the symbol resolves. Status labels used
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

`receiver-module.kicad_pcb`: 6-layer board (stackup below), 50 x 30 mm outline on Edge.Cuts, the 220 imported footprints (unplaced; layout in progress). Rules and fabrication settings follow `docs/pcb/jlcpcb-fab-settings.md` (research, PROPOSED values, nothing measured).

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

