#!/usr/bin/env python3
"""Generate power.kicad_sch (Rev A, spec section 1 + docs/calculations/apd-bias-design.md).
Run from anywhere: python3 gen/power.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

# Freeze guard: layout started 2026-10-09; see gen/FROZEN.
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "FROZEN")):
    sys.stderr.write("generators are frozen since 2026-10-09 (layout started); see gen/FROZEN\n")
    sys.exit(2)

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/power.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
L = "AharoniLab_Passive:L"
FBd = "AharoniLab_Passive:FerriteBead_Small"
NTC = "AharoniLab_Passive:Thermistor_NTC"
POT = "AharoniLab_Passive:R_Potentiometer_Trim"
DIO = "AharoniLab_Passive:DFLS1150-7"
TP = "AharoniLab_Connector:TestPoint"  # TP2 only
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
R1206 = "AharoniLab_Resistor_SMD:R_1206_3216Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
C805 = "AharoniLab_Capacitor_SMD:C_0805_2012Metric_N"
C1206 = "AharoniLab_Capacitor_SMD:C_1206_3216Metric_N"
C1210 = "AharoniLab_Capacitor_SMD:C_1210_3225Metric_N"
L805 = "AharoniLab_Inductor_SMD:L_0805_2012Metric_N"
HALF = {R: 2.54, C: 2.54, FBd: 2.54, L: 3.81, NTC: 3.81}

s = Sheet.load(PATH)
GND = lambda p, d="d", n=2.54: s.stub(p, d, n, "GND", kind="global")


def part(lib, ref, val, pin1, o="v", fp=None, dnp=False):
    """Two-pin part with pin 1 at `pin1`; o='v' pin1 on top, o='h' pin1 on the left."""
    h = HALF[lib]
    if o == "v":
        i = s.place(lib, ref, val, (pin1[0], pin1[1] + h), footprint=fp, dnp=dnp)
    else:
        i = s.place(lib, ref, val, (pin1[0] + h, pin1[1]), rot=90, footprint=fp, dnp=dnp)
    if o == "h":   # rotated part: put reference above and value below the body, horizontal
        cx, cy = i.at
        for p in s.symbols[-1]:
            if isinstance(p, list) and p[0] == "property" and str(p[1]) in ("Reference", "Value"):
                p[3] = ["at", cx, cy - 2.54 if str(p[1]) == "Reference" else cy + 2.54, 90]
                if len(p) > 4:
                    for q in p:
                        if isinstance(q, list) and q[0] == "effects":
                            q[:] = [e for e in q if not (isinstance(e, list) and e[0] == "justify")]
    assert tuple(round(v, 2) for v in i.pin("1")) == tuple(round(v, 2) for v in pin1), (ref, i.pin("1"), pin1)
    return i


def move_text(ref_xy, val_xy):
    """Relocate Reference/Value text of the most recently placed symbol (horizontal, centred)."""
    for p in s.symbols[-1]:
        if isinstance(p, list) and p[0] == "property" and str(p[1]) in ("Reference", "Value"):
            xy = ref_xy if str(p[1]) == "Reference" else val_xy
            p[3] = ["at", xy[0], xy[1], 0]
            for q in p:
                if isinstance(q, list) and q[0] == "effects":
                    q[:] = [e for e in q if not (isinstance(e, list) and e[0] == "justify")]


def cap_down(ref, val, x, y, fp, dnp=False):
    """Capacitor hanging from (x, y) to a GND label below."""
    c = part(C, ref, val, (x, y), "v", fp, dnp)
    GND(c.pin("2"))
    return c


def res_down(ref, val, x, y, fp=R603, dnp=False, gnd=True):
    r = part(R, ref, val, (x, y), "v", fp, dnp)
    if gnd:
        GND(r.pin("2"))
    return r


XR = 292.1          # output label column

# ======================================================================
# TOP BAND: input caps, U1 TPS79901 3V3, U4 TPS7A2033 3V3_D
# ======================================================================
Y5 = 66.04
s.label("+5V", (25.4, Y5), 180)   # internal merged rail (U5 OUT); VBUS comes from the Connector
u1 = s.place("AharoniLab_Power:TPS79901DDCT", "U1", "TPS79901DDCT", (88.9, 68.58))
s.connect((25.4, Y5), u1.pin("IN"))
cap_down("C1", "10uF 10V", 38.1, Y5, C805)
cap_down("C2", "100nF", 50.8, Y5, C603)
cap_down("C9", "1uF", 73.66, Y5, C603)
s.wire([(76.2, Y5), (76.2, u1.pin("EN")[1]), u1.pin("EN")])
GND(u1.pin("GND"))
# 3V3 output + divider
s.stub(u1.pin("FB"), "r", 2.54, "V3_FB")
s.wire([u1.pin("OUT"), (XR, Y5)])
s.hier_label("3V3", (XR, Y5), 0, "output")
cap_down("C10", "4.7uF 10V", 109.22, Y5, C805)
cap_down("C11", "4.7uF 10V", 121.92, Y5, C805)
r1 = part(R, "R1", "17.8k 1%", (137.16, Y5), "v", R603)
r2 = part(R, "R2", "10.0k 1%", (137.16, 71.12), "v", R603)
GND(r2.pin("2"))
s.stub((137.16, 71.12), "l", 2.54, "V3_FB")
c12 = part(C, "C12", "1nF C0G", (154.94, Y5), "v", C603)
s.wire([c12.pin("2"), (154.94, 71.12), (137.16, 71.12)])

# ---- U5 TPS259631DDAR eFuse (decision 14): IN = VBUS (from the Connector), OUT = +5V ----
u5 = s.place("AharoniLab_Power:TPS259631DDAR", "U5", "TPS259631DDAR", (129.54, 38.1))   # footprint: the library symbol's own (Texas_DDA-R-PDSO-G8_SO-PowerPAD-8)
move_text((129.54, 24.0), (145.0, 58.0))
in_, en_, ov_, dv_ = u5.pin("IN"), u5.pin("EN/UVLO"), u5.pin("OVLO"), u5.pin("dVdt")
s.hier_label("VBUS", (78.74, in_[1]), 180, "input")
XD = 96.52
s.wire([(78.74, in_[1]), (XD, in_[1]), in_])
cap_down("C33", "4.7uF 25V", 88.9, in_[1], C805)
# R35 IN -> EN/UVLO, R36 EN/UVLO -> OVLO, R37 OVLO -> GND (vertical chain, pin 1 on top)
r35 = part(R, "R35", "357k 1%", (XD, in_[1]), "v", R603)
r36 = part(R, "R36", "43.2k 1%", (XD, en_[1]), "v", R603)
r37 = part(R, "R37", "100k 1%", (XD, r36.pin("2")[1]), "v", R603)
GND(r37.pin("2"))
s.wire([(XD, en_[1]), en_])
s.wire([ov_, (109.22, ov_[1]), (109.22, r36.pin("2")[1]), r36.pin("2")])
# dVdt: C32 47 nF to GND
s.wire([dv_, (114.3, dv_[1])])
c32 = part(C, "C32", "47nF X7R 10V", (114.3, dv_[1]), "v", C603)
GND(c32.pin("2"))
GND(u5.pin("GND")); GND(u5.pin("EP"))
# OUT -> +5V
s.stub(u5.pin("OUT"), "r", 10.16, "+5V")
# ILM: R38 1.21k to GND, TP3 IMON
ilm = u5.pin("ILM")
s.wire([ilm, (149.86, ilm[1])])
r38 = part(R, "R38", "1.21k 1%", (144.78, ilm[1]), "v", R603)
GND(r38.pin("2"))
tp3 = s.place(TP, "TP3", "IMON", (149.86, ilm[1]), footprint="AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect")
# FLT: TP4, R39 100k DNP pull-up to 3V3_D
flt = u5.pin("FLT")
s.wire([flt, (162.56, flt[1])])
r39 = part(R, "R39", "100k", (157.48, flt[1] - 5.08), "v", R603, dnp=True)
s.stub(r39.pin("1"), "u", 2.54, "3V3_D")
tp4 = s.place(TP, "TP4", "FLT", (162.56, flt[1]), footprint="AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect")
s.text("""U5 TPS259631DDAR eFuse (PROPOSED; TPS2596 SLVSET8A p.4, p.22):
IN = VBUS, OUT = +5V. R35 357k / R36 43.2k / R37 100k set UVLO and OVLO,
R38 1.21k sets ILM, C32 47 nF sets dVdt, C33 4.7 uF on VBUS.
FLT open-drain (TP4); R39 pull-up DNP. Not simulated or measured.""", (20, 18), 1.27)

# ---- 3V3_D digital rail: U4 TPS7A2033PDBV (spec 1.5) ----
u4 = s.place("AharoniLab_Power:TPS7A2033PDBV", "U4", "TPS7A2033PDBV", (210.82, 78.74))
u4i, u4e, u4o = u4.pin("IN"), u4.pin("EN"), u4.pin("OUT")
s.label("+5V", (177.8, u4i[1]), 180)
s.wire([(177.8, u4i[1]), u4i])
cap_down("C29", "1uF 10V", 185.42, u4i[1], C603)
s.wire([u4e, (190.5, u4e[1]), (190.5, u4i[1])])
GND(u4.pin("GND"))
s.no_connect(u4.pin("NC"))
s.wire([u4o, (XR, u4o[1])])
s.hier_label("3V3_D", (XR, u4o[1]), 0, "output")
cap_down("C30", "10uF 10V", 226.06, u4o[1], C805)
cap_down("C31", "1uF 10V", 236.22, u4o[1], C603)
s.text("""3V3_D: U4 TPS7A2033 3.3 V, 300 mA, own rail
for ESP32-C6, CAN, DAC, ADC (about 60 mA est.).
ESP32 radio MUST stay disabled (Wi-Fi TX peaks
251-382 mA). PROPOSED, estimate not measured.""", (172, 50), 1.27)

# ======================================================================
# BOTTOM BAND: LT8365 APD bias
# ======================================================================
PI = 165.1
s.label("+5V", (25.4, PI), 180)
s.wire([(25.4, PI), (40.64, PI)])
cap_down("C18", "10uF 50V", 33.02, PI, C1206)
l2 = part(L, "L2", "0.47uH 2.1A", (40.64, PI), "h", L805)
s.wire([l2.pin("2"), (83.82, PI), (83.82, 177.8)])
cap_down("C19", "10uF 50V", 58.42, PI, C1206)
cap_down("C20", "4.7uF 50V", 71.12, PI, C805)
s.stub((78.74, PI), "u", 2.54, "5V_HVIN")
s.place("power:PWR_FLAG", "#FLG02", "PWR_FLAG", (83.82, PI + 6.35), in_bom=False)
L1Y = 177.8
l1 = part(L, "L1", "10uH 1.5A", (88.9, L1Y), "h", "AharoniLab_Inductor_SMD:Wuerth_74437324100")
s.wire([(83.82, L1Y), l1.pin("1")])
s.wire([l1.pin("2"), (111.76, L1Y)])

u3 = s.place("AharoniLab_Power:LT8365EMSE", "U3", "LT8365EMSE", (96.52, 203.2))
GND(u3.pin("GND"))
for pn, name in (("EN/UVLO", "EN"), ("VIN", "5V_HVIN"), ("BIAS", "BIAS"), ("SYNC/MODE", "SYNC"),
                 ("RT", "RT"), ("SS", "SS")):
    s.stub(u3.pin(pn), "l", 2.54, name)
s.no_connect(u3.pin("NC"))
s.stub(u3.pin("FBX"), "r", 2.54, "FBX")
s.stub(u3.pin("VC"), "r", 2.54, "VC")
iv = u3.pin("INTVCC")
s.wire([iv, (121.92, iv[1])])
cap_down("C21", "1uF 25V", 121.92, iv[1], C603)
# SW bus
sw1, sw2 = u3.pin("SW1"), u3.pin("SW2")
s.wire([sw1, (111.76, sw1[1])])
s.wire([sw2, (111.76, sw2[1])])
s.wire([(111.76, L1Y), (111.76, sw2[1])])
# power stage
d1 = s.place(DIO, "D1", "DFLS1150-7", (121.92, L1Y), mirror="y")
s.wire([(111.76, L1Y), d1.pin("A")])
r7 = part(R, "R7", "20R", (130.81, L1Y), "h", "AharoniLab_Resistor_SMD:R_0805_2012Metric_N")
s.wire([d1.pin("K"), r7.pin("1")])
s.wire([r7.pin("2"), (182.88, L1Y)])
s.stub((142.24, L1Y), "u", 2.54, "HV_V1")
cap_down("C5", "0.1uF 200V X7R", 182.88, L1Y, C1206)
RB, RC = 185.42, 195.58
s.wire([(111.76, RB), (116.84, RB)])
c6 = part(C, "C6", "0.1uF 200V X7R", (116.84, RB), "h", C1206)
s.wire([c6.pin("2"), (127, RB)])
d3 = s.place(DIO, "D3", "DFLS1150-7", (137.16, RB))
s.wire([(127, RB), d3.pin("K")])
s.wire([d3.pin("A"), (142.24, RB), (142.24, L1Y)])
s.wire([(142.24, RB), (142.24, 190.5)])
c7 = part(C, "C7", "0.1uF 200V X7R", (142.24, 190.5), "v", C1206)
d4 = s.place(DIO, "D4", "DFLS1150-7", (137.16, RC), mirror="y")
s.wire([(127, RB), (127, RC), d4.pin("A")])
s.stub((127, 190.5), "l", 2.54, "HV_PUMP")
s.wire([d4.pin("K"), (142.24, RC)])
s.stub((142.24, RC), "d", 2.54, "HV_RAW")
d2 = s.place(DIO, "D2", "DFLS1150-7", (119.38, 170.18), dnp=True)
s.wire([(111.76, L1Y), (111.76, 170.18), d2.pin("K")])
s.wire([d2.pin("A"), (125.73, 170.18)])
s.global_label("GND", (125.73, 170.18), 0)
r30 = part(R, "R30", "47R", (170.18, RC), "h", R1206)
s.wire([(142.24, RC), r30.pin("1")])
s.wire([r30.pin("2"), (203.2, RC), (203.2, 200.66)])
cap_down("C25", "1nF 500V", 177.8, RC, C1206)
s.stub((177.8, RC), "u", 2.54, "HV_OUT")
# clamp
q1 = s.place("AharoniLab_Transistor:MMBTA42", "Q1", "MMBTA42", (200.66, 205.74))
q2 = s.place("AharoniLab_Transistor:MMBT3904", "Q2", "MMBT3904", (198.12, 215.9), mirror="y")
move_text((186, 218.5), (186, 220.5))
r17 = part(R, "R17", "4.99M 1%", (187.96, RC), "v", R603)
r18 = part(R, "R18", "4.99M 1%", (187.96, 200.66), "v", R603)
s.wire([r18.pin("2"), q1.pin("B")])
s.wire([q2.pin("C"), q1.pin("B")])
r16 = part(R, "R16", "4.02k 1%", (208.28, 210.82), "h", R603)
s.wire([q1.pin("E"), r16.pin("1")])
s.wire([q1.pin("E"), q2.pin("B")])
s.wire([q2.pin("E"), (213.36, q2.pin("E")[1]), (213.36, 210.82)])
s.wire([(213.36, 215.9), (215.9, 215.9)])
s.label("HV_CLAMP", (215.9, 215.9), 0)
r19 = part(R, "R19", "27k 1206 200V", (223.52, 210.82), "h", R1206)
s.wire([(213.36, 210.82), r19.pin("1")])
s.wire([r19.pin("2"), (XR, 210.82)])
cap_down("C8", "10nF 500V C0G", 238.76, 210.82, C1210)
s.hier_label("APD_BIAS", (XR, 210.82), 0, "output")
# monitor
s.stub((236.22, 167.64), "u", 2.54, "HV_OUT")
r20 = part(R, "R20", "4.99M 1%", (236.22, 167.64), "v", R603)
r32 = part(R, "R32", "4.99M 1%", (236.22, 172.72), "v", R603)
res_down("R21", "100k 1%", 236.22, 177.8)
s.wire([(236.22, 177.8), (XR, 177.8)])
s.hier_label("HV_MON", (XR, 177.8), 0, "output")
cap_down("C28", "10nF", 254, 177.8, C603)

# ---- support networks, row 1 (y = 231.14) and row 2 (y = 251.46) ----
Y1, Y2 = 231.14, 251.46
# EN divider + HV disable gate Q3 (decision 11)
r22 = part(R, "R22", "200k 1%", (30.48, Y1 - 5.08), "v", R603)
s.stub(r22.pin("1"), "u", 2.54, "5V_HVIN")
r23 = res_down("R23", "200k 1%", 30.48, Y1)
q3 = s.place("AharoniLab_Transistor:DMN2056U-7", "Q3", "DMN2056U-7", (50.8, 236.22), mirror="y")
s.wire([(30.48, Y1), q3.pin("D")])
s.label("EN", (43.18, Y1), 0)
GND(q3.pin("S"))
gx = 63.5
s.wire([q3.pin("G"), (gx, 236.22)])
r33 = part(R, "R33", "100k", (gx, 226.06), "v", R603)
s.stub(r33.pin("1"), "u", 2.54, "3V3_D")
s.wire([r33.pin("2"), (gx, 236.22)])
r34 = part(R, "R34", "1k", (66.04, 236.22), "h", R603)
s.wire([(gx, 236.22), r34.pin("1")])
s.wire([r34.pin("2"), (73.66, 236.22)])
s.hier_label("HV_DIS", (73.66, 236.22), 0, "input")
j1 = s.place("AharoniLab_Connector:Conn_01x02", "J1", "HV FORCE ON", (gx + 5.08, 243.84), dnp=True,
             footprint="AharoniLab_Connector:PinHeader_1x02_P2.54mm_Vertical")
s.wire([(gx, 236.22), j1.pin("Pin_1")])
move_text((gx + 8.89, 241.8), (gx + 8.89, 249.5))
GND(j1.pin("Pin_2"), "l")
# SYNC options
s.label("SYNC", (83.82, Y1), 180)
tp2 = s.place(TP, "TP2", "SYNC_EXT", (119.38, Y1), rot=180,
              footprint="AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect")
s.wire([(83.82, Y1), tp2.pin("1")])
res_down("R26", "100k", 93.98, Y1, dnp=True)
res_down("R27", "0R", 106.68, Y1, dnp=True)
# DAC leg
s.hier_label("DAC_HV", (144.78, Y1), 180, "input")
s.wire([(144.78, Y1), (149.86, Y1)])
r13 = part(R, "R13", "10k", (149.86, Y1), "h", R603)
s.wire([r13.pin("2"), (165.1, Y1)])
cap_down("C27", "100nF", 165.1, Y1, C603)
r14 = part(R, "R14", "442k 0.1%", (177.8, Y1), "h", R603)
s.wire([(165.1, Y1), r14.pin("1")])
s.wire([r14.pin("2"), (213.36, Y1)])
s.stub((190.5, Y1), "u", 2.54, "FBX")
cap_down("C26", "10pF C0G", 198.12, Y1, C603, dnp=True)
xs = [228.6, 241.3, 254.0, 266.7]
prev = (213.36, Y1)
for ref, x in zip(("R8", "R9", "R10", "R11"), xs):
    r = part(R, ref, "2.05M 1%", (x, Y1), "h", R603)
    s.wire([prev, r.pin("1")])
    prev = r.pin("2")
s.wire([prev, (276.86, Y1)])
s.label("HV_OUT", (276.86, Y1), 0)
r12 = part(R, "R12", "86.6k 1%", (213.36, Y1), "v", R603)
th1 = part(NTC, "TH1", "NTC 10k B3950", (213.36, Y1 + 5.08), "v", "AharoniLab_Resistor_SMD:R_0603_1608Metric_N")
move_text((225, Y1 + 5.5), (225, Y1 + 8.0))
GND(th1.pin("2"))
rv1 = s.place(POT, "RV1", "50k trim", (231.14, 254.0), dnp=True,
              footprint="AharoniLab_Resistor_SMD:Bourns_3224W_SMD")
s.stub(rv1.pin("1"), "u", 2.54, "3V3")
GND(rv1.pin("3"))
move_text((221.0, 255.0), (221.0, 257.0))
s.wire([rv1.pin("2"), (243.84, rv1.pin("2")[1])])
r15 = part(R, "R15", "274k", (243.84, rv1.pin("2")[1]), "h", R603, dnp=True)
s.stub(r15.pin("2"), "r", 2.54, "FBX")
# row 2 cells: RT, SS, BIAS, VC
s.label("RT", (35.56, Y2), 180)
s.wire([(35.56, Y2), (43.18, Y2)])
res_down("R24", "84.5k 1%", 43.18, Y2)
s.label("SS", (60.96, Y2), 180)
s.wire([(60.96, Y2), (68.58, Y2)])
cap_down("C22", "0.22uF", 68.58, Y2, C603)
s.label("BIAS", (91.44, Y2), 180)
s.wire([(91.44, Y2), (109.22, Y2)])
s.place("power:PWR_FLAG", "#FLG03", "PWR_FLAG", (95.25, Y2), in_bom=False)   # BIAS is tied by passive 0R options only
res_down("R28", "0R", 99.06, Y2)
r29 = res_down("R29", "0R", 109.22, Y2, dnp=True, gnd=False)
s.stub(r29.pin("2"), "d", 2.54, "5V_HVIN")
s.label("VC", (135.89, Y2), 180)
s.wire([(135.89, Y2), (137.16, Y2)])
cap_down("C24", "10pF C0G", 137.16, Y2, C603, dnp=True)
r25 = part(R, "R25", "84.5k 1%", (154.94, Y2), "h", R603)
s.wire([(137.16, Y2), r25.pin("1")])
s.wire([r25.pin("2"), (170.18, Y2)])
cap_down("C23", "1nF C0G", 170.18, Y2, C603)

# ---- close the gap left by the removed LM27762 block: move everything at y >= 150 up by DY ----
DY, THR = 60.96, 150.0


def _shift(node):
    if isinstance(node, list):
        if node and node[0] == "at" and len(node) >= 3 and float(node[2]) >= THR:
            node[2] = round(float(node[2]) - DY, 2)
        elif node and node[0] == "xy" and float(node[2]) >= THR:
            node[2] = round(float(node[2]) - DY, 2)
        else:
            for n in node:
                _shift(n)


for it in list(s.symbols) + list(s.items) + list(s.wires) + list(s.ncs):
    _shift(it)
for i in s.instances:
    if i.at[1] >= THR:
        i.at = (i.at[0], round(i.at[1] - DY, 2))
s.junctions = [(x, round(y - DY, 2) if y >= THR else y) for x, y in s.junctions]

# ---- text -----------------------------------------------------------
TX = 308.0
s.text("Power: VBUS in -> U5 eFuse -> +5V. U1 TPS79901 3V3, U4 TPS7A2033 3V3_D, U3 LT8365 APD bias (100-220 V) -> APD_BIAS.", (20, 12.7), 2.5)
s.text("""Design intent (Rev A, revision 4; nothing here is simulated or measured; details and citations in docs/schematic/power.md)
PROPOSED  +5V (U5 OUT) entry: C1 10 uF + C2 100 nF.
PROPOSED  U1 TPS79901: VOUT = 1.193 V x (1 + R1/R2) = 3.316 V nominal (R1 17.8k, R2 10.0k). CFB 1 nF (see note).
VERIFIED  TPS79901 CFB is required for stability; 3 pF to 1 nF when R1||R2 = 250k; <5 pF for fast start (SBVS056L p.14, 8.2.2.6).
UNRESOLVED  Here R1||R2 = 6.4k, not 250k: the datasheet range was not stated for this impedance; 1 nF is a PROPOSED value.
PROPOSED  3V3 load estimate (rev 2): OPA857 26.8 mA max + OPA855 19.5 mA max (IQ 17.8 typ, 16-19.5 mA at VS = 5 V, OPA855 SBOS622D PDF p.7; Fig 6-27 p.12 shows about 16-17.5 mA at 3.3 V, so 19.5 is conservative) + TLV3605 17.5 mA max + OPA2320 ~2 mA = about 66 mA. U1 TPS79901 is rated 200 mA. PROPOSED, not measured.
REMOVED  (decision 12) U2 LM27762 +/-3V7, 5V_A bead/caps, PGOOD_VGA and TP1: the VCA821 VGA is gone, the OPA855 runs from 3V3.
PROPOSED  U3 LT8365 values per docs/calculations/apd-bias-design.md sections 3.2 and 4: 500 kHz (RT 84.5k), L1 10 uH, boost to ~110 V + doubler.
VERIFIED  SYNC/MODE: float = pulse-skip, GND = Burst, 100k to GND = Burst/SSFM (LT8365 Rev. A p.7). BIAS tie to GND if unused; INTVCC 1 uF (p.7).
PROPOSED  EN/UVLO 200k/200k from 5V_HVIN, always connected. Q3 DMN2056U-7 pulls EN/UVLO to GND = HV OFF. Gate = HV_DIS, R33 100k pull-up to 3V3_D, R34 1k series: HV is OFF until the ESP32 drives HV_DIS low after verifying the DAC (decision 11). J1 HV FORCE ON (DNP) shorts the gate to GND for bench use without firmware.\nPROPOSED  U4 TPS7A2033 3V3_D: 300 mA, radio must stay disabled; load est. 60 mA (docs/research/module-controller.md). CIN 1 uF, COUT 10 uF + 1 uF (datasheet minimum 1 uF, max 200 uF: SBVS338H p.5).
PROPOSED  BIAS: R28 0R to GND fitted; R29 0R to 5V_HVIN DNP. Fit exactly one of them. SYNC options R26/R27/TP2 are DNP.
PROPOSED  D2 (GND to SW, from the p.30 250 V example, purpose not stated) is DNP. Q1/Q2 clamp ~150 uA. C8 and R19 form filter stage 1.
PROPOSED  HV_MON = HV_OUT/101 (R20+R32 10M, R21 100k): 1.39 V at 140 V. Stage 2 filter (10k + 10 nF) is on the front-end sheet.
Net names: HV_V1, HV_PUMP, HV_RAW, HV_OUT, HV_CLAMP, 5V_HVIN, EN, SYNC, BIAS, RT, SS, VC, FBX are local labels; APD_BIAS = HV_FILT.
Hierarchical pins: in VBUS, DAC_HV, HV_DIS; out 3V3, 3V3_D, APD_BIAS, HV_MON.
PROPOSED  (decision 14, revision 4) U5 TPS259631DDAR eFuse: IN pin 4 = VBUS (single 5 V input from the Connector sheet), OUT pin 5 = +5V (internal rail for U1, U3 via L2, U4), GND pin 1 and exposed pad pin 9 = GND (TPS2596 SLVSET8A p.4). Fixed-clamp variants rejected; this variant gives x1 auto-retry (Device Comparison p.3). Abs max on IN 21 V (p.1, p.5).
PROPOSED  UVLO/OVLO divider R35 357k / R36 43.2k / R37 100k (1 %): overvoltage cut-off 5.76-6.20 V rising (below the 7.0 V abs max of the TPS79901, SBVS056L p.4), UVLO 4.06-4.32 V rising, 3.72-4.00 V falling (calculated with tolerances, not simulated).
PROPOSED  ILM R38 1.21k 1 %: ILIM 0.68 / 0.76 / 0.84 A min/typ/max (TPS2596 Eq. 5 p.22). A real current limit, not the 0.5 A USB budget. TP3 IMON on ILM (about 0.79 V/A). C32 47 nF on dVdt: about 5.3 ms ramp, about 23 mA inrush into an assumed 25 uF (estimate, measure in G1).
PROPOSED  FLT (pin 6) open-drain, TP4; R39 100k pull-up DNP to 3V3_D. UNRESOLVED: both rails are off while the eFuse is cut off, so a pull-up reads 0 V and cannot separate fault from no power; FLT is not routed to the ESP32. FLT pin abs max not read.
PROPOSED  C33 4.7 uF 25 V 0805 on VBUS at IN. C1/C2 stay on +5V (OUT). Removed: TPS2121, +5V_CABLE, PWR_SRC, old R39-R42, C34, the PR1 divider.
PROPOSED  Budget about 0.19 A worst case from +5V (docs/research/usb-standalone-power.md section 1.5, estimate) plus up to 35 mA on 3V3 for the LVDS fan-out U50 (LVDS104 p.5); radio must stay disabled. UNRESOLVED: whether a bus-powered hub holds a module to 100 mA.
PROPOSED  ERC: U5 OUT (pin 5) is power_out on the +5V net, so +5V needs no PWR_FLAG; the root PWR_FLAG #FLG04 sits on VBUS. USB-alone firmware starts HV at the low-bias end in steps (PROPOSED).""", (TX, 28), 1.4)
s.text("""HV WARNING
APD bias reaches 220 V. Stored energy ~2.3 mJ (docs/calculations/apd-bias-design.md section 4). Can be hazardous.
Never probe HV_OUT, HV_RAW, HV_PUMP, HV_V1 or HV_CLAMP directly. Use HV_MON (HV_OUT/101) for observation.
Capacitors C5-C8, C25 and resistors R19, R30 carry >= 200 V ratings; keep 200 V creepage/clearance on every HV_ net,
series-limited, with the HV netclass 1.0 mm clearance. Keep the APD_BIAS/FBX area away from TIA_IN.
HV is OFF by default (Q3 gate pulled up); J1 FORCE ON overrides the firmware disable: fit only on the bench with the DAC set. Discharge through the divider takes ~0.5 s: wait before touching.
References: LT8365 Rev. A datasheet p.30 (250 V example), DC2838A demo manual Rev. 0.""", (TX, 190), 1.4)
import textwrap
for it in s.items:
    if it[0] == "text" and len(str(it[1])) > 400:
        lines = []
        for ln in str(it[1]).split("\\n"):
            lines += textwrap.wrap(ln, 100, subsequent_indent="    ") or [""]
        it[1] = type(it[1])("\\n".join(lines))
s.save(PATH)
print("wrote", PATH)
