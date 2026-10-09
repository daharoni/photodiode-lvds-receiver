#!/usr/bin/env python3
"""Generate controller.kicad_sch (Rev A, spec section 7: ESP32-C6 module controller).
Run from anywhere: python3 gen/controller.py
Coordinates are written in 1.27 mm grid units (x right, y down); u() applies the origin offset."""
import os, sys, textwrap
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kicad_sch import Sheet
from kicad_sch.sexpr import Str

PATH = os.path.join(ROOT, "hardware/pcb/receiver-module/controller.kicad_sch")
R = "AharoniLab_Passive:R_Small_US"
C = "AharoniLab_Passive:C_Small"
TP = "AharoniLab_Connector:TestPoint"
R603 = "AharoniLab_Resistor_SMD:R_0603_1608Metric_N"
C603 = "AharoniLab_Capacitor_SMD:C_0603_1608Metric_N"
C402 = "AharoniLab_Capacitor_SMD:C_0402_1005Metric_N"
C805 = "AharoniLab_Capacitor_SMD:C_0805_2012Metric_N"
TPFP = "AharoniLab_Connector:TestPoint_Pad_1.0x1.0mm_interconnect"
G = 1.27
OX, OY = 10, 0


def u(x, y):
    return ((x + OX) * G, (y + OY) * G)


# The old MCU sheet is copied to controller.kicad_sch first; its sheet uuid is kept so the root instance path stays valid.
s = Sheet.load(PATH, root_uuid="20237707-2fe5-41a5-bbd6-cb6c24e8ba32", sheet_uuid="9c1b5363-b8fe-46ae-a030-8579ae40f325")
s.title_block = ["title_block", ["title", Str("Controller (ESP32-C6, DAC, ADC, CAN)")],
                 ["date", Str("2026-10-08")], ["rev", Str("A1")], ["company", Str("Aharoni Lab, UCLA")]]


def _sym(inst):
    return s.symbols[s.instances.index(inst)]


def _prop(inst, name):
    for e in _sym(inst):
        if isinstance(e, list) and e and e[0] == "property" and str(e[1]) == name:
            return e


def hide(inst, *names):
    for n in names:
        e = _prop(inst, n)
        if e is not None and ["hide", "yes"] not in e:
            e.insert(4, ["hide", "yes"])


def tpos(inst, name, dx, dy, just=None):
    e = _prop(inst, name)
    e[3] = ["at", round(inst.at[0] + dx * G, 4), round(inst.at[1] + dy * G, 4), 90 if inst.rot in (90, 270) else 0]
    for i, it in enumerate(e):
        if isinstance(it, list) and it and it[0] == "effects":
            fx = ["effects", ["font", ["size", 1.27, 1.27]]]
            if just:
                fx.append(["justify"] + just.split())
            e[i] = fx


def hres(inst, dy=2.4):
    tpos(inst, "Reference", 0, -dy)
    tpos(inst, "Value", 0, dy)


def rv(ref, val, x, y, dnp=False, fp=R603):
    return s.place(R, ref, val, u(x, y), rot=0, footprint=fp, dnp=dnp)


def rh(ref, val, x, y, dnp=False, fp=R603):
    i = s.place(R, ref, val, u(x, y), rot=90, footprint=fp, dnp=dnp)
    hres(i)
    return i


def cv(ref, val, x, y, fp=C603):
    return s.place(C, ref, val, u(x, y), rot=0, footprint=fp)


def W(*pts):
    s.wire([u(*p) for p in pts])


def P(inst, pin):
    return inst.pin(pin)


def stub(inst, pin, d, n, label, kind="local", shape="passive"):
    return s.stub(inst.pin(pin), d, n * G, label, kind=kind, shape=shape)


def gnd(inst, pin, d="d", n=2):
    return s.stub(inst.pin(pin), d, n * G, "GND", kind="global")


def v33(inst, pin, d="u", n=2):
    return s.stub(inst.pin(pin), d, n * G, "3V3_D")


def lab(name, x, y, rot=0):
    s.label(name, u(x, y), rot)


def wrap(txt, width):
    out = []
    for ln in txt.split("\n"):
        out += textwrap.wrap(ln, width, subsequent_indent="  ", break_long_words=False) or [""]
    return "\n".join(out)


def note(txt, x, y, size=1.27, width=110):
    s.text(wrap(txt, width), u(x, y), size)


def flag(ref, x, y):
    s.place("power:PWR_FLAG", ref, "PWR_FLAG", u(x, y), in_bom=False)


# ============================== U60 ESP32-C6-MINI-1 ==============================
cx, cy = 150, 100
esp = s.place("AharoniLab_MCU:ESP32-C6-MINI-1", "U60", "ESP32-C6-MINI-1-N4", u(cx, cy), mirror="y")
# mirror="y": GPIO8..GPIO17 are on the left, EN and GPIO0..GPIO7 on the right
gnd(esp, "[1,2,11,14,36-53]", "d", 2)
# 3V3 pin 3 (top): 10 uF 0805 + 100 nF 0402 and the 3V3_D hierarchical input
p3 = P(esp, "3")
ny = u(0, 76)[1]
n3 = (p3[0], ny)
s.wire([p3, n3])
c191 = cv("C191", "10u", cx - 10, 72, fp=C805)
c192 = cv("C192", "100n", cx + 10, 72, fp=C402)
for cc in (c191, c192):
    s.wire([n3, (cc.pin("2")[0], ny), cc.pin("2")])
    gnd(cc, "1", "u")
s.stub(n3, "u", 4 * G, "3V3_D", kind="hier", shape="input")

# ---- left side stubs (GPIO8..GPIO17)
stub(esp, "GPIO8", "l", 2, "GPIO8")
stub(esp, "GPIO9", "l", 2, "BOOT")
stub(esp, "GPIO12/USB_D-", "l", 2, "USB_DM_E")
stub(esp, "GPIO13/USB_D+", "l", 2, "USB_DP_E")
stub(esp, "GPIO14", "l", 2, "LE_HYS_E")
s.no_connect(P(esp, "GPIO15"))
stub(esp, "GPIO18", "l", 2, "CAN_TX")
stub(esp, "GPIO19", "l", 2, "CAN_RX")
stub(esp, "GPIO20", "l", 4, "TIA_CTRL", kind="hier", shape="output")
s.no_connect(P(esp, "GPIO21"))   # AUX2 removed in revision 4; IO21 free
stub(esp, "GPIO22", "l", 2, "DAC_RDY")
stub(esp, "GPIO23", "l", 2, "STATUS")
stub(esp, "GPIO16/U0TXD", "l", 2, "TXD0")
stub(esp, "GPIO17/U0RXD", "l", 2, "RXD0")
# ---- right side stubs (EN, GPIO0..GPIO7)
stub(esp, "EN", "r", 2, "EN")
stub(esp, "GPIO0", "r", 4, "HV_DIS", kind="hier", shape="output")
stub(esp, "GPIO1", "r", 4, "SHDN_N", kind="hier", shape="output")
stub(esp, "GPIO2", "r", 2, "SDA")
stub(esp, "GPIO3", "r", 2, "SCL")
stub(esp, "GPIO4", "r", 4, "CC1_SENSE", kind="hier", shape="input")
stub(esp, "GPIO5", "r", 4, "CC2_SENSE", kind="hier", shape="input")
stub(esp, "GPIO6", "r", 2, "LDAC")
# AUX: GPIO7 -> R204 1k -> hierarchical AUX
r204 = rh("R204", "1k", 176, 102)
s.connect(P(esp, "GPIO7"), r204.pin("2") if r204.pin("2")[0] < r204.pin("1")[0] else r204.pin("1"))
aux_out = r204.pin("1") if r204.pin("2")[0] < r204.pin("1")[0] else r204.pin("2")
s.stub(aux_out, "r", 4 * G, "AUX", kind="hier", shape="bidirectional")

# ---- strapping / boot / EN network (above the module, left)
r190 = rv("R190", "10k", 112, 56); v33(r190, "1")
c190 = cv("C190", "1u", 122, 58)
s.wire([P(r190, "2"), (P(r190, "2")[0], P(c190, "1")[1]), P(c190, "1")])
gnd(c190, "2")
s.stub(P(r190, "2"), "d", 2 * G, "EN")
r191 = rv("R191", "10k", 128, 56); v33(r191, "1"); s.stub(P(r191, "2"), "d", 2 * G, "BOOT")
r192 = rv("R192", "10k", 136, 56); v33(r192, "1"); s.stub(P(r192, "2"), "d", 2 * G, "GPIO8")

# ---- RESET / BOOT tactile switches (decision 13): EN to GND, BOOT (IO9) to GND; TP60/TP61 stay in parallel
for ref, net, x in (("SW60", "EN", 146), ("SW61", "BOOT", 156)):
    sw = s.place("AharoniLab_Switch:PTS810SJM250SMTRLFS", ref, "RESET" if net == "EN" else "BOOT", u(x, 62), rot=90,
                 footprint="AharoniLab_Switch_SMD:SW_SPST_PTS810")
    top, bot = sorted((sw.pin("1"), sw.pin("2")), key=lambda q: q[1])
    s.stub(top, "u", 2 * G, net)
    s.stub(bot, "d", 2 * G, "GND", kind="global")
    tpos(sw, "Reference", 2.5, -2.5, "left"); tpos(sw, "Value", 2.5, 2.5, "left")
    for nm_ in ("Reference", "Value"):
        _prop(sw, nm_)[3][3] = 0

# ---- LE_HYS: GPIO14 -> R205 0R DNP -> hier LE_HYS
lab("LE_HYS_E", 128, 118, 0)
r205 = rh("R205", "0R", 124, 118, dnp=True)
s.wire([u(128, 118), r205.pin("1") if r205.pin("1")[0] > r205.pin("2")[0] else r205.pin("2")])
le_out = r205.pin("2") if r205.pin("1")[0] > r205.pin("2")[0] else r205.pin("1")
s.stub(le_out, "l", 4 * G, "LE_HYS", kind="hier", shape="output")

# ============================== USB-C and ESD (left) ==============================
# J60, its Rd/shield parts, VBUS_SENSE and #FLG60 are gone (revision 4): the receptacle is J50 on the Connector sheet.
# U61 USBLC6-2SC6
u61 = s.place("AharoniLab_Misc:USBLC6-2SC6", "U61", "USBLC6-2SC6", u(85, 72))
stub(u61, "1", "l", 4, "USB_DP", kind="hier", shape="bidirectional"); stub(u61, "3", "l", 4, "USB_DM", kind="hier", shape="bidirectional")
gnd(u61, "2", "d"); stub(u61, "5", "u", 4, "VBUS", kind="hier", shape="input")
r193 = rh("R193", "22R", 101, 70)
r194 = rh("R194", "22R", 112, 86)
for rr, up, dn in ((r193, "6", "USB_DP_E"), (r194, "4", "USB_DM_E")):
    a, b = rr.pin("1"), rr.pin("2")
    near, far = (a, b) if a[0] < b[0] else (b, a)
    s.connect(P(u61, up), near, via="v")
    s.stub(far, "r", 2 * G, dn)
    # DNP D+/D- cap to GND on the ESP32 side of the series resistor (C206 on USB_DP_E, C207 on USB_DM_E)
    cref = "C206" if dn == "USB_DP_E" else "C207"
    cd = s.place(C, cref, "TBD", (far[0], far[1] + 3 * G), footprint=C402, dnp=True)
    s.wire([far, cd.pin("1")]); gnd(cd, "2")

for rr in (r193, r194):
    tpos(rr, "Reference", 0, -4.6); tpos(rr, "Value", 0, -2.4)
tpos(u61, "Value", 7, 10, "left")
tpos(esp, "Value", 14, 26, "left")
# status LED
lab("STATUS", 56, 124, 180)
r203 = rh("R203", "1k", 62, 124)
d60 = s.place("AharoniLab_Passive:LED", "D60", "LED", u(72, 124), rot=180, footprint="AharoniLab_LED_SMD:LED_0805_2012Metric")
a, b = r203.pin("1"), r203.pin("2")
near, far = (a, b) if a[0] < b[0] else (b, a)
s.wire([u(56, 124), near]); s.wire([far, d60.pin("A")])
s.stub(d60.pin("K"), "r", 2 * G, "GND", kind="global")

# ============================== I2C DAC U62 (MCP4728) ==============================
ux, uy = 215, 60
u62 = s.place("AharoniLab_Misc:MCP4728T-E_UN", "U62", "MCP4728T-E_UN", u(ux, uy))
for pin, nm in (("SCL", "SCL"), ("SDA", "SDA"), ("~{LDAC}", "LDAC"), ("RDY/~{BSY}", "DAC_RDY")):
    stub(u62, pin, "l", 2, nm)
for pin, nm in (("OUTA", "DACO_A"), ("OUTB", "DACO_B"), ("OUTC", "DACO_C"), ("OUTD", "DACO_D")):
    stub(u62, pin, "r", 2, nm)
vdd = P(u62, "VDD")
s.wire([vdd, (vdd[0], u(0, 44)[1])])
c194 = cv("C194", "100n", ux + 7, 46, fp=C402)
s.wire([(vdd[0], u(0, 44)[1]), c194.pin("1")]); gnd(c194, "2")
s.stub((vdd[0], u(0, 44)[1]), "u", 2 * G, "3V3_D")
gnd(u62, "VSS", "d")
# pull-ups on the I2C bus and the DAC control pins
for k, (ref, nm, x) in enumerate((("R195", "SDA", 176), ("R196", "SCL", 184), ("R197", "LDAC", 192), ("R198", "DAC_RDY", 200))):
    rr = rv(ref, "4.7k" if k < 2 else "10k", x, 78); v33(rr, "1"); s.stub(P(rr, "2"), "d", 2 * G, nm)

# DAC output RC rows
rows = ((30, "DACO_A", None, "R210", "C201"), (44, "DACO_B", "DAC_TH", "R211", "C202"),
        (58, "DACO_C", "DAC_HV", "R212", "C203"), (72, "DACO_D", None, "R213", "C204"))
for y, src, out, rr, cc in rows:
    lab(src, 248, y, 180)
    rres = rh(rr, "100R", 254, y)
    a, b = rres.pin("1"), rres.pin("2")
    near, far = (a, b) if a[0] < b[0] else (b, a)
    s.wire([u(248, y), near])
    ccap = cv(cc, "100n", 262, y + 4)
    s.wire([far, (ccap.pin("1")[0], far[1]), ccap.pin("1")]); gnd(ccap, "2")
    if out:
        s.wire([(ccap.pin("1")[0], far[1]), u(268, y)])
        s.hier_label(out, u(268, y), 0, "output")
    else:
        s.wire([(ccap.pin("1")[0], far[1]), u(268, y)])
        lab("DAC_A" if src == "DACO_A" else "DAC_D", 268, y, 0)

# ============================== I2C ADC U63 (ADS1115) ==============================
ax, ay = 215, 110
u63 = s.place("AharoniLab_Misc:ADS1115IDGSR", "U63", "ADS1115IDGSR", u(ax, ay), mirror="y")
stub(u63, "SDA", "l", 2, "SDA"); stub(u63, "SCL", "l", 2, "SCL")
s.stub(P(u63, "ADDR"), "l", 4 * G, "GND", kind="global")
s.no_connect(P(u63, "ALERT/RDY"))
gnd(u63, "GND", "d")
vdd = P(u63, "VDD")
s.wire([vdd, (vdd[0], u(0, 92)[1])])
c195 = cv("C195", "100n", ax + 7, 94, fp=C402)
s.wire([(vdd[0], u(0, 92)[1]), c195.pin("1")]); gnd(c195, "2")
s.stub((vdd[0], u(0, 92)[1]), "u", 2 * G, "3V3_D")
rows = ((92, "AIN0", "HV_MON", "R206", "C197"), (106, "AIN1", "RSSI", "R207", "C198"),
        (120, "AIN2", "VTH_MON", "R208", "C199"), (134, "AIN3", None, "R209", "C200"))
for y, pin, net, rr, cc in rows:
    stub(u63, pin, "r", 2, "ADC_" + pin)
    lab("ADC_" + pin, 248, y, 180)
    rres = rh(rr, "10k", 254, y)
    a, b = rres.pin("1"), rres.pin("2")
    near, far = (a, b) if a[0] < b[0] else (b, a)
    s.wire([u(248, y), near])
    ccap = cv(cc, "10n", 262, y + 4)
    s.wire([far, (ccap.pin("1")[0], far[1]), ccap.pin("1")]); gnd(ccap, "2")
    s.wire([(ccap.pin("1")[0], far[1]), u(268, y)])
    if net:
        s.hier_label(net, u(268, y), 0, "input")
    else:
        s.global_label("GND", u(268, y), 0)

# ============================== CAN U64 (SN65HVD230) ==============================
kx, ky = 200, 156
u64 = s.place("AharoniLab_Interface:SN65HVD230D", "U64", "SN65HVD230D", u(kx, ky))
stub(u64, "D", "l", 2, "CAN_TX"); stub(u64, "R", "r", 2, "CAN_RX")
s.no_connect(P(u64, "Vref_OUT"))
tpos(u64, "Value", 6, 13, "left")
s.stub(P(u64, "CANL"), "r", 8 * G, "CAN_L", kind="hier", shape="bidirectional")
s.stub(P(u64, "CANH"), "r", 8 * G, "CAN_H", kind="hier", shape="bidirectional")
gnd(u64, "GND", "d")
r199 = rv("R199", "100k", 179, ky + 4)
s.wire([P(u64, "RS"), (P(r199, "1")[0], P(u64, "RS")[1]), P(r199, "1")]); gnd(r199, "2")
vcc = P(u64, "VCC")
ny = u(0, ky - 16)[1]
s.wire([vcc, (vcc[0], ny)])
c196 = cv("C196", "100n", kx - 6, ky - 18, fp=C402)
s.wire([(vcc[0], ny), (c196.pin("2")[0], ny), c196.pin("2")]); gnd(c196, "1", "u")
s.stub((vcc[0], ny), "u", 2 * G, "3V3_D")

# ============================== test points (column) ==============================
tps = ("EN", "BOOT", "TXD0", "RXD0", "SDA", "SCL", "CAN_TX", "CAN_RX", "DAC_A", "DAC_D")
for k, nm in enumerate(tps):
    y = 112 + 5 * k
    t = s.place(TP, "TP%d" % (60 + k), nm, u(16, y), rot=270, footprint=TPFP)
    hide(t, "Value")
    tpos(t, "Reference", -2, 0, "right")
    s.stub(t.pin("1"), "r", 3 * G, nm)

# ============================== notes and design intent ==============================
note("U60 module notes: ESP32-C6-MINI-1 (PCB antenna). Place at a board edge with the antenna end over the board edge and keep copper, "
     "parts and the HV/TIA area out of the antenna keep-out (MINI DS v1.5 Fig 3-1 p10, Fig 11-1 p44; numeric clearances UNRESOLVED, "
     "from the Hardware Design Guidelines). The radio is not used.", 104, 132, width=50)
note("Strapping (MINI DS Table 4-1/4-3 p12-13): GPIO9 high = SPI boot; GPIO9 low with GPIO8 high = download boot. "
     "EN: 10k + 1u RC power-up delay (p40). GPIO15 left open (default eFuses ignore it).", 100, 36, width=60)
note("DAC_HV safe default: MCP4728 EEPROM for channel C is programmed to 0xFFF (lowest bias), VREF = VDD, PD = 00, "
     "never power-down. HV_DIS (GPIO0, pull-up on the Power sheet) gates the bias regardless. UNRESOLVED until firmware exists.", 104, 146, width=50)
_n = """BUTTONS (PROPOSED): SW60 RESET (EN to GND) and SW61 BOOT (IO9 to GND), C&K PTS810 SJM 250; TP60/TP61 in parallel. R190 10k + C190 1u is the debounce and the recommended EN RC (MINI-1 datasheet v1.5 p.40, HDG p.10). Download boot = GPIO9 0 with GPIO8 1 at EN rising (MINI-1 datasheet Table 4-3 p.13), VERIFIED. Fitted even though RTS/DTR auto-reset exists (TRM v1.2 p.1030 Table 32.3-2): recovery for empty flash or a disabled USB PHY (HDG p.30).
CC SENSE (PROPOSED, decision 14): CC1_SENSE (IO4, ADC1_CH4) and CC2_SENSE (IO5, ADC1_CH5) arrive from the Connector sheet already divided 100k/100k with 100 nF; only the 0-1.9 V ATTEN2 range is read (ESP32-C6 datasheet v1.5 Table 5-6 p.66, +-23 mV after calibration), so Rp classification is thin (firmware: three agreeing reads). IO4/IO5 are strapping pins (MTMS/MTDI) that only select SDIO sampling edges (MINI-1 datasheet Table 4-4 p.14); SDIO unused, PROPOSED harmless. UNRESOLVED: finer ADC attenuation range; clamp-injection current for a fault on the CC taps (input high max VDD + 0.3 V, Table 5-4 p.65). VBUS_SENSE and PWR_SRC are removed.
FIRMWARE STATES (PROPOSED, firmware/esp32/README.md): cc_class, cc_orient and usb_host are logged hints; the definitive system indicator is LINK_ALL from the FPGA master. The ESP32 must not clear HV_DIS on the basis of CC levels alone. UNRESOLVED: firmware policy for the D+ pull-up backdrive into an unpowered host (TRM p.1042); self-test cannot prove the comparator or LVDS output without an FPGA or optical source; ground offset between laptop and FPGA supply not analysed; EN-side ESD diode; eFuse dVdt ramp (about 5.3 ms estimated) versus the 10 ms EN RC.""".split("\n")
_usb = "USB D+/D- (PROPOSED, decision 14): USB_DP/USB_DM arrive from J50 on the Connector sheet (hierarchical, bidirectional). R193/R194 22R (ESP32-C6 Hardware Design Guidelines p.18 section 1.3.13: reserve 22/33 ohm and capacitors to ground; MINI-1 datasheet v1.5 Fig. 9-1 p.40 leaves them TBD), with DNP C206/C207 (0402, value TBD) from USB_DP_E/USB_DM_E to GND on the module side. UNRESOLVED: effect of 22 ohm with USBLC6 and auto-reset through them, untested. VBUS surge protection is the eFuse U5 on the Power sheet (21 V abs max, TPS2596 p.5), not the USBLC6; USBLC6-2SC6 VBUS-pin clamp behaviour UNRESOLVED (ST datasheet not read). Place U61 near J50 at layout."
note(_usb, 44, 10, width=52)
note(_n[0], 98, 10, width=52)
note(_n[1], 152, 10, width=52)
note(_n[2], 206, 10, width=52)
note("Optional CAN bus ESD part: not fitted, no part chosen (DNP footprint note only).", 228, 152, width=40)

intent = """DESIGN INTENT (Controller sheet, revision 4, decisions 12, 13 and 14). Labels: VERIFIED = datasheet cited, PROPOSED = design intent, UNRESOLVED = open. Nothing here is measured or simulated.
ROLE (PROPOSED): on-module ESP32-C6 does the slow trims and housekeeping, never the data path. (1) Range trim: DAC_HV (MCP4728 ch C) moves the APD bias toward the Q(M) optimum, and TIA_CTRL (IO20) schedules the OPA857 gain 20k / 5k from RSSI (ADS1115 AIN1) and FPGA link validity (received over CAN). (2) Threshold trim: DAC_TH (ch B) sets the Slicer threshold node; VTH_MON (AIN2) reads it back. (3) HV gating: HV_DIS (IO0) enables the APD bias supply; HV_MON (AIN0) reads the bias. (4) Module identity and status over CAN (CAN_H/CAN_L, 125 kbit/s), plus SHDN_N and LE_HYS to the Slicer. DAC_A (ch A) and DAC_D are spare test pads (TP68, TP69); ADS1115 AIN3 is tied to GND through its RC (spare).
UNPROGRAMMED ESP32 (PROPOSED): the module decodes. TIA_CTRL floats, so the Front End pull-up gives 20 k; SHDN_N pull-up keeps the comparator on; the Slicer threshold sits at VCM_REF through its resistor network. BUT HV_DIS is pulled up on the Power sheet, so an unprogrammed module has NO APD bias and no gain. Bench jumper J1 (HV FORCE ON, Power sheet) forces HV on. DAC_HV default (EEPROM) is the lowest bias.
PIN MAP (module pad; research doc section 1): IO0 HV_DIS, IO1 SHDN_N, IO2 SDA, IO3 SCL, IO6 LDAC, IO7 AUX via R204 1k, IO14 LE_HYS via R205 (0R, DNP), IO20 TIA_CTRL (direct, pull-up on the Front End), IO21 no_connect (AUX2 removed), IO8 strap pull-up, IO9 BOOT, IO12/IO13 USB D-/D+, IO16/IO17 TXD0/RXD0 pads, IO18 CAN_TX, IO19 CAN_RX, IO22 DAC RDY, IO23 status LED, IO4 CC1_SENSE and IO5 CC2_SENSE (hierarchical inputs from the Connector). IO15 and IO21 are no_connect.
CHANGE FROM EARLIER SPEC: IO10 and IO11 do not exist on the MINI-1 (MINI DS Table 3-1 p10-11; 22 GPIOs), so LDAC is IO6 and AUX is IO7 (JTAG MTCK/MTDO pins; USB-Serial-JTAG is the debug path). IO15 is a strapping pin, so TIA_CTRL uses IO20. PROPOSED.
STRAPPING (VERIFIED, MINI DS Table 4-1..4-3 p12-13): GPIO9 weak pull-up, high = SPI boot; download boot needs GPIO8 = 1 and GPIO9 = 0 (BOOT pad to GND, then EN pad). GPIO8 has R192 10k to 3V3_D. Do not drive IO8/IO9 at reset. IO0, IO1, IO14 are Hi-Z at reset (C6 DS Table 2-2 p17-18), so the pull resistors on the other sheets fix the safe state. IO18-IO23 have weak pull-ups at reset (CAN_TX idles recessive; TIA_CTRL reads high = 20 k even before the Front End pull-up).
USB (PROPOSED, decision 14): the receptacle is J50 on the Connector sheet; USB_DP/USB_DM, VBUS (U61 pin 5 only) and CC1_SENSE/CC2_SENSE arrive as hierarchical inputs. D+/D- through R193/R194 22R with DNP C206/C207 to GND (details in the notes at the top). UART fallback on TP62/TP63.
CAN (PROPOSED, research section 3): SN65HVD230 with RS = 100k to GND (slope control, 600/800/1200 ns rise, SLOS346O p8; stub rule SLLA270 p9 allows at least 20 m, PROPOSED arithmetic; revision 4). 125 kbit/s. NO termination on the module; one 120 ohm (or 2 x 60 ohm + 4.7 nF split, SLLA270 p8) at the FPGA-end junction only. Vref_OUT unconnected.
I2C (VERIFIED, MCP4728 DS22187E p21-24; ADS1115 SBAS444E p20): private bus, MCP4728 at 0x60, ADS1115 ADDR = GND at 0x48. MCP4728 factory default is 0 V on all channels (not Hi-Z). ADS1115 inputs must stay within GND-0.3 .. VDD+0.3 V; the three sources are <= 3.3 V nodes. LDAC is held high by R197 so a high LDAC keeps the EEPROM values on the outputs.
UNRESOLVED: USB series resistor effect and auto-reset over USB; DAC_TH safe direction; verification of the DAC_HV default after EEPROM programming (General Call Read); firmware range-trim and TIA_CTRL scheduling algorithm; measured 3V3_D current; antenna keep-out numbers; -1 versus -1U module; VBUS back-feed against the 5 V cable rail."""
paras = intent.split("\n")
cols = [paras[0:3], paras[3:7], paras[7:]]
for k, ps in enumerate(cols):
    s.text(wrap("\n".join(ps), 80), u(k * 86, 170), 1.27)

s.save(PATH)
print("wrote", PATH)
