# receiver-module (KiCad 10 project skeleton)

Photodiode LVDS Receiver, Rev A0, Aharoni Lab, UCLA.

**Nothing in this project is fabrication-approved.** It is a skeleton: hierarchical sheets with
pin declarations and design notes only. No components, no part values, no footprints. Status labels
used in notes: VERIFIED / PROPOSED / UNRESOLVED.

## How to open

Open `receiver-module.kicad_pro` in KiCad 10. Symbol and footprint libraries come from the global
tables (the lab library is global via `${AHARONI_LAB_KICAD_LIB}`); this project has no
`sym-lib-table` or `fp-lib-table` on purpose. Project text variables: TITLE, REV, COMPANY.

## Sheets

| File | Purpose |
|---|---|
| `receiver-module.kicad_sch` | Root: hierarchical sheet symbols only, in signal-flow order |
| `power.kicad_sch` | 5V in; 3V3 LDO, plus/minus 3V7, APD_BIAS (programmable, temperature-compensated 100-220 V APD bias supply; part TBD, pending docs/research/apd-bias-supply.md; replaces the MAX15032 block; HV creepage note), filtered 5V_A |
| `frontend.kicad_sch` | APD S12023-10 (cathode via RC filter from APD_BIAS, anode to TIA_IN; FDS010 TO-5 optional alternate footprint), OPA857 TIA, AC coupling, VCA821 VGA, level shift to SDET |
| `detector.kicad_sch` | Fast high/low capture coupon producing VHIGH, VLOW (unvalidated) |
| `control.kicad_sch` | VCM_DET, VMID, VSPAN (also output as buffered slow nodes to test pads), integrator, gain/threshold selectors, LOS |
| `slicer.kicad_sch` | TLV3605 comparator, hysteresis, LVDS_P/LVDS_N out |
| `connector.kicad_sch` | +5V in, LVDS to ECP5, debug header and test pads (including VMID, VSPAN inputs; APD_BIAS only as a scaled monitor) |
| `mcu.kicad_sch` | Optional SAMD51 supervisor (DNP for Rev A) |

`GND` is a global net (global label in every sub-sheet). Other power nets are sheet pins.

## Board

`receiver-module.kicad_pcb`: empty 4-layer board (F.Cu, In1.Cu, In2.Cu, B.Cu; inner planes are
placeholders), 50 x 30 mm outline on Edge.Cuts, no footprints. Layout starts after the G1
feasibility gate. Net class `LVDS` (0.2 mm width / 0.2 mm gap) is a placeholder to be computed from
the stackup.
