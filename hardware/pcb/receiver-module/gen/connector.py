#!/usr/bin/env python3
"""Generate connector.kicad_sch (Rev A, spec section 6). Run: python3 gen/connector.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/connector.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
CONN = "AharoniLab_Connector:Conn_01x06"
TP = "AharoniLab_Connector:TestPoint"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"

s = Sheet.load(PATH)
XL = 38.1
JX = 203.2

def conn(ref, name, y, nets):
    """nets: per pin (kind, name). kind: 'hier_in','hier_out','local','global'."""
    j = s.place(CONN, ref, name, (JX, y), footprint=None) if False else s.place(CONN, ref, name, (JX, y))
    for i, (kind, net) in enumerate(nets, 1):
        p = j.pin(str(i))
        if kind == "global":
            s.stub(p, "l", 5.08, net, kind="global")
        elif kind == "local":
            s.stub(p, "l", 5.08, net)
        else:
            s.hier_label(net, (XL, p[1]), 180, "output" if kind == "hier_out" else "input")
            s.wire([(XL, p[1]), p])
    return j

# J50 ULX3S: 1 +5V, 2 GND, 3 LVDS_P, 4 LVDS_N, 5 GND, 6 HOLD_N
conn("J50", "ULX3S", 76.2, [("hier_out", "+5V"), ("global", "GND"), ("hier_in", "LVDS_P"),
                            ("hier_in", "LVDS_N"), ("global", "GND"), ("hier_out", "HOLD_N")])
# J51 DEBUG: 1 GND, 2 LOS, 3 SHDN_N, 4 LE_HYS, 5 HOLD_N, 6 HV_MON
conn("J51", "DEBUG", 127.0, [("global", "GND"), ("hier_in", "LOS"), ("hier_out", "SHDN_N"),
                             ("hier_out", "LE_HYS"), ("local", "HOLD_N"), ("local", "HV_MON")])

# R180: bench-only 100R across the pair, DNP (labels keep the LVDS rows free of crossings)
r180 = s.place(R, "R180", "100R 0.1%", (165.1, 101.6), dnp=True, footprint=R603)
s.stub(r180.pin("1"), "u", 2.54, "LVDS_P")
s.stub(r180.pin("2"), "d", 2.54, "LVDS_N")
# R181: LE_HYS pull-up so an unplugged header leaves the latch released
r181 = s.place(R, "R181", "100k", (180.34, 101.6), footprint=R603)
s.stub(r181.pin("1"), "u", 2.54, "3V3")
s.stub(r181.pin("2"), "d", 2.54, "LE_HYS")

# Test point column
tps = [("3V3", "hier"), ("+3V7", "hier"), ("-3V7", "hier"), ("5V_A", "hier"), ("VMID", "hier"),
       ("VSPAN", "hier"), ("HV_MON", "hier"), ("GND", "global"), ("GND", "global")]
y = 152.4
for n, (net, kind) in enumerate(tps):
    tp = s.place(TP, "TP%d" % (50 + n), net, (63.5, y), footprint=TPFP)
    p = tp.pin("1")
    if kind == "hier":
        s.hier_label(net, (XL, y), 180, "input"); s.wire([(XL, y), p])
    elif kind == "local":
        s.stub(p, "l", 12.7, net)
    else:
        s.stub(p, "l", 12.7, net, kind="global")
    y += 12.7

s.text("Connector: J50 ULX3S link, J51 debug header, bench test points.", (38.1, 20.32), 2.5)
s.text("""Design intent (Rev A, nothing here is simulated or measured)

ULX3S target pairs (PROPOSED; ULX3S schematics v3.1.7 p.2, Lattice FPGA-TN-02032 v1.4 p.14, p.26):
  First choice gp/gn[8..13] (bank 7, left), second choice gp/gn[14..21] (banks 2/3, right).
  Do not use gp/gn[0..7] or [22..27]: banks 0/1 have no differential input and no on-die termination.
  Constrain the true pad (gp) only; gn is the complement. Do not guess polarity: swap in gateware if reversed.
Termination rule (PROPOSED; docs/research/ulx3s-lvds-input.md s.3): terminate at the FPGA with DIFFRESISTOR="100".
  R180 (100R) is DNP and bench-only (scope or test load with no FPGA attached).
  NEVER fit R180 with DIFFRESISTOR on: two 100R loads make ~50R and cut VOD by about half (arithmetic, not measured).
  No series capacitors and no pull-ups on the pair (TLV3605 output is DC-coupled at ~1.2 V common mode, TLV3605 DS p.7).
  ECP5 LVDS input common-mode range: UNRESOLVED (FPGA-DS-02012 not obtained).
LE_HYS: R181 100k pull-up to 3V3 on this sheet only, so an unplugged header leaves the latch released (PROPOSED).
  SHDN_N pull-up is on the slicer sheet, HOLD_N pull-up on the control sheet.
HV rule (PROPOSED): no bare APD_BIAS pad on this sheet. HV_MON (~Vout/101, unbuffered 10 M / 100 k divider with 10 nF, source impedance ~100 k) is the ONLY HV observation point.""",
       (38.1, 30.48), 1.5)
s.text("""J50 ULX3S pinout (2.54 mm, 1x6)
1  +5V      board input from ULX3S
2  GND      return beside the pair
3  LVDS_P   TLV3605 OUT+ (to gp)
4  LVDS_N   TLV3605 OUT- (to gn)
5  GND      return beside the pair
6  HOLD_N   FPGA drives (control sheet)""", (228.6, 68.58), 1.5)
s.text("""J51 DEBUG pinout (2.54 mm, 1x6)
1  GND
2  LOS      loss-of-signal (monitor)
3  SHDN_N   slicer SHDN, active-low, not a guaranteed zero
4  LE_HYS   latch/hysteresis, R181 pull-up to 3V3
5  HOLD_N   control sheet, pull-up on control sheet
6  HV_MON   ~Vout/101, only HV observation point""", (228.6, 119.38), 1.5)
s.text("Test points TP50-TP58: 3V3, +3V7, -3V7, 5V_A, VMID, VSPAN, HV_MON, GND, GND. Hierarchical pins 3V3, +3V7, -3V7, 5V_A, HV_MON, HOLD_N are new on this sheet.", (38.1, 275.0), 1.5)
s.save(PATH)
