#!/usr/bin/env python3
"""Generate detector.kicad_sch (Rev A, spec section 5). Run from anywhere: python3 gen/detector.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/detector.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
TP = "AharoniLab_Connector:TestPoint"
JP = "AharoniLab_Connector:SolderJumper_2_Open"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
C402 = "AharoniLab_Capacitor_SMD:C_0402_1005Metric_N"
C805 = "AharoniLab_Capacitor_SMD:C_0805_2012Metric_N"
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"

s = Sheet.load(PATH)
XL = 30.48

# ---- hierarchical inputs with local-label stubs -------------------------
for name, y in (("5V_A", 53.34), ("3V3", 58.42), ("VCM_DET", 63.5)):
    s.hier_label(name, (XL, y), 180, "input")
    s.wire([(XL, y), (XL + 5.08, y)])
    s.label(name, (XL + 5.08, y), 0)

# ---- input: SDET -> JP40 -> R150 -> DET_IN bus ---------------------------
YIN, XB = 127.0, 66.04
s.hier_label("SDET", (XL, YIN), 180, "input")
jp40 = s.place(JP, "JP40", "SolderJumper_2_Open", (45.72, YIN))
s.connect((XL, YIN), jp40.pin("1"))
r150 = s.place(R, "R150", "49.9", (58.42, YIN - 2.54), footprint=R603)   # vertical, pin 2 at the bottom
s.connect(jp40.pin("2"), r150.pin("2"))
s.wire([r150.pin("1"), (r150.pin("1")[0], YIN - 5.08), (XB, YIN - 5.08)])   # joins the DET_IN bus
s.text("JP40 default: bridge", (40.64, YIN + 3.81), 1.27)
tp42 = s.place(TP, "TP42", "DET_IN", (73.66, YIN), dnp=False, footprint=TPFP)
s.connect((XB, YIN), tp42.pin("1"))
s.wire([(XB, 86.36), (XB, 137.16)])   # DET_IN bus (U40 + at 86.36, U41 + at 137.16)


def channel(n, yc, ref_u, ref_d, ref_c, ref_r, ref_tp, cap_ref, res_ref, hold_name, cathode_at_cap, jp_ref, out_name,
            amp_unit_pos, caps):
    """One channel. yc = centre y of the OPA356. caps = (c100n, c1u, c10u) refs. hold_name = CH or CL."""
    u = s.place("AharoniLab_OpAmp:OPA356AIDBVR", ref_u, "OPA356AIDBVR", (96.52, yc))
    # + input from DET_IN bus
    s.connect((XB, u.pin("3")[1]), u.pin("3"))
    # feedback: out -> right, down, left, up into -
    out, inn = u.pin("1"), u.pin("4")
    fb = yc + 20.32
    s.wire([out, (106.68, yc), (106.68, fb), (83.82, fb), (83.82, inn[1]), inn])
    # V-: down to a GND label drawn to the right so the feedback wire stays clear
    vm = u.pin("2")
    s.wire([vm, (vm[0], vm[1] + 7.62)])
    s.global_label("GND", (vm[0], vm[1] + 7.62), 0)
    # V+: up to rail, local 5V_A label, three bypass caps hanging up from the rail
    vp = u.pin("5")
    rail = vp[1] - 2.54
    s.wire([vp, (vp[0], rail)])
    s.wire([(78.74, rail), (119.38, rail)])
    s.label("5V_A", (78.74, rail), 180)
    for ref, val, fp, x in zip(caps, ("100n", "1u", "10u"), (C402, C603, C805), (99.06, 109.22, 119.38)):
        c = s.place(C, ref, val, (x, rail - 2.54), footprint=fp)
        s.connect(c.pin("2"), (x, rail))
        s.stub(c.pin("1"), "u", 2.54, "GND", kind="global")
    # diode
    d = s.place("AharoniLab_Passive:BAS70", ref_d, "BAS70", (116.84, yc), rot=180 if cathode_at_cap else 0)
    s.connect((106.68, yc), d.pin("1" if cathode_at_cap else "3"))      # anode (D40) / cathode (D41) at the buffer output
    cap_side = d.pin("3" if cathode_at_cap else "1")
    s.connect(cap_side, (127.0, yc))
    # hold node: C to GND, R to VCM_DET, TP above
    c = s.place(C, cap_ref, "47p C0G", (127.0, yc + 5.08), footprint=C603, fields={})
    s.connect((127.0, yc), (127.0, yc + 2.54))
    s.stub(c.pin("2"), "d", 2.54, "GND", kind="global")
    r = s.place(R, res_ref, "1M", (137.16, yc + 5.08), footprint=R603)
    s.wire([(127.0, yc), (137.16, yc), (137.16, yc + 2.54)])
    s.stub(r.pin("2"), "d", 2.54, "VCM_DET")
    tp = s.place(TP, ref_tp, hold_name, (132.08, yc - 7.62), footprint=TPFP)
    s.connect((132.08, yc), tp.pin("1"))
    # hold-node name on the wire between R and U42 input
    # OPA2320 buffer
    b = s.place("AharoniLab_OpAmp:OPA2320AIDR", "U42", "OPA2320AIDR", (160.02, yc), unit=amp_unit_pos)
    plus, minus, bo = b.pin("3" if amp_unit_pos == 1 else "5"), b.pin("2" if amp_unit_pos == 1 else "6"), \
        b.pin("1" if amp_unit_pos == 1 else "7")
    s.wire([(137.16, yc), (147.32, yc), (147.32, plus[1]), plus])
    s.wire([bo, (170.18, yc), (170.18, yc + 10.16), (147.32, yc + 10.16), (147.32, minus[1]), minus])
    jp = s.place(JP, jp_ref, "SolderJumper_2_Open", (182.88, yc))
    s.connect(bo, jp.pin("1"))
    s.text("%s default: bridge" % jp_ref, (177.8, yc + 3.81), 1.27)
    s.connect(jp.pin("2"), (198.12, yc))
    s.hier_label(out_name, (198.12, yc), 0, "output")
    return u


YH, YL = 88.9, 139.7
channel(1, YH, "U40", "D40", None, None, "TP40", "C150", "R151", "CH", True, "JP41", "VHIGH", 1,
        ("C152", "C153", "C154"))
channel(2, YL, "U41", "D41", None, None, "TP41", "C151", "R152", "CL", False, "JP42", "VLOW", 2,
        ("C155", "C156", "C157"))

s.label("DET_IN", (XB, 101.6), 0)

# ---- U42 power unit ------------------------------------------------------
u3 = s.place("AharoniLab_OpAmp:OPA2320AIDR", "U42", "OPA2320AIDR", (223.52, 114.3), unit=3)
vp, vm = u3.pin("8"), u3.pin("4")
rail = vp[1] - 2.54
s.wire([vp, (vp[0], rail), (233.68, rail)])
s.wire([(215.9, rail), (vp[0], rail)])
s.label("3V3", (215.9, rail), 180)
c158 = s.place(C, "C158", "100n", (233.68, rail - 2.54), footprint=C402)
s.connect(c158.pin("2"), (233.68, rail))
s.stub(c158.pin("1"), "u", 2.54, "GND", kind="global")
s.stub(vm, "d", 2.54, "GND", kind="global")

# ---- text ---------------------------------------------------------------
s.text("Detector coupon: fast high/low capture (U40-U42). UNRESOLVED: not a validated 20 ns detector. Disconnectable at JP40 (input) and JP41/JP42 (outputs).", (XL, 30), 2.0)
import textwrap
WRAP = lambda x: "\n".join(textwrap.fill(l, 150, subsequent_indent="            ") for l in x.split("\n"))
s.text(WRAP("""Design intent (Rev A; nothing here is simulated or measured)
UNRESOLVED  Whole block. A coupon to capture the high and low levels of SDET so Control can derive a threshold; it is NOT a validated 20 ns precision peak detector.
PROPOSED    SDET -> JP40 (default: bridge) -> R150 49.9 ohm -> DET_IN. U40/U41 OPA356 unity buffers (+ = DET_IN, 200 MHz GBW, 360 V/us, SBOS212A p.3) drive D40/D41 BAS70 into hold nodes CH/CL.
            D40 anode at U40 output, cathode at CH (positive peak). D41 cathode at U41 output, anode at CL (negative peak). CH/CL: C150/C151 47 pF C0G to GND, R151/R152 1 M to VCM_DET.
            U42 OPA2320 (3V3): A buffers CH -> JP41 (default: bridge) -> VHIGH; B buffers CL -> JP42 (default: bridge) -> VLOW. TP40 CH, TP41 CL, TP42 DET_IN.
            Footprints allow C150/C151 22-100 pF and R151/R152 0.5-5 M; pick by G2 test. The OPA356 input range is V- - 0.1 V to V+ - 1.5 V (SBOS212A p.3), so U40/U41 are on 5V_A (3V3 would leave 1.8 V, too small for the SDET swing about 1.65 V).
            Bypass at each OPA356 V+ pin: 100 nF 0402 + 1 uF + 10 uF (datasheet minimum recommended is 10 uF, p.10).
KNOWN ERRORS (all uncorrected here): (1) Schottky forward drop about 0.3 V (BAS70, unverified at this current) makes VHIGH low and VLOW high by the same amount; with a 1 M load it varies with level and temperature.
            (2) Droop: CH/CL decay through R151/R152 with tau = 1 M x 47 pF = 47 us, so captured levels sag between peaks of a sparse 8b/10b stream. (3) OPA356 output into the diode and 47 pF is untested for stability.
            (4) Input leakage of the diode and U42 pins (pA scale) is negligible against 1 M but is not measured. (5) Hold buffers see no reset: the level follows the data pattern, not the instantaneous eye.
G2 TESTS    Compare VHIGH/VLOW against eye-histogram high/low levels over pattern density, bias and temperature; measure droop, drop, and added jitter on SDET with JP40 closed vs open.
ALTERNATIVES  Two-diode (drop-cancelling) or in-loop (diode inside the amplifier feedback) detectors, a faster precision rectifier, or ADC capture in the MCU (optional extra only; analog-first stays the baseline)."""), (XL, 185), 1.5)
s.save(PATH)
print("wrote", PATH)
