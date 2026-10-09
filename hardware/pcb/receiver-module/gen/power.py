#!/usr/bin/env python3
"""Generate power.kicad_sch (Rev A, spec section 1 + docs/calculations/apd-bias-design.md).
Run from anywhere: python3 gen/power.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

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
s.label("+5V", (25.4, Y5), 180)   # internal merged rail (U5 OUT); the cable rail is +5V_CABLE
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

# ---- U5 TPS2121RUXR source mux (decision 13): +5V_CABLE priority, VBUS fallback, OUT = +5V ----
u5 = s.place("AharoniLab_Power:TPS2121RUXR", "U5", "TPS2121RUXR", (129.54, 38.1),
             footprint="AharoniLab_Package_DFN_QFN:RUX0012A")
move_text((129.54, 22.0), (111.76, 58.4))
X5 = 87.63
in1, in2 = u5.pin("IN1"), u5.pin("IN2")
s.hier_label("+5V_CABLE", (78.74, in1[1]), 180, "input")
s.connect((78.74, in1[1]), in1)
s.hier_label("VBUS", (78.74, in2[1]), 180, "input")
s.connect((78.74, in2[1]), in2)
c33 = s.place(C, "C33", "4.7uF 10V", (X5, in1[1] - 2.54), rot=180, footprint=C805)   # hangs up, GND above
s.stub(c33.pin("2"), "u", 2.54, "GND", kind="global")
cap_down("C34", "4.7uF 10V", X5, in2[1], C805)
for pn, nm in (("PR1", "PR1"), ("OV1", "OV1"), ("OV2", "OV2")):
    s.stub(u5.pin(pn), "l", 2.54, nm)
s.stub(u5.pin("CP2"), "l", 2.54, "GND", kind="global")
GND(u5.pin("GND"))
for x, top, ra, rb, va, vb, nm in ((27.94, "+5V_CABLE", "R35", "R36", "294k 1%", "100k 1%", "PR1"),
                                  (48.26, "+5V_CABLE", "R39", "R40", "464k 1%", "100k 1%", "OV1"),
                                  (68.58, "VBUS", "R41", "R42", "464k 1%", "100k 1%", "OV2")):
    ra_ = part(R, ra, va, (x, 33.02), "v", R603)
    s.stub(ra_.pin("1"), "u", 2.54, top)
    rb_ = res_down(rb, vb, x, 38.1)
    s.stub((x, 38.1), "l", 2.54, nm)
# OUT pins 1 and 8 -> +5V
o1, o8 = u5.pin("1"), u5.pin("8")
s.wire([o1, (o1[0] + 5.08, o1[1]), (o1[0] + 5.08, o8[1]), o8])
s.stub((o1[0] + 5.08, o8[1]), "r", 2.54, "+5V")
# ST -> PWR_SRC with R37 pull-up to 3V3_D
st = u5.pin("ST")
s.wire([st, (XR, st[1])])
s.hier_label("PWR_SRC", (XR, st[1]), 0, "output")
r37 = part(R, "R37", "10k", (165.1, st[1] - 5.08), "v", R603)
s.stub(r37.pin("1"), "u", 2.54, "3V3_D")
# ILM -> R38 100k to GND; SS -> C32 220 nF to GND
ilm, ss = u5.pin("ILM"), u5.pin("SS")
s.wire([ilm, (165.1, ilm[1])])
res_down("R38", "100k 1%", 165.1, ilm[1])
s.wire([ss, (149.86, ss[1])])
cap_down("C32", "220nF", 149.86, ss[1], C603)
s.text("""U5 TPS2121 source mux (PROPOSED; SLVSEA3F pin table p.4-5,
Table 9-3 p.18, ST p.18, ILM p.13): cable priority, USB-C VBUS
fallback. PR1 divider R35/R36, OV1 R39/R40, OV2 R41/R42 (VBUS).
ILM R38 100k (1.24 A typ; minimum at 100k UNRESOLVED), SS C32 220 nF.
ST low = USB powers the module (PWR_SRC). Not simulated or measured.""", (20, 52), 1.27)

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
s.text("Power: +5V_CABLE / VBUS in -> U5 mux -> +5V. U1 TPS79901 3V3, U4 TPS7A2033 3V3_D, U3 LT8365 APD bias (100-220 V) -> APD_BIAS.", (20, 12.7), 2.5)
s.text("""Design intent (Rev A, revision 3; nothing here is simulated or measured; details and citations in docs/schematic/power.md)
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
Hierarchical pins: in +5V_CABLE, VBUS, DAC_HV, HV_DIS; out 3V3, 3V3_D, APD_BIAS, HV_MON, PWR_SRC.
PROPOSED  (decision 13, revision 3) U5 TPS2121RUXR: IN1 pin 7 = +5V_CABLE (priority), IN2 pin 2 = VBUS (USB-C), OUT pins 1 and 8 = +5V (internal merged rail for U1, U3 via L2, U4); GND pin 12; CP2 pin 3 = GND. Pin numbers match the TPS2121 pin table (SLVSEA3F p.4-5, the symbol's ILM is the datasheet ILIM).
PROPOSED  Priority: PR1 from +5V_CABLE through R35 294k / R36 100k: cable selected above about 3.98-4.33 V rising, dropped below about 3.90-4.10 V (SLVSEA3F p.7-8 VREF 0.99-1.10 V, p.18 Table 9-3). UNRESOLVED: chatter near the threshold with a real ULX3S rail (hysteresis only about 0.08 V on the rail).
PROPOSED  Overvoltage: OV1 R39 464k / R40 100k from +5V_CABLE, OV2 R41 464k / R42 100k from VBUS; trip about 5.6-6.2 V, below the TPS799 7.0 V abs max (SBVS056L p.4); OV pin range 0-5.5 V (SLVSEA3F p.6).
VERIFIED  ST (pin 9): R37 10k pull-up to 3V3_D, PWR_SRC high = cable (or OUT Hi-Z), low = USB (SLVSEA3F p.18); pull-up range 6-20k p.6.
PROPOSED  ILM R38 100k (maximum RILM; ILM = 65.2/RILM^0.861 = 1.24 A typ, p.13). UNRESOLVED: the datasheet table has no 100k row (1.5 A typ at 80k, p.8), so the minimum limit is not stated. SS C32 220 nF (about 350-400 V/s, p.13 Table 9-1 scaled, estimate); first-plug settling and inrush UNRESOLVED until measured. The limit protects U5 and the cable; it does not enforce the 0.5 A USB budget.
PROPOSED  C33 4.7 uF 0805 on +5V_CABLE at IN1, C34 4.7 uF 0805 on VBUS at IN2 (TI recommends a larger input capacitor to damp cable ringing, SLVSEA3F p.33); C1/C2 stay on +5V (OUT). UNRESOLVED: USB attach capacitance limit not checked against the USB spec. No TVS (24 V abs max p.6), no other reverse protection (keyed connector).
PROPOSED  No back-feed (fast reverse blocking, <= 1 uA leakage, SLVSEA3F p.7, p.15): both present means cable powers and USB carries data only. Switchover about 100 us typ (tSW p.7); hold-up droop about 1 V estimated, not measured.
PROPOSED  ERC: U5 OUT pins 1 and 8 are power_out on the +5V net, so +5V needs no PWR_FLAG; the root PWR_FLAG #FLG04 sits on +5V_CABLE. Budget about 0.19 A worst case (docs/research/usb-standalone-power.md section 1.5, estimate); radio must stay disabled. USB-alone firmware starts HV at the low-bias end in steps (PROPOSED).""", (TX, 28), 1.4)
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
