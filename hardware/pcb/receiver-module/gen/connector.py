#!/usr/bin/env python3
"""Generate connector.kicad_sch (Rev A rev. 2026-10-08, spec section 6). Run: python3 gen/connector.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/connector.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
J50L = "AharoniLab_Connector:61201221621"
J51L = "AharoniLab_Connector:Conn_01x06"
TP = "AharoniLab_Connector:TestPoint"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"

s = Sheet.load(PATH)
XL = 38.1

# ---- J50 module cable (2x06 shrouded). Odd pins on the left of the symbol, even on the right.
JX, JY = 127.0, 55.88
j50 = s.place(J50L, "J50", "MODULE CABLE", (JX, JY))
# (pin, side, kind, net, shape)
J50_MAP = [
    ("1", "hier", "+5V_CABLE", "output"), ("2", "local", "+5V_CABLE", None),
    ("3", "global", "GND", None), ("4", "global", "GND", None),
    ("5", "hier", "LVDS_P", "input"), ("6", "hier", "LVDS_N", "input"),
    ("7", "global", "GND", None), ("8", "global", "GND", None),
    ("9", "hier", "CAN_H", "bidirectional"), ("10", "hier", "CAN_L", "bidirectional"),
    ("11", "local", "AUX2_CAB", None), ("12", "local", "AUX_CAB", None),
]
for num, kind, net, shape in J50_MAP:
    p = j50.pin(num)
    d = "l" if int(num) % 2 else "r"
    if kind == "hier":
        s.stub(p, d, 5.08, net, kind="hier", shape=shape)
    elif kind == "global":
        s.stub(p, d, 5.08, net, kind="global")
    else:
        s.stub(p, d, 7.62, net)

# ---- Bench-only parts (all DNP)
BY = 101.6
r180 = s.place(R, "R180", "100R 0.1%", (45.72, BY), dnp=True, footprint=R603)
s.stub(r180.pin("1"), "u", 2.54, "LVDS_P")
s.stub(r180.pin("2"), "d", 2.54, "LVDS_N")
r182 = s.place(R, "R182", "60.4R 1%", (71.12, BY), rot=90, dnp=True, footprint=R603)
r183 = s.place(R, "R183", "60.4R 1%", (106.68, BY), rot=90, dnp=True, footprint=R603)
c180 = s.place(C, "C180", "4.7nF", (88.9, BY + 10.16), dnp=True, footprint=C603)
s.stub(r182.pin("1"), "l", 2.54, "CAN_H")
s.stub(r183.pin("2"), "r", 2.54, "CAN_L")
s.connect(r182.pin("2"), r183.pin("1"))
s.wire([c180.pin("1"), (88.9, BY)])
s.label("CAN_SPLIT", (91.44, BY), 0)
s.stub(c180.pin("2"), "d", 2.54, "GND", kind="global")

# ---- AUX / AUX2 paths: J50.12 -> R186 1k -> AUX ; J50.11 -> R187 1k -> AUX2 (reserved ESP32 GPIOs)
r186 = s.place(R, "R186", "1k", (160.02, 152.4), rot=90, footprint=R603)
s.stub(r186.pin("1"), "l", 2.54, "AUX_CAB")
s.stub(r186.pin("2"), "r", 2.54, "AUX", kind="hier", shape="bidirectional")
r187 = s.place(R, "R187", "1k", (160.02, 165.1), rot=90, footprint=R603)
s.stub(r187.pin("1"), "l", 2.54, "AUX2_CAB")
s.stub(r187.pin("2"), "r", 2.54, "AUX2", kind="hier", shape="bidirectional")

# ---- J51 DEBUG: 1 GND, 2 RSSI, 3 AUX2, 4 AUX, 5 HV_MON, 6 3V3_D
j51 = s.place(J51L, "J51", "DEBUG", (220.98, 127.0))
for i, (kind, net) in enumerate([("global", "GND"), ("local", "RSSI"), ("local", "AUX2"),
                                 ("local", "AUX"), ("local", "HV_MON"), ("local", "3V3_D")], 1):
    p = j51.pin(str(i))
    if kind == "global":
        s.stub(p, "l", 5.08, net, kind="global")
    else:
        s.stub(p, "l", 5.08, net)

# ---- Test points TP50-TP55
tps = [("3V3", "hier"), ("3V3_D", "hier"), ("RSSI", "hier"), ("HV_MON", "hier"), ("GND", "global"), ("GND", "global")]
y = 185.42
for n, (net, kind) in enumerate(tps):
    tp = s.place(TP, "TP%d" % (50 + n), net, (63.5, y), footprint=TPFP)
    p = tp.pin("1")
    if kind == "hier":
        s.hier_label(net, (XL, y), 180, "input"); s.wire([(XL, y), p])
    else:
        s.stub(p, "l", 12.7, net, kind="global")
    y += 10.16

# ---- Move small-passive ref/value text off their own wires: above/below the body, centred.
def tidy_text(inst, horizontal):
    sym = s.symbols[s.instances.index(inst)]
    for prop in sym:
        if isinstance(prop, list) and prop[0] == "property" and str(prop[1]) in ("Reference", "Value"):
            at = [x for x in prop if isinstance(x, list) and x[0] == "at"][0]
            eff = [x for x in prop if isinstance(x, list) and x[0] == "effects"][0]
            eff[:] = [x for x in eff if not (isinstance(x, list) and x[0] == "justify")]
            if horizontal:
                at[1:4] = [inst.at[0], inst.at[1] + (-2.2 if str(prop[1]) == "Reference" else 2.2), 90]
            else:
                at[1:4] = [inst.at[0] + 2.0, inst.at[1] + (-1.0 if str(prop[1]) == "Reference" else 1.0), 0]
                eff.append(["justify", "left"])
for ri in (r182, r183, r186, r187):
    tidy_text(ri, True)
for ri in (r180, c180):
    tidy_text(ri, False)

s.text("Connector: J50 module cable (ULX3S side), J51 debug header, bench test points.", (38.1, 12.7), 2.5)
s.text("""Design intent (Rev A revision 3, 2026-10-09, decisions 12 and 13; nothing here is simulated or measured)

+5V_CABLE (PROPOSED, decision 13): J50 pins 1 and 2 are the system rail, renamed from +5V. It is the priority input of the Power sheet source mux U5 (TPS2121);
  the module never sources it, and with USB-C also attached the cable powers the module and USB carries data only.

ULX3S target pairs (PROPOSED; ULX3S schematics v3.1.7 p.2, Lattice FPGA-TN-02032 v1.4 p.14, p.26):
  First choice gp/gn[8..13] (bank 7, left), second choice gp/gn[14..21] (banks 2/3, right).
  Do not use gp/gn[0..7] or [22..27]: banks 0/1 have no differential input and no on-die termination.
  Constrain the true pad (gp) only; gn is the complement. Do not guess polarity: swap in gateware if reversed.
LVDS termination rule (PROPOSED; docs/research/ulx3s-lvds-input.md s.3): terminate at the FPGA with DIFFRESISTOR="100".
  R180 (100R) is DNP and bench-only (scope or test load with no FPGA attached).
  NEVER fit R180 with DIFFRESISTOR on: two 100R loads make ~50R and cut VOD by about half (arithmetic, not measured).
  No series capacitors and no pull-ups on the pair (TLV3605 output is DC-coupled at ~1.2 V common mode, TLV3605 DS p.7).
  ECP5 LVDS input common-mode range: UNRESOLVED (FPGA-DS-02012 not obtained).
CAN rule (PROPOSED; docs/research/module-controller.md s.3, SLLA270 p.4, p.8): NO termination on the module.
  One split termination (2 x 60R 1% + 4.7 nF to ground) sits at the FPGA-end junction only; modules are plug-in, so a
  module-end resistor would leave with the module and load the star (120/N ohm). R182/R183/C180 here are DNP
  and for a single-module bench setup only; never fit them on a module that joins a star.
  Bit rate 125 kbit/s (8 us bit), PROPOSED; verify on the bench at G1/G2.
AUX / AUX2 (PROPOSED): J50.12 -> R186 1k -> AUX and J50.11 -> R187 1k -> AUX2, both bidirectional to the Controller
  (reserved ESP32 GPIOs, undefined function). The old HOLD_N buffer (U50, R184, R185, C181) is removed in revision 2.
  SHDN_N and LE_HYS are driven from the Controller sheet; no pull-ups here.
HV rule (PROPOSED): no bare APD_BIAS pad on this sheet. HV_MON (~Vout/101, unbuffered 10 M / 100 k divider with 10 nF,
  source impedance ~100 k) is the ONLY HV observation point.""",
       (150.0, 205.0), 1.5)
s.text("""J50 MODULE CABLE pinout (Wuerth 61201221621, 2x06 shrouded, 2.54 mm; PROPOSED,
docs/research/module-controller.md s.6; pins 2n-1/2n share a row)
Row 1:  1 +5V_CABLE  2 +5V_CABLE  system supply rail (mux priority input on Power, never sourced by the module)
Row 2:  3 GND      4 GND      power return
Row 3:  5 LVDS_P   6 LVDS_N   50 Mbps pair on adjacent pins (twisted pair)
Row 4:  7 GND      8 GND      ground row between LVDS and CAN
Row 5:  9 CAN_H    10 CAN_L   CAN pair
Row 6:  11 AUX2    12 AUX     reserved control lines, each 1k to the Controller (ESP32 GPIOs)
Pin 12: research doc proposes SPARE (wire to GND at both ends if unused); the spec makes it AUX.""",
       (200.0, 20.0), 1.5)
s.text("""J51 DEBUG pinout (2.54 mm, 1x6)
1  GND
2  RSSI     received-signal strength (Monitor sheet)
3  AUX2     after R187 1k
4  AUX      after R186 1k
5  HV_MON   ~Vout/101, only HV observation point
6  3V3_D    digital rail""", (240.0, 120.0), 1.5)
s.text("Test points TP50-TP55: 3V3, 3V3_D, RSSI, HV_MON, GND, GND. DNP bench parts: R180, R182, R183, C180.", (38.1, 280.0), 1.5)
s.save(PATH)
