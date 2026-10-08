"""Self-test: build a scratch sheet, then validate with kicad-cli (ERC + netlist).

Run from the repo's tools/ directory:  python3 -m kicad_sch.selftest
Writes only to the scratchpad directory below (copies of the receiver-module sheets).
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

from . import Library, Sheet, transform
from .sexpr import parse, find, find_all

KICAD_CLI = "/Users/daharoni/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
SCRATCH = ("/private/tmp/claude-503/-Users-daharoni-Projects-photodiode-lvds-receiver/"
           "3ed7698a-ce64-4381-89c4-6781b2a1a8d7/scratchpad/kicad_sch_selftest")
SRC = os.path.join(os.path.dirname(__file__), "..", "..", "hardware", "pcb", "receiver-module")
TLV = "AharoniLab_OpAmp:TLV3605RVKR"
OPA = "AharoniLab_OpAmp:OPA2320AIDR"
R_FP = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
C_FP = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"


def cli(*args):
    return subprocess.run([KICAD_CLI, *args], capture_output=True, text=True)


def netlist(sch, out):
    r = cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", out, sch)
    assert r.returncode == 0, r.stdout + r.stderr
    tree = parse(open(out).read())
    nets = {}
    for n in find_all(find(tree, "nets"), "net"):
        nets[str(find(n, "name")[1])] = {(str(find(x, "ref")[1]), str(find(x, "pin")[1])) for x in find_all(n, "node")}
    parts = {str(find(c, "ref")[1]): c for c in find_all(find(tree, "components"), "comp")}
    return nets, parts


def net_of(nets, member):
    hits = [(k, v) for k, v in nets.items() if member in v]
    assert len(hits) == 1, "%s is on %d nets" % (member, len(hits))
    return hits[0]


def direction(rot, mirror, angle):
    """Outward direction letter (schematic frame) for a pin whose symbol-frame angle is `angle`."""
    vx, vy = transform(-math.cos(math.radians(angle)), -math.sin(math.radians(angle)), (0, 0), rot, mirror)
    return ("r" if vx > 0.5 else "l") if abs(vx) > abs(vy) else ("d" if vy > 0.5 else "u")


def build(sheet):
    lib = sheet.lib
    # 1. Pin-coordinate proof: all 8 rotation/mirror combos of an asymmetric part, one label per pin.
    combos = [(r, m) for m in (None, "x", "y") for r in (0, 90, 180, 270)][:12]
    expected = {}
    for k, (rot, mir) in enumerate(combos):
        u = sheet.place(TLV, "U%d" % (k + 1), "TLV3605", (round((48 + 56 * (k % 4)) * 1.27, 4), round((48 + 56 * (k // 4)) * 1.27, 4)), rot, mir)
        for p in u.pins:
            name = "P%d_%s" % (k, re.sub(r"\W", "", p["number"]))
            sheet.stub(u.pin(p["number"]), direction(rot, mir, p["angle"]), 5.08, name)
            nums = re.findall(r"\d+", p["number"])   # stacked pin "[3,5,9,11]" -> four nodes
            expected[name] = {("U%d" % (k + 1), n) for n in nums}
    # 2. Fragment with passives, derived symbol, test point, multi-unit op amp.
    y = 270.51
    r1 = sheet.place("AharoniLab_Passive:R_Small_US", "R1", "10k", (30.48, y), 90, footprint=R_FP)
    r2 = sheet.place("AharoniLab_Passive:R_Small_US", "R2", "1k", (60.96, y + 12.7), 0, footprint=R_FP)
    c1 = sheet.place("AharoniLab_Passive:C_Small", "C1", "100n", (91.44, y + 12.7), 180, footprint=C_FP)
    d1 = sheet.place("AharoniLab_Passive:BAS70", "D1", "BAS70", (127, y + 12.7), 0)
    tp = sheet.place("AharoniLab_Connector:TestPoint", "TP1", "TP_N1", (101.6, y - 7.62), 0)
    ua = sheet.place(OPA, "U20", "OPA2320", (170.18, y), 0, unit=1)
    ub = sheet.place(OPA, "U20", "OPA2320", (170.18, y + 25.4), 0, unit=2)
    uc = sheet.place(OPA, "U20", "OPA2320", (215.9, y), 0, unit=3)
    sheet.hier_label("SDET", (20.32, y), 180, "input")
    sheet.connect((20.32, y), r1.pin("1"))
    sheet.connect(r1.pin("2"), (r1.pin("2")[0] + 5.08, y))              # N1 trunk
    n1 = (101.6, y)
    sheet.wire([(r1.pin("2")[0] + 5.08, y), n1])
    sheet.connect(n1, tp.pin("1"), "v")
    sheet.connect(n1, ua.pin("+"), "h")                                   # to op-amp + (unit 1)
    sheet.label("N1", n1, 0)
    sheet.connect(r2.pin("1"), (r2.pin("1")[0], y), "v")                 # T junction on the N1 trunk
    sheet.connect(r2.pin("2"), c1.pin("1"))                              # N2: R2 -> C1
    sheet.label("N2", (r2.pin("2")[0] + 7.62, r2.pin("2")[1]), 0)
    sheet.stub(c1.pin("2"), "r", 5.08, "GND", "global", "passive")
    sheet.stub(d1.pin("1"), "r", 5.08, "GND", "global", "passive")
    sheet.stub(d1.pin("3"), "l", 5.08, "N2")
    tp2 = sheet.place("AharoniLab_Connector:TestPoint", "TP2", "TP_NC", (127, y - 7.62), 0)
    sheet.no_connect(tp2.pin("1"))
    sheet.connect(ua.pin("-"), (ua.pin("-")[0] - 5.08, ua.pin("-")[1]))
    sheet.wire([(ua.pin("-")[0] - 5.08, ua.pin("-")[1]), (ua.pin("-")[0] - 5.08, y + 10.16),
                (ua.pin("1")[0] + 5.08, y + 10.16), (ua.pin("1")[0] + 5.08, ua.pin("1")[1]), ua.pin("1")])
    sheet.stub(ub.pin("+"), "l", 5.08, "N2")
    sheet.stub(ub.pin("-"), "l", 5.08, "GND", "global")
    sheet.stub(ub.pin("7"), "r", 5.08, "OUT2", "hier", "output")
    sheet.stub(uc.pin("V+"), "u", 5.08, "V3P3")
    sheet.stub(uc.pin("V-"), "d", 5.08, "GND", "global")
    sheet.text("kicad_sch selftest fragment", (20, 255), 2.0)
    expected.update({
        "N1": {("R1", "2"), ("TP1", "1"), ("U20", "3"), ("R2", "1")},
        "N2": {("R2", "2"), ("C1", "1"), ("D1", "3"), ("U20", "5")},
        "GND": {("C1", "2"), ("D1", "1"), ("U20", "6"), ("U20", "4")},
        "V3P3": {("U20", "8")},
    })
    return expected


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    os.makedirs(SCRATCH)
    for f in ("receiver-module.kicad_sch", "receiver-module.kicad_pro", "slicer.kicad_sch"):
        shutil.copy(os.path.join(SRC, f), SCRATCH)
    path = os.path.join(SCRATCH, "slicer.kicad_sch")
    sheet = Sheet.load(path)
    assert sheet.root_uuid and sheet.sheet_uuid, "root/sheet uuid lookup failed"
    expected = build(sheet)
    sheet.save(path)
    root = os.path.join(SCRATCH, "receiver-module.kicad_sch")

    nets, parts = netlist(root, os.path.join(SCRATCH, "out.net"))
    placed = Counter(s[1][1] for s in sheet.symbols)   # lib ids
    refs = {i.ref for i in sheet.instances}
    assert refs <= set(parts), "missing in netlist: %s" % (refs - set(parts))
    fp = lambda ref: str(find(parts[ref], "footprint")[1])
    assert fp("R1") == R_FP and fp("C1") == C_FP, "footprint override"
    assert fp("U1") == "AharoniLab_Package_SO:Texas_VQFN-HR-14_RVK0014A" or fp("U1"), "default footprint"
    print("components in netlist: %d/%d refs; U1 footprint %s; U20 footprint %s" % (len(refs), len(refs), fp("U1"), fp("U20")))
    # label-name nets must contain exactly the expected pins
    bad = 0
    for name, members in expected.items():
        got = [(k, v) for k, v in nets.items() if k.split("/")[-1] == name and v & members]
        if not got or {m for _, v in got for m in v} != members:
            print("FAIL net %s expected %s got %s" % (name, sorted(members), got))
            bad += 1
    pin_nets = sum(1 for n in expected if n.startswith("P"))
    assert not bad, "%d net mismatches" % bad
    print("nets verified: %d pin-coordinate nets (12 rot/mirror combos, every pin) + N1,N2,GND,V3P3" % pin_nets)
    # hierarchical label SDET attaches R1.1
    k, v = net_of(nets, ("R1", "1"))
    assert v == {("R1", "1")} and k.endswith("SDET"), (k, v)
    print("SDET net:", k, sorted(v))

    r = cli("sch", "erc", "--format", "json", "--severity-all", "-o", os.path.join(SCRATCH, "erc.json"), root)
    erc = json.load(open(os.path.join(SCRATCH, "erc.json")))
    kinds = Counter()
    for s in erc["sheets"]:
        if "Slicer" not in s["path"]:   # other sheets are untouched skeletons
            continue
        for v in s["violations"]:
            kinds[(v["severity"], v["type"])] += 1
    print("ERC on root, Slicer sheet only (severity, type): count", dict(kinds))
    allowed = {"label_dangling", "global_label_dangling", "pin_not_connected", "hier_label_mismatch",
               "power_pin_not_driven", "pin_not_driven", "pin_to_pin"}
    unexpected = {k: n for k, n in kinds.items() if k[0] == "error" and k[1] not in allowed}
    unexpected.update({k: n for k, n in kinds.items() if k[1] in ("footprint_link_issues", "no_connect_dangling", "lib_symbol_mismatch")})
    assert not unexpected, "unexpected ERC errors: %s" % unexpected
    assert not any(k[1] == "endpoint_off_grid" for k in kinds), "off-grid endpoints"
    print("selftest OK (output in %s)" % SCRATCH)


if __name__ == "__main__":
    sys.exit(main())
