#!/usr/bin/env python3
"""Generate connector.kicad_sch (Rev A revision 4, decision 14, spec section 6). Run: python3 gen/connector.py"""
import os, sys, textwrap
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/connector.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
J50L = "AharoniLab_Connector:632723300011"
J51L = "AharoniLab_Connector:Conn_01x06"
U50L = "AharoniLab_Interface:SN65LVDS104PW"
ESDL = "AharoniLab_Misc:TPD6E05U06"
TP = "AharoniLab_Connector:TestPoint"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
C402 = "AharoniLab_Capacitor_SMD:C_0402_1005Metric_N"
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"

s = Sheet.load(PATH)
GND = lambda p, d="d", n=2.54: s.stub(p, d, n, "GND", kind="global")


def tidy_text(inst, horizontal):
    """Reference above and value below a horizontal part (or beside a vertical one), centred."""
    sym = s.symbols[s.instances.index(inst)]
    for prop in sym:
        if isinstance(prop, list) and prop[0] == "property" and str(prop[1]) in ("Reference", "Value"):
            at = [x for x in prop if isinstance(x, list) and x[0] == "at"][0]
            eff = [x for x in prop if isinstance(x, list) and x[0] == "effects"][0]
            eff[:] = [x for x in eff if not (isinstance(x, list) and x[0] == "justify")]
            if horizontal:
                at[1:4] = [inst.at[0], inst.at[1] + (-2.2 if str(prop[1]) == "Reference" else 2.2), 0]
            else:
                at[1:4] = [inst.at[0] + 2.0, inst.at[1] + (-1.0 if str(prop[1]) == "Reference" else 1.0), 0]
                eff.append(["justify", "left"])


def rh(ref, val, cx, cy, dnp=False, fp=R603):
    """Horizontal resistor centred at (cx, cy); returns (inst, left pin, right pin)."""
    i = s.place(R, ref, val, (cx, cy), rot=90, footprint=fp, dnp=dnp)
    tidy_text(i, True)
    a, b = i.pin("1"), i.pin("2")
    return (i,) + ((a, b) if a[0] < b[0] else (b, a))


def rv(ref, val, x, y, dnp=False, fp=R603):
    """Vertical part, pin 1 on top at (x, y); returns the instance."""
    i = s.place(R, ref, val, (x, y + 2.54), footprint=fp, dnp=dnp)
    tidy_text(i, False)
    return i


def cv(ref, val, x, y, fp=C603, dnp=False):
    i = s.place(C, ref, val, (x, y + 2.54), footprint=fp, dnp=dnp)
    tidy_text(i, False)
    return i


# ====================================================================== J50 USB-C receptacle
JX, JY = 254.0, 101.6
j50 = s.place(J50L, "J50", "632723300011", (JX, JY))
# (pin, kind, net, shape)
J50_MAP = [
    ("A1", "global", "GND", None), ("A2", "local", "LVDS_OUT1_P", None), ("A3", "local", "LVDS_OUT1_N", None),
    ("A4", "hier", "VBUS", "output"), ("A5", "local", "CC1", None), ("A6", "hier", "USB_DP", "bidirectional"),
    ("A7", "hier", "USB_DM", "bidirectional"), ("A8", "local", "AUX_CAB", None), ("A9", "local", "VBUS", None),
    ("A10", "local", "CAN_L", None), ("A11", "local", "CAN_H", None), ("A12", "global", "GND", None),
    ("B1", "global", "GND", None), ("B2", "local", "LVDS_OUT2_P", None), ("B3", "local", "LVDS_OUT2_N", None),
    ("B4", "local", "VBUS", None), ("B5", "local", "CC2", None), ("B6", "local", "USB_DP", None),
    ("B7", "local", "USB_DM", None), ("B8", "local", "AUX_CAB", None), ("B9", "local", "VBUS", None),
    ("B10", "hier", "CAN_L", "bidirectional"), ("B11", "hier", "CAN_H", "bidirectional"), ("B12", "global", "GND", None),
]
for num, kind, net, shape in J50_MAP:
    d = "l" if num[0] == "A" else "r"
    s.stub(j50.pin(num), d, 5.08, net, kind=kind, shape=shape or "passive")
# shield S1 -> C181 1n || R170 1M (DNP) to GND
s1 = j50.pin("S1")
ys = s1[1] + 5.08
s.wire([s1, (s1[0], ys)])
s.label("SHIELD", (s1[0], ys), 0)
s.wire([(s1[0], ys), (s1[0] + 7.62, ys)])
c181 = cv("C181", "1nF", s1[0], ys)
r170 = rv("R170", "1M", s1[0] + 7.62, ys, dnp=True)
GND(c181.pin("2")); GND(r170.pin("2"))

# ====================================================================== U50 SN65LVDS104PW fan-out
UX, UY = 88.9, 101.6
u50 = s.place(U50L, "U50", "SN65LVDS104PW", (UX, UY))
a, b = u50.pin("A"), u50.pin("B")
s.hier_label("LVDS_P", (50.8, a[1]), 180, "input"); s.wire([(50.8, a[1]), a])
s.hier_label("LVDS_N", (50.8, b[1]), 180, "input"); s.wire([(50.8, b[1]), b])
r180 = s.place(R, "R180", "100R 0.1%", (63.5, (a[1] + b[1]) / 2), footprint=R603)
tidy_text(r180, False)
s.wire([r180.pin("1"), (63.5, a[1])]); s.wire([r180.pin("2"), (63.5, b[1])])
for pn in ("EN1", "EN2", "EN3"):
    s.stub(u50.pin(pn), "l", 5.08, "3V3")
s.stub(u50.pin("EN4"), "l", 5.08, "GND", kind="global")
GND(u50.pin("GND"))
for pn, net in (("1Y", "LVDS_OUT1_P"), ("1Z", "LVDS_OUT1_N"), ("2Y", "LVDS_OUT2_P"), ("2Z", "LVDS_OUT2_N"),
                ("3Y", "LVDS_DBG_P"), ("3Z", "LVDS_DBG_N")):
    s.stub(u50.pin(pn), "r", 5.08, net)
s.no_connect(u50.pin("4Y")); s.no_connect(u50.pin("4Z"))
vcc = u50.pin("VCC")
yv = vcc[1] - 5.08
s.wire([vcc, (vcc[0], yv), (vcc[0] + 15.24, yv)])
s.label("3V3", (vcc[0], yv), 180)
c184 = cv("C184", "100nF", vcc[0] + 7.62, yv, fp=C402)
c185 = cv("C185", "1uF", vcc[0] + 15.24, yv)
GND(c184.pin("2")); GND(c185.pin("2"))
# R177 100R across the J51 scope pair (DNP)
r177 = rv("R177", "100R", 101.6, 134.62, dnp=True)
s.stub(r177.pin("1"), "u", 2.54, "LVDS_DBG_P"); s.stub(r177.pin("2"), "d", 2.54, "LVDS_DBG_N")

# ====================================================================== ESD arrays
def esd(ref, x, y, chans):
    u = s.place(ESDL, ref, "TPD6E05U06", (x, y))
    for pn, net in chans:
        if net is None:
            s.no_connect(u.pin(pn))
        else:
            s.stub(u.pin(pn), "l", 5.08, net)
    # pins 1-4, 6, 7 are hidden NC-type pins in the library symbol: no flag needed (a flag there is dangling)
    GND(u.pin("5")); GND(u.pin("10"))
    return u

esd("U51", 172.72, 101.6, [("14", "LVDS_OUT1_P"), ("13", "LVDS_OUT1_N"), ("12", "LVDS_OUT2_P"),
                           ("11", "LVDS_OUT2_N"), ("9", "CC1"), ("8", "CC2")])
esd("U52", 172.72, 152.4, [("14", "CAN_H"), ("13", "CAN_L"), ("12", "CAN_H"), ("11", "CAN_L"),
                           ("9", "AUX_CAB"), ("8", None)])

# ====================================================================== CC Rd and taps, AUX
def cc_tap(n, y, rd, rs, rsh, csh, net, sense):
    s.label(net, (45.72, y), 180)
    ri, pl, pr = rh(rs, "100k", 55.88, y)
    s.wire([(45.72, y), pl])
    s.wire([pr, (73.66, y), (81.28, y)])
    s.hier_label(sense, (81.28, y), 0, "output")
    rd_ = rv(rd, "5.1k 1%", 50.8, y)
    GND(rd_.pin("2"))
    r_ = rv(rsh, "100k", 66.04, y); GND(r_.pin("2"))
    c_ = cv(csh, "100nF", 73.66, y); GND(c_.pin("2"))

cc_tap(1, 170.18, "R181", "R185", "R187", "C182", "CC1", "CC1_SENSE")
cc_tap(2, 190.5, "R184", "R188", "R189", "C183", "CC2", "CC2_SENSE")
s.label("AUX_CAB", (45.72, 210.82), 180)
ri, pl, pr = rh("R186", "1k", 55.88, 210.82)
s.wire([(45.72, 210.82), pl])
s.wire([pr, (66.04, 210.82)])
s.hier_label("AUX", (66.04, 210.82), 0, "bidirectional")

# ====================================================================== CAN split termination (DNP, single-module bench only)
s.label("CAN_H", (101.6, 190.5), 180)
r182, l1, r1 = rh("R182", "60.4R 1%", 109.22, 190.5, dnp=True)
r183, l2, r2 = rh("R183", "60.4R 1%", 121.92, 190.5, dnp=True)
s.wire([(101.6, 190.5), l1]); s.wire([r1, l2]); s.wire([r2, (134.62, 190.5)])
s.label("CAN_L", (134.62, 190.5), 0)
c180 = cv("C180", "4.7nF", 115.57, 190.5, dnp=True)
GND(c180.pin("2"))

# ====================================================================== J51 scope header
j51 = s.place(J51L, "J51", "DEBUG / scope", (203.2, 187.96))
for i, (kind, net) in enumerate([("global", "GND"), ("local", "LVDS_DBG_P"), ("local", "LVDS_DBG_N"),
                                 ("local", "CAN_H"), ("local", "CAN_L"), ("local", "AUX")], 1):
    s.stub(j51.pin(str(i)), "l", 5.08, net, kind=kind)

# ====================================================================== test points TP50-TP55
XL = 292.1
tps = [("3V3", "hier"), ("3V3_D", "hier"), ("RSSI", "hier"), ("HV_MON", "hier"), ("GND", "global"), ("GND", "global")]
y = 170.18
for n, (net, kind) in enumerate(tps):
    tp = s.place(TP, "TP%d" % (50 + n), net, (317.5, y), footprint=TPFP)
    p = tp.pin("1")
    if kind == "hier":
        s.hier_label(net, (XL, y), 180, "input"); s.wire([(XL, y), p])
    else:
        s.stub(p, "l", 12.7, net, kind="global")
    y += 10.16


def wrap(txt, w):
    out = []
    for ln in txt.split("\n"):
        out += textwrap.wrap(ln, w, subsequent_indent="  ", break_long_words=False) or [""]
    return "\n".join(out)


s.text("Connector: J50 USB-C (Wuerth 632723300011, 24-pin), U50 LVDS fan-out, U51/U52 ESD, J51 scope header (revision 4, decision 14).", (38.1, 12.7), 2.5)
s.text(wrap("""Design intent (Rev A revision 4, 2026-10-09, decision 14; PROPOSED unless labelled; nothing here is simulated or measured)
ONE CONNECTOR: J50 carries 5 V (VBUS pins A4/A9/B4/B9 tied, hierarchical output VBUS to the Power eFuse and the Controller), USB 2.0 D+/D- (A6/B6 tied = USB_DP, A7/B7 tied = USB_DM), the 50 Mbps LVDS pair on both SuperSpeed TX pairs through the fan-out U50 (1Y/1Z -> A2/A3, 2Y/2Z -> B2/B3), CAN on both RX pairs (CAN_H = B11 and A11, CAN_L = B10 and A10) and the SBU pair tied as AUX (A8/B8 -> AUX_CAB -> R186 1k -> AUX). Plug orientation does not matter: P to SSTXp and N to SSTXn on both pairs (USB Type-C R2.5 Table 3-10 p.83).
Rd/CC: R181 and R184 5.1 k 1 % on CC1 and CC2 (Type-C R2.0 Table 4-25 p.236). Taps 100k/100k with 100 nF give CC1_SENSE and CC2_SENSE for the ESP32 ADC; 100k/100k keeps the pin below 3.3 V even with 5.5 V VCONN on the unused CC (TC R2.5 p.155). The 200 k tap lowers Rd by about 2.5 %: fold into firmware thresholds.
U50 SN65LVDS104PW (LVDS104 SLLS396G p.3-5, p.16 Fig. 25): no on-chip termination, so R180 100 ohm 0.1 % across A/B is FITTED; enables active high (section 9.4 Table 2), EN1-EN3 to 3V3, EN4 to GND (output 4 disabled, 4Y/4Z no_connect), output 3 feeds J51 with R177 100 ohm DNP across it (UNRESOLVED whether an unloaded output 3 is acceptable). 23 mA typ, 35 mA max (p.5). VOD 250/350/450 mV (TLV3605 p.7) against the 100 mV buffer threshold: 150 mV margin at minimum VOD (arithmetic). Fail-safe: static high with no TLV3605 power (p.15-16). Do NOT add a second 100 ohm at the FPGA without DIFFRESISTOR consideration: the ECP5 input is terminated on-die (DIFFRESISTOR 100, docs/research/ulx3s-lvds-input.md); each of the two paths sees one load.
ESD: U51 (SSTX1, SSTX2 pairs, CC1, CC2) and U52 (CAN on both RX pairs, SBU AUX_CAB, one spare channel) TPD6E05U06RVZ (TI SLVSBO7O Table 5.4 p.7: 0.47 pF, VRWM 5.5 V); place within a few mm of J50. D+/D- clamp is U61 on the Controller sheet.
CAN: no termination on the module (SLLA270 p.4, p.8); R182/R183/C180 are DNP for a single-module bench; never fit them on a module in a star. 125 kbit/s PROPOSED. Two bused pairs give about 45 ohm in parallel, acceptable at the slowed edges.
Shield: S1 to GND through C181 1 nF with R170 1 M (DNP). Layout rules (not schematic): Dp/Dn ties within 3.5 mm of J50 (TC Table 3-4 note 1 p.77).
UNRESOLVED: top- or mid-mount J50; SBU exposure to a laptop alternate mode; unidirectional ESD clamp near -0.7 V versus cable GND drop on CAN; the 3.3 V-only ESP32 GPIO behind R186 1k.""", 150), (38.1, 232.0), 1.1)
s.text(wrap("""J50 pin map (WE 632723300011 p.3, TC Table 3-4 p.76; A5/B5 are labelled CC/VCONN by Wuerth, wired as CC1/CC2: PROPOSED reading)
A1 GND  A2 SSTXP1=LVDS_OUT1_P  A3 SSTXN1=LVDS_OUT1_N  A4 VBUS  A5 CC1  A6 DP1=USB_DP  A7 DN1=USB_DM  A8 SBU1=AUX_CAB  A9 VBUS  A10 SSRXN2=CAN_L  A11 SSRXP2=CAN_H  A12 GND
B1 GND  B2 SSTXP2=LVDS_OUT2_P  B3 SSTXN2=LVDS_OUT2_N  B4 VBUS  B5 CC2  B6 DP2=USB_DP  B7 DN2=USB_DM  B8 SBU2=AUX_CAB  B9 VBUS  B10 SSRXN1=CAN_L  B11 SSRXP1=CAN_H  B12 GND
J51 DEBUG (2.54 mm 1x6): 1 GND, 2 LVDS_DBG_P (U50 3Y), 3 LVDS_DBG_N (U50 3Z), 4 CAN_H, 5 CAN_L, 6 AUX.
Test points TP50-TP55: 3V3, 3V3_D, RSSI, HV_MON, GND, GND. DNP: R170, R177, R182, R183, C180.
Cable rule: passive full-featured USB 3.2 Gen 1, 3 A, e-marked, <= 2 m certified; 3 m only after a bench check (TC Table 3-1 p.44, 3.4.1.1 p.83, 4.4.1 p.151). Labelling: USB-C: USB 2.0 and 5 V only on a host; SuperSpeed pairs carry proprietary LVDS/CAN, not USB 3; the module is not USB 3 compliant.
HV rule: no bare APD_BIAS pad on this sheet; HV_MON (about Vout/101) is the only HV observation point.
ULX3S target pairs (PROPOSED; ULX3S schematics v3.1.7 p.2, Lattice FPGA-TN-02032 v1.4 p.14, p.26): first choice gp/gn[8..13] (bank 7), second gp/gn[14..21]; not [0..7] or [22..27]. Constrain gp only; do not guess polarity.""", 150), (200.0, 232.0), 1.1)
s.save(PATH)
print("wrote", PATH)
