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
TP = "AharoniLab_Connector:TestPoint"
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
# TOP BAND: input, 5V_A, TPS79901 3V3
# ======================================================================
Y5 = 66.04
s.hier_label("+5V", (25.4, Y5), 180, "input")
u1 = s.place("AharoniLab_Power:TPS79901DDCT", "U1", "TPS79901DDCT", (88.9, 68.58))
s.connect((25.4, Y5), u1.pin("IN"))
cap_down("C1", "10uF 10V", 38.1, Y5, C805)
cap_down("C2", "100nF", 50.8, Y5, C603)
cap_down("C9", "1uF", 73.66, Y5, C603)
s.wire([(76.2, Y5), (76.2, u1.pin("EN")[1]), u1.pin("EN")])
GND(u1.pin("GND"))
# 5V_A branch
s.wire([(63.5, Y5), (63.5, 43.18), (66.04, 43.18)])
fb1 = part(FBd, "FB1", "600R 0805", (66.04, 43.18), "h", "AharoniLab_Inductor_SMD:L_0805_2012Metric_N")
s.wire([fb1.pin("2"), (XR, 43.18)])
cap_down("C3", "10uF 10V", 78.74, 43.18, C805)
cap_down("C4", "100nF", 91.44, 43.18, C603)
s.hier_label("5V_A", (XR, 43.18), 0, "output")
# power flags: passive parts (bead, inductor) do not drive power_in pins, so ERC needs a driver on each node
s.place("power:PWR_FLAG", "#FLG01", "PWR_FLAG", (101.6, 43.18), in_bom=False)
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

# ======================================================================
# MIDDLE BAND: LM27762 +/-3V7
# ======================================================================
u2 = s.place("AharoniLab_Power:LM27762", "U2", "LM27762", (88.9, 116.84), unit=1)
vin = u2.pin("VIN")
s.label("+5V", (40.64, vin[1]), 180)
s.wire([(40.64, vin[1]), vin])
cap_down("C13", "4.7uF 10V", 45.72, vin[1], C805)
c1m, c1p = u2.pin("C1-"), u2.pin("C1+")
c14 = part(C, "C14", "1uF", (63.5, c1m[1] + 1.27), "v", C603)
s.wire([c1m, (63.5, c1m[1]), c14.pin("1")])
s.wire([c1p, (63.5, c1p[1]), c14.pin("2")])
# EN+/EN- tied to VIN
for pn in ("EN+", "EN-"):
    p = u2.pin(pn)
    s.wire([p, (50.8, p[1])])
s.wire([(50.8, vin[1]), (50.8, u2.pin("EN-")[1])])
# PGOOD pull-up and test point
pg = u2.pin("PGOOD")
r31 = part(R, "R31", "100k", (58.42, pg[1] - 5.08), "v", R603)
s.stub(r31.pin("1"), "u", 2.54, "3V3")
s.wire([pg, r31.pin("2")])
tp1 = s.place(TP, "TP1", "PG_VGA", (58.42, pg[1] + 5.08), rot=180,
              footprint="AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect")
s.wire([r31.pin("2"), tp1.pin("1")])
# ground / pad
g, pad = u2.pin("GND"), u2.pin("PAD")
s.wire([g, (111.76, g[1]), (111.76, pad[1]), pad])
s.global_label("GND", (114.3, g[1]), 0)
s.wire([(111.76, g[1]), (114.3, g[1])])
# CPOUT cap lying horizontally to GND
cp = u2.pin("CPOUT")
s.wire([cp, (cp[0] + 10.16, cp[1])])
c15 = part(C, "C15", "4.7uF 10V", (cp[0] + 10.16, cp[1]), "h", C805)
GND(c15.pin("2"), "r")
# +3V7
op = u2.pin("OUT+")
s.wire([op, (XR, op[1])])
s.hier_label("+3V7", (XR, op[1]), 0, "output")
cap_down("C16", "2.2uF 10V", 142.24, op[1], C603)
fbp = u2.pin("FB+")
r3 = part(R, "R3", "210k 1%", (119.38, op[1]), "v", R603)
s.wire([r3.pin("2"), (119.38, fbp[1])])
s.wire([fbp, (119.38, fbp[1])])
r4 = part(R, "R4", "100k 1%", (119.38, fbp[1]), "v", R603)
GND(r4.pin("2"))
# -3V7
om = u2.pin("OUT-")
s.wire([om, (XR, om[1])])
s.hier_label("-3V7", (XR, om[1]), 0, "output")
cap_down("C17", "2.2uF 10V", 142.24, om[1], C603)
fbn = u2.pin("FB-")
r6 = part(R, "R6", "100k 1%", (129.54, fbn[1] - 5.08), "v", R603)
GND(r6.pin("1"), "u")
r5 = part(R, "R5", "205k 1%", (129.54, fbn[1]), "v", R603)
s.wire([fbn, r5.pin("1")])
s.wire([r5.pin("2"), (129.54, om[1])])

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
# EN divider + HV_EN header
r22 = part(R, "R22", "200k 1%", (30.48, Y1 - 5.08), "v", R603)
s.stub(r22.pin("1"), "u", 2.54, "5V_HVIN")
r23 = res_down("R23", "200k 1%", 30.48, Y1)
j1 = s.place("AharoniLab_Connector:Conn_01x03", "J1", "HV_EN", (58.42, Y1 + 2.54),
             footprint="AharoniLab_Connector:PinHeader_1x03_P2.54mm_Vertical")
s.wire([(30.48, Y1), j1.pin("Pin_1")])
s.stub(j1.pin("Pin_2"), "l", 2.54, "EN")
GND(j1.pin("Pin_3"), "l")
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
cap_down("C26", "10pF C0G", 203.2, Y1, C603, dnp=True)
xs = [218.44, 231.14, 243.84, 256.54]
prev = (213.36, Y1)
for ref, x in zip(("R8", "R9", "R10", "R11"), xs):
    r = part(R, ref, "2.05M 1%", (x, Y1), "h", R603)
    s.wire([prev, r.pin("1")])
    prev = r.pin("2")
s.wire([prev, (266.7, Y1)])
s.label("HV_OUT", (266.7, Y1), 0)
r12 = part(R, "R12", "86.6k 1%", (213.36, Y1), "v", R603)
th1 = part(NTC, "TH1", "NTC 10k B3950", (213.36, Y1 + 5.08), "v", "AharoniLab_Resistor_SMD:R_0603_1608Metric_N")
GND(th1.pin("2"))
rv1 = s.place(POT, "RV1", "50k trim", (231.14, 254.0), dnp=True,
              footprint="AharoniLab_Resistor_SMD:Bourns_3224W_SMD")
s.stub(rv1.pin("1"), "u", 2.54, "3V3")
GND(rv1.pin("3"))
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

# ---- text -----------------------------------------------------------
TX = 308.0
s.text("Power: +5V in. U1 TPS79901 3V3, U2 LM27762 +/-3V7, 5V_A bead-filtered rail, U3 LT8365 APD bias (100-220 V) -> APD_BIAS.", (20, 20), 2.5)
s.text("""Design intent (Rev A; nothing here is simulated or measured; details and citations in docs/schematic/power.md)
PROPOSED  +5V entry: 10 uF + 100 nF, no reverse protection (keyed connector). 5V_A = FB1 bead + 10 uF + 100 nF for the OPA356 buffers.
PROPOSED  U1 TPS79901: VOUT = 1.193 V x (1 + R1/R2) = 3.316 V nominal (R1 17.8k, R2 10.0k). CFB 1 nF (see note).
VERIFIED  TPS79901 CFB is required for stability; 3 pF to 1 nF when R1||R2 = 250k; <5 pF for fast start (SBVS056L p.14, 8.2.2.6).
UNRESOLVED  Here R1||R2 = 6.4k, not 250k: the datasheet range was not stated for this impedance; 1 nF is a PROPOSED value.
PROPOSED  U2 LM27762: +3.72 V (R3 210k, R4 100k, 1.2 V ref) and -3.72 V (R5 205k, R6 100k, 1.22 V ref); R3 != R5 (correction 14).
VERIFIED  LM27762 FB equations and R >= 50k: SNVSAF7C p.13 (Eq. 1) and p.14 (Eq. 3). Caps: 4.7 uF CIN/CCP, 0.47-1 uF flying, 2.2 uF out (p.14-15).
PROPOSED  PGOOD pull-up 100k to 3V3 (datasheet example uses 10k to VIN, p.14). EN+/EN- tied to VIN.
PROPOSED  U3 LT8365 values per docs/calculations/apd-bias-design.md sections 3.2 and 4: 500 kHz (RT 84.5k), L1 10 uH, boost to ~110 V + doubler.
VERIFIED  SYNC/MODE: float = pulse-skip, GND = Burst, 100k to GND = Burst/SSFM (LT8365 Rev. A p.7). BIAS tie to GND if unused; INTVCC 1 uF (p.7).
PROPOSED  EN/UVLO 200k/200k from 5V_HVIN with J1 HV_EN: jumper 1-2 enable, 2-3 disable (no jumper = EN divider open, EN floating: UNRESOLVED).
PROPOSED  BIAS: R28 0R to GND fitted; R29 0R to 5V_HVIN DNP. Fit exactly one of them. SYNC options R26/R27/TP2 are DNP.
PROPOSED  D2 (GND to SW, from the p.30 250 V example, purpose not stated) is DNP. Q1/Q2 clamp ~150 uA. C8 and R19 form filter stage 1.
PROPOSED  HV_MON = HV_OUT/101 (R20+R32 10M, R21 100k): 1.39 V at 140 V. Stage 2 filter (10k + 10 nF) is on the front-end sheet.
Net names: HV_V1, HV_PUMP, HV_RAW, HV_OUT, HV_CLAMP, 5V_HVIN, EN, SYNC, BIAS, RT, SS, VC, FBX are local labels; APD_BIAS = HV_FILT.
Pending: DAC_HV and HV_MON pins are added to the root sheet by the orchestrator.""", (TX, 28), 1.4)
s.text("""HV WARNING
APD bias reaches 220 V. Stored energy ~2.3 mJ (docs/calculations/apd-bias-design.md section 4). Can be hazardous.
Never probe HV_OUT, HV_RAW, HV_PUMP, HV_V1 or HV_CLAMP directly. Use HV_MON (HV_OUT/101) for observation.
Capacitors C5-C8, C25 and resistors R19, R30 carry >= 200 V ratings; keep 200 V creepage/clearance on every HV_ net,
series-limited, with the HV netclass 1.0 mm clearance. Keep the APD_BIAS/FBX area away from TIA_IN.
Do not fit a jumper on J1 pins 2-3 and 1-2 at once. Discharge through the divider takes ~0.5 s: wait before touching.
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
