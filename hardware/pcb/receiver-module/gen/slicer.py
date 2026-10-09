#!/usr/bin/env python3
"""Generate slicer.kicad_sch (revision 2, spec section 3): threshold network | TLV3605 | LVDS out.
Run from anywhere: python3 gen/slicer.py"""
import os, sys, textwrap
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

# Freeze guard: layout started 2026-10-09; see gen/FROZEN.
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "FROZEN")):
    sys.stderr.write("generators are frozen since 2026-10-09 (layout started); see gen/FROZEN\n")
    sys.exit(2)

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/slicer.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
TP = "AharoniLab_Connector:TestPoint"
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
C402 = "AharoniLab_Capacitor_SMD:C_0402_1005Metric_N"

s = Sheet.load(PATH)


def _prop(inst, name):
    for e in s.symbols[s.instances.index(inst)]:
        if isinstance(e, list) and e and e[0] == "property" and str(e[1]) == name:
            return e


def tpos(inst, name, dx, dy, just=None):
    e = _prop(inst, name)
    e[3] = ["at", round(inst.at[0] + dx, 4), round(inst.at[1] + dy, 4), 90 if inst.rot in (90, 270) else 0]
    for i, it in enumerate(e):
        if isinstance(it, list) and it and it[0] == "effects":
            fx = ["effects", ["font", ["size", 1.27, 1.27]]]
            if just and just != "center":
                fx.append(["justify"] + just.split())
            e[i] = fx


def part(lib, ref, val, at, fp, rot=0, dnp=False, left=False):
    i = s.place(lib, ref, val, at, rot=rot, footprint=fp, dnp=dnp)
    if rot in (90, 270):
        tpos(i, "Reference", 0, -3.81, "center"); tpos(i, "Value", 0, -2.2, "center")
    elif left:
        tpos(i, "Reference", -2.0, -1.27, "right"); tpos(i, "Value", -2.0, 0.0, "right")
    else:
        tpos(i, "Reference", 2.0, -1.27, "left"); tpos(i, "Value", 2.0, 0.0, "left")
    return i


def gnd(pt, n=2.54):
    return s.stub(pt, "d", n, "GND", kind="global")


def tp(ref, name, at, dnp=False):
    i = s.place(TP, ref, name, at, footprint=TPFP, dnp=dnp)
    tpos(i, "Reference", 1.9, -0.6, "left"); tpos(i, "Value", 1.9, 0.9, "left")
    return i


def block(title, lines, at, width=110, size=1.5):
    out = [title]
    for ln in lines:
        out += textwrap.wrap(ln, width=width, subsequent_indent="           ")
    s.text("\n".join(out), at, size)


XU, YU = 200.66, 127.0
u = s.place("AharoniLab_OpAmp:TLV3605RVKR", "U20", "TLV3605RVKR", (XU, YU))
tpos(u, "Reference", 12.7, 9.5, "left"); tpos(u, "Value", 12.7, 11.1, "left")
inp, inm = u.pin("IN+"), u.pin("IN-")
shdn, le = u.pin("SHDN"), u.pin("LE/HYS")
op, om = u.pin("OUT+"), u.pin("OUT-")
XR = 175.26                                    # IN+ riser

# ------------------------- SDET_P (IN+) ------------------------------------------
YS = 106.68
s.hier_label("SDET_P", (101.6, YS), 180, "input")
s.wire([(101.6, YS), (XR, YS)])
s.wire([inp, (XR, inp[1]), (XR, 96.52)])
tp21 = tp("TP21", "SDET_P", (114.3, 101.6), dnp=True)
s.wire([(114.3, YS), tp21.pin("1")])
s.label("SDET_P", (127.0, YS), 0)

# ------------------------- hysteresis: OUT+ -> C87 + R87 -> IN+ ----------------------------
XF = 231.14
yo = op[1]
s.wire([op, (XF, yo)])
s.wire([(XF, yo), (XF, 96.52)])
r87 = part(R, "R87", "5.49k", (223.52, 96.52), R603, rot=90)
c87 = part(C, "C87", "100p", (208.28, 96.52), C603, rot=90)
s.wire([(XF, 96.52), r87.pin("2")])
s.wire([r87.pin("1"), c87.pin("2")])
s.wire([c87.pin("1"), (XR, 96.52)])
s.text("positive feedback, AC coupled", (203.2, 90.0), 1.27)

# ------------------------- IN- row = SDET_N threshold node --------------------------------
YN = inm[1]
s.wire([inm, (167.64, YN)])
r84 = part(R, "R84", "1k", (177.8, 129.54), R603, left=True)
s.wire([(177.8, YN), r84.pin("1")])
s.wire([r84.pin("2"), (177.8, 147.32)])
s.hier_label("VCM_REF", (127.0, 147.32), 180, "input")
s.wire([(127.0, 147.32), (177.8, 147.32)])
tp20 = tp("TP20", "SDET_N", (160.02, 119.38))
s.wire([(160.02, YN), tp20.pin("1")])
r85 = part(R, "R85", "100k", (167.64, 129.54), R603, left=True)
s.wire([(167.64, YN), r85.pin("1")])
s.wire([r85.pin("2"), (167.64, 142.24)])
s.hier_label("DAC_TH", (127.0, 142.24), 180, "input")
s.wire([(127.0, 142.24), (167.64, 142.24)])
c84 = part(C, "C84", "10n", (157.48, 129.54), C603, left=True)
s.wire([(157.48, YN), c84.pin("1")])
gnd(c84.pin("2"))
s.wire([(167.64, YN), (152.4, YN)])
r86 = part(R, "R86", "10k", (149.86, YN), R603, rot=90)
s.wire([(152.4, YN), r86.pin("2")])
s.hier_label("VTH_MON", (139.7, YN), 180, "output")
s.wire([r86.pin("1"), (139.7, YN)])
s.label("SDET_N", (169.0, YN), 0) if False else None

# ------------------------- SHDN_N (outer column) and LE_HYS (inner column) -------------------------
XS, XL = 180.34, 185.42
s.wire([shdn, (XS, shdn[1]), (XS, 154.94)])
s.wire([(XS, 152.4), (170.18, 152.4)])
s.hier_label("SHDN_N", (170.18, 152.4), 180, "input")
r81 = part(R, "R81", "10k", (XS, 157.48), R603, left=True)
s.stub(r81.pin("2"), "d", 2.54, "3V3")
s.wire([le, (XL, le[1]), (XL, 154.94)])
r82 = part(R, "R82", "150k", (XL, 157.48), R603, dnp=True)
gnd(r82.pin("2"))
r83 = part(R, "R83", "0R", (193.04, 152.4), R603, rot=90, dnp=True)
s.wire([(XL, 152.4), r83.pin("1")])
s.hier_label("LE_HYS", (203.2, 152.4), 0, "input")
s.wire([r83.pin("2"), (203.2, 152.4)])

# ------------------------- LVDS outputs ---------------------------------------------------
XO = 246.38
s.wire([(XF, yo), (XO, yo)])
s.hier_label("LVDS_P", (XO, yo), 0, "output")
s.wire([om, (XO, om[1])])
s.hier_label("LVDS_N", (XO, om[1]), 0, "output")
s.text("100 ohm termination R180 is across U50 A/B on the Connector sheet", (236.0, 133.0), 1.27)

# ------------------------- ground ---------------------------------------------------------
vee, ep = u.pin("VEE"), u.pin("EP")
s.wire([vee, (vee[0], vee[1] + 2.54), (ep[0], vee[1] + 2.54), ep])
s.wire([((vee[0] + ep[0]) / 2, vee[1] + 2.54), ((vee[0] + ep[0]) / 2, vee[1] + 5.08)])
s.global_label("GND", ((vee[0] + ep[0]) / 2, vee[1] + 5.08), 270)

# ------------------------- supplies --------------------------------------------------------
vcci, vcco = u.pin("VCCI"), u.pin("VCCO")
RAIL = 101.6
s.wire([(185.42, RAIL), (215.9, RAIL)])                         # rail starts at the C81 tap (no loose end)
s.hier_label("3V3", (215.9, RAIL), 0, "input")
s.wire([vcci, (vcci[0], RAIL)])
for ref, val, fp, x in (("C81", "1u", C603, 185.42), ("C80", "100n", C402, 193.04)):
    c = part(C, ref, val, (x, RAIL + 2.54), fp, left=True)
    s.wire([(x, RAIL), c.pin("1")])
    gnd(c.pin("2"))
r80 = part(R, "R80", "0R", (vcco[0], RAIL + 2.54), R603, left=True)
s.wire([(vcco[0], RAIL), r80.pin("1")])
s.wire([r80.pin("2"), vcco])
YB = 106.68
s.wire([(vcco[0], YB), (223.52, YB)])
for ref, val, fp, x in (("C82", "100n", C402, 213.36), ("C83", "1u", C603, 223.52)):
    c = part(C, ref, val, (x, YB + 2.54), fp)
    s.wire([(x, YB), c.pin("1")])
    gnd(c.pin("2"))
flg = s.place("power:PWR_FLAG", "#FLG10", "PWR_FLAG", (208.28, YB), in_bom=False)
_p = _prop(flg, "Reference"); _p.insert(4, ["hide", "yes"])

# ------------------------- text -------------------------------------------------------------
s.text("Slicer: SDET_P is compared with the VCM_REF baseline (SDET_N, trimmed by DAC_TH) in a TLV3605 with 3 mV external hysteresis; LVDS out.", (101.6, 30.48), 2.5)
for x, t in ((101.6, "1 inputs: SDET_P, threshold network SDET_N"), (200.0, "2 TLV3605 comparator"), (236.0, "3 LVDS out")):
    s.text(t, (x, 78.0), 1.5)
block("Design intent (revision 2, decision 12; nothing here is simulated or measured)", [
    "PROPOSED   The signal arrives already AC coupled and referenced to VCM_REF (Front End sheet). With 8b/10b the eye centre is that baseline, so IN- is "
    "the same baseline plus a small trim: no peak tracking. Light on makes SDET_P go BELOW the baseline (OPA857 output swings down, SBOS630D p.19), so "
    "LVDS_P is LOW for a one: the FPGA must invert, or LVDS_P/N be swapped at the FPGA.",
    "PROPOSED   Threshold SDET_N: R84 1k from VCM_REF (matches the 1k return R59 on IN+, so bias currents cancel: IB -1 uA typ / +-5 uA max, IOS +-1 uA, "
    "SNOSDA2F p.7; a single 1k would give 1 mV typ / 5 mV max, 10k would give 10 / 50 mV). DAC_TH through R85 100k: trim = (DAC - VCM_REF) x 1k/101k, "
    "so a 0 to 3.3 V DAC with VCM_REF 1.65 V moves the threshold +-16.3 mV (8 uV per 12-bit LSB). C84 10n to GND keeps IN- quiet (corner 16 kHz). "
    "VTH_MON = SDET_N through R86 10k for the ADC.",
    "PROPOSED   External hysteresis (research 2-4 mV; the internal LE/HYS pin cannot go below about 8 mV, SNOSDA2F p.8, Fig. 7-4 p.16): positive feedback from "
    "OUT+ to IN+ through R87 5.49k in series with C87 100p. OUT+ swings 350 mVpp (VOD 350 mV typ, VOCM 1.2 V, p.7). Source seen at IN+ at signal speed = "
    "49.9 ohm (R56) || 1k (R59) = 47.5 ohm. Window = 350 mV x 47.5/(5490 + 47.5) = 3.0 mV. C87 blocks DC: a bare resistor would shift IN+ by "
    "(1.2 - 1.65) x 1k/(1k + 5.49k) = -69 mV. High-pass corner 1/(2 pi x 5.54k x 100p) = 287 kHz, tau 554 ns, so a 100 ns run (5 UI) keeps 83 % of the "
    "window. The spec text of about 100k with a 1k source only holds for slow (DC) states: at 50 MHz edges it gives 0.17 mV. UNRESOLVED: effect on jitter not simulated.",
    "PROPOSED   LE/HYS (pin 8) left open = internal hysteresis 0 mV and latch off (p.8). R82 150k to GND (30 mV, DNP) and R83 0R to LE_HYS (DNP) are footprints "
    "only. SHDN (pin 7): R81 10k pull-up, SHDN_N active low (VIH 1.5 V, VIL 0.4 V, p.8); shutdown is not a guaranteed zero output (standing correction 11).",
    "VERIFIED   VCCI = VCCO = 3V3 (2.4 to 5.5 V, p.19); 100 nF 0402 + 1 uF at each of VCCI and VCCO, VCCO through R80 0R (bead option). VEE and EP to GND "
    "(datasheet gives no pad requirement beyond a ground plane). PWR_FLAG on the VCCO net because R80 is passive.",
    "PROPOSED   LVDS: OUT+ = LVDS_P, OUT- = LVDS_N; 100 ohm termination R180 across the A/B inputs of the fan-out buffer U50 on the Connector sheet, a few cm away (revision 4; SN65LVDS104 has no on-chip termination, LVDS104 p.16 Fig. 25; the ECP5 end is terminated with DIFFRESISTOR, docs/research/ulx3s-lvds-input.md). TP20 SDET_N, TP21 SDET_P (DNP, "
    "the probe loads the input).",
    "UNRESOLVED Comparator input noise and delay below 10 mV overdrive are not in the datasheet (docs/research/post-amp-slicer.md section 1); IB at VCM = 1.65 V is "
    "not specified."], (101.6, 172))
s.save(PATH)
print("wrote", PATH)
