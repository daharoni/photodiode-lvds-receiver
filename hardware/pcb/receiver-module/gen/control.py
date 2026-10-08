#!/usr/bin/env python3
"""Generate control.kicad_sch = the Monitor sheet (revision 2, spec section 4: VCM_REF and RSSI).
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
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"
OA = "AharoniLab_OpAmp:OPA2320AIDR"
G = 1.27
OX, OY = 10, 0   # page origin offset in grid units (keeps labels clear of the frame)


def u(x, y):
    return ((x + OX) * G, (y + OY) * G)


s = Sheet.load(PATH)


def _prop(inst, name):
    for e in s.symbols[s.instances.index(inst)]:
        if isinstance(e, list) and e and e[0] == "property" and str(e[1]) == name:
            return e


def tpos(inst, name, dx, dy, just=None):
    """Move a Reference/Value text to (dx, dy) grid units from the symbol origin."""
    e = _prop(inst, name)
    e[3] = ["at", round(inst.at[0] + dx * G, 4), round(inst.at[1] + dy * G, 4), 0]
    for i, it in enumerate(e):
        if isinstance(it, list) and it and it[0] == "effects":
            fx = ["effects", ["font", ["size", 1.27, 1.27]]]
            if just:
                fx.append(["justify"] + just.split())
            e[i] = fx


def r(ref, val, x, y, horiz=False, dnp=False):
    return s.place(R, ref, val, u(x, y), rot=90 if horiz else 0, footprint=R603, dnp=dnp)


def c(ref, val, x, y, fp=C603):
    return s.place(C, ref, val, u(x, y), footprint=fp)


def W(*pts):
    s.wire([u(*p) for p in pts])


def gnd(pin):
    s.stub(pin, "d", 2 * G, "GND", kind="global")


def tp(ref, name, x, y):
    """Test point above the wire at (x, y); pin is at the symbol origin."""
    W((x, y), (x, y - 3))
    s.place(TP, ref, name, u(x, y - 3), rot=0, footprint=TPFP)


# ---- 3V3 in ----------------------------------------------------------------
s.hier_label("3V3", u(8, 12), 180, "input")
W((8, 12), (12, 12))
s.label("3V3", u(12, 12), 0)             # local 3V3 net; distributed by stubs below
s.text("Monitor: VCM_REF baseline reference (U30A) and RSSI peak detector (D30, U30B). Left: VCM_REF; right: RSSI.", u(0, 6), 2)

# ============ block 1: VCM_REF (1.65 V) ========================================
s.text("1. VCM_REF", u(14, 14), 1.8)
a = r("R100", "10k", 30, 24)
b = r("R101", "10k", 30, 28)
for q in (a, b):
    tpos(q, "Reference", -1.5, -0.8, "right")
    tpos(q, "Value", -1.5, 0.8, "right")
s.stub(a.pin("1"), "u", 2 * G, "3V3")
gnd(b.pin("2"))
cc = c("C100", "100n", 37, 28)
gnd(cc.pin("2"))
W((30, 26), (40, 26), (40, 28), (44, 28))
u30a = s.place(OA, "U30", "OPA2320AIDR", u(50, 30), unit=1)
W((56, 30), (56, 36), (40, 36), (40, 32), (44, 32))      # unity-gain feedback from the amplifier pin
r102 = r("R102", "10", 62, 30, horiz=True)
tpos(r102, "Reference", 0, -2.5)
tpos(r102, "Value", 0, 2.5)
W((56, 30), (60, 30))
c101 = c("C101", "1u", 70, 34)
gnd(c101.pin("2"))
W((64, 30), (84, 30))
W((70, 30), (70, 32))
s.hier_label("VCM_REF", u(84, 30), 0, "output")
tp("TP30", "VCM_REF", 76, 30)

# ---- U30 power unit ---------------------------------------------------------
u30c = s.place(OA, "U30", "OPA2320AIDR", u(50, 62), unit=3)
s.stub(u30c.pin("8"), "u", 2 * G, "3V3")
gnd(u30c.pin("4"))
c103 = c("C103", "100n", 60, 62)
s.stub(c103.pin("1"), "u", 2 * G, "3V3")
gnd(c103.pin("2"))

# ============ block 2: RSSI peak detector =====================================
B = 24   # x shift of block 2 in grid units
s.text("2. RSSI (negative-peak detector)", u(96 + B, 14), 1.8)
s.hier_label("TIA_TAP", u(98 + B, 30), 180, "input")
d30 = s.place("AharoniLab_Passive:BAS70", "D30", "BAS70", u(110 + B, 30), rot=0)
W((98 + B, 30), (107 + B, 30))                 # TIA_TAP -> cathode (K)
W((113 + B, 30), (136 + B, 30), (136 + B, 28), (140 + B, 28))   # anode -> RSSI_HOLD -> U30B IN+
s.label("RSSI_HOLD", u(115 + B, 30), 0)
r103 = r("R103", "1M", 120 + B, 36)
tpos(r103, "Reference", -1.5, -0.8, "right")
tpos(r103, "Value", -1.5, 0.8, "right")
W((120 + B, 30), (120 + B, 34))
s.stub(r103.pin("2"), "d", 2 * G, "3V3")
c102 = c("C102", "1n C0G", 128 + B, 36)
W((128 + B, 30), (128 + B, 34))
gnd(c102.pin("2"))
tp("TP32", "RSSI_HOLD", 134 + B, 30)
u30b = s.place(OA, "U30", "OPA2320AIDR", u(146 + B, 30), unit=2)
W((152 + B, 30), (152 + B, 36), (136 + B, 36), (136 + B, 32), (140 + B, 32))
W((152 + B, 30), (168 + B, 30))
s.hier_label("RSSI", u(168 + B, 30), 0, "output")
tp("TP31", "RSSI", 160 + B, 30)


def wrap(txt, width):
    out = []
    for ln in txt.split("\n"):
        out += textwrap.wrap(ln, width, subsequent_indent="  ", break_long_words=False) or [""]
    return "\n".join(out)


s.text("R100/R101 10k 1 % (or better): 3V3/2 = 1.65 V nominal.\nR102 10 ohm isolates C101 1 uF; VCM_REF is taken AFTER R102.", u(14, 46), 1.27)
s.text("D30 BAS70: K on TIA_TAP, A on RSSI_HOLD. OPA857 OUT swings DOWN from OUTN (1.83 V) on photocurrent,\n"
       "so the detector holds the NEGATIVE peak; RSSI falls as the light rises. 1 M (to 3V3) x 1 nF = tau 1 ms.", u(96, 52), 1.27)

intent = """DESIGN INTENT (Monitor sheet, revision 2, decision 12). Status labels per CLAUDE.md. Nothing here is measured or simulated.

WHAT THIS SHEET IS FOR
VCM_REF is the common baseline of every AC-coupled stage downstream of the OPA857: the return of the post-amp input coupling (Front End), the OPA855 gain reference, and the comparator input returns (Slicer). It sits at 3V3/2 = 1.65 V so the TLV3605 inputs are mid-range. With 8b/10b the eye centre is the AC-coupled baseline, so no tracking threshold is needed (docs/research/post-amp-slicer.md).
RSSI is a slow, RELATIVE received-light indicator for the ESP32 (read by the ADS1115) to trim APD bias (DAC_HV) and the OPA857 20k/5k gain. It is not calibrated: the BAS70 forward drop and the 1 k tap resistor on the Front End (R58) shift it; the ESP32 calibrates against the FPGA's 8b/10b validity.

VCM_REF (PROPOSED)
U30A OPA2320 unity buffer of a 10k/10k divider from 3V3 with C100 100 nF at the midpoint. U30A drives C101 1 uF through R102 10 ohm and VCM_REF is taken after R102. Reason: the unity-gain OPA320 is stated stable with a pure capacitive load up to about 1 nF, and a 10 to 20 ohm series resistor is the datasheet's technique for larger loads (SBOS513F, 7.3.8, PDF p.19, Figure 36); ESR of caps above 1 uF can also help. A 1 uF load is above the datasheet's own illustrated cases, so the margin is UNRESOLVED until the VCM_REF step response is measured. The loads are a few 1 k returns to VCM_REF (microamps in use, 1.65 mA each only if one were shorted to ground), so the 10 ohm drop is negligible.

RSSI (PROPOSED)
OPA857 OUT swings down below OUTN (1.83 V) for photocurrent into IN (SBOS630D, 7.3.1 PDF p.15; 8.1 PDF p.17; 8.2.1.2 step 2 PDF p.18), so D30 (cathode on TIA_TAP, anode on RSSI_HOLD) captures the negative peak. R103 1 M returns RSSI_HOLD to 3V3 and C102 1 nF C0G gives tau 1 ms. At idle R103 passes about (3.3 - 1.83) V / 1 M = 1.5 uA through D30 and the 1 k tap into the TIA output: about 1.5 mV, negligible. RSSI_HOLD therefore idles at about OUTN + Vf (roughly 1.9 to 2.0 V; Vf at 1.5 uA not looked up) and falls as the light rises. TIA_TAP is DC-coupled, so the pull-up cannot saturate anything. U30B buffers RSSI_HOLD to RSSI (unity gain).
PROPOSED  No dead zone: with R103 to VCM_REF the diode would stay off for the first 0.3 to 0.5 V of swing (TIA idles at 1.83 V, RSSI_HOLD at 1.65 V). The 3V3 return keeps D30 slightly conducting so RSSI tracks the TIA minimum from the first microamp. Cost: the idle level depends on Vf (relative indicator, the ESP32 calibrates). Not simulated or measured.

REMOVED (decision 12)
VMID, VSPAN, VCM_DET, VTARGET, VG_HI/VG_LO, VLOS_TH references, the AGC integrator, TMUX1112 freeze switches, TLV3201 LOS comparator and the VG/VTH selectors: the VCA821 VGA and analog AGC are gone, so nothing needs them. Range control is a firmware trim from RSSI."""
s.text(wrap(intent, 170), u(0, 84), 1.5)
s.save(PATH)
print("wrote", PATH)
