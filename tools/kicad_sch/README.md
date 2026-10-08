# kicad_sch

Stdlib-only helpers to generate KiCad 10 schematic sheets (`.kicad_sch`, version 20260306)
that place symbols from the Aharoni lab library. Run from `tools/`: `python3 -m kicad_sch.selftest`.

```python
from kicad_sch import Library, Sheet

sheet = Sheet.load("hardware/pcb/receiver-module/slicer.kicad_sch")  # keeps uuid, paper, title_block;
                                                                    # root/sheet uuids found via receiver-module.kicad_sch
r1 = sheet.place("AharoniLab_Passive:R_Small_US", "R1", "10k", at=(30.48, 101.6), rot=90,
                 footprint="AharoniLab_Resistor_SMD:R_0603_1608Metric_N")
c1 = sheet.place("AharoniLab_Passive:C_Small", "C1", "100n", at=(50.8, 106.68),
                 footprint="AharoniLab_Capacitor_SMD:C_0603_1608Metric_N")
sheet.hier_label("SDET", (20.32, 101.6), 180, "input")
sheet.connect((20.32, 101.6), r1.pin("1"))                 # orthogonal route, "h" or "v" first
sheet.connect(r1.pin("2"), c1.pin("1"), via="h")
sheet.stub(c1.pin("2"), "d", 2.54, "GND", kind="global")   # wire outward + label
sheet.save("hardware/pcb/receiver-module/slicer.kicad_sch")  # auto_junctions() runs here
```

Everything except uuid/paper/title_block of the loaded file is replaced on `save()`.

## Conventions
- Millimetres; every pin must land on the 1.27 mm grid (`place()` raises otherwise). Keep `at=` on the grid.
- Schematic Y points down; symbol-library Y points up. `rot` is counter-clockwise as seen on screen
  (0/90/180/270); `mirror="x"` flips top/bottom, `mirror="y"` flips left/right. Rotation is applied first,
  then the mirror (verified by the selftest against kicad-cli netlists for all 12 combinations).
- `inst.pin(key)` takes a pin number or name and returns the absolute (x, y); ambiguous or missing keys raise
  with the list of available pins. Multi-unit parts: place each unit with `unit=n` and the same `ref`.
  Stacked pins appear as one entry, e.g. number `"[3,5,9,11]"` (TLV3605 VEE).
- `connect(p1, p2, via)`: one straight wire if aligned, else an L: `"h"` goes horizontal first, `"v"` vertical first.
- `stub(pin, "l"|"r"|"u"|"d", length, label, kind="local"|"global"|"hier", shape=...)`: label text points away from the pin.
- Pin names/numbers: `Library().pins("AharoniLab_OpAmp:TLV3605RVKR")` lists unit, number, name, type, x, y, angle, length.
- Generic R/C/L symbols have no footprint; pass `footprint=` to `place()`.
- Derived symbols (`extends`) are flattened into the embedded `lib_symbols` definition, as KiCad does.

## Validate
```
CLI=/Users/daharoni/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$CLI sch erc --format json --severity-all -o erc.json receiver-module.kicad_sch
$CLI sch export netlist --format kicadsexpr -o out.net receiver-module.kicad_sch
```
Run both on the ROOT sheet so instance paths and hierarchical labels resolve.
