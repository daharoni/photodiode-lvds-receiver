#!/usr/bin/env python3
"""Generate receiver-module.kicad_sch (root): six hierarchical sheet symbols joined by local labels.
Run LAST (after power, frontend, slicer, control, connector, controller): python3 gen/root.py
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
    if not os.path.exists(os.path.join(D, fn_)):
        continue   # e.g. detector.kicad_sch was removed in decision 12
    nm = {"controller.kicad_sch": "Controller", "control.kicad_sch": "Monitor"}.get(fn_, str(pr["Sheetname"]))
    ident[fn_] = (nm, str(find(sh, "uuid")[1]), str(pg))
# file -> (column, y, ordered input pins, ordered output pins)
COL = [38.1, 119.38, 195.58, 271.78]
W = 35.56
# file -> (column, y, inputs, outputs, bidirectional)
LAYOUT = {
    "power.kicad_sch":     (0, 55.88,  ["VBUS", "DAC_HV", "HV_DIS"], ["3V3", "3V3_D", "APD_BIAS", "HV_MON"], []),
    "frontend.kicad_sch":  (1, 55.88,  ["APD_BIAS", "3V3", "TIA_CTRL", "VCM_REF"], ["SDET_P", "TIA_TAP"], []),
    "slicer.kicad_sch":    (2, 55.88,  ["SDET_P", "VCM_REF", "DAC_TH", "3V3", "SHDN_N", "LE_HYS"],
                            ["LVDS_P", "LVDS_N", "VTH_MON"], []),
    "connector.kicad_sch": (3, 55.88,  ["LVDS_P", "LVDS_N", "RSSI", "HV_MON", "3V3", "3V3_D"],
                            ["VBUS", "CC1_SENSE", "CC2_SENSE"], ["USB_DP", "USB_DM", "CAN_H", "CAN_L", "AUX"]),
    "control.kicad_sch":   (1, 134.62, ["3V3", "TIA_TAP"], ["VCM_REF", "RSSI"], []),
    "controller.kicad_sch": (2, 134.62, ["3V3_D", "HV_MON", "RSSI", "VTH_MON", "VBUS", "CC1_SENSE", "CC2_SENSE"],
                            ["DAC_TH", "DAC_HV", "HV_DIS", "SHDN_N", "LE_HYS", "TIA_CTRL"],
                            ["USB_DP", "USB_DM", "CAN_H", "CAN_L", "AUX"]),
}
assert set(LAYOUT) == set(ident), (set(LAYOUT) ^ set(ident))

s = Sheet.load(PATH)
s.text("Root sheet. Signal flow: Power -> Front End -> Slicer/LVDS -> Connector. No AGC loop and no detector sheet (decision 12).\n"
       "Monitor sheet buffers VCM_REF (1.65 V baseline) and the RSSI minimum detector from TIA_TAP; the Controller (ESP32-C6, decisions 11/12) sets\n"
       "DAC_TH/DAC_HV/HV_DIS/SHDN_N/LE_HYS/TIA_CTRL, reads HV_MON/RSSI/VTH_MON, and talks CAN through the Connector; the single USB-C J50 on the Connector sheet carries VBUS, USB, LVDS, CAN and AUX (decision 14).\n"
       "Status labels VERIFIED/PROPOSED/UNRESOLVED; no part values approved for fabrication.", (25.4, 15), 1.5)
s.text("Rails VBUS (Connector -> Power and Controller; the single 5 V input, decision 14), 3V3, 3V3_D are sheet pins; +5V is internal to Power (U5 TPS259631 eFuse OUT); GND is global. HV_ nets and APD_BIAS are net class HV (1.0 mm clearance).\n"
       "LVDS_P is low for a logic one (post-amp non-inverting after an OPA857 whose OUT swings down with light); the FPGA inverts.", (25.4, 35), 1.5)

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
        s.stub(p, "l" if side == "l" else "r", 5.08 if n != "VBUS" or fn != "power.kicad_sch" else 12.7, n)
        pinpos[(fn, n)] = p

# VBUS driver flag (the Connector output is not a power_out; ERC needs a power_out source). The only flag on VBUS (#FLG60 removed).
px, py = pinpos[("power.kicad_sch", "VBUS")]
s.place("power:PWR_FLAG", "#FLG04", "PWR_FLAG", (px - 6.35, py), in_bom=False)
# GND flag on a global GND label
s.place("power:PWR_FLAG", "#FLG05", "PWR_FLAG", (38.1, 241.3), in_bom=False)
s.wire([(38.1, 241.3), (45.72, 241.3)])
s.global_label("GND", (45.72, 241.3), 0)
s.text("Global net GND enters here only to carry a PWR_FLAG for ERC. USB_DP, USB_DM, AUX, CAN_H, CAN_L run Connector <-> Controller; CC1_SENSE, CC2_SENSE Connector -> Controller.", (25.4, 248.92), 1.5)
s.save(PATH)
print("wrote", PATH)
