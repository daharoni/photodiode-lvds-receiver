#!/usr/bin/env python3
"""Generate slicer.kicad_sch (Rev A, spec section 3). Run from anywhere: python3 gen/slicer.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/slicer.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
TP = "AharoniLab_Connector:TestPoint"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
C402 = "AharoniLab_Capacitor_SMD:C_0402_1005Metric_N"

s = Sheet.load(PATH)
X, Y = 200.66, 127.0
u = s.place("AharoniLab_OpAmp:TLV3605RVKR", "U20", "TLV3605RVKR", (X, Y))
XL, XR = 50.8, 254.0                      # sheet-edge label columns

# ---- inputs -----------------------------------------------------------
s.hier_label("SDET", (XL, 121.92), 180, "input")
s.connect((XL, 121.92), u.pin("IN+"))
s.hier_label("VTH", (XL, 124.46), 180, "input")
s.connect((XL, 124.46), u.pin("IN-"))
# probe points: SDET tap goes up, VTH tap goes down (no crossings)
tp21 = s.place(TP, "TP21", "SDET", (116.84, 114.3), rot=0, dnp=True,
               footprint="AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect")
s.connect((116.84, 121.92), tp21.pin("1"))
tp20 = s.place(TP, "TP20", "VTH", (116.84, 129.54), rot=180,
               footprint="AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect")
s.connect((116.84, 124.46), tp20.pin("1"))

# ---- SHDN_N with pull-up (row y=139.7, then up to the pin) -------------
s.hier_label("SHDN_N", (XL, 139.7), 180, "input")
shdn = u.pin("SHDN")
s.wire([(XL, 139.7), (182.88, 139.7), (182.88, shdn[1]), shdn])
r81 = s.place(R, "R81", "10k", (175.26, 137.16), footprint=R603)   # pin1 up, pin2 on the row
s.connect(r81.pin("2"), (175.26, 139.7))
s.stub(r81.pin("1"), "u", 2.54, "3V3")

# ---- LE/HYS: R82 150k to GND, R83 0R (DNP) to LE_HYS --------------------
le = u.pin("LE/HYS")
s.wire([le, (185.42, le[1]), (185.42, 147.32)])
r82 = s.place(R, "R82", "150k", (185.42, 149.86), footprint=R603)
s.connect((185.42, 147.32), r82.pin("1"))
s.stub(r82.pin("2"), "d", 2.54, "GND", kind="global")
r83 = s.place(R, "R83", "0R", (175.26, 149.86), dnp=True, footprint=R603)
s.connect(r83.pin("1"), (175.26, 147.32))
s.connect((175.26, 147.32), (185.42, 147.32))
s.hier_label("LE_HYS", (XL, 152.4), 180, "input")
s.connect((XL, 152.4), r83.pin("2"))

# ---- outputs ----------------------------------------------------------
s.connect(u.pin("OUT+"), (XR, u.pin("OUT+")[1]))
s.hier_label("LVDS_P", (XR, u.pin("OUT+")[1]), 0, "output")
s.connect(u.pin("OUT-"), (XR, u.pin("OUT-")[1]))
s.hier_label("LVDS_N", (XR, u.pin("OUT-")[1]), 0, "output")

# ---- ground -----------------------------------------------------------
vee, ep = u.pin("VEE"), u.pin("EP")
s.wire([vee, (vee[0], vee[1] + 2.54)])
s.wire([ep, (ep[0], ep[1] + 2.54), (vee[0], ep[1] + 2.54)])
s.global_label("GND", (vee[0], vee[1] + 2.54), 270)

# ---- supply group above the IC ----------------------------------------
RAIL = 88.9
BUS = 96.52
vcci, vcco = u.pin("VCCI"), u.pin("VCCO")
s.hier_label("3V3", (XL, RAIL), 180, "input")
s.wire([(XL, RAIL), (vcco[0], RAIL)])
s.wire([vcci, (vcci[0], RAIL)])                   # VCCI straight to 3V3
# VCCI bypass: 100n 0402 nearest the pin, 1u 0603 beyond it
s.wire([(vcci[0], BUS), (182.88, BUS)])
for ref, val, fp, x in (("C80", "100n", C402, 193.04), ("C81", "1u", C603, 182.88)):
    c = s.place(C, ref, val, (x, BUS + 2.54), footprint=fp)
    s.connect((x, BUS), c.pin("1"))
    s.stub(c.pin("2"), "d", 2.54, "GND", kind="global")
# VCCO via R80 (0R, bead option) with its own bypass
r80 = s.place(R, "R80", "0R", (vcco[0], RAIL + 2.54), footprint=R603)
s.connect(r80.pin("2"), vcco)
s.wire([(vcco[0], BUS), (223.52, BUS)])
s.place("power:PWR_FLAG", "#FLG10", "PWR_FLAG", (vcco[0] + 5.08, BUS), in_bom=False)   # R80 is passive: give VCCO a driver for ERC
for ref, val, fp, x in (("C82", "100n", C402, 213.36), ("C83", "1u", C603, 223.52)):
    c = s.place(C, ref, val, (x, BUS + 2.54), footprint=fp)
    s.connect((x, BUS), c.pin("1"))
    s.stub(c.pin("2"), "d", 2.54, "GND", kind="global")

# ---- text -------------------------------------------------------------
s.text("Slicer: TLV3605 LVDS comparator (U20). IN+ = SDET, IN- = VTH. Left to right: inputs, comparator, LVDS pair out.", (XL, 40), 2.5)
s.text("""Design intent (Rev A, nothing here is simulated or measured)
PROPOSED  IN+ = SDET (AC-coupled detector output), IN- = VTH (threshold from Control). Output high when SDET > VTH.
PROPOSED  VCCI = VCCO = 3V3. VCCI direct to 3V3; VCCO through R80 0R (option for a bead). Each pin has 100 nF 0402 + 1 uF 0603.
VERIFIED  Supply range 2.4 V to 5.5 V; separate VCCI/VCCO; bypass 0.1 uF ceramic directly between VCCI/VCCO and VEE (SNOSDA2F p.19, 7.3 and 7.4.1 item 2).
PROPOSED  SHDN (pin 7): R81 10k pull-up to 3V3; SHDN_N from Control, active low. VIH 1.5 V min, VIL 0.4 V max, 1.8 V logic compatible (SNOSDA2F p.8, EC table, and p.13 6.4).
          Shutdown is not a guaranteed zero output (standing correction 11); the FPGA watchdog must catch a stuck output.
VERIFIED  LE/HYS (pin 8): output latches when the pin is below 800 mV above VEE (p.14, 7.1.3; EC table VIL_LE 0.35 V max, VIH_LE 1.5 V min, p.8).
          Floating = 0 mV hysteresis; resistor to VEE sets it: 150k = 30 mV, 56k = 60 mV (p.8 and p.15, 7.1.4).
PROPOSED  R82 150k to GND = 30 mV hysteresis (R82 footprint also takes 56k for 60 mV). R83 0R, DNP: fit only if the FPGA is to force the latch.
UNRESOLVED  Pin voltage of LE/HYS with R82 fitted is not given in the datasheet. If R83 is fitted the FPGA must drive low only (open drain) or tri-state; driving high may override the hysteresis setting.
PROPOSED  OUT+ = LVDS_P, OUT- = LVDS_N, VOD 350 mV typ into 100 ohm. No termination on this board: the ECP5 has on-die 100 ohm termination (docs/research/ulx3s-lvds-input.md).
PROPOSED  VEE (3, 5, 9, 11) and exposed pad (13) to GND. Datasheet gives no pad connection requirement beyond layout item 1 (solid ground plane); pad tied to GND by this schematic.
PROPOSED  TP20 VTH, TP21 SDET (DNP: the probe adds load on SDET). Keep SDET and VTH traces short and matched; OUT+/OUT- matched length (p.19 layout items 3 and 6).""", (XL, 175), 1.5)
s.save(PATH)
print("wrote", PATH)
