# J50 receptacle DFM test board

Purpose: find out, before any real order, whether JLCPCB's instant-quote DFM
check accepts the through-hole B row of the Wuerth 632723300011 USB-C
receptacle (footprint `AharoniLab_Connector:Wuerth_632723300011`) on the
6-layer JLC06161H-3313 ENIG stackup used by the receiver module. Background:
`docs/pcb/j50-receptacle-dfm.md`.

Status: UNRESOLVED. Nothing here was measured or run through JLCPCB; the board
only proves the files load in KiCad 10 (kicad-cli DRC loads it; its
violations are expected, see below).

## What is on the board

40 x 15 mm, 6 layers, same header, layer list, stackup and plot parameters as
`hardware/pcb/receiver-module/receiver-module.kicad_pcb`. No nets, no zones.

| Ref | Footprint | B-row pads |
|---|---|---|
| J50 (x=10) | Wuerth_632723300011 as in the lab library | 0.65 mm pad, 0.40 mm drill, 0.8 mm pitch: annular ring 0.125 mm, hole-to-hole 0.40 mm |
| J51 (x=30) | same footprint | B1-B12 pads enlarged to 0.70 mm (annular ring 0.15 mm); drills unchanged |

Both connectors are placed with the connector edge (footprint y=10.58) on the
bottom board edge (footprint origin at y=4.42), so the pads sit inside the
outline. Two instances do not fit a 20 x 15 mm outline, hence 40 mm. Also on
the board: 0.145 mm tracks on F.Cu and 0.6/0.3 mm vias so the file is not
empty. Only the B row differs between J50 and J51; the A-row SMT pads, shell
posts (0.4 mm drills) and mid-plate slots (0.2 mm drills) are identical.

Expected KiCad DRC noise (default rules, no project file): clearance, 0.145 mm
track width, 0.2 mm drill under the 0.3 mm default minimum, dangling tracks/vias.

## Files

- `j50-dfm-test.kicad_pcb`: the board.
- `release/j50-dfm-test-gerbers.zip`: Gerbers (6 copper layers, mask, paste,
  silk, Edge.Cuts, job file) plus `-PTH.drl` and `-NPTH.drl` (Excellon, mm,
  decimal). Committed copy; `fab/` and the top-level zip are git-ignored.

## Upload steps (jlcpcb.com)

1. Quote page (jlcpcb.com, "Order now" / Instant Quote): add the zip
   `release/j50-dfm-test-gerbers.zip`.
2. Set Layers = 6, PCB Thickness = 1.6 mm, Surface Finish = ENIG,
   Impedance Control = yes with stackup JLC06161H-3313. Leave other options at
   defaults. Dimensions should read 40 x 15 mm.
3. Wait for the "PCB analysis" / DFM result. Read every warning and error,
   especially anything mentioning "hole to hole", "annular ring", "via/PTH
   size", "min hole" or "minimum trace spacing". Note which of J50 and J51 the
   marker points at (J50 B row is at x~10 mm, J51 at x~30 mm) and take a
   screenshot of each message.
4. The free standalone check is JLCPCB's DFM analysis tool at
   https://jlcpcb.com/dfm (upload the same zip). Run it too; it can report
   different details than the quote page. Do not place the order.

## Decision table

| Result | Action |
|---|---|
| J50 (0.65 pads) accepted, no hole-to-hole/annular-ring error | Keep the footprint as is. |
| J50 flagged, J51 (0.70 pads) accepted | Enlarge the B-row pads to 0.70 mm in the lab library footprint (PR to that repo). Check the 0.70 pad against the 0.8 mm pitch and 0.7 mm row spacing. |
| Both flagged on hole-to-hole 0.40 mm or annular ring | Through-hole B row not manufacturable at JLCPCB on this stackup: switch to an SMT-only receptacle per `docs/pcb/j50-receptacle-dfm.md`. |
| Only a warning (not an error) | Record the exact text; ask JLCPCB support/engineering whether it blocks production before relying on it. |

Whichever way it goes, record the outcome (date, screenshot, message text) in
`docs/pcb/j50-receptacle-dfm.md`. An accepted quote DFM check is not proof that
CAM engineers will not query the order later.
