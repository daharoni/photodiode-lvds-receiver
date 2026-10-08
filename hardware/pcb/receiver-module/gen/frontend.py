#!/usr/bin/env python3
"""Generate frontend.kicad_sch (Rev A, spec section 2). Run from anywhere: python3 gen/frontend.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

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

s = Sheet.load(PATH)
XL = 25.4


def place_text(inst, ref_xy, val_xy):
    """Move the Reference/Value text of an already placed symbol (horizontal passives)."""
    sym = s.symbols[s.instances.index(inst)]
    for pr in sym:
        if isinstance(pr, list) and pr and pr[0] == "property" and str(pr[1]).strip('"') in ("Reference", "Value"):
            xy = ref_xy if str(pr[1]).strip('"') == "Reference" else val_xy
            for i, e in enumerate(pr):
                if isinstance(e, list) and e and e[0] == "at":
                    pr[i] = ["at", xy[0], xy[1], 90]
                if isinstance(e, list) and e and e[0] == "effects":
                    pr[i] = ["effects", ["font", ["size", 1.27, 1.27]]]

def gnd_cap(ref, val, fp, x, ytop, rail_y):
    """Capacitor hanging from a rail at rail_y: pin1 on rail, pin2 to GND."""
    c = s.place(C, ref, val, (x, ytop + 2.54), footprint=fp)
    s.connect((x, rail_y), c.pin("1"))
    s.stub(c.pin("2"), "d", 2.54, "GND", kind="global")
    return c

# ======================= APD with stage-2 HV filter ========================
s.hier_label("APD_BIAS", (XL, 101.6), 180, "input")
r50 = s.place(R, "R50", "10k", (55.88, 101.6), rot=270, footprint=R1206)
s.connect((XL, 101.6), r50.pin("1")) if r50.pin("1")[0] < r50.pin("2")[0] else s.connect((XL, 101.6), r50.pin("2"))
xk = 58.42
rp = max((r50.pin("1"), r50.pin("2")))
assert abs(rp[0] - xk) < 1e-6
d10 = s.place("AharoniLab_Passive:S12023-10", "D10", "S12023-10", (63.5, 127.0))
s.wire([rp, (xk, 127.0)])                      # HV_K down to the cathode
s.label("HV_K", (xk, 106.68), 0)
c50 = s.place(C, "C50", "10n", (50.8, 114.3), footprint=C1210)
s.connect((xk, 111.76), c50.pin("1"))
s.stub(c50.pin("2"), "d", 2.54, "GND", kind="global")
s.stub(d10.pin("CASE"), "d", 2.54, "GND", kind="global")
# TIA_IN: anode to OPA857 IN
XO, YO = 104.14, 132.08
u10 = s.place("AharoniLab_OpAmp:OPA857", "U10", "OPA857", (XO, YO))
s.connect(d10.pin("A"), u10.pin("IN"))
s.label("TIA_IN", (67.31, 127.0), 0)

# DNP bench fallback FDS010: same nets through labels
d11 = s.place("AharoniLab_Passive:FDS010", "D11", "FDS010", (40.64, 134.62), dnp=True)
s.stub(d11.pin("K"), "l", 2.54, "HV_K", kind="local")
s.stub(d11.pin("A"), "r", 2.54, "TIA_IN", kind="local")
s.stub(d11.pin("CASE"), "d", 2.54, "GND", kind="global")

# ======================= OPA857 =============================================
# VS+ (9,10,11): bus at x=76.2 up to the 3V3 line
BUSX = 76.2
for n in ("9", "10", "11"):
    p = u10.pin(n)
    s.wire([p, (BUSX, p[1])])
RAIL = 91.44
s.hier_label("3V3", (XL, RAIL), 180, "input")
s.wire([(XL, RAIL), (96.52, RAIL)])
s.wire([(BUSX, RAIL), (BUSX, u10.pin("11")[1])])
gnd_cap("C55", "100n", C402, 81.28, 93.98, RAIL)
gnd_cap("C56", "100n", C402, 88.9, 93.98, RAIL)
gnd_cap("C57", "1u", C603, 96.52, 93.98, RAIL)
# Test pins, NC, CTRL select
t14, t13, nc = u10.pin("14"), u10.pin("13"), u10.pin("16")
s.stub(t14, "l", 2.54, "3V3", kind="local")
s.stub(t13, "l", 2.54, "GND", kind="global")
s.no_connect(nc)
jp = s.place("AharoniLab_Connector:SolderJumper_3_Open", "JP10", "3V3=20k",
             (55.88, 142.24), rot=90)
s.stub(jp.pin("3"), "u", 2.54, "3V3", kind="local")      # B side: 3V3 (default bridge)
s.stub(jp.pin("1"), "d", 2.54, "GND", kind="global")     # A side: GND (5k)
cj = jp.pin("2")
s.wire([cj, (cj[0], 139.7), (73.66, 139.7), (73.66, u10.pin("CTRL")[1]), u10.pin("CTRL")])
# right side: GND bus
gx = 132.08
for n in ("1", "3", "4", "6", "7", "12", "17"):
    p = u10.pin(n)
    s.wire([p, (gx, p[1])])
s.wire([(gx, u10.pin("1")[1]), (gx, u10.pin("17")[1])])
s.stub((gx, u10.pin("17")[1]), "d", 2.54, "GND", kind="global")
# outputs
out, outn = u10.pin("OUT"), u10.pin("OUTN")
c51 = s.place(C, "C51", "100n", (144.78, out[1]), rot=270, footprint=C603)
c52 = s.place(C, "C52", "100n", (144.78, outn[1]), rot=270, footprint=C603)
s.connect(out, min(c51.pin("1"), c51.pin("2"))); s.connect(outn, min(c52.pin("1"), c52.pin("2")))
s.label("TIA_OUT", (132.08, out[1]), 0)
s.label("TIA_REF", (132.08, outn[1]), 0)
tp12 = s.place(TP, "TP12", "TIA_REF", (137.16, 124.46), rot=180, footprint=TPFP)
s.connect((137.16, outn[1]), tp12.pin("1"))

# ======================= AC coupling returns ================================
vp, vn = max(c51.pin("1"), c51.pin("2")), max(c52.pin("1"), c52.pin("2"))
r51 = s.place(R, "R51", "10k", (152.4, 111.76), footprint=R603)
s.connect((152.4, vp[1]), r51.pin("2")); s.wire([vp, (152.4, vp[1])])
s.stub(r51.pin("1"), "u", 2.54, "GND", kind="global")
r52 = s.place(R, "R52", "10k", (152.4, 127.0), footprint=R603)
s.wire([vn, (152.4, vn[1])]); s.connect((152.4, vn[1]), r52.pin("1"))
s.stub(r52.pin("2"), "d", 2.54, "GND", kind="global")

# ======================= VCA821 =============================================
XV, YV = 203.2, 127.0
u11 = s.place("AharoniLab_OpAmp:VCA821IDGS", "U11", "VCA821IDGS", (XV, YV))
s.wire([(152.4, vp[1]), (165.1, vp[1]), (165.1, u11.pin("+VIN")[1]), u11.pin("+VIN")])
s.wire([(152.4, vn[1]), (157.48, vn[1]), (157.48, u11.pin("-VIN")[1]), u11.pin("-VIN")])
s.label("VGA_P", (156.21, vp[1]), 0)
s.label("VGA_N", (153.67, vn[1]), 0)
# RG loop below-left of the pins
rg = s.place(R, "R53", "80.6", (186.69, 137.16), rot=270, footprint=R603)
pa, pb = sorted((rg.pin("1"), rg.pin("2")))
prg, nrg = u11.pin("+RG"), u11.pin("-RG")
s.wire([prg, (pa[0], prg[1]), pa])
s.wire([nrg, (pb[0], nrg[1]), pb])
# VG with R55/C53
s.hier_label("VG", (167.64, YV), 180, "input")
r55 = s.place(R, "R55", "100", (175.26, YV), rot=270, footprint=R603)
s.connect((167.64, YV), min(r55.pin("1"), r55.pin("2")))
vgn = (180.34, YV)
s.connect(max(r55.pin("1"), r55.pin("2")), vgn)
s.connect(vgn, u11.pin("VG"))
c53 = s.place(C, "C53", "1n", (180.34, 132.08), footprint=C603)
s.connect(vgn, c53.pin("1"))
s.stub(c53.pin("2"), "d", 2.54, "GND", kind="global")
# supplies
vcc = u11.pin("+VCC")
s.wire([vcc, (vcc[0], 99.06)])
s.wire([(177.8, 99.06), (vcc[0], 99.06), (210.82, 99.06)])
s.hier_label("+3V7", (210.82, 99.06), 0, "input")
gnd_cap("C58", "100n", C402, 185.42, 99.06, 99.06)
gnd_cap("C60", "2u2", C603, 177.8, 99.06, 99.06)
vee = u11.pin("-VCC")
s.wire([vee, (vee[0], 149.86)])
s.wire([(177.8, 149.86), (vee[0], 149.86), (210.82, 149.86)])
s.hier_label("-3V7", (210.82, 149.86), 0, "input")
for ref, val, fp, x in (("C59", "100n", C402, 185.42), ("C61", "2u2", C603, 177.8)):
    c = s.place(C, ref, val, (x, 152.4), footprint=fp)
    s.connect((x, 149.86), c.pin("1"))
    s.stub(c.pin("2"), "d", 2.54, "GND", kind="global")
s.stub(u11.pin("GND"), "d", 2.54, "GND", kind="global")
# RF feedback loop
o, fb = u11.pin("OUT"), u11.pin("FB")
r54 = s.place(R, "R54", "402", (223.52, 127.0), footprint=R603)
s.wire([o, (223.52, o[1])]); s.connect(fb, r54.pin("2")); s.wire([fb, (223.52, fb[1])])

# ======================= level shift ========================================
c54 = s.place(C, "C54", "10n", (243.84, o[1]), rot=270, footprint=C603)
cl, cr = sorted((c54.pin("1"), c54.pin("2")))
s.wire([(223.52, o[1]), cl])
s.label("VGA_OUT", (229.87, o[1]), 0)
tp10 = s.place(TP, "TP10", "VGA_OUT", (226.06, 119.38), footprint=TPFP)
s.connect((226.06, o[1]), tp10.pin("1"))
xs = 251.46
s.wire([cr, (xs, o[1]), (261.62, o[1])])
s.hier_label("SDET", (261.62, o[1]), 0, "output")
tp11 = s.place(TP, "TP11", "SDET", (256.54, 119.38), footprint=TPFP)
s.connect((256.54, o[1]), tp11.pin("1"))
r56 = s.place(R, "R56", "10k", (xs, 129.54), footprint=R603)
s.connect((xs, o[1]), r56.pin("1"))
s.wire([r56.pin("2"), (xs, 134.62), (261.62, 134.62)])
s.hier_label("VCM_DET", (261.62, 134.62), 0, "input")

# ======================= text ================================================
s.text("Front end: S12023-10 APD, OPA857 TIA, AC coupling, VCA821 VGA, level shift to SDET. Left to right in signal order.", (XL, 40), 2.5)
s.text("HV: HV_K is the APD cathode net (up to 220 V). Keep-out from TIA_IN (200 V creepage/clearance). No HV test points. R50 and C50 sit at the cathode.", (XL, 58), 1.5)
s.text("APD polarity: cathode (D10 pin 1) to positive bias, anode (pin 3) to TIA_IN, case (pin 2) to GND. D11 FDS010 is a DNP bench fallback on the same nets.", (XL, 62), 1.5)
s.text("""Design intent (Rev A, nothing here is simulated or measured)
PROPOSED   Stage 2 filter R50 10k (1206, 200 V) + C50 10n (1210, 500 V C0G) at the cathode from APD_BIAS to HV_K; stage 1 is on the Power sheet. 2 uC dump-risk note and 4.7n alternative: open test item.
VERIFIED   Polarity and pins: S12023-10 K=1, CASE=2, A=3 (lab library symbol). Cathode to positive bias (standing correction 2). 6 pF for S12023-10 and FDS010 alike.
VERIFIED   OPA857: Test_SD (13) to GND and Test_IN (14) to +VS for normal operation (SBOS630D p.4 pin table); CTRL logic 1 = 20k, 0 = 5k, VIH 2 V, VIL 0.8 V (p.6-7); OUTN is a 1.83 V typ reference (p.6, VICR).
PROPOSED   JP10 3-pad solder jumper on CTRL: common = CTRL, default bridge to the 3V3 side (20k gain), GND side = 5k. Footprint is open, bridge at assembly.
PROPOSED   OPA857 VS+ (9, 10, 11) on 3V3 with 2 x 100n 0402 + 1u 0603; all GND pins and PAD to GND; NC (16) no connect. Keep decouplers < 0.25 in from the pins (p.24 layout).
PROPOSED   AC coupling C51/C52 100n into R51/R52 10k to GND (corner 159 Hz); both OUT and OUTN coupled (standing correction 1).
VERIFIED   VCA821 DGS pins and RF 402 / RG 80.6 for 20 dB (SBOS407D p.4 pin table, p.28 Table 2: RG 80, RF 402 is the G = 10 column). RF is compensation (standing correction 5): keep the datasheet network.
PROPOSED   VG through R55 100 + C53 1n. VCC pins on +/-3V7 with 100n 0402 + 2u2 0603 each.
UNRESOLVED Datasheet input limit (p.9, Figure: VIN max = 2 x RG x 2.6 mA) is ~0.42 Vpp at RG = 80 ohm; the 20k TIA path saturates it near 21 uA peak. RG may need to move up.
UNRESOLVED OPA857 stability at 6 pF source capacitance is not verified. The datasheet characterises CS = 1.5 pF (p.6).
PROPOSED   Level shift C54 10n + R56 10k to VCM_DET (corner 1.6 kHz). TP10 VGA_OUT, TP11 SDET, TP12 TIA_REF.
UNRESOLVED VCA821 supply is specified 7 V to 12 V total (p.36); +/-3.7 V is 7.4 V, 0.4 V above the minimum.""", (XL, 175), 1.5)
place_text(r50, (55.88, 98.0), (55.88, 104.8))
place_text(c51, (144.78, 112.5), (144.78, 114.2))
place_text(c52, (144.78, 125.3), (144.78, 127.0))
place_text(rg, (186.69, 134.2), (186.69, 140.0))
place_text(r55, (175.26, 130.2), (175.26, 131.9))
place_text(c54, (243.84, 121.0), (243.84, 127.6))
place_text(jp, (49.53, 141.0), (49.53, 143.5))
s.save(PATH)
print("wrote", PATH)
