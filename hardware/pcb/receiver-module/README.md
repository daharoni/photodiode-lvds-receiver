# receiver-module (KiCad 10 project, Rev A schematic)

Photodiode LVDS Receiver, Rev A0, Aharoni Lab, UCLA.

**Nothing in this project is fabrication-approved.** The six hierarchical sheets are populated
with lab-library parts, values and footprints per `docs/schematic/rev-a-sheet-specs.md`; project ERC on the root
reports 0 errors and 0 warnings (kicad-cli 10.0.5, 2026-10-09, revision 4 after decision 14). The netlist has 220 components (Power 79, Controller 55, Connector 29, Front End 27, Slicer 17, Monitor 13) on 144 nets. The PCB has no footprints yet. Status labels used
in notes: VERIFIED / PROPOSED / UNRESOLVED.

## Generated sheets

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

`receiver-module.kicad_pcb`: empty 4-layer board (F.Cu, In1.Cu, In2.Cu, B.Cu; inner planes are
placeholders), 50 x 30 mm outline on Edge.Cuts, no footprints. Layout starts after the G1
feasibility gate. Net class `LVDS` (0.2 mm width / 0.2 mm gap) is a placeholder to be computed from
the stackup.
