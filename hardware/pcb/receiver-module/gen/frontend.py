#!/usr/bin/env python3
"""Generate frontend.kicad_sch (revision 2, spec section 2): APD -> OPA857 TIA -> AC coupling -> OPA855 x7
-> low-pass -> AC coupling -> SDET_P. Run from anywhere: python3 gen/frontend.py"""
import os, sys, textwrap
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

# Freeze guard: layout started 2026-10-09; see gen/FROZEN.
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "FROZEN")):
    sys.stderr.write("generators are frozen since 2026-10-09 (layout started); see gen/FROZEN\n")
    sys.exit(2)

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/frontend.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
TP = "AharoniLab_Connector:TestPoint"
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
R1206 = "AharoniLab_Resistor_SMD:R_1206_3216Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
C402 = "AharoniLab_Capacitor_SMD:C_0402_1005Metric_N"
C1210 = "AharoniLab_Capacitor_SMD:C_1210_3225Metric_N"
G = 1.27

s = Sheet.load(PATH)


def _prop(inst, name):
    for e in s.symbols[s.instances.index(inst)]:
        if isinstance(e, list) and e and e[0] == "property" and str(e[1]) == name:
            return e


def tpos(inst, name, dx, dy, just=None, rot=0):
    """Move a Reference/Value text to (dx, dy) mm from the symbol origin."""
    e = _prop(inst, name)
    e[3] = ["at", round(inst.at[0] + dx, 4), round(inst.at[1] + dy, 4), 90 if inst.rot in (90, 270) else 0]
    for i, it in enumerate(e):
        if isinstance(it, list) and it and it[0] == "effects":
            fx = ["effects", ["font", ["size", 1.27, 1.27]]]
            if just and just != "center":
                fx.append(["justify"] + just.split())
            e[i] = fx


def rv(ref, val, at, fp=R603, rot=0, dnp=False, side="r"):
    """Resistor; side 'r' puts ref/value right of a vertical part, 'a' above a horizontal one."""
    i = s.place(R, ref, val, at, rot=rot, footprint=fp, dnp=dnp)
    labels(i, rot, side)
    return i


def cv(ref, val, at, fp=C603, rot=0, side="r"):
    i = s.place(C, ref, val, at, rot=rot, footprint=fp)
    labels(i, rot, side)
    return i


def labels(i, rot, side):
    if rot in (90, 270):      # horizontal part: text above
        tpos(i, "Reference", 0, -3.81, "center")
        tpos(i, "Value", 0, -2.2, "center")
    else:                     # vertical part: text to the right
        tpos(i, "Reference", 2.0, -1.27, "left")
        tpos(i, "Value", 2.0, 0.0, "left")


def gnd(pt, n=2.54):
    return s.stub(pt, "d", n, "GND", kind="global")


def tp(ref, name, at, rot=0):
    i = s.place(TP, ref, name, at, rot=rot, footprint=TPFP)
    tpos(i, "Reference", 1.9, -0.6, "left"); tpos(i, "Value", 1.9, 0.9, "left")
    return i


def block(title, lines, at, width=110, size=1.5):
    out = [title]
    for ln in lines:
        out += textwrap.wrap(ln, width=width, subsequent_indent="           ")
    s.text("\n".join(out), at, size)

# ======================== stage 1: APD with stage-2 HV filter ======================
YA = 101.6
s.hier_label("APD_BIAS", (30.48, YA), 180, "input")
r50 = rv("R50", "10k", (50.8, YA), R1206, rot=90)
s.wire([(30.48, YA), r50.pin("1")])
d10 = s.place("AharoniLab_Passive:S12023-10", "D10", "S12023-10", (60.96, 121.92))
s.wire([r50.pin("2"), (55.88, YA), (55.88, 121.92)])             # HV_K down to the cathode
s.label("HV_K", (55.88, 106.68), 0)
c50 = cv("C50", "10n", (50.8, 111.76), C1210)
s.wire([(55.88, 109.22), c50.pin("1")])
gnd(c50.pin("2"))
s.wire([d10.pin("CASE"), (59.69, 127.0), (57.15, 127.0)])
s.global_label("GND", (57.15, 127.0), 180)
tpos(d10, "Reference", 0, -6.35, "center"); tpos(d10, "Value", 0, -4.8, "center")

d11 = s.place("AharoniLab_Passive:FDS010", "D11", "FDS010", (35.56, 121.92), dnp=True)
s.stub(d11.pin("K"), "l", 2.54, "HV_K")
s.stub(d11.pin("A"), "r", 2.54, "TIA_IN")
gnd(d11.pin("CASE"))
tpos(d11, "Reference", 0, -6.35, "center"); tpos(d11, "Value", 0, -4.8, "center")

# ======================== stage 2: OPA857 TIA =====================================
XO, YO = 101.6, 132.08
u10 = s.place("AharoniLab_OpAmp:OPA857", "U10", "OPA857", (XO, YO))
s.wire([d10.pin("A"), (66.04, 121.92), (66.04, 127.0), u10.pin("IN")])
s.label("TIA_IN", (68.58, 127.0), 0)
# VS+ (9, 10, 11) bus at x = 71.12, rail at y = 101.6
for n in ("9", "10", "11"):
    p = u10.pin(n)
    s.wire([p, (71.12, p[1])])
s.wire([(71.12, 121.92), (71.12, YA)])
s.hier_label("3V3", (66.04, YA), 180, "input")
s.wire([(66.04, YA), (71.12, YA)])
s.wire([(71.12, YA), (99.06, YA)])
for ref, val, fp, x in (("C56", "100n", C402, 78.74), ("C57", "100n", C402, 88.9), ("C59", "1u", C603, 99.06)):
    c = cv(ref, val, (x, 104.14), fp)
    s.wire([(x, YA), c.pin("1")])
    gnd(c.pin("2"))
s.stub(u10.pin("14"), "l", 2.54, "3V3")
s.stub(u10.pin("13"), "l", 2.54, "GND", kind="global")
# OPA857 pin 16 is a no_connect-type pin: left open, no flag needed
# CTRL: R57 pull-up + JP10 jumper on the bus x = 53.34
s.wire([u10.pin("CTRL"), (53.34, 132.08), (53.34, 154.94)])
s.wire([(53.34, 137.16), (55.88, 137.16)])
s.hier_label("TIA_CTRL", (55.88, 137.16), 0, "input")
r57 = rv("R57", "100k", (48.26, 139.7))
tpos(r57, "Reference", -2.0, -1.27, "right"); tpos(r57, "Value", -2.0, 0.0, "right")
s.stub(r57.pin("1"), "u", 2.54, "3V3")
s.wire([r57.pin("2"), (53.34, 142.24)])
jp = s.place("AharoniLab_Connector:SolderJumper_3_Open", "JP10", "3V3=20k", (40.64, 154.94), rot=90)
s.stub(jp.pin("3"), "u", 2.54, "3V3")
s.stub(jp.pin("1"), "d", 2.54, "GND", kind="global")
s.wire([jp.pin("2"), (53.34, 154.94)])
tpos(jp, "Reference", -7.0, -0.6, "center"); tpos(jp, "Value", -7.0, 0.9, "center")
s.text("CTRL: R57 gives 20k; JP10 B-C forces 20k, A-C forces 5k", (30.48, 170.0), 1.27)
# GND bus on the right side of the OPA857
gx = 132.08
for n in ("1", "3", "4", "6", "7", "12", "17"):
    p = u10.pin(n)
    s.wire([p, (gx, p[1])])
s.wire([(gx, u10.pin("1")[1]), (gx, u10.pin("17")[1])])
gnd((gx, u10.pin("17")[1]))
# outputs
YM = 116.84                                  # main signal row
out, outn = u10.pin("OUT"), u10.pin("OUTN")
tp12 = tp("TP12", "TIA_REF", (134.62, 121.92), 180)
s.wire([outn, tp12.pin("1")])
_p = _prop(tp12, "Value"); _p.insert(4, ["hide", "yes"])

# ======================== stage 3: coupling into the post-amp ==================
s.wire([out, (130.81, YM)])                    # TIA_OUT
c51 = cv("C51", "100n", (137.16, YM), C603, rot=90)
s.wire([(130.81, YM), c51.pin("1")])
# TIA_TAP: R58 1k to the Monitor sheet's RSSI pick-off
s.wire([(130.81, YM), (130.81, 106.68), (134.62, 106.68)])
r58 = rv("R58", "1k", (137.16, 106.68), rot=90)
s.wire([(134.62, 106.68), r58.pin("1")])
s.wire([r58.pin("2"), (144.78, 106.68)])
s.hier_label("TIA_TAP", (144.78, 106.68), 0, "output")
s.wire([c51.pin("2"), (142.24, YM), (167.64 + 30.48, YM)])      # PA_IN to U11 IN+
s.label("PA_IN", (149.86, YM), 0)
r51 = rv("R51", "1k", (142.24, 121.92))
s.wire([(142.24, YM), r51.pin("1")])
s.stub(r51.pin("2"), "d", 2.54, "VCM_REF")
_vp = r51.pin("2")
s.wire([_vp, (_vp[0] - 7.62, _vp[1])])
s.hier_label("VCM_REF", (_vp[0] - 7.62, _vp[1]), 180, "input")

# ======================== stage 4: OPA855 x7 ======================================
DX = 30.48                                    # stage 4 sits DX to the right of the first draft
XA, YAm = 175.26 + DX, 114.3
u11 = s.place("AharoniLab_OpAmp:OPA855IDSGR", "U11", "OPA855IDSGR", (XA, YAm), mirror="x")
tpos(u11, "Reference", 0.0, 10.0, "left"); tpos(u11, "Value", 0.0, 11.6, "left")
assert abs(u11.pin("IN+")[0] - (167.64 + DX)) < 1e-6 and abs(u11.pin("IN+")[1] - YM) < 1e-6
s.wire([(142.24, YM), u11.pin("IN+")]) if False else None
inm = u11.pin("IN-")
# RG to PA_REF (VCM_REF decoupled)
xr = 157.48 + DX
s.wire([inm, (xr, inm[1])])
r54 = rv("R54", "49.9", (xr, 106.68))
tpos(r54, "Reference", -2.0, -1.27, "right"); tpos(r54, "Value", -2.0, 0.0, "right")
s.wire([(xr, inm[1]), r54.pin("2")])
s.wire([r54.pin("1"), (xr, 101.6)])
r60 = rv("R60", "10", (xr, 96.52))
tpos(r60, "Reference", -2.0, -1.27, "right"); tpos(r60, "Value", -2.0, 0.0, "right")
s.wire([(xr, 101.6), r60.pin("2")])
s.stub(r60.pin("1"), "u", 2.54, "VCM_REF")
c53 = cv("C53", "1u", (xr - 10.16, 104.14), C603)
tpos(c53, "Reference", -2.0, -1.27, "right"); tpos(c53, "Value", -2.0, 0.0, "right")
s.wire([(xr, 101.6), (xr - 10.16, 101.6)])
gnd(c53.pin("2"))
s.label("PA_REF", (xr - 2.54, 101.6), 0) if False else None
# RF loop: FB -> right -> up -> left (RF) -> down -> IN-
fb = u11.pin("FB")
r53 = rv("R53", "301", (XA, 93.98), rot=90)
xl = 162.56 + DX
s.wire([fb, (190.5 + DX, fb[1]), (190.5 + DX, 93.98), r53.pin("2")])
s.wire([r53.pin("1"), (xl, 93.98), (xl, inm[1])])
# VS-/EP to GND (top), PD high, VS+ decoupling (bottom)
vm, ep = u11.pin("VS-"), u11.pin("EP")
s.wire([vm, (vm[0], 104.14), (ep[0], 104.14), ep])
s.wire([((vm[0] + ep[0]) / 2, 104.14), ((vm[0] + ep[0]) / 2, 101.6)])
s.global_label("GND", ((vm[0] + ep[0]) / 2, 101.6), 90)
pd = u11.pin("PD")
s.stub(pd, "r", 2.54, "3V3")
vp = u11.pin("VS+")
s.wire([vp, (vp[0], 132.08)])
s.wire([(167.64 + DX, 132.08), (180.34 + DX, 132.08)])      # rail starts at the C52 tap (no loose end)
s.stub((180.34 + DX, 132.08), "r", 2.54, "3V3")
c52 = cv("C52", "100n", (167.64 + DX, 134.62), C402)
c58 = cv("C58", "1u", (177.8 + DX, 134.62), C603)
s.wire([(167.64 + DX, 132.08), c52.pin("1")]); s.wire([(177.8 + DX, 132.08), c58.pin("1")])
gnd(c52.pin("2")); gnd(c58.pin("2"))

# ======================== stage 5: low-pass ======================================
o = u11.pin("OUT")
YO5 = o[1]
s.wire([o, (193.04 + DX, YO5)])
tp10 = tp("TP10", "PA_OUT", (190.5 + DX - 1.27*0, 121.92), 0)
s.wire([(190.5 + DX, YO5), tp10.pin("1")])
s.label("PA_OUT", (186.69 + DX, 111.76), 0) if False else None
r56 = rv("R56", "49.9", (195.58 + DX, YO5), rot=90)
s.wire([(193.04 + DX, YO5), r56.pin("1")])
XL5 = 205.74 + DX
s.wire([r56.pin("2"), (XL5, YO5)])
c54 = cv("C54", "47p", (XL5, 119.38), C603)
s.wire([(XL5, YO5), c54.pin("1")])
gnd(c54.pin("2"))
s.label("LPF_OUT", (XL5 + 1.27, YO5), 0)
# ======================== stage 6: coupling to the comparator ========================
c55 = cv("C55", "100n", (XL5 + 12.7, YO5), C603, rot=90)
s.wire([(XL5, YO5), c55.pin("1")])
xs = XL5 + 25.4
s.wire([c55.pin("2"), (xs, YO5), (xs + 12.7, YO5)])
s.hier_label("SDET_P", (xs + 12.7, YO5), 0, "output")
tp11 = tp("TP11", "SDET_P", (xs + 5.08, 109.22), 0)
s.wire([(xs + 5.08, YO5), tp11.pin("1")])
r59 = rv("R59", "1k", (xs, 119.38))
s.wire([(xs, YO5), r59.pin("1")])
s.stub(r59.pin("2"), "d", 2.54, "VCM_REF")

# ======================== text =========================================================
s.text("Front end: APD -> OPA857 TIA -> AC coupling -> OPA855 x7 -> low-pass -> AC coupling -> SDET_P (baseline VCM_REF)", (30.48, 30.48), 2.5)
for x, t in ((30.48, "1 APD + HV filter"), (66.04, "2 OPA857 TIA, 3.3 V"), (130.0, "3 AC coupling + RSSI tap"),
             (170.0, "4 OPA855, G = 1 + 301/49.9 = 7"), (228.6, "5 low-pass 68 MHz"), (256.0, "6 AC coupling")):
    s.text(t, (x, 76.0), 1.5)
BL = 175.0
block("Design intent (revision 2, decision 12; nothing here is simulated or measured)", [
    "PROPOSED   Chain: S12023-10 APD, OPA857 TIA (20k/5k), AC coupling C51/R51, OPA855 non-inverting gain 7, 68 MHz low-pass, AC coupling "
    "C55/R59 to SDET_P. DC level of the whole post-amp path is VCM_REF (1.65 V from the Monitor sheet), so the output idles at the comparator baseline.",
    "PROPOSED   Stage 2 HV filter R50 10k (1206, 200 V) + C50 10n (1210, 500 V C0G) at the cathode; stage 1 is on the Power sheet. "
    "HV_K is up to 220 V: keep-out to TIA_IN (200 V creepage/clearance), no HV test points.",
    "VERIFIED   OPA857 (SBOS630D): bias APD cathode to positive supply, anode to IN, so the output swings DOWN below OUTN = 1.83 V "
    "(p.19, 8.2.1.2 step 2; p.15, 7.3.1). Test_SD (13) GND, Test_IN (14) 3V3 (p.4 pin table). CTRL 1 = 20k, 0 = 5k (p.6).",
    "VERIFIED   OPA855 (SBOS622D): FB (pin 1) is internally the amplifier output; RF goes FB to IN- on the same side of the package, "
    "OUT drives the load, NC pin 2 stays open (p.17, 8.3.2, Fig. 8-4). PD high = on, enable threshold 1.5 V typ / 1.8 V max above VS-; "
    "PD bias 70 uA typ, 140 uA max (p.7), so PD goes straight to 3V3 (a 10k would drop 0.7-1.4 V). Thermal pad to VS- (p.20, 8.4.1; p.29).",
    "VERIFIED   OPA855 input common-mode 1.3 V max low to 2.7 V min high at VS+ = 3.3 V (p.6): VCM_REF 1.65 V is inside. Overdrive recovery 3 ns "
    "(p.6). Datasheet gain-7 test values are RF 453 / RG about 75 (Fig. 7-3, p.15); no RF/RG table exists, so 301/49.9 (G = 7.03) is PROPOSED: "
    "lower resistances load the output less than the test values on a 3.3 V part. UNRESOLVED: stability with RF 301 not checked.",
    "PROPOSED   RG returns to PA_REF = VCM_REF through R60 10 ohm with C53 1u to GND, so gain is referenced to the baseline and the 1u cap does not load "
    "the Monitor sheet's VCM_REF buffer. Input return R51 1k to VCM_REF (corner 1.6 kHz, 100 us). OPA855 IB -12 uA typ (p.6) into 1k gives about +80 mV "
    "output offset (derived), which moves the idle point to about 1.73 V, close to the 1.75 V mid-swing of the 1.15 to 2.35 V output limits (p.7).",
    "PROPOSED   Clip level (derived): 1.15 Vpp / (7 x 18.2k) = 9 uA at 20k, 36.5 uA at 5k; OPA857 saturates at 60 uA / 240 uA (p.15, 7.3.1). "
    "Output is AC coupled after the clipping amplifier so clipping is symmetric about the baseline.",
    "PROPOSED   Low-pass R56 49.9 + C54 47p = 68 MHz (research 60-80 MHz). SDET_P: C55 100n, R59 1k to VCM_REF (matched to the 1k on the Slicer's IN- side). "
    "TP10 PA_OUT, TP11 SDET_P, TP12 TIA_REF. TIA_TAP = TIA_OUT through R58 1k to the RSSI detector.",
    "UNRESOLVED OPA857 stability and bandwidth at 6 pF source capacitance (datasheet characterises 1.5 pF, p.6). OPA855 stability at G = 7 into the "
    "49.9 ohm / 47 pF load not simulated. Received power not measured."], (30.48, 186))
place_done = True
s.save(PATH)
print("wrote", PATH)
