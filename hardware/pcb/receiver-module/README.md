# receiver-module (KiCad 10 project, Rev A schematic)

Photodiode LVDS Receiver, Rev A0, Aharoni Lab, UCLA.

**Nothing in this project is fabrication-approved.** The seven hierarchical sheets are populated
with lab-library parts, values and footprints per `docs/schematic/rev-a-sheet-specs.md`; project ERC
is clean (0 errors, 3 justified warnings, 2026-10-08). The PCB has no footprints yet. Status labels used
in notes: VERIFIED / PROPOSED / UNRESOLVED.

## Generated sheets

Each sub-sheet and the root are produced by `gen/<sheet>.py` using the `tools/kicad_sch` package
(`cd tools && python3 gen/...` from the project root; see `tools/kicad_sch/README.md`). Regenerate in
the order power, frontend, slicer, control, detector, connector, mcu, root. Each sheet keeps its uuid, so
instance paths stay stable. KiCad's bundled `power:PWR_FLAG` / `power:GND` symbols are used alongside
the lab library. Reference designator ranges per sheet are listed in the spec document.

Validation: `kicad-cli sch erc` and `kicad-cli sch export netlist` on `receiver-module.kicad_sch`
(kicad-cli path in CLAUDE.md).

## How to open

Open `receiver-module.kicad_pro` in KiCad 10. Symbol and footprint libraries come from the global
tables (the lab library is global via `${AHARONI_LAB_KICAD_LIB}`); this project has no
`sym-lib-table` or `fp-lib-table` on purpose. Project text variables: TITLE, REV, COMPANY.

## Sheets

| File | Purpose |
|---|---|
| `receiver-module.kicad_sch` | Root: hierarchical sheet symbols only, in signal-flow order |
| `power.kicad_sch` | 5V in; TPS79901 3V3, LM27762 +/-3V7, bead-filtered 5V_A, LT8365 boost + doubler APD bias (HV_ nets, clamp, stage-1 RC filter) -> APD_BIAS, HV_MON divider, DAC_HV trim input |
| `frontend.kicad_sch` | APD S12023-10 (cathode via RC filter from APD_BIAS, anode to TIA_IN; FDS010 TO-5 optional alternate footprint), OPA857 TIA, AC coupling, VCA821 VGA, level shift to SDET |
| `detector.kicad_sch` | Fast high/low capture coupon producing VHIGH, VLOW (unvalidated) |
| `control.kicad_sch` | VCM_DET, VMID, VSPAN, true integrator with TMUX1112 freeze (HOLD_N from the FPGA), gain/threshold selector headers, TLV3201 LOS status |
| `slicer.kicad_sch` | TLV3605 comparator, hysteresis, LVDS_P/LVDS_N out |
| `connector.kicad_sch` | +5V in, LVDS to ECP5, debug header and test pads (including VMID, VSPAN inputs; APD_BIAS only as a scaled monitor) |
| `mcu.kicad_sch` | 6-pin header for an external SAMD51 board (DAC_GAIN, DAC_TH, DAC_HV, HV_MON); no MCU on Rev A |

`GND` is a global net (global label in every sub-sheet). Other power nets are sheet pins. Nets at or above 50 V are prefixed `HV_` and, with `APD_BIAS`, belong to net class `HV` (1.0 mm clearance).

## Board

`receiver-module.kicad_pcb`: empty 4-layer board (F.Cu, In1.Cu, In2.Cu, B.Cu; inner planes are
placeholders), 50 x 30 mm outline on Edge.Cuts, no footprints. Layout starts after the G1
feasibility gate. Net class `LVDS` (0.2 mm width / 0.2 mm gap) is a placeholder to be computed from
the stackup.
