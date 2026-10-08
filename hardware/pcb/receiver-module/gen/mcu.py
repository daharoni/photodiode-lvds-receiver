#!/usr/bin/env python3
"""Generate mcu.kicad_sch (Rev A, spec section 7). Run: python3 gen/mcu.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/mcu.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
CONN = "AharoniLab_Connector:Conn_01x06"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
s = Sheet.load(PATH)
XL, JX = 38.1, 203.2
j = s.place(CONN, "J60", "MCU", (JX, 76.2))
for i, (kind, net) in enumerate([("hier_in", "3V3"), ("global", "GND"), ("hier_out", "DAC_GAIN"),
                                 ("hier_out", "DAC_TH"), ("hier_out", "DAC_HV"), ("hier_in", "HV_MON")], 1):
    p = j.pin(str(i))
    if kind == "global":
        s.stub(p, "l", 5.08, net, kind="global")
    else:
        s.hier_label(net, (XL, p[1]), 180, "input" if kind == "hier_in" else "output")
        s.wire([(XL, p[1]), p])
for n, (ref, net) in enumerate((("R190", "DAC_GAIN"), ("R191", "DAC_TH"), ("R192", "DAC_HV"))):
    r = s.place(R, ref, "100k", (152.4 + 12.7 * n, 101.6), footprint=R603)
    s.stub(r.pin("1"), "u", 2.54, net)
    s.stub(r.pin("2"), "d", 2.54, "GND", kind="global")
s.text("MCU hooks: header J60 for an external SAMD51 board (DAC outputs, HV_MON for its ADC). No SAMD51 on Rev A.", (38.1, 20.32), 2.5)
s.text("""Design intent (Rev A, nothing here is simulated or measured)

No SAMD51 on Rev A. The header exposes the optional hooks only; the analog-first chain works without it (PROPOSED).
SAMD51 DACs are 12-bit (decision-log standing correction); ADC inputs to be buffered later (UNRESOLVED).
J60 pin 1 (3V3) is a REFERENCE ONLY, 10 mA max: do not power an MCU board from it (PROPOSED).
Pull-downs R190-R192 (100k) hold DAC_GAIN, DAC_TH and DAC_HV at 0 V when no DAC is fitted (PROPOSED).
  Pull-down polarity: UNRESOLVED. They may become pull-ups once the DAC polarity is decided.
DAC_HV: 0 V vs Hi-Z is NOT the same set point (docs/calculations/apd-bias-design.md s.3.2 "Range", PROPOSED, hand calculation):
  DAC alone spans +/-30.6 V (61 V span, LSB 14.9 mV); pot span 99 V; both at 0 V = 215 V hardware maximum (maximum trim);
  both at 3.3 V = 55 V (firmware limit to >= 100 V). DAC pin Hi-Z at reset -> 135.9 V.
  With R192 fitted and no DAC driving, DAC_HV reads 0 V -> the bias goes to the MAXIMUM end of the trim, not 135.9 V.
  Check APD bias limits (100-220 V) before fitting any MCU board.
HV_MON (~Vout/101) is the only HV observation point; keep it within the MCU ADC range with a buffer (UNRESOLVED).""", (38.1, 30.48), 1.5)
s.text("""J60 MCU pinout (2.54 mm, 1x6)
1  3V3       reference only, 10 mA max
2  GND
3  DAC_GAIN  VCA gain control (R190 pull-down)
4  DAC_TH    slicer threshold (R191 pull-down)
5  DAC_HV    APD bias trim (R192 pull-down)
6  HV_MON    ~Vout/101""", (228.6, 68.58), 1.5)
s.save(PATH)
