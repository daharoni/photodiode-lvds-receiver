#!/usr/bin/env python3
"""Generate receiver-module.kicad_sch (root): seven hierarchical sheet symbols joined by local labels.
Run LAST (after power, frontend, slicer, control, detector, connector, controller): python3 gen/root.py
Pins are derived from each sub-sheet's hierarchical labels and asserted against the layout table."""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet
from kicad_sch.sexpr import parse, find, find_all

D = os.path.join(ROOT, "hardware/pcb/receiver-module")
PATH = os.path.join(D, "receiver-module.kicad_sch")

old = parse(open(PATH).read())
# existing sheet identities (uuid, page) are kept so sub-sheet instance paths stay valid
ident = {}
for sh in find_all(old, "sheet"):
    pr = {p[1]: p[2] for p in find_all(sh, "property")}
    pg = find(find(find(find(sh, "instances"), "project"), "path"), "page")[1]
    fn_ = {"mcu.kicad_sch": "controller.kicad_sch"}.get(str(pr["Sheetfile"]), str(pr["Sheetfile"]))
    ident[fn_] = ("Controller" if fn_ == "controller.kicad_sch" else str(pr["Sheetname"]), str(find(sh, "uuid")[1]), str(pg))
# file -> (column, y, ordered input pins, ordered output pins)
COL = [38.1, 119.38, 195.58, 271.78, 347.98]
W = 35.56
# file -> (column, y, inputs, outputs, bidirectional)
LAYOUT = {
    "power.kicad_sch":     (0, 55.88,  ["+5V", "DAC_HV", "HV_DIS"],
                            ["3V3", "3V3_D", "+3V7", "-3V7", "5V_A", "APD_BIAS", "HV_MON", "PGOOD_VGA"], []),
    "frontend.kicad_sch":  (1, 55.88,  ["APD_BIAS", "3V3", "+3V7", "-3V7", "VG", "VCM_DET"], ["SDET"], []),
    "detector.kicad_sch":  (2, 55.88,  ["SDET", "5V_A", "3V3", "VCM_DET"], ["VHIGH", "VLOW"], []),
    "control.kicad_sch":   (2, 116.84, ["3V3", "VHIGH", "VLOW", "HOLD_N", "DAC_GAIN", "DAC_TH"],
                            ["VCM_DET", "VG", "VTH", "LOS", "VMID", "VSPAN"], []),
    "slicer.kicad_sch":    (3, 55.88,  ["SDET", "VTH", "3V3", "SHDN_N", "LE_HYS"], ["LVDS_P", "LVDS_N"], []),
    "connector.kicad_sch": (4, 55.88,  ["LVDS_P", "LVDS_N", "LOS", "VMID", "VSPAN", "3V3", "3V3_D", "+3V7", "-3V7", "5V_A", "HV_MON"],
                            ["+5V", "HOLD_N"], ["CAN_H", "CAN_L", "AUX"]),
    "controller.kicad_sch": (1, 160.02, ["3V3_D", "LOS", "PGOOD_VGA", "HV_MON", "VSPAN", "VG", "VMID"],
                            ["HV_DIS", "SHDN_N", "LE_HYS", "DAC_GAIN", "DAC_TH", "DAC_HV"], ["CAN_H", "CAN_L", "AUX"]),
}
assert set(LAYOUT) == set(ident), (set(LAYOUT) ^ set(ident))

s = Sheet.load(PATH)
s.text("Root sheet. Signal flow: Power -> Front End -> Slicer/LVDS -> Connector; Detector and Control close the AGC/threshold loop; the Controller (ESP32-C6, decision 11)\n"
       "sets gain/threshold/HV, monitors HV/LOS and talks CAN to the headstage through the Connector. Status labels: VERIFIED / PROPOSED / UNRESOLVED.\n"
       "No part values are approved for fabrication.", (25.4, 15), 1.5)
s.text("Power rails +5V, 3V3, 3V3_D, +3V7, -3V7, 5V_A are carried as hierarchical sheet pins (joined on this sheet by local labels).\n"
       "GND is a global net: each sub-sheet carries a global label GND (no sheet pin).", (25.4, 35), 1.5)

pinpos = {}
for fn, (col, y, ins, outs, bis) in LAYOUT.items():
    sub = parse(open(os.path.join(D, fn)).read())
    hl = {str(h[1]): str(find(h, "shape")[1]) for h in find_all(sub, "hierarchical_label")}
    want = {n: "input" for n in ins}
    want.update({n: "output" for n in outs})
    want.update({n: "bidirectional" for n in bis})
    assert hl == want, "%s: sub-sheet labels %s != layout %s" % (fn, sorted(hl.items()), sorted(want.items()))
    name, uuid, page = ident[fn]
    x = COL[col]
    h = round(5.08 * (max(len(ins), len(outs) + len(bis)) + 1), 2)
    pins = [(n, "input", "l", 5.08 * (i + 1)) for i, n in enumerate(ins)] + \
           [(n, "output", "r", 5.08 * (i + 1)) for i, n in enumerate(outs)] + \
           [(n, "bidirectional", "r", 5.08 * (len(outs) + i + 1)) for i, n in enumerate(bis)]
    pos = s.sheet_symbol(name, fn, (x, y), (W, h), pins, uuid, page)
    for n, shape, side, _ in pins:
        p = pos[n]
        s.stub(p, "l" if side == "l" else "r", 5.08 if n != "+5V" or fn != "power.kicad_sch" else 12.7, n)
        pinpos[(fn, n)] = p

# +5V driver flag (connector +5V is a passive-ish sheet output; ERC needs a power_out source)
px, py = pinpos[("power.kicad_sch", "+5V")]
s.place("power:PWR_FLAG", "#FLG04", "PWR_FLAG", (px - 6.35, py), in_bom=False)
# GND flag on a global GND label
s.place("power:PWR_FLAG", "#FLG05", "PWR_FLAG", (38.1, 254.0), in_bom=False)
s.wire([(38.1, 254.0), (45.72, 254.0)])
s.global_label("GND", (45.72, 254.0), 0)
s.text("Global net GND enters here only to carry a PWR_FLAG for ERC. The Controller is the ESP32-C6 sheet (decision 11); the MCU sheet is gone.\n"
       "HOLD_N is a plain wire: Connector -> Control (buffered on the Connector sheet). HV_MON is Power -> Controller and Connector; DAC_HV and HV_DIS are Controller -> Power.\n"
       "The Control hierarchical pin LOS is the active-low net LOS_N on the Control sheet. CAN_H, CAN_L and AUX run Controller <-> Connector.", (25.4, 262), 1.5)
s.save(PATH)
print("wrote", PATH)
