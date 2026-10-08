#!/usr/bin/env python3
"""Generate control.kicad_sch (Rev A, spec section 4: slow AGC / threshold loop).
Run from anywhere: python3 gen/control.py
Coordinates below are written in 1.27 mm grid units (x right, y down); u() converts and applies the origin offset."""
import os, sys, textwrap
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/control.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
TP = "AharoniLab_Connector:TestPoint"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
C1206 = "AharoniLab_Capacitor_SMD:C_1206_3216Metric_N"
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"
OA = "AharoniLab_OpAmp:OPA2320AIDR"
G = 1.27
OX, OY = 10, 0   # page origin offset in grid units (keeps labels clear of the frame)


def u(x, y):
    return ((x + OX) * G, (y + OY) * G)


s = Sheet.load(PATH)


def _sym(inst):
    return s.symbols[s.instances.index(inst)]


def _prop(inst, name):
    for e in _sym(inst):
        if isinstance(e, list) and e and e[0] == "property" and str(e[1]) == name:
            return e


def hide(inst, *names):
    for n in names:
        e = _prop(inst, n)
        if e is not None and ["hide", "yes"] not in e:
            e.insert(4, ["hide", "yes"])


def tpos(inst, name, dx, dy, just=None):
    """Move a visible Reference/Value text to (dx, dy) grid units from the symbol origin."""
    e = _prop(inst, name)
    e[3] = ["at", round(inst.at[0] + dx * G, 4), round(inst.at[1] + dy * G, 4), 90 if inst.rot in (90, 270) else 0]
    for i, it in enumerate(e):
        if isinstance(it, list) and it and it[0] == "effects":
            fx = ["effects", ["font", ["size", 1.27, 1.27]]]
            if just:
                fx.append(["justify"] + just.split())
            e[i] = fx


def hres(inst, dy=2.4):
    """Horizontal resistor/cap: ref above, value below, centred."""
    tpos(inst, "Reference", 0, -dy)
    tpos(inst, "Value", 0, dy)



def r(ref, val, x, y, horiz=False, dnp=False, fp=R603):
    i = s.place(R, ref, val, u(x, y), rot=90 if horiz else 0, footprint=fp, dnp=dnp)
    if horiz:
        hres(i)
    return i


def c(ref, val, x, y, horiz=False, fp=C603):
    i = s.place(C, ref, val, u(x, y), rot=90 if horiz else 0, footprint=fp)
    if horiz:
        hres(i)
    return i


def W(*pts):
    s.wire([u(*p) for p in pts])


def lab(name, x, y, rot=0):
    s.label(name, u(x, y), rot)


def gnd(x, y, rot=270):
    s.global_label("GND", u(x, y), rot)


def v33(x, y, rot=90):
    s.label("3V3", u(x, y), rot)


def tp(ref, name, x, y, up=True):
    t = s.place(TP, ref, name, u(x, y), rot=0 if up else 180, footprint=TPFP)
    return t


def stub_up_gnd(pin, n=2):
    x, y = pin
    s.wire([(x, y), (x, y + n * G)])
    s.global_label("GND", (x, y + n * G), 270)


def stub_down_gnd(pin, n=2):
    stub_up_gnd(pin, n)


def pstub(pin, d, n, label, kind="local"):
    s.stub(pin, d, n * G, label, kind=kind)


def power_unit(ref, x, y, capref, capx):
    """Op-amp power unit 3 with its own 100 nF cap beside it (rails by local/global label)."""
    p = s.place(OA, ref, "OPA2320AIDR", u(x, y), unit=3)
    hide(p, "Value")
    s.stub(p.pin("8"), "u", 2 * G, "3V3")
    s.stub(p.pin("4"), "d", 2 * G, "GND", kind="global")
    cc = c(capref, "100n", capx, y)
    s.stub(cc.pin("1"), "u", 2 * G, "3V3")
    s.stub(cc.pin("2"), "d", 2 * G, "GND", kind="global")
    return p


def divider(x, yc, rt, vt, rb, vb, cref, cval, name, label, tpref=None):
    """3V3 - rt - node - rb - GND; node -> cap to GND and a named label."""
    a = r(rt[0], rt[1], x, yc)
    b = r(rb[0], rb[1], x, yc + 4)
    s.stub(a.pin("1"), "u", 2 * G, "3V3")
    s.stub(b.pin("2"), "d", 2 * G, "GND", kind="global")
    cp = c(cref, cval, x + 8, yc + 4)
    s.stub(cp.pin("2"), "d", 2 * G, "GND", kind="global")
    W((x, yc + 2), (x + 8, yc + 2))
    W((x + 8, yc + 2), (x + 16, yc + 2))
    s.label(name, u(x + 16, yc + 2), 0)
    if tpref:
        W((x + 4, yc + 2), (x + 4, yc - 1))
        tp(tpref, name, x + 4, yc - 1)


# ---- block titles ------------------------------------------------------------
s.text("1. References: VCM_DET, VTARGET, VG_HI/VG_LO, VLOS_TH (all from 3V3 dividers)", u(0, 5), 2)
s.text("2. VMID and VSPAN", u(0, 41), 2)
s.text("3. AGC integrator, freeze switches, clamps", u(96, 41), 2)
s.text("4. LOS comparator and source selectors", u(196, 41), 2)

# ============================ block 1: references =============================
W((14, 16), (8, 16))
s.hier_label("3V3", u(8, 16), 180, "input")
a = r("R100", "10k", 14, 18)
b = r("R101", "10k", 14, 22)
s.stub(a.pin("1"), "u", 2 * G, "3V3")
s.stub(b.pin("2"), "d", 2 * G, "GND", kind="global")
cc = c("C100", "100n", 20, 22)
s.stub(cc.pin("2"), "d", 2 * G, "GND", kind="global")
W((14, 20), (20, 20))
W((20, 20), (34, 20), (34, 24), (40, 24))
u30a = s.place(OA, "U30", "OPA2320AIDR", u(46, 26), unit=1)
hide(u30a, "Value")
W((55, 26), (55, 32), (37, 32), (37, 28), (40, 28))   # unity-gain loop under the amplifier
W((52, 26), (60, 26))
s.hier_label("VCM_DET", u(60, 26), 0, "output")

divider(84, 18, ("R105", "23.2k"), 0, ("R106", "10.0k"), 0, "C103", "1u", "VTARGET", None, "TP33")
divider(112, 18, ("R107", "13k"), 0, ("R108", "20k"), 0, "C104", "1u", "VG_HI", None)
divider(140, 18, ("R109", "100k"), 0, ("R110", "6.8k"), 0, "C105", "1u", "VG_LO", None)
divider(168, 18, ("R111", "100k"), 0, ("R112", "10k"), 0, "C106", "100n", "VLOS_TH", None)

# ============================ block 2: VMID, VSPAN ============================
# VMID
r102 = r("R102", "10k 0.1%", 14, 56)
r103 = r("R103", "10k 0.1%", 14, 60)
W((14, 54), (14, 52), (8, 52))
s.hier_label("VHIGH", u(8, 52), 180, "input")
W((14, 62), (14, 64), (8, 64))
s.hier_label("VLOW", u(8, 64), 180, "input")
c101 = c("C101", "100p", 28, 60)
s.stub(c101.pin("2"), "d", 2 * G, "GND", kind="global")
W((14, 58), (28, 58))
W((28, 58), (34, 58), (34, 56), (40, 56))
u30b = s.place(OA, "U30", "OPA2320AIDR", u(46, 58), unit=2)
hide(u30b, "Value")
W((55, 58), (55, 64), (37, 64), (37, 60), (40, 60))
W((52, 58), (60, 58))
s.hier_label("VMID", u(60, 58), 0, "output")
W((57, 58), (57, 54))
tp("TP32", "VMID", 57, 54)
power_unit("U30", 82, 58, "C109", 88)

# VSPAN subtractor (standing correction 7): R41 VLOW->IN-, R42 OUT->IN-, R43 VHIGH->IN+, R44 IN+->GND
u31a = s.place(OA, "U31", "OPA2320AIDR", u(46, 88), unit=1)
hide(u31a, "Value")
r43 = r("R43", "10k 0.1%", 26, 86, horiz=True)
r44 = r("R44", "10k 0.1%", 34, 82)
r41 = r("R41", "10k 0.1%", 26, 94, horiz=True)
r42 = r("R42", "10k 0.1%", 46, 98, horiz=True)
W((28, 86), (40, 86))
W((34, 84), (34, 86))
s.stub(r44.pin("1"), "u", 2 * G, "GND", kind="global")
s.stub(r43.pin("1"), "l", 3 * G, "VHIGH")
s.stub(r41.pin("1"), "l", 3 * G, "VLOW")
W((28, 94), (37, 94), (37, 90), (40, 90))
W((55, 88), (55, 98), (48, 98))
W((44, 98), (37, 98), (37, 94))
W((52, 88), (60, 88))
s.hier_label("VSPAN", u(60, 88), 0, "output")
W((57, 88), (57, 84))
tp("TP31", "VSPAN", 57, 84)
power_unit("U31", 66, 100, "C110", 72)

# ============================ block 3: integrator + freeze =====================
u33 = s.place("AharoniLab_Misc:TMUX1112PWR", "U33", "TMUX1112PWR", u(120, 104))
# series switch pair in the VSPAN -> R104 path: D1 in (VSPAN), S1-S2 joined, D2 out
s.stub(u33.pin("D1"), "r", 4 * G, "VSPAN")
W((110, 94), (106, 94), (106, 98), (110, 98))      # S1 <-> S2
W((130, 98), (144, 98))                            # D2 -> R104
r104 = r("R104", "100k", 146, 98, horiz=True)
u31b = s.place(OA, "U31", "OPA2320AIDR", u(166, 98), unit=2)
hide(u31b, "Value")
W((148, 98), (156, 98))
W((156, 98), (156, 106))
W((156, 100), (160, 100))
c102 = c("C102", "47n C0G", 166, 106, horiz=True, fp=C1206)
W((156, 106), (164, 106))
W((168, 106), (176, 106), (176, 98))
W((172, 98), (176, 98))
W((160, 96), (157, 96), (157, 92))
lab("VTARGET", 157, 92, 180)
# VINT node, test point, clamps
W((176, 98), (184, 98))
W((176, 98), (176, 93))
tp("TP30", "VINT", 176, 93)
d30 = s.place("AharoniLab_Passive:BAS70", "D30", "BAS70", u(184, 92), rot=270, dnp=True)
hide(d30, "Value")
d31 = s.place("AharoniLab_Passive:BAS70", "D31", "BAS70", u(184, 104), rot=270, dnp=True)
hide(d31, "Value")
W((184, 95), (184, 98))
W((184, 101), (184, 98))
W((184, 89), (184, 87), (188, 87))
lab("VG_HI", 188, 87, 0)
W((184, 107), (184, 109), (188, 109))
lab("VG_LO", 188, 109, 0)
W((184, 98), (190, 98))
lab("VINT", 190, 98, 0)
# freeze switch control inputs
# SEL1 (switch 1) is tied to 3V3 through fitted R120 (0R). LOS_N reaches SEL1 only through DNP R121 (0R, bench option):
# the analog LOS comparator must not freeze the integrator (startup deadlock, see Design intent).
W((110, 110), (100, 110))
r120 = r("R120", "0R", 100, 106)
s.stub(r120.pin("1"), "u", 2 * G, "3V3")
W((100, 108), (100, 110))
r121 = r("R121", "0R DNP", 94, 110, horiz=True, dnp=True)
W((96, 110), (100, 110))
W((92, 110), (92, 106))
lab("LOS_N", 92, 106, 90)
sel2 = u33.pin("SEL2")
W((80, 112), (110, 112))
s.hier_label("HOLD_N", u(80, 112), 180, "input")
r119 = r("R119", "100k", 88, 108)
s.stub(r119.pin("1"), "u", 2 * G, "3V3")
W((88, 110), (88, 112))
# unused switches 3 and 4: sources to GND, drains NC, selects to GND (TMUX1112 datasheet p24: unused pins to GND)
for pn in ("S3", "S4", "SEL3", "SEL4"):
    s.stub(u33.pin(pn), "l", 3 * G, "GND", kind="global")
for pn in ("D3", "D4", "4", "12"):
    s.no_connect(u33.pin(pn))
# supply
W((120, 88), (120, 82))
v = u(120, 82)
s.stub(v, "u", 2 * G, "3V3")
c112 = c("C112", "100n", 132, 84)
W((120, 82), (132, 82))
s.stub(c112.pin("2"), "d", 2 * G, "GND", kind="global")
s.stub(u33.pin("GND"), "d", 2 * G, "GND", kind="global")

# ============================ block 4: LOS comparator ==========================
XL = 8   # extra x offset for block 4
u32 = s.place("AharoniLab_OpAmp:TLV3201AIDBVR", "U32", "TLV3201AIDBVR", u(225 + XL, 100))
r114 = r("R114", "10k", 208 + XL, 98, horiz=True)
W((210 + XL, 98), (219 + XL, 98))
s.stub(r114.pin("1"), "l", 3 * G, "VSPAN")
s.stub(u32.pin("-"), "l", 3 * G, "VLOS_TH")
W((231 + XL, 100), (236 + XL, 100))
W((236 + XL, 100), (236 + XL, 86), (228 + XL, 86))
r113 = r("R113", "1M", 226 + XL, 86, horiz=True)
W((224 + XL, 86), (216 + XL, 86), (216 + XL, 98))
W((236 + XL, 100), (244 + XL, 100))
W((244 + XL, 100), (244 + XL, 97))
lab("LOS_N", 244 + XL, 97, 90)
W((244 + XL, 100), (244 + XL, 104))
tp("TP36", "LOS_N", 244 + XL, 104, up=False)
W((244 + XL, 100), (252 + XL, 100))
s.hier_label("LOS", u(252 + XL, 100), 0, "output")
s.stub(u32.pin("V+"), "u", 2 * G, "3V3")
s.stub(u32.pin("GND"), "d", 2 * G, "GND", kind="global")
c111 = c("C111", "100n", 250 + XL, 88)
s.stub(c111.pin("1"), "u", 2 * G, "3V3")
s.stub(c111.pin("2"), "d", 2 * G, "GND", kind="global")


def selector(y, jpref, jpname, a_net, out_net, man_net, dac_net, rdac, rtrim, rman, cman, rvref, tpref):
    """JP header: pin1 = a_net source, pin2 = common (output), pin3 = manual trimmer."""
    x = 280 + XL
    jp = s.place("AharoniLab_Connector:Conn_01x03", jpref, jpname, u(x, y))
    s.stub(jp.pin("1"), "l", 3 * G, a_net)
    # output row
    W((x - 4, y), (x - 36, y))
    s.hier_label(out_net, u(x - 36, y), 180, "output")
    rd = r(rdac, "0R", x - 18, y - 6, dnp=True)
    W((x - 18, y - 4), (x - 18, y))
    W((x - 18, y - 8), (x - 18, y - 10), (x - 26, y - 10))
    s.hier_label(dac_net, u(x - 26, y - 10), 180, "input")
    W((x - 34, y), (x - 34, y + 4))
    tp(tpref, out_net, x - 34, y + 4, up=False)
    # manual path
    W((x - 4, y + 2), (x - 10, y + 2), (x - 10, y + 8))
    rm = r(rman, "1k", x - 16, y + 8, horiz=True)
    W((x - 14, y + 8), (x - 10, y + 8))
    W((x - 10, y + 8), (x - 10, y + 10))
    cm = c(cman, "100n", x - 10, y + 12)
    s.stub(cm.pin("2"), "d", 2 * G, "GND", kind="global")
    rv = s.place("AharoniLab_Passive:R_Potentiometer_Trim", rtrim, "10k", u(x - 25, y + 12), rot=0,
                 footprint="AharoniLab_Resistor_SMD:Bourns_3224W_SMD")
    tpos(rv, "Reference", -2, -1.2, "right")
    tpos(rv, "Value", -2, 0.4, "right")
    tpos(rm, "Reference", 0, 2.4)
    tpos(rm, "Value", 0, 4.2)
    tpos(rd, "Reference", 3, -0.8, "left")
    tpos(rd, "Value", 3, 0.8, "left")
    W((x - 22, y + 12), (x - 22, y + 8), (x - 18, y + 8))
    s.stub(rv.pin("1"), "u", 2 * G, "3V3")
    s.stub(rv.pin("3"), "d", 2 * G, "GND", kind="global")
    W((x - 10, y + 5), (x - 13, y + 5))
    lab(man_net, x - 13, y + 5, 180)


selector(128, "JP30", "VG_SEL", "VINT", "VG", "VG_MAN", "DAC_GAIN", "R116", "RV30", "R115", "C107", None, "TP34")
selector(166, "JP31", "VTH_SEL", "VMID", "VTH", "VTH_MAN", "DAC_TH", "R118", "RV31", "R117", "C108", None, "TP35")

# ============================ annotations =====================================
def wrap(txt, width):
    out = []
    for ln in txt.split("\n"):
        out += textwrap.wrap(ln, width, subsequent_indent="  ", break_long_words=False) or [""]
    return "\n".join(out)


def note(txt, x, y, size=1.27, width=100):
    s.text(wrap(txt, width), u(x, y), size)


note("VSPAN = VHIGH - VLOW (R41 VLOW->IN-, R42 OUT->IN-,\nR43 VHIGH->IN+, R44 IN+->GND; all 10k 0.1 % matched).\nVMID = (VHIGH + VLOW) / 2: matched pair, unity buffer.", 0, 106)
note("Freeze path: VSPAN -> S1 -> S2 -> R104 (two switches in series). TMUX1112: a switch is closed when SELx = 1\n"
     "(datasheet Table 8-2, p24). SEL1 = 3V3 via R120 (0R fitted; LOS_N only via DNP R121), SEL2 = HOLD_N (1 = run; R119 pull-up).\n"
     "Either switch open: no current in R104, C102 keeps its charge, VINT holds (freeze, not reset).\n"
     "Unused switches 3 and 4: sources and selects to GND, drains NC (datasheet p24).", 96, 50)
note("Integrator: tau = R104 x C102 = 100k x 47 nF = 4.7 ms. IN+ = VTARGET.\n"
     "VSPAN above VTARGET -> VINT ramps down -> VG down -> gain down.", 96, 62)
note("D30 / D31: soft clamp of VINT to VG_LO .. VG_HI (0.2 .. 2.0 V). DNP, UNRESOLVED.", 150, 112)
note("LOS hierarchical pin = net LOS_N (active-low LOS: high = signal present, low = lost).\n"
     "Trip points with R113/R114: VSPAN rising 0.303 V, falling 0.270 V (about 33 mV hysteresis). PROPOSED.\n"
     "Span alone does not prove signal presence.", 196, 48)
note("JP30 VG_SEL: jumper 1-2 = AGC (VINT),\n2-3 = manual trimmer RV30,\nopen + fit R116 = DAC_GAIN drives VG.", 196, 136)
note("JP31 VTH_SEL: jumper 1-2 = VMID,\n2-3 = manual trimmer RV31,\nopen + fit R118 = DAC_TH drives VTH.", 196, 174)

intent = """DESIGN INTENT (Control sheet, Rev A). Status labels: PROPOSED unless stated. Nothing on this sheet is measured or simulated.

WHAT THE LOOP DOES
The slicer's peak detectors give VHIGH (top of the received eye) and VLOW (bottom). VSPAN = VHIGH - VLOW is the eye height. This slow loop (about 5 ms) adjusts the
VCA821 gain control VG so that VSPAN stays at VTARGET (0.994 V), and offers VMID (the eye midpoint) as the comparator threshold VTH.

BLOCKS
1. References: 3V3 dividers give VCM_DET (1.65 V, buffered), VTARGET (0.994 V), VLOS_TH (0.30 V), VG_HI (2.0 V) and VG_LO (0.2 V).
2. VMID is the average of VHIGH and VLOW, the ideal slicing threshold. VSPAN is a four-resistor subtractor; the 0.1 % match of R41-R44 sets the span error.
3. U31B with R104 100k and C102 47 nF is a true integrator (capacitor in the feedback path). It compares VSPAN with VTARGET and accumulates the difference in VINT.
4. U32 compares VSPAN with VLOS_TH and raises LOS_N when the eye is large enough. JP30 / JP31 choose the source of VG and VTH (AGC or VMID, trimmer, or DAC).

SIGN OF THE LOOP (negative feedback)
VSPAN enters the inverting side, so VSPAN above VTARGET makes VINT ramp down. Lower VINT gives lower VG, the VCA821 gain falls with VG (0 to 2 V, VCA821 datasheet p1),
the eye shrinks and VSPAN comes back to VTARGET. An integrator keeps ramping until the error is zero, so the steady-state error is zero.

FREEZE IS NOT A RESET
Two TMUX1112 switches sit in series in the VSPAN -> R104 path. Switch 1 (SEL1) is tied to 3V3 through fitted 0R R120, so it is always closed; LOS_N reaches SEL1 only through the DNP 0R R121 (bench option).
When the FPGA pulls HOLD_N low, switch 2 opens, no current flows in R104 and C102 keeps its charge. VINT, and therefore the gain, stays at its last good value. A reset would dump the charge and force a re-acquisition from a fixed start gain
after every fade. Holding keeps the last good gain, so recovery from a short dropout is immediate. R119 pulls HOLD_N high: with the FPGA absent the loop runs.
The analog LOS comparator does NOT freeze the integrator (design decision, avoids the startup deadlock: low eye -> LOS_N low -> frozen -> gain can never rise).
With no signal the loop therefore drives VG toward its upper bound (SEARCH state at maximum gain, docs/architecture.md "States" table). The FPGA's HOLD_N is the only freeze.
LOS_N remains the LOS status output (hierarchical pin LOS) and the debug header signal.

UNRESOLVED
- VG upper bound: with no signal the integrator winds toward its upper bound. The VG upper bound versus the VCA821 2 V gain-control range is UNRESOLVED (D30 clamp is DNP).
- Anti-windup acting on the state is only partly designed: freeze covers HOLD only. D30/D31 are a soft output bound (DNP). Behaviour at the rails (VINT 0 / 3.3 V) is open.
- Loop gain, phase margin and the real VCA821 gain law at 3.7 V rails are neither simulated nor measured. The 4.7 ms time constant is from decision-log 9.
- Loading of the slicer peak detectors by R102/R103/R43/R44 (about 20k across VHIGH/VLOW) is not checked.
- Switch charge injection and leakage on C102 (TMUX1112 leakage is pA-level, datasheet) are not quantified. C102 as 47 nF C0G in 1206 needs a stock check.
- The 100k pull-up on HOLD_N and the 1 M / 10k hysteresis values are first guesses."""
s.text(wrap(intent, 150), u(0, 127), 1.5)

s.save(PATH)
print("wrote", PATH)
