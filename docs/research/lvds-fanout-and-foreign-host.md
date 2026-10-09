# LVDS fan-out buffer, foreign-host safety and cable signal integrity (single 24-pin USB-C connector)

Labels: VERIFIED (cited document, revision, page), PROPOSED (reasoned recommendation or arithmetic), UNRESOLVED (not settled by documents in hand).
Checked 2026-10-09. Nothing here was measured or simulated. Raw downloads and SHA-256: `docs/research/downloads/lvds-fanout/MANIFEST.md`.
Datasheet abbreviations: LVDS104 = TI SN65LVDS104/105 SLLS396G (Dec 2015); LVDS22 = TI SN65LVDS22/LVDM22 SLLS315C (June 2002); HVD230 = SN65HVD23x SLOS346O (Apr 2018, `docs/datasheets/sn65hvd230.pdf`); TLV = TLV3604/5/7 SNOSDA2F (`docs/datasheets/tlv3605.pdf`); ECP5 DS = Lattice FPGA-DS-02012 v3.4 (`docs/datasheets/ecp5-ds-02012.pdf`); TN = FPGA-TN-02032 v1.4; TUSB = TI TUSB1002 SLLSEU4E (USB 3.1 redriver, secondary source); SLLA270 = TI CAN physical layer note (Jan 2008). Page numbers are printed = PDF pages unless stated.

## Summary for decision 14

1. Part (PROPOSED): **SN65LVDS104PW** (TI, TSSOP-16, 1 LVDS in, 4 LVDS out, 3.3 V) as the fan-out buffer, TLV3605 to buffer input with the 100 ohm termination at the buffer input (it has none on chip), two outputs to TX1/TX2, outputs 3/4 disabled (EN3, EN4 low) or kept as a debug/spare pair. Alternative: **SN65LVDS22PW** (TSSOP-16, 2x2 crosspoint used as a splitter, S1=S0=0, so 1A/1B drives both outputs; about 13 mA typ / 20 mA max instead of 23/35 mA, but no jitter or part-to-part data). Both are in the KiCad bundled `Package_SO:TSSOP-16_4.4x5mm_P0.65mm` (file present in KiCad 10.0.5 and in `AharoniLab_Package_SO`). Neither has a symbol in the bundled KiCad symbols or the lab library: a lab-library PR is needed.
2. Compatibility with the TLV3605 (VERIFIED, numbers below): TLV3605 VOD 250/350/450 mV and VOCM 1.125/1.2/1.375 V (TLV p.7) against LVDS104 threshold +-100 mV and common-mode range 0 to VCC-0.8 V (LVDS104 p.4, p.5). Margin at minimum VOD is 147 mV. Supply current 23 mA typ, 35 mA max with all four outputs loaded (LVDS104 p.5): 3V3 budget 66 mA (power.md) + 35 = about 101 mA, inside the TPS79901's 200 mA (TPS799 SBVS056L, 500 uA to 200 mA load-regulation rows; power.md notes this rating was not rechecked there).
3. Buffer is needed (PROPOSED, arithmetic): driving both pairs from the TLV3605 gives 50 ohm, VOD about 125/175/225 mV, only 25 mV above the ECP5 +-100 mV threshold at minimum, and halves the hysteresis window and makes it depend on whether a cable is plugged. Rejected.
4. Foreign host (laptop USB 3.x port) is safe on every electrical path examined, with the caveats in section 3: (a) the host's Rx.Detect looks for a DC path to ground on its TX pair, which is our CAN pins, whose HVD230 input resistance is 20 to 50 kohm per pin (HVD230 p.7) against a USB 3 termination of 18 to 30 ohm common-mode (TUSB p.8, secondary): about 3 orders of magnitude apart, so the host should stay in Rx.Detect, never send LFPS or data, and never enable its receiver termination (high impedance, >= 30 kohm per TUSB p.8). (b) Even if it did, our LVDS outputs are short-circuit-rated to +-10 mA (LVDS104 p.5) and the host would see at most about 175 mV; CANH/CANL tolerate -4 to 16 V (HVD230 p.5) against a host swing of order +-0.6 V around 0 to 2 V. Label: SAFE per datasheet limits, host behaviour from secondary sources, not tested with any laptop (UNRESOLVED until bench-tested with one or two real hosts; see open items).
5. Reverse accident (laptop into the FPGA-end breakout): laptop and breakout are both DFPs (Rp on CC both sides), so no attach should occur. FPGA LVDS input: abs max -0.5 to 3.63 V (ECP5 DS Table 3.1, p.51); the DIFFRESISTOR 100 ohm is differential only and gives the host no DC path to ground, so the host does not detect a receiver. Risk that remains: a breakout that sources 5 V on VBUS unconditionally into a DFP. Breakout must enable VBUS only after seeing Rd (PROPOSED). Type-C spec not obtained: UNRESOLVED.
6. Signal integrity (PROPOSED): 90 ohm cable into 100 ohm gives Gamma = +5.3 %, an echo of at most about 19 mV (5.5 % of 350 mV) arriving 26 to 30 ns after the edge (1.3 to 1.5 UI); against 147 mV minimum margin this is negligible. No series termination, keep the ECP5 DIFFRESISTOR; terminate the breakout's second (unused) RX pair with 100 ohm.
7. CAN (PROPOSED): HVD230 RS resistor R199 is 10 kohm (controller.md), giving tr 80/120/160 ns (HVD230 p.8). SLLA270 p.9 rule (stub <= 1/3 of critical length) allows about 2.7 m at the 80 ns minimum edge and 5 ns/m, so a 3 m stub is marginal; **change R199 to 100 kohm** (tr 600/800/1200 ns, HVD230 p.8) which stays far inside the 8 us bit at 125 kbit/s and allows stubs of 20 m by the same rule. Termination at the breakout only (split 2x60.4 ohm + 4.7 nF) as already planned; bench-verify.
8. Open items: bench-test with a real laptop (USB 3 Type-C, ideally two OSes/vendors) with scope on the CAN pins; obtain USB 3.2 and Type-C specs for primary-source citations; confirm USB-C full-featured cable lane mapping (TX1/TX2 to RX1/RX2 crossing) from the Type-C spec; firmware must keep CAN TX silent (RS high or listen-only) until traffic or a configured partner exists; check SBU/AUX protection (ESP32 GPIO is 3.3 V only); EN3/EN4 tie-offs; a lab-library symbol for the buffer; confirm LVDS104 ordering/stock.

## 1. Fan-out buffer selection

### 1.1 Candidates

| Part | Topology | Package | 3.3 V | Verdict | Cite |
|---|---|---|---|---|---|
| SN65LVDS104 | 1 LVDS to 4 LVDS, 400 Mbps typ | SOIC-16 (9.9x3.91) or TSSOP-16 (5.0x4.4); RthJA 74.4 / 101.6 C/W | 3.0 to 3.6 V | **Top** (VERIFIED facts below) | LVDS104 p.1, p.3, p.4 |
| SN65LVDS22PW | 2 in / 2 out multiplexed repeater, splitter mode | TSSOP-16 (and SOIC-16); TI product page shows PW 5 x 6.4 mm incl. leads, status ACTIVE (WebFetch of ti.com/product/SN65LVDS22, 2026-10-09; page not archived) | 3.0 to 3.6 V | **Alternative** | LVDS22 p.1, p.4, p.5, p.6 |
| SN65LVDS105 | LVTTL in, 4 LVDS out | same as 104 | yes | Rejected: input is LVTTL (A pin, no B), not LVDS | LVDS104 p.1, p.3 |
| SN65LVDS108 / 116 | 1:8 / 1:16 | 38-pin DBT / 64-pin DGG | yes | Rejected: too large for the use | LVDS104 p.3 (selection guide) |
| SN65LVDS100/LVDT100 | 1:1 translator/repeater (two needed), LVDT has 110 ohm input termination | VSSOP-8 3x3 | yes | Fallback only: two parts, ICC 25 typ / 30 max mA each (about 50 mA for two), 2 Gbps edge rates are needless | SLLS516E p.1, p.5 |
| DS90LV004 | four independent 1.5 Gbps buffers (not a fan-out) | TQFP (48-pin class) | yes | Rejected: large, not a repeater of one input | SNLS190P p.1 |
| ON Semi, Renesas, Microchip LVDS fan-outs | not surveyed | | | UNRESOLVED (no non-TI part was checked) | none |

SN65LVDS22 limits to note: only "Designed for data rates up to 250 Mbps" (p.1) and no part-to-part skew or jitter numbers (p.6). It has two outputs only, exactly what we need, and per-driver enables 1DE/2DE (p.1, p.4).

### 1.2 SN65LVDS104 extracted facts (all VERIFIED, SLLS396G unless noted)

| Item | Value | Page |
|---|---|---|
| Supply | VCC 3 / 3.3 / 3.6 V; abs max VCC -0.5 to 4 V; A, B, Y, Z -0.5 to 4 V; enables -0.5 to 6 V | p.4 |
| Supply current | enabled, RL = 100 ohm, all four outputs: 23 mA typ, 35 mA max; disabled 3 mA typ, 8 mA max | p.5 |
| Power at 3.3 V (arithmetic) | typ 76 mW, max 116 mW (at 3.6 V: 126 mW); package rating 774 mW (PW) at 25 C | p.5, p.7 |
| Input threshold | VIT+ = +100 mV, VIT- = -100 mV; "requires +-100 mV of input signal"; no hysteresis specified | p.5, p.15 |
| Input common-mode range | 0 to VCC - 0.8 V (2.5 V at 3.3 V) for any bus terminal | p.4 |
| Input current | A/B: -11 uA typ at 0 V; input capacitance 3 pF | p.5 |
| Fail-safe | Open input (cable removed or driver Hi-Z): receiver pulls both lines to near VCC through 300 kohm; fail-safe AND gate with thresholds about 2.3 V forces the output high (Y high, Z low). Function table row "Open: H L". External termination across A/B does not defeat it. | p.15, p.16 |
| Input termination | None on chip (SN65LVDT parts are a different family). 100 ohm external, within 10 %, placed as close to the receiver as possible. | p.16 Fig. 25, p.24 s.10.2.3.7 |
| Output VOD | 247 / 340 / 454 mV into 100 ohm (RL = 100 ohm, VID = +-100 mV); VOC(SS) 1.125 to 1.375 V | p.5 |
| Output when disabled or VCC < 1.5 V | high impedance; IOZ +-1 uA; power-off output current VCC = 1.5 V, VO = 2.4 V: +-1 uA | p.1, p.5 |
| Short-circuit output current IOS | max +-10 mA with VOY or VOZ = 0 V and with VOD = 0 V (outputs shorted together) | p.5 |
| Propagation delay | tPLH 2.4 / 3.2 / 4.2 ns, tPHL 2.2 / 3.1 / 4.2 ns (min/typ/max, 100 ohm, 10 pF) | p.6 |
| Part-to-part skew | tsk(pp) 1.5 ns max; channel-to-channel skew 20 ps typ, 100 ps max; pulse skew 150 / 500 ps | p.6 |
| Rise/fall | 0.3 / 0.8 / 1.2 ns | p.6 |
| Jitter | Fig. 9: peak-to-peak eye-pattern jitter, 2^15 PRBS, all outputs loaded, 100 ohm: read from the plot about 200 to 320 ps at 50 Mbps (about 1 to 1.6 % of the 20 ns UI); the test input already has 115 ps p-p at 100 Mbps and the board adds about 70 ps. Plot reading, not a table value. | p.9 |
| ESD | 12 kV HBM (JEDEC), 1.5 kV CDM; 16 kV MIL-STD class 3A on bus pins | p.4 |
| Package | D (SOIC) and PW (TSSOP) 16-pin; PW body 5.00 x 4.40 mm | p.1 |

Footprint (VERIFIED by file search): `Package_SO:TSSOP-16_4.4x5mm_P0.65mm` exists in KiCad 10.0.5's bundled footprint library and `AharoniLab_Package_SO:TSSOP-16_4.4x5mm_P0.65mm` exists in the lab library. The TI mechanical drawing was not compared against the footprint (UNRESOLVED, check at layout). Pin map: EN1 1, EN2 2, EN3 3, VCC 4, GND 5, A 6, B 7, EN4 8, 4Z 9, 4Y 10, 3Z 11, 3Y 12, 2Z 13, 2Y 14, 1Z 15, 1Y 16 (p.3). Enables are active high with VIH >= 2 V, VIL <= 0.8 V (p.4); they have no documented internal pull-up, so tie each one (3V3 or GND, or an ESP32 GPIO later).

### 1.3 Does it accept the TLV3605 output? (VERIFIED arithmetic from cited numbers)

| Quantity | TLV3605 (TLV p.7) | SN65LVDS104 input (p.4, p.5) | Result |
|---|---|---|---|
| Differential swing | VOD 250 / 350 / 450 mV into 100 ohm | threshold +-100 mV | margin 150 mV at minimum (about 147 mV against the 3 mV hysteresis window of slicer.md is irrelevant: that window acts at the TLV3605 input, not here) |
| Common mode | VOCM 1.125 / 1.2 / 1.375 V | 0 to 2.5 V | inside |
| Termination | datasheet wants 100 ohm across the outputs (TLV p.19 item 6; p.13) | none on chip | place one 100 ohm 0.1 % resistor across A/B at the buffer, a few cm of 100 ohm pair from the TLV3605 |
| Load seen by TLV3605 | 100 ohm || 3 pF | | same as the present FPGA termination case: the R87/C87 hysteresis tap is unchanged (3.0 mV window per slicer.md) and no longer depends on the cable |

PROPOSED: R180 (DNP 100 ohm bench termination across LVDS_P/N on the Connector sheet) moves to the buffer input as the real termination. The 100 ohm and the buffer's 300 kohm fail-safe pull-ups: with no TLV3605 power both lines float up and the buffer drives a static high on all outputs (VERIFIED behaviour p.15-16, consequence PROPOSED). That is a harmless DC state for a foreign host.

### 1.4 Output behaviour into illegal loads

| Case | Behaviour | Label |
|---|---|---|
| (a) Outputs open (no cable) | Current-steering LVDS driver (about 3.5 mA, 350 mV into 100 ohm) swings toward the rails with no load. No document statement about open-circuit voltage; it cannot exceed VCC and the absolute maximum on Y/Z is -0.5 to 4 V (p.4). Nothing in the datasheet prohibits it. | PROPOSED (inference); abs max VERIFIED |
| (b) Each line 50 ohm to GND (USB 3 receiver termination) | Datasheet short-circuit test is stricter than this: VOY or VOZ = 0 V gives max +-10 mA (p.5). With a 3.5 mA drive into 50 ohm the lines sit at roughly 0 and 175 mV and VOD about 175 mV (arithmetic). The datasheet gives no short-circuit duration limit, so continuous operation is not stated. | PROPOSED; IOS VERIFIED; duration UNRESOLVED |
| (c) Outputs shorted together | VOD = 0 V test gives max +-10 mA (p.5). | VERIFIED as a characterised condition; duration UNRESOLVED |
| (d) Host applies DC to the outputs powered | Abs max Y/Z -0.5 to 4 V; USB 3 host TX DC common mode 0 to 2 V and detect step <= 600 mV (TUSB p.8, secondary) gives about -0.5 to 2.6 V worst case plus 0.6 V swing: within limits | PROPOSED |
| (e) Host applies DC while the module is unpowered | Outputs high impedance for VCC < 1.5 V, power-off output current +-1 uA at 2.4 V (p.1, p.5) | VERIFIED |

LVDS22 gives the same IOS (max -10 mA) and the same Hi-Z-when-unpowered (p.1, p.5); its abs max for Y/Z is also -0.5 to 4 V (p.3).

## 2. Alternative: TLV3605 driving both pairs directly (no buffer; rejected)

- Two 100 ohm loads in parallel are 50 ohm. The TLV3605 datasheet only specifies VOD into 100 ohm (TLV p.7); the output type is not described as current-mode. Assuming a current-steering LVDS output (PROPOSED), VOD scales with load: 125 / 175 / 225 mV (min/typ/max).
- ECP5 LVDS input: VTHD +-100 mV, VCM 0.05 to 2.35 V, VINP/VINM 0 to 2.4 V (ECP5 DS Table 3.13, PDF p.58, VERIFIED). Margin at minimum VOD: 125 - 100 = 25 mV (versus 147 mV with the buffer). That leaves almost nothing for the 5 % cable echo (section 4), noise and the unspecified TLV3605 delay at small overdrive. Cable DC resistance would eat more.
- Hysteresis: the R87/C87 network taps OUT+ (slicer.md). Window = OUT+ swing x 47.5/(5490+47.5) = 3.0 mV at 350 mV; halving the swing halves the window to about 1.5 mV, and it would change by 2x between "cable plugged" and "no cable" (PROPOSED arithmetic from slicer.md). Cable echoes also appear directly on OUT+ and are coupled to IN+ through the same network (about 0.86 % of 19 mV = 0.16 mV, small, but the point is that the comparator output is no longer isolated from the cable).
- Foreign host: the TLV3605 would face host-applied DC with no buffer; the TLV3605 output abs max was not checked here (UNRESOLVED).
- Conclusion: rejected. A buffer isolates the comparator, restores 100 ohm loading and 147 mV minimum margin for 25 to 35 mA at 3.3 V.

## 3. Foreign-host safety

### 3.1 What a USB 3.x host does (secondary sources; USB 3.2 specification not obtained)

I could not download the USB 3.2 specification (usb.org distributes a licensed zip of about 97 MB; no direct file was fetchable). The facts below come from TI's TUSB1002 datasheet (a redriver that implements the USB 3.1 receive/transmit electrical parameters), Xillybus's LTSSM tutorial, a USB-IF compliance document title seen in search results (LFPS Rx/Tx compliance update Rev 5, not downloaded) and a patent description. Label: secondary, so nothing in this section is VERIFIED against USB 3.2 itself. UNRESOLVED until the USB 3.2 spec (Chapter 6, Rx.Detect and receiver termination) and the Type-C spec are read.

| Topic | Statement | Source | Label |
|---|---|---|---|
| Rx.Detect method | The port periodically applies a small voltage ramp to both wires of its transmitter pair and measures the resulting current pulse/charging behaviour through the AC-coupling capacitors toward the far end; a receiver termination to ground makes the pair charge differently from an open or high-impedance load. A purely differential termination does not pass the test (Xillybus). | Xillybus tutorial (xillybus.com/tutorials/usb-ltssm-lfps-power-management); a patent text found by web search (US 8,489,781 per the search URL, not read in full) | secondary |
| Detect voltage | Allowed voltage change during receiver detection V(TX-RCV-DETECT) 600 mV max (the step is a rise) | TUSB p.8 | VERIFIED in TUSB, secondary to USB 3.x |
| Detect result: no termination | Transmitter stays in the detect state and "periodically performs far-end receiver detection" (U2/U3 and disconnect states: TUSB p.18 s.7.7). No LFPS is sent before a receiver is detected; Polling (LFPS) starts only after detection (Xillybus: "Receiver found: the Polling state is invoked"). No polling interval is stated by Xillybus; TUSB has a device-specific setting of 8 or 12 ms. | TUSB p.17-18; Xillybus | secondary; interval UNRESOLVED |
| Receiver termination | Receiver DC common-mode impedance 18 to 30 ohm and differential 72 to 120 ohm, "present when SuperSpeed USB device detected on TXP/N" (this is the 50 ohm to ground per line); with no device detected or while VCC ramps the DC input common-mode impedance is >= 30 kohm (high impedance) | TUSB p.8 | VERIFIED in TUSB, secondary to USB 3.x |
| LFPS levels | Compliance LFPS Rx testing uses 800 mVpp and 1200 mVpp differential, 50 ns period; receive detect threshold 100 to 300 mV pp (TUSB p.8) | USB-IF LFPS compliance doc as quoted by web search; TUSB p.8 | secondary |
| SuperSpeed TX | Differential swing of order 0.8 to 1.2 Vpp (TUSB specs its own TX at 900 / 1000 / 1200 mVpp min, 1450 mV max, p.8); TX DC common mode 0 to 2 V, typ 1.85 V | TUSB p.8 | secondary; host-side limits UNRESOLVED |
| AC coupling | USB 3 transmitters are AC-coupled at the TX side, so our LVDS DC level (about 1.2 V) reaches the host RX termination directly while host TX DC never reaches our CAN pins | design knowledge, not cited | PROPOSED; host RX DC common-mode tolerance UNRESOLVED |

### 3.2 Chain of events when a module is plugged into a laptop

Orientation and lane mapping are a Type-C cable matter (not verified, UNRESOLVED): either TX1 or TX2 of the module meets the host RX pair, and either RX1 or RX2 of the module meets the host TX pair.

1. CC/Rd: module is a UFP with Rd (decision 13 and the Controller sheet); the host applies VBUS and the SuperSpeed lanes are enabled for detect.
2. Host Rx.Detect on its TX pair. This pair lands on our CAN_H/CAN_L pair: HVD230 CANH, CANL each see RI = 20 / 35 / 50 kohm (p.7) to an internal bias, input capacitance 32 pF, differential resistance 40 / 70 / 100 kohm. Unpowered the same pins pass 100 to 350 uA at 7 V with VCC = 0 (II, p.7). Both lines together as a common-mode load are about 10 to 25 kohm, three orders of magnitude above the 18 to 30 ohm of a real termination. The ESD capacitance, 32 pF per pin plus the cable, is small against the host's TX AC coupling capacitor, so the charging time is dominated by the resistance. PROPOSED conclusion: no termination is detected (a host test of a 10 to 25 kohm load is still UNRESOLVED; the TUSB shows the no-device impedance is quoted as >= 30 kohm, so we are marginally below the "typical open" resistance but nowhere near a termination).
3. No termination detected: the host remains in Rx.Detect polling, sends no LFPS and no SuperSpeed signalling, and keeps its receiver termination off (high impedance) so our LVDS buffer sees at least tens of kohm per line (PROPOSED, from the TUSB statement).
4. Worst case if the host did signal: swing at our CAN pins about 0.8 to 1.2 Vpp differential, bias 0 to 2 V, the AC-coupled side drives in common mode up to about +-0.6 V steps. HVD230 allows -4 to 16 V on any bus terminal and +-25 V transient through 100 ohm (p.5); the differential input range is +-6 V (VID, recommended operating, p.6). VERIFIED limits, margins comfortable (more than 5 V).
5. Worst case if the host also terminated: our LVDS driver is short-circuit rated and delivers about 175 mV into 50 ohm per line (see 1.4 b); the host RX sees a 1.2 V common-mode DC level with a small differential signal. Host RX DC common-mode tolerance not documented here: UNRESOLVED, but the offered level is below the host's own TX DC common mode of up to 2 V (TUSB p.8), so a host cannot plausibly require less.
6. CAN activity: only the ESP32 firmware starts CAN frames. HVD230 dominant drives CANH 2.45 V to VCC and CANL 0.5 to 1.25 V (p.7); IOS +-250 mA so the transceiver survives a 50 ohm host termination, 3.3 V / 50 ohm = 66 mA, though the host side has an AC-coupling capacitor in series (open at DC), so DC loading does not occur. PROPOSED: the firmware keeps the CAN driver silent (RS high standby or listen-only) until it sees bus traffic, so a lone module on a laptop never transmits into the host's receive pair.
7. USB 2.0 D+/D- on the ESP32 and VBUS follow decision 13 and `docs/research/usb-standalone-power.md`; this document does not cover them.
8. SBU = AUX: the pins are on the same connector and may be actively driven by hosts for sideband (DisplayPort alt mode, USB4); our AUX is an ESP32 GPIO through 1 kohm (connector.md). ESP32 3.3 V GPIOs are not 5 V tolerant. PROPOSED: add a series resistor plus clamp or analog switch on SBU. UNRESOLVED: the Type-C SBU voltage limits are not in hand.

### 3.3 Verdict (module and laptop)

PROPOSED, based on datasheet limits and secondary-source host behaviour, not tested with any laptop:
- Laptop is not put at risk by our LVDS buffer (current-steering outputs, +-10 mA short-circuit rated, 0 to 3.6 V range, Hi-Z unpowered) or by our CAN transceiver (no termination, 20 to 50 kohm per pin).
- Module is not put at risk by the host's TX (0 to 2 V DC plus under 1.5 Vpp, within the HVD230 -4 to 16 V and LVDS104 -0.5 to 4 V limits).
- Expected outcome: the host never completes SuperSpeed link training with the module, which is fine because the module uses USB 2.0 only on a laptop.
- Label for the doc and board: "USB-C: USB 2.0 and 5 V only on a host; SuperSpeed pairs carry proprietary LVDS/CAN, not USB 3."; the module is not USB 3 compliant and must not be advertised as such.
- Residual risks: (i) a host that terminates on any DC path; (ii) SBU; (iii) VBUS capacitance/inrush (power.md C33/C34 note); (iv) electrical-idle host TX could couple a 10 mV-class signal into CAN (receiver threshold 500 to 900 mV, HVD230 p.7, so ignored).

### 3.4 Reverse accident: laptop plugged into the FPGA-end breakout

Breakout (PROPOSED): source 5 V with Rp on CC, CAN transceiver on the TX pairs, FPGA LVDS on the RX pair.
- Type-C: a laptop port is also a DFP with Rp. Rp to Rp: neither side sees Rd, so no attach, no VBUS, no SuperSpeed. Type-C spec not obtained: UNRESOLVED.
- Largest hazard (PROPOSED): a breakout that drives 5 V on VBUS permanently would back-feed the laptop's VBUS output. The breakout must switch VBUS on only after Rd is detected on CC (a simple CC comparator plus load switch, or a Type-C source controller). Not verified against the Type-C spec.
- FPGA LVDS input: what the laptop could apply: nothing unless it signals, which needs its own Rx.Detect to see a termination to ground. The ECP5 DIFFRESISTOR (TN p.15; p.20; p.26) is across the pair, giving no DC path to ground, so Rx.Detect sees no receiver (PROPOSED). If the host did signal, the TX swing 0.8 to 1.2 Vpp AC-coupled around a floating common mode: input transient limit is -0.5 to 3.63 V (ECP5 DS Table 3.1, p.51, VERIFIED), IIN +-10 uA power on or off (Table 3.13, p.58); the pair is outside the recommended VCM range 0.05 to 2.35 V when the common mode floats, so reception would just fail. A 1.2 V pp swing centred near 1.2 V is inside the limit. No damage expected.
- Breakout CAN: the CAN transceiver's CANH/CANL drive into the laptop RX pair only after the laptop's own detect, which does not happen; if it did, 50 ohm to ground per line is 66 mA at 3.3 V, inside the transceiver's +-250 mA IOS (HVD230 p.7).

## 4. Signal integrity (PROPOSED, reasoned; no measurement or simulation)

### 4.1 LVDS, 50 Mbps over 3 m of 90 ohm USB 3 pair

Assumptions: cable differential impedance about 90 ohm (USB 3 convention; not verified here), velocity 4.3 to 5 ns/m (SLLA270 p.9 uses 5 ns/m for a twisted pair; a PTFE/PE foam USB 3 cable is typically somewhat faster), 100 ohm termination at the FPGA.
- One-way delay 13 to 15 ns, round trip 26 to 30 ns, which is 1.3 to 1.5 UI.
- Far-end reflection: Gamma = (100 - 90) / (100 + 90) = +0.053 (5.3 %).
- Near end: the LVDS driver is current-mode with an impedance that is not specified in the datasheet; a bound of |Gamma_source| <= 1 gives a second-pass echo of at most 0.053 x (1 + 0.053) x 350 mV = about 19 mV at the FPGA, 26 to 30 ns after the edge, so it lands in the middle of the following bit (6 to 10 ns into it). Against 247 mV minimum VOD (peak, 494 mV p-p) and a 100 mV threshold the echo costs at most 19 mV of 147 mV margin (13 %), a negligible margin loss for a 50 Mbps NRZ signal with the 8b/10b DC balance.
- Edge rate 0.3 to 1.2 ns (LVDS104 p.6) is much shorter than the line delay, so the reflection is a full step; no ringing problem since it is one echo.
- Cable DC resistance (PROPOSED, copper wire table values): 30 to 34 AWG is roughly 0.34 to 0.86 ohm/m per conductor, 2 conductors x 3 m = 2 to 5 ohm in series with the 100 ohm load, so 2 to 5 % amplitude loss: minimum VOD 247 mV falls to about 235 mV. Skin/dielectric loss at 25 MHz fundamental: expected small, not quantified.
- Common-mode: ground difference between module and ULX3S is carried by the cable GND (shared); LVDS tolerates +-1 V (LVDS22 text, p.1 "up to 1 V of ground potential difference"); the ECP5 VCM window is 0.05 to 2.35 V against the module's 1.2 V.
- Series termination: does not help a current-steering driver and would reduce amplitude: not worth it.
- External 90 ohm instead of the DIFFRESISTOR: removes the 5.3 % echo, but the on-die resistor tolerance is not given in TN or DS (UNRESOLVED) and adds a part on the breakout; the echo is not a problem, so keep DIFFRESISTOR="100" (decision as in ulx3s-lvds-input.md) unless bench eyes show closure. Terminate the second (unused) RX pair on the breakout with a 100 ohm resistor (otherwise the second 3 m pair is an open-ended line driven by the second buffer output; harmless to the part, but it reflects fully and adds crosstalk and EMI).
- Fan-out loading: the two buffer outputs drive separate pairs, no sharing.

### 4.2 CAN, 125 kbit/s

- Bit time 8 us; HVD230 with RS = 10 kohm: tr 80 / 120 / 160 ns, tf 80 / 125 / 150 ns, tPLH 70/125, tPHL 130/180 ns (HVD230 p.8); t(LOOP1) 105 to 175 ns (p.8).
- Stub limit (SLLA270 p.9, VERIFIED statement of the rule): maximum unterminated stub = 1/3 of the critical length, critical length = transition time / down-and-back delay per metre, at 5 ns/m. ISO 11898 recommends 0.3 m at 1 Mbit/s (SLLA270 p.5; p.10). SLLA270 p.10 gives its own example: 10 kohm on RS and 160 ns gives 5 1/3 m.
  - With 80 ns (worst-case tr, RS 10 kohm): stub <= 80 ns / (3 x 10 ns/m) = 2.7 m; with 120 ns typ 4 m. A 3 m cable stub is marginal at the minimum edge.
  - With RS 100 kohm: tr 600 / 800 / 1200 ns (HVD230 p.8) gives >= 20 m by the same rule. tPHL up to 1.2 us and t(LOOP) 535 to 990 ns (p.8) are still about 12 % of the 8 us bit, far inside the sample point. PROPOSED: R199 to 100 kohm.
- Termination at the breakout only: the cable pair is about 90 ohm against the 120 ohm termination, so these are not matched transmission lines (at 800 ns edges a 3 m stub is electrically short: 30 ns down-and-back against an 800 ns edge, about 4 %). SLLA270 p.4 says do not terminate on a removable node, so one termination at the breakout end is the compliant choice with the split termination of p.8 Fig. 10 (already decision in connector.md). With two or more modules star-connected to the breakout, each has an unterminated stub of up to 3 m and the breakout is a point where the stubs meet: reflection reasoning only; PROPOSED, to bench-verify.
- RX1/RX2 bused on the module and TX1/TX2 bused at the breakout puts the two cable pairs in parallel (about 45 ohm combined); acceptable at these edge rates. The mismatch is inside the slow edges. Bus idle DC: HVD230 recessive level about 2.3 V (VOL recessive, p.7), which is the same DC level across both bused pairs.
- Single termination yields the bus load RL = 120 ohm instead of 60 ohm: dominant amplitude higher, within +-6 V receiver range (HVD230 p.6); receiver thresholds 500 to 900 mV (p.7).

## 5. UNRESOLVED / not verified list

1. USB 3.2 spec Chapter 6 (Rx.Detect timing and thresholds, receiver DC tolerance) and the USB Type-C spec (cable lane mapping, SBU, VBUS gating): not downloaded. Host behaviour is from TUSB1002, Xillybus and a search summary.
2. Real-laptop test of a module with a foreign host, scope on CAN pins; a host that treats 10 to 25 kohm per pin as terminated.
3. LVDS104 output short-circuit duration; SN65LVDS22 lifecycle detail beyond one web fetch.
4. Non-TI fan-out parts (ON, Renesas, Microchip) not surveyed.
5. ECP5 DIFFRESISTOR tolerance; ECP5 maximum input transient behaviour at floating common mode.
6. USB-C cable impedance, velocity and DC resistance values used in section 4 are typical assumptions, not from a cited document.
7. SBU voltage limits and the EN3/EN4 tie-off choice.
