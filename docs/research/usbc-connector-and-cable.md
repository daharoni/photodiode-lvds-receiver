# One 24-pin USB-C receptacle and a passive C-to-C cable: research for decision 14

Date 2026-10-09. Research and proposal only. Nothing here was simulated or measured, and nothing was changed in the generators, sheets, spec or decision log.

Labels (CLAUDE.md rule 2): VERIFIED (checked against a cited document, revision, page/table), PROPOSED (design intent or reasoned estimate), UNRESOLVED (open). Downloads are in `docs/research/downloads/usbc-connector/` (see `MANIFEST.md` there; URLs and SHA-256).

Documents cited:
- "TC": USB Type-C Cable and Connector Specification, Release 2.5, March 2026 (`typec-r2.5.pdf`, from the usb.org release zip). Page numbers are the printed page numbers in the page header.
- "WE": Wuerth 632723300011 datasheet, revision 003.000, 2025-09-04 (`wurth-632723300011.pdf`, PDF page).
- "GCT4115", "GCT4110", "GCT4085": GCT drawings (PDF page).
- "TPDxE05U06": TI SLVSBO7O, Aug 2024. "ESD122": TI SLVSDP5A, Aug 2018. "PUSB3FR4": Nexperia, 12 July 2018.

## Summary for decision 14

1. VERIFIED (TC Table 3-10 p.83): a standard full-featured C-to-C cable is wired so that plug-1 TX1 goes to plug-2 RX1, TX2 to RX2, RX1 to TX1, RX2 to TX2, with p to p and n to n (no polarity inversion), and the two SBU wires cross (SBU1 to SBU2, SBU2 to SBU1). CC is one wire (A5 to A5). D+/D- is one pair (A6/A7 to A6/A7). Plug pins B6/B7 do not exist.
2. VERIFIED by derivation (TC Table 3-4 p.76 plus plug geometry): flipping a plug swaps TX1<->TX2, RX1<->RX2, SBU1<->SBU2, CC1<->CC2 with polarity preserved (A_n lands on B_n). Dp1/Dp2 do not swap in function: only the Dp position changes. Consequence for the module: because only one D+/D- pair exists in the cable, the module receptacle must tie Dp1 to Dp2 and Dn1 to Dn2 (TC Table 3-4 note 1, p.77, max 3.5 mm shorting trace) so the ESP32 is connected in both orientations.
3. The concept works in all four flip combinations (section 2): if the module drives the same LVDS on TX1 and TX2 and buses CAN_H/CAN_L on both RX pairs, the breakout always sees the LVDS on both RX1 and RX2 and the module always sees the breakout CAN on both RX pairs. Only SBU polarity of the pairing changes (crossed when both ends are in the same orientation, straight otherwise); tying SBU1 to SBU2 at both ends is electrically sound and removes the dependence (PROPOSED, with one caveat: TC section 4.3 p.150 says a non-USB4 port's SBU pins shall be open or at least 950 kohm).
4. All full-featured C-to-C cables must be electronically marked (TC 3.4.1.1 p.83). The cable has a VCONN wire (wire 18) and an Ra of 0.8 to 1.2 kohm on each VCONN pin (TC Table 3-10 p.83, Table 4-29 p.246). Both module CC pins therefore must tolerate up to 5.5 V (TC vVCONNValid 3.0 to 5.5 V, p.155) when the module is plugged into a laptop or charger that sources VCONN.
5. Length: the spec's passive-cable lengths are USB 3.2 Gen 1 <= 2 m, Gen 2 <= 1 m, USB 2.0 <= 4 m (TC Table 3-1 p.44, informative). A certified passive full-featured 3 m cable at 5 Gbps does not exist under that table; the market check (section 3.5) found 3 m offers that are either unspecified or Gen 2x2 (probably active). For our signals (50 Mb/s LVDS, 125 kbit/s CAN) loss is negligible; the real risks are (a) an active/redriver cable that blocks both signals, and (b) a USB 2.0-only C-to-C cable with no SS wires. PROPOSED: specify the cable as "passive, full-featured, SS wires verified by DC continuity", prefer <= 2 m where possible, and verify every 3 m cable on a breakout before use.
6. VBUS: a 3 A cable must have <= 250 mV GND and <= 500 mV VBUS drop at its rated current, contacts included (TC 4.4.1 p.151), so at 0.3 A a compliant 3 A cable drops <= 75 mV total. A non-compliant 28 AWG 3 m cable would drop about 0.38 V at 0.3 A (PROPOSED, section 3.4).
7. Receptacle: three of the six candidates named in the brief are NOT 24-pin parts: GCT USB4110 and USB4085 are 16-contact USB 2.0 receptacles (VERIFIED, GCT drawings), and Molex 2171790001 is a USB 2.0 part with 8 dummy contacts (PROPOSED, distributor listings; datasheet not obtained). Top pick: Wuerth 632723300011 (24-pin, horizontal THR/SMT hybrid, 5 A, 10,000 cycles; VERIFIED in WE). It has no KiCad footprint in the bundled library nor in the lab library, so a footprint must be added to the lab library from WE p.1. Alternative with a bundled KiCad footprint: GCT USB4115-03-C (vertical SMT, `Connector_USB:USB_C_Receptacle_GCT_USB4115-03-C`).
8. ESD: keep USBLC6-2SC6 on D+/D-; protect CC1, CC2, SBU (tied) and the eight SS pins with two TI TPD6E05U06 (12 channels, 0.47 pF typ, VRWM 5.5 V). ESD122 (VRWM +/-3.6 V) and PUSB3FR4 (VI max 3.3 V) must not be used on CC, SBU or the CAN pins.
9. Breakout: Rp = 56 kohm to 5 V on each CC pin (TC Table 4-27 p.245); VBUS should be gated until Rd is seen (TC 4.4.2 p.152) so that a laptop plugged into the breakout by mistake is not back-fed.

Open items (all UNRESOLVED):
- Whether any commercially sold 3 m cable is passive full-featured; verify on hardware (section 3.5).
- Footprint for the Wuerth part (lab library PR) and the mechanical choice horizontal vs vertical; GCT USB4115 pad geometry not cross-checked against its drawing.
- Amphenol 12401610E4#2A: 24-pin by distributor listings and a KiCad footprint exists, but the drawing was not obtainable (HTTP 403).
- Module behaviour when plugged into a laptop USB-C port for programming: the laptop's SS TX pairs land on the module CAN pins and the module LVDS lands on the laptop's SS RX pins; damage/tolerance was not verified (section 5.3).
- CAN topology: 14 stubs of up to 3 m at 125 kbit/s on a shared bus (CiA 303-1 / ISO 11898 stub limits were not fetched).
- Crosstalk from the CAN edges into the adjacent LVDS pair inside the cable (not measured).
- Effect of up to 0.4 V cable drop on the module rails (module regulator dropout not checked here).

## 1. Receptacle pin map and what a plug flip does

### 1.1 Receptacle pins (VERIFIED: TC Table 3-4, p.76)

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| A1 | GND | B12 | GND |
| A2 | TXp1 | B11 | RXp1 |
| A3 | TXn1 | B10 | RXn1 |
| A4 | VBUS | B9 | VBUS |
| A5 | CC1 | B8 | SBU2 |
| A6 | Dp1 | B7 | Dn2 |
| A7 | Dn1 | B6 | Dp2 |
| A8 | SBU1 | B5 | CC2 |
| A9 | VBUS | B4 | VBUS |
| A10 | RXn2 | B3 | TXn2 |
| A11 | RXp2 | B2 | TXp2 |
| A12 | GND | B1 | GND |

Notes (TC Table 3-4 p.77): B6/B7 are not present in the plug; the receptacle must support the D+/D- pair on Dp1/Dn1 or Dp2/Dn2, and the two Dp (and two Dn) may be shorted on the host/device within 3.5 mm; all VBUS pins and all GND pins are bussed on the PCB; the shell is separate. The same A/B pin names are used for plug pins in TC Table 3-10.

### 1.2 What a flip does (VERIFIED by derivation from TC Table 3-4 and the plug/receptacle layout, Figures 2-1 and 2-2, p.36-37; the spec does not print this mapping as a table)

The plug is symmetric under a 180 degree rotation about the insertion axis. The receptacle B-row is the A-row rotated by 180 degrees (B12 sits under A1), so a plug contact A_n lands on receptacle B_n when the plug is flipped, and B_n lands on A_n. Applying this to Table 3-4:

| Plug pin (name) | Normal: lands on | Flipped: lands on | Effect |
|---|---|---|---|
| A2 TXp1, A3 TXn1 | A2 TXp1, A3 TXn1 | B2 TXp2, B3 TXn2 | TX1 <-> TX2, p stays p, n stays n |
| B2 TXp2, B3 TXn2 | B2, B3 | A2 TXp1, A3 TXn1 | same |
| B11 RXp1, B10 RXn1 | B11, B10 | A11 RXp2, A10 RXn2 | RX1 <-> RX2, polarity preserved |
| A11 RXp2, A10 RXn2 | A11, A10 | B11 RXp1, B10 RXn1 | same |
| A8 SBU1 | A8 SBU1 | B8 SBU2 | SBU1 <-> SBU2 |
| A5 CC | A5 CC1 | B5 CC2 | CC1 <-> CC2 (the plug's other pin, B5, is VCONN) |
| A6 Dp1, A7 Dn1 | A6 Dp1, A7 Dn1 | B6 Dp2, B7 Dn2 | D+ stays D+, D- stays D-; only the receptacle position (1 vs 2) changes |
| A1/B1/A12/B12, A4/B4/A9/B9 | GND, VBUS | GND, VBUS | unchanged |

Confirmed against Table 3-4: A2/B2 are TXp1/TXp2, A3/B3 are TXn1/TXn2, A11/B11 are RXp2/RXp1, A10/B10 are RXn2/RXn1, A8/B8 are SBU1/SBU2, A5/B5 are CC1/CC2, A6/B6 are Dp1/Dp2, A7/B7 are Dn1/Dn2. TC section 4.2.2 p.150 and Table 4-1 p.149 state that the two Dp/Dn pin sets exist "to enable plug flipping".

## 2. Cable wiring and the four flip combinations

### 2.1 Full-featured C-to-C wiring (VERIFIED: TC Table 3-10, p.83)

| Plug 1 pin | Wire | Plug 2 pin |
|---|---|---|
| A1,B1,A12,B12 GND | 1 [16] | A1,B1,A12,B12 GND |
| A4,B4,A9,B9 VBUS | 2 [17] | A4,B4,A9,B9 VBUS |
| A5 CC | 3 | A5 CC |
| B5 VCONN | 18 | B5 VCONN |
| A6 Dp1 / A7 Dn1 | 4 / 5 | A6 Dp1 / A7 Dn1 |
| A2 TXp1 / A3 TXn1 | 6 / 7 | B11 RXp1 / B10 RXn1 |
| B11 RXp1 / B10 RXn1 | 8 / 9 | A2 TXp1 / A3 TXn1 |
| B2 TXp2 / B3 TXn2 | 10 / 11 | A11 RXp2 / A10 RXn2 |
| A11 RXp2 / A10 RXn2 | 12 / 13 | B2 TXp2 / B3 TXn2 |
| A8 SBU1 | 14 (SBU_A) | B8 SBU2 |
| B8 SBU2 | 15 (SBU_B) | A8 SBU1 |
| Shell | braid | Shell |

Notes from the same table: shield and GND are connected in each plug (note 6); a 10 nF VBUS bypass capacitor is required at each end of a full-featured cable (note 4); pin B5 (VCONN) is used in electronically marked cables (note 2), and all full-featured cables must be e-marked (TC 3.4.1.1 p.83). Only wire 3 carries CC; the other CC position in each plug is VCONN (TC section 2, p.36-37). Wire 18 is the VCONN wire between plugs; whether a given cable has it connected through (versus an e-marker in only one plug) was not verified: UNRESOLVED, and the design below does not depend on it.

### 2.2 The four combinations (PROPOSED analysis; computed with a script from TC Tables 3-4 and 3-10 and the flip rule of section 1.2; module = plug 1 end, breakout = plug 2 end)

Module drives LVDS on receptacle TX1 (A2/A3) and TX2 (B2/B3) and buses CAN_H on both RXp pins and CAN_L on both RXn pins. The breakout drives its CAN on TX1 and TX2 and receives LVDS on RX1 and RX2.

| Module end | Breakout end | Module TX1 arrives at breakout | Module TX2 arrives at breakout | Breakout TX1 / TX2 arrive at module | Module SBU1 / SBU2 arrive at breakout | Module CC1 / CC2 wire |
|---|---|---|---|---|---|---|
| normal | normal | RX1 (B11/B10) | RX2 (A11/A10) | RX1 / RX2 | SBU2 / SBU1 | CC1 to breakout CC1 |
| normal | flipped | RX2 | RX1 | RX2 / RX1 (swapped) | SBU1 / SBU2 | CC1 to breakout CC2 |
| flipped | normal | RX2 | RX1 | RX2 / RX1 | SBU1 / SBU2 | CC1 to breakout CC2 |
| flipped | flipped | RX1 | RX2 | RX1 / RX2 | SBU2 / SBU1 | CC1 to breakout CC1 |

Proof sketch (VERIFIED against the tables by the script run; statement is PROPOSED analysis): the cable maps every plug-1 TX pair to a plug-2 RX pair with p to p, n to n, and each end's flip is a TX1<->TX2 / RX1<->RX2 relabeling with polarity preserved. So the set of two pairs driven by the module at plug 1 always maps onto the set {RX1, RX2} at the breakout receptacle, only the labels may swap. If both module TX pairs carry the same LVDS, the breakout sees it on RX1 and RX2 in all four cases, polarity correct. The same argument in the other direction puts the breakout CAN on both module RX pairs in all four cases (CAN_H on the p pins and CAN_L on the n pins, never inverted). The breakout therefore needs to take only one pair (for example RX1) to the FPGA; leave the other pair terminated with 100 ohm (or also usable). Both ends see "the same signal on both pairs", so no orientation logic is required.

SBU: the cable crosses SBU_A and SBU_B (section 2.1), and a flip swaps SBU1/SBU2 at each end, so SBU1 at the module reaches breakout SBU2 when both ends are in the same orientation (cases 1 and 4) and SBU1 when the orientations differ (cases 2 and 3). The AUX line with no tie would therefore swap sides depending on how the user plugs in.

Tying SBU1 to SBU2 at both ends (PROPOSED): electrically sound. The cable then has two parallel wires (14 and 15) between the same two nets, in every orientation; no loop or contention results because both wires connect net M (module SBU1+SBU2) to net B (breakout SBU1+SBU2). Cable SBU wires are single-ended with zCable 32 to 53 ohm, <= 5 ohm DC resistance, <= 26 ns delay, and insertion loss limits of 2 dB at 0.5 MHz, 4 dB at 1 MHz and 9 dB at 10 MHz (VERIFIED, TC Table 3-24 p.113), so AUX should be a slow signal (about <= 1 MHz, PROPOSED). Caveat (VERIFIED, TC 4.3 p.150 and Table 4-31 p.246): a port that implements neither USB4 nor an Alternate Mode shall leave SBU open or weakly pulled down (>= 950 kohm). Our use is outside USB, which is acceptable for a private link but is unsafe if the module is plugged into a laptop (section 5.3, UNRESOLVED).

D+/D-: wires 4/5 are on plug pins A6/A7 only, so with the module end flipped the cable D+/D- lands on the module's B6/B7 (Dp2/Dn2). Tie Dp1 to Dp2 and Dn1 to Dn2 close to the receptacle (VERIFIED requirement basis: TC Table 3-4 note 1 p.77), with the USBLC6-2SC6 on the tied nodes (PROPOSED). In the table above, the "Dp" wire reaches the breakout only if the breakout end is in a matching orientation; the breakout does not use D+/D-, so this does not matter there. For the laptop programming case the laptop receptacle ties or switches its own Dp1/Dp2.

### 2.3 Orientation detection from CC (VERIFIED: TC section 4.5.1 and Table 4-10 p.162, Table 4-35 p.254)

Only the CC wire reaches the far end; the plug's other CC pin is VCONN and presents Ra (0.8 to 1.2 kohm to ground, TC Table 4-29 p.246) in a powered cable. A sink (the module, Rd 5.1 kohm on each CC) sees a voltage above vRd-connected (min 0.249 V, TC Table 4-35 p.254) only on the pin carrying the source's Rp; that pin's number is its orientation (CC1 high = plug normal, CC2 high = flipped) (TC p.162, "the CC pin that is at a higher voltage (i.e., pulled up by Rp in the Source) indicates the orientation of the plug"). A source (the breakout) sees Rd on the CC-wire pin and Ra on the VCONN pin (TC Table 4-10 p.162: Rd+Ra means powered cable with sink attached). The module currently has no CC voltage reader (usb-standalone-power.md section 1.4); orientation detection is not needed by this concept because of the dual-pair fan-out, but a CC sense to the ESP32 ADC would be needed for anything that distinguishes a laptop from a breakout (section 5.3).

## 3. Cable physics

### 3.1 What is in a full-featured C-to-C cable (VERIFIED: TC Tables 3-6 p.79 and 3-8 p.81; TC 3.7.1 p.95; TC 3.4 p.83)

| Wire | Reference gauge (informative, TC Table 3-8) |
|---|---|
| GND, VBUS (wires 1, 2, and optional 16, 17) | 20 to 28 AWG |
| CC (wire 3) | 32 to 34 AWG |
| D+/D- (UTP, wires 4, 5) | 28 to 34 AWG, unshielded twisted pair |
| 4 shielded differential pairs SDP1..4 (wires 6 to 13) | 26 to 34 AWG; coaxial or shielded twisted pair (drain wires needed for twinax) |
| SBU_A, SBU_B (wires 14, 15) | 32 to 34 AWG |
| VCONN (wire 18) | 32 to 34 AWG |

The spec does not specify gauge (TC 3.3.3 p.81: "This specification does not specify wire gauge"); it gives typical ranges and a typical full-featured outer diameter of 4 to 6 mm. An overall braid encloses all wires and is terminated to the plug shells (TC 3.4 p.83). The recommended differential impedance of the shielded pairs is 90 ohm +/- 5 ohm, or 45 ohm +/- 3 ohm single-ended for coax (TC 3.7.1 p.95, informative).

### 3.2 Length limits by generation and why (VERIFIED: TC Table 3-1 p.44, informative; limits in TC 3.7.2.3 p.101 and 3.7.2.4 p.105)

| Cable | Passive length | Insertion-loss limit at Nyquist (cable assembly) |
|---|---|---|
| USB 2.0 Type-C (no SS wires) | <= 4 m | not applicable (no SS pairs) |
| USB 3.2 Gen 1 / USB4 Gen 2 (5 Gbps) | <= 2 m | >= -7.0 dB at 2.5 GHz, > -11.5 dB at 5 GHz (TC 3.7.2.4.1 p.105) |
| USB 3.2 Gen 2 / USB4 Gen 2 (10 Gbps) | <= 1 m | >= -4 dB at 2.5 GHz, >= -6 dB at 5 GHz, >= -11 dB at 10 GHz (TC 3.7.2.3.1 p.101) |
| USB4 Gen 3 | <= 0.8 m | >= -4.2 dB at 2.5 GHz, -6 dB at 5 GHz, -7.5 dB at 10 GHz (TC 3.7.2.5.1 p.107) |

Caution: the spec headings for these requirements overlap in generation (3.7.2.3 is headed "USB 3.2 Gen2 and USB4 Gen2" but its limits include a 10 GHz value; 3.7.2.4 is headed "USB 3.2 Gen1 and USB4 Gen2"); the limits above are quoted as printed under each heading and the mapping to generations is UNRESOLVED. The footnote of Table 3-1 says the lengths are "informative and represent the practical lengths based on cable performance requirements": the length limit is a consequence of the loss budget. Example (VERIFIED numbers from TC Table 3-21 p.95, PROPOSED arithmetic): 28 AWG twisted-pair loss is -2.1 dB/m at 2.5 GHz, so 2 m is -4.2 dB and 3 m is -6.3 dB, against the -7.0 dB Gen 1 total that must also cover the plugs and any host/device channel; 3 m at 28 AWG is therefore marginal even for Gen 1, and thinner wires fail. Active cables (up to 5 m) are covered by TC section 6 (p.278 and following).

### 3.3 What this implies for 50 Mb/s LVDS and 125 kbit/s CAN (PROPOSED reasoned estimate, not measured)

- The SS-loss limits apply at 2.5 GHz. Our 50 Mb/s signal has a 25 MHz fundamental. Scaling Table 3-21's 28 AWG figure (-1.0 dB/m at 0.625 GHz) by sqrt(f) gives roughly -0.2 dB/m at 25 MHz; the 34 AWG figure (-1.8 dB/m at 0.625 GHz) gives roughly -0.4 dB/m, about -1.1 dB over 3 m. The sqrt(f) scaling is an extrapolation below the table's range and is an estimate only.
- DC resistance matters more at this frequency: a 34 AWG pair is about 0.86 ohm/m per wire (copper at 20 degC, computed, not from a cable datasheet), so a 3 m pair loop is about 5 ohm, which is about 5 % of a 100 ohm termination (about 0.4 dB, about 18 mV on a 3.5 mA LVDS current). Negligible.
- Delay is about 3 m x 4 to 5 ns/m, about 12 to 15 ns, less than one 20 ns UI; the FPGA receiver samples with its own clock, so latency is irrelevant (PROPOSED). Intra-pair skew is recommended < 10 ps/m (TC 3.7.1.1 p.95), negligible at 20 ns UI.
- CAN at 125 kbit/s (8 us bit) on the same wires: loss and reflection at 25 MHz-class are irrelevant to a 125 kbit/s signal whose edges are tens of ns; the main design questions are topology (14 stubs on a shared bus, UNRESOLVED) and common-mode range across the cable GND drop. Two cable pairs bused together are a parallel connection of two 90 ohm pairs (about 45 ohm), another reason the CAN termination must be set at the breakout bus ends, not at the module (PROPOSED).
- Crosstalk from CAN edges (about 2 V swing) into the neighbouring LVDS pair (about 350 mV swing) inside the cable was not estimated or measured: UNRESOLVED (the SS crosstalk limits in TC 3.7.2 are defined for 5/10 Gbps and do not bound 25 MHz CAN edges).
- A cable that does not meet the Gen 1 3 m budget (all of them under TC Table 3-1) is therefore still electrically adequate for our signals if it is passive with the SS wires present; "not USB-IF-certifiable at 3 m" is not a defect for this link (PROPOSED).

### 3.4 VBUS drop over 3 m

- VERIFIED (TC 4.4.1 p.151): maximum cable IR drop is 250 mV for GND and 500 mV for VBUS at the cable's rated VBUS current, contact resistance included. A compliant 3 A cable therefore has at most about 0.25 ohm of GND+VBUS loop resistance, which is about 75 mV at 0.3 A (PROPOSED arithmetic).
- PROPOSED (copper at 20 degC, one VBUS wire plus one GND wire, 3 m each, computed from the AWG diameter formula; the braid and the second VBUS/GND wires in parallel and the contacts are not included; not from a cable datasheet):

| Gauge | Loop resistance, 3 m | Drop at 0.3 A |
|---|---|---|
| 20 AWG | 0.20 ohm | 60 mV |
| 24 AWG | 0.51 ohm | 0.15 V |
| 28 AWG | 1.28 ohm | 0.38 V |

- Receptacle contact resistance adds at most 40 mohm per contact (GCT) or 30 mohm (WE) per contact, with four VBUS and four GND contacts in parallel in each receptacle (WE p.3, GCT4115 p.1); negligible. The module's 5 V input minimum versus a 4.75 V source minus 0.4 V drop was not checked against the power sheet: UNRESOLVED.

### 3.5 Active cables, USB 2.0-only cables and how to tell (PROPOSED warnings)

- Active/redriver cables: the spec allows active cables up to 5 m that "function like passive cables from the user's perspective" for USB (TC p.278), but their SS paths contain redrivers/retimers that are built for 5/10 Gbps link signalling (receiver detect, LFPS, idle squelch, AC coupling). A redriver is expected to pass neither a 125 kbit/s CAN signal nor a continuous 50 Mb/s LVDS signal reliably (reasoning, not measured; PROPOSED). Avoid them.
- USB 2.0-only C-to-C cables (TC Table 3-11 p.84 wires 1 to 5 and 18 only; "TX/RX and SBU signals are not implemented", TC p.37): they lack the SS pairs and the SBU wires and are the most common 3 m "USB-C cable" at low cost. They connect VBUS, GND, CC and D+/D- only.
- How to tell (PROPOSED): look for the USB-IF "SuperSpeed 5 Gbps" (or 10/20 Gbps) logo and a USB-IF certification mark (TC 3.4.1.1 p.83 says certified full-featured cables should carry the certified icons giving the data rate); the product text should say "full-featured", "5 Gbps" or "USB 3.2 Gen 1", not "charging cable", "USB 2.0 480 Mbps" or "charge and sync". The cable's outer diameter (4 to 6 mm for full-featured vs 2 to 4 mm for USB 2.0, TC 3.3.3 p.81) is a weak hint. A definitive check is a DC continuity test on a breakout (A2 at plug 1 to B11 at plug 2 etc.): a passive full-featured cable shows a few ohms; USB 2.0-only and most active cables show open on the SS wires. Active cables cannot be told apart by logo; mark the test result on the cable.
- All full-featured cables are e-marked (TC 3.4.1.1 p.83); an e-marker alone does not make a cable active.

### 3.6 Market check, 2026-10-09 (web search; secondary sources, no price claims, availability not confirmed)

| Vendor, part | Length | Claim in listing | Note |
|---|---|---|---|
| Eaton Tripp Lite U420-010 | 3.05 m (10 ft) | USB-C M/M, USB 3.2 Gen 1 (5 Gbps), up to 3 A (reseller page tecisoft.com) | passive vs active not stated: UNRESOLVED; best lead for a 3 m 5 Gbps cable |
| Eaton Tripp Lite U420-003 | 0.91 m | Gen 1, 5 Gbps, 3 A (CDW listing) | short reference part |
| C2G 28830 / C2G28883 | 3 ft / 6.5 ft | USB-C to USB-C, USB 3.1/3.2 Gen 1, 3 A, 5 Gbps | no 3 m C-to-C found in this family (the 10 ft C2G items found are C-to-A) |
| StarTech USB315CCV2M | 2 m | 5 Gbps C-to-C | 2 m class |
| StarTech UCC-3M-10G-USB-CABLE | 3 m | listed as an active 10 Gbps cable | active: avoid |
| StarTech (3 m, 10 ft, USB 2.0 C-to-C) | 3 m | USB 2.0 only | no SS wires: avoid |
| Newnex screw-locking C-to-C: U4SRC01C04-030 (single screw, one end), U4SRC01C02-030 (dual screw, one end) | 3 m | page lists "USB 3.2 Gen 2x2", 20 V/3 A, range introduced as passive; no 5 Gbps screw-lock part listed | a 3 m passive Gen 2x2 cable is not allowed by TC Table 3-1, so this part is probably active or not compliant: UNRESOLVED; ask the vendor |
| Newnex U4S5C04C04-010 / -020 (single screw both ends), U4S5C02C02-010 / -020 (dual screw both ends) | 1 m, 2 m | Gen 2x2, 3 A, screw-locking | usable lengths with locking |
| Coolgear dual screw lock Type-C to A (1 m, USB 3.2 Gen 1, 3 A) | 1 m | C-to-A, not C-to-C | shows the screw-lock Type-C plug exists in a 5 Gbps part |
| JAE DX07 series screw-lock harness | custom | M2 thumbscrew in plug hood per the USB 3.1 screw-lock spec, up to 10 Gbps, 5 A | cable-harness maker, not a stock cable |
| Jimier / CoreDepot dual-thumbscrew panel-mount C-to-C (Newegg Business listings) | n/a | 10 Gbps, 65 W | panel-mount, M2 screws |

Screw-lock pitch/placement differ (a guide cites M2 screws at 15 or 19 mm centres, single or dual; telewiretech.com guide, secondary): a locking cable only helps if the module and breakout receptacles have matching screw holes, which neither candidate receptacle in section 4 has; the locking option is therefore a mechanical add-on (UNRESOLVED).

## 4. Receptacle selection

### 4.1 Candidates

| Part | Verdict | Basis |
|---|---|---|
| GCT USB4110 | NOT 24-pin. USB 2.0, 16 contacts (A1, A4..A9, A12, B1, B4..B9, B12 only) | VERIFIED: GCT4110 p.1 ("USB Type C Receptacle for USB 2.0 SMT Type, PCB Top Mount") |
| GCT USB4085 | NOT 24-pin. USB 2.0, 16 contacts, DIP type, top mount | VERIFIED: GCT4085 p.1 |
| Molex 2171790001 | probably NOT: "USB 2.0, 24 positions (16 signal plus 8 dummy)" | PROPOSED: DigiKey listings; Molex datasheet not obtained (no connection) |
| Wuerth 632723300011 | 24-pin, USB 3.1 Type-C, horizontal THR/SMT "Type C Hybrid 1.6mm" | VERIFIED: WE p.1 and p.3 |
| GCT USB4115-03-C | 24-pin, USB3.2 Gen2, vertical SMT, H = 9.30 mm | VERIFIED: GCT4115 p.1-2 |
| Amphenol 12401610E4#2A | listings say 24 positions, surface mount right-angle; KiCad has the footprint (24 SMD pads, 4 shell through-hole pads) | PROPOSED/UNRESOLVED: drawing not obtainable (HTTP 403) |
| Amphenol 12401548E4#2A | listings say 24 positions, hybrid SMT/THT; Arrow lists it as obsolete | PROPOSED/UNRESOLVED: same |
| Wuerth 632723300112 | not checked | the we-online.com datasheet URL returned 404 |

### 4.2 Top pick: Wuerth 632723300011 (VERIFIED from WE, revision 003.000, 2025-09-04)

| Item | Value |
|---|---|
| Pin numbering | 24 pins A1..A12 and B1..B12 as in TC Table 3-4; WE p.3 lists A2 SSTXp1, A3 SSTXn1, B11 SSRXp1, B10 SSRXn1, A10 SSRXn2, A11 SSRXp2, B2 SSTXp2, B3 SSTXn2, A6 Dp1, A7 Dn1, B6 Dp2, B7 Dn2, A8 SBU1, B8 SBU2. WE labels A5 "CC" and B5 "VCONN" (cable-plug names); on a receptacle these are CC1 and CC2 per TC Table 3-4, so wire A5/B5 as CC1/CC2 (PROPOSED reading) |
| Mounting and footprint (WE p.1) | horizontal, "THR/SMT", "Type C Hybrid 1.6mm": row A as 12 SMD pads, row B as plated through-holes (drill 0.4 mm, pad 0.65 mm, two staggered rows), 4 oval shield posts; recommended PCB thickness 1.6 mm, pin length 1.9 mm; land pattern with a "P.C.B End" line. Top vs mid mount not determined from the drawing: UNRESOLVED |
| Current (WE p.3) | 5 A rated; 48 V DC working; 100 V AC withstanding; contact resistance 30 mohm max |
| Mating cycles (WE p.3) | 10,000 |
| Force (WE p.3) | insertion 5 to 20 N, extraction 8 to 20 N |
| Temperature (WE p.3) | -40 to +105 degC |
| Certification | USB approval TID 5200000116, UL E323964 (WE p.3) |
| KiCad bundled footprint | none: no Wuerth 632723300011 in `Connector_USB.pretty` (checked against the KiCad 10.0.5 bundle on this machine), none in the lab library `~/Projects/kicad-lab-library` (checked). Wuerth offers Eagle/Cadence/STEP downloads (WE p.7), not KiCad. PROPOSED: create `AharoniLab_Connector:...632723300011` in the lab library from the WE p.1 land pattern and add a symbol (CLAUDE.md: new parts go in by PR to the lab library) |

Why pick it (PROPOSED): hybrid through-hole B row and shield posts give better mechanical retention than an all-SMT shell, suited to a lab module that is plugged and unplugged by hand; 0.5 mm pitch is acceptable for a professional fab (given in the brief).

### 4.3 Alternative: GCT USB4115-03-C (VERIFIED from GCT4115, revision B, PCN B8 17/12/25)

| Item | Value |
|---|---|
| Pin numbering | A1 GND, A2 SSTXp1, A3 SSTXn1, A4 VBUS, A5 CC1, A6 Dp1, A7 Dn1, A8 SBU1, A9 VBUS, A10 SSRXn2, A11 SSRXp2, A12 GND; B1 GND, B2 SSTXp2, B3 SSTXn2, B4 VBUS, B5 CC2, B6 Dp2, B7 Dn2, B8 SBU2, B9 VBUS, B10 SSRXn1, B11 SSRXp1, B12 GND (same as TC Table 3-4; GCT4115 p.2) |
| Type | vertical SMT, H = 9.30 mm; plug enters perpendicular to the PCB; 24 signal pads 0.30 mm wide plus shield pads (GCT4115 p.1-2) |
| Current | 5 A total on the VBUS pins, 6.25 A on the GND pins, 1.25 A on A5/B5, 0.25 A on each other pin; 48 V DC; contact resistance 40 mohm max initial, 50 mohm after test (GCT4115 p.1) |
| Mating cycles | 20,000 (GCT4115 p.1) |
| Temperature | -25 to +85 degC (GCT4115 p.1) |
| Certification | USB-IF TID 11254, IEC 62680-1-3:2022 (GCT4115 p.1) |
| KiCad bundled footprint | `Connector_USB:USB_C_Receptacle_GCT_USB4115-03-C` (30 pads: 24 signal plus shield; geometry not cross-checked against the GCT4115 p.2 land pattern: UNRESOLVED) |

Drawback: vertical, so the cable leaves perpendicular to the PCB; this only suits the final enclosure if the module is mounted with the connector facing out of the top, which is mechanical TBD.

### 4.4 ESD protection (D+/D- stays on USBLC6-2SC6)

The ESP32-C6 USB is full speed (12 Mb/s) so USBLC6-2SC6 capacitance is not an issue (brief; ESP32 USB speed not re-verified here). New lines to protect at the connector: TXp1/TXn1/TXp2/TXn2 (LVDS out), RXp1/RXn1/RXp2/RXn2 (CAN bus), SBU (tied nets), CC1, CC2. That is 11 channels.

| Part | Channels | Capacitance | Working voltage | Source | Fit |
|---|---|---|---|---|---|
| TI TPD4E05U06 (USON-10) | 4, unidirectional | 0.5 pF typ I/O to GND (VIO 2.5 V, 1 MHz) | VRWM 5.5 V, VBR 6.5 to 8.5 V, leakage 10 nA max | TPDxE05U06 Table 5.4 p.7 | works on all lines; 5.5 V rating covers VCONN (TC vVCONNValid <= 5.5 V, p.155) |
| TI TPD6E05U06 (USON-14, RVZ) | 6, unidirectional | 0.47 pF typ | same as above | TPDxE05U06 Table 5.4 p.7 | PROPOSED choice: two devices cover 12 channels with one spare, flow-through routing for stacked connector rows |
| TI ESD122 (X2SON) | 2, bidirectional | 0.2 pF typ I/O to GND, 0.27 max; 0.1 pF between I/Os | VRWM +/-3.6 V, VBR >= 5 V | ESD122 Table 6.6 p.5 | LVDS TX pins only; not for CC (VCONN up to 5.5 V), SBU or the CAN pins; TI states it is intended for USB Type-C TX/RX lines (p.1) |
| Nexperia PUSB3FR4 (DFN2510A-10) | 4, "rail-to-rail" with snap-back | 0.29 pF typ, 0.34 max (VI 1.5 V) | VI -0.5 to 3.3 V (limiting values) | PUSB3FR4 Tables 4 and 5, p.3 | LVDS TX pins only; not for CC, SBU or CAN |
| Nexperia PESD5V0X4UF, ST ECMF, ST USBLC6-4 | not checked | not checked | not checked | datasheets not obtained (Nexperia URL gave an HTML stub; st.com unreachable) | UNRESOLVED |

PROPOSED allocation: two TPD6E05U06 placed within a few mm of the connector; one for TX1, TX2, RX1 pair lines (and spare), one for RX2, SBU, CC1, CC2, or any split that keeps stubs short. 0.5 pF per line is insignificant for 50 Mb/s LVDS and 125 kbit/s CAN, so capacitance is not the selection criterion here; the voltage rating is. Unidirectional devices clamp at about -0.7 V: with up to 0.4 V of cable GND drop (section 3.4) and CAN levels referenced to the far-end ground, check CAN common-mode excursions against this clamp (UNRESOLVED). VBUS surge protection is U5 (24 V abs max) with C34 (existing, `usb-standalone-power.md`), not a TVS here.

## 5. Breakout board concept (PROPOSED)

### 5.1 Wiring per receptacle

| Receptacle pins | Connect to |
|---|---|
| A1, A12, B1, B12 (GND), shell | board GND (shell via the same rule as the module) |
| A4, A9, B4, B9 (VBUS) | 5 V through a per-port current-limited load switch, gated by Rd detection (section 5.2) |
| A5 (CC1), B5 (CC2) | Rp 56 kohm to 5 V on each pin |
| B11/B10 (RX1) | 100 ohm termination across the pair and then the ULX3S LVDS input (one pair per module); AC or DC coupling to be decided with `ulx3s-lvds-input.md` |
| A11/A10 (RX2) | 100 ohm termination across the pair (not used, or may be bussed to the same FPGA input if a mux is wanted) |
| A2/A3 (TX1), B2/B3 (TX2) | breakout CAN_H (p pins A2, B2) and CAN_L (n pins A3, B3) bused to the shared CAN bus through a per-port stub/ESD |
| A8, B8 (SBU1, SBU2) | tied together, to the AUX net |
| A6/B6, A7/B7 (D+/D-) | not used (no data) or to a test header |

### 5.2 Rp and the source behaviour

VERIFIED (TC Table 4-27 p.245): Rp to a 4.75 to 5.5 V pull-up is 56 kohm +/-20 % for Default USB Power, 22 kohm +/-5 % for 1.5 A at 5 V, 10 kohm +/-5 % for 3.0 A at 5 V (36/12/4.7 kohm for a 3.3 V pull-up). Default means 500 mA (USB 2.0) or 900 mA (USB 3.2 single lane) (TC Table 4-20 p.227). PROPOSED: use 56 kohm to 5 V because the module needs 0.3 A, and the lowest Rp current leaves the most margin against ground-drop offset on the CC voltage: with 56 kohm and the module's 5.1 kohm Rd the CC pin sits at 5 V x 5.1/(56+5.1) = 0.42 V nominal, 0.27 to 0.66 V over tolerance, which sits inside the source's Rd detect window of 0.272 to 1.32 V (TC Table 4-38 p.256) and above vRd-connected 0.249 V (TC Table 4-35 p.254); a cable ground drop of about 0.4 V (section 3.4) would add to the voltage seen by the source, leaving it below the 1.32 V disconnect threshold; the 22 kohm and 10 kohm options leave less margin (arithmetic, PROPOSED). The module's Ra-side CC pin (the plug's VCONN) shows Rp against Ra: 5 V x 1 kohm/(56+1 kohm) = 0.09 V, below vCCRes-Ra-USB max 0.143 V (TC Table 4-38 p.256), so the breakout will classify it as Ra (arithmetic, PROPOSED).

The module needs Rd 5.1 kohm on both CC pins, which it already has (R200/R201, `docs/schematic/controller.md`; TC Table 4-28 p.245: +/-20 % 5.1 kohm to ground is the Rd value, +/-10 % is needed only to detect advertised current).

A Source shall keep VBUS off until a Sink is attached (VERIFIED, TC 4.4.2 p.152: "The Source's USB Type-C receptacle VBUS pin shall remain unpowered ... until a Sink is attached"). PROPOSED: the breakout port should switch VBUS on only when Rd is detected on one CC pin (for example a comparator at the 0.27 V threshold driving a load switch with current limit), with the switch also supplying the per-port current limit (14 modules at 0.3 A are 4.2 A total; the breakout supply must be sized for that, not checked here). A breakout with Rp on both pins and VBUS permanently on is not a compliant source.

### 5.3 What happens with the wrong partner (PROPOSED reasoning; not tested)

Laptop plugged into the breakout by mistake. A laptop port is a dual-role port (DRP) or a host. A DRP alternates between presenting Rp and Rd; when it presents Rd it sees the breakout's Rp and becomes a sink; the breakout sees Rd, turns VBUS on (section 5.2) and the laptop is powered from the breakout rail as a default-power sink (up to 0.5 to 0.9 A, TC Table 4-20 p.227), which loads the breakout rail but the per-port limit contains it. The breakout does not respond to USB PD or connect D+/D-, so the laptop will not enumerate anything. If the laptop port is a pure host or is presenting Rp, the breakout sees Rp (no Rd), keeps VBUS off, and the two sources do not connect (TC Table 4-27 note p.245 warns that two connected sources "could result in unexpected current flow"; this is why VBUS is gated). Unresolved: the laptop's SS TX pairs would meet the breakout's CAN pins on TX1/TX2 and the laptop's SBU pins would meet the AUX net; a laptop in the sink role should not transmit SS, but this was not verified.

The same hazard exists in the intended programming case (module plugged into a laptop): the module's LVDS outputs drive the laptop's SS RX pins (the module LVDS is about 350 mV differential at a 1.2 V common-mode, assumed, not read from the TLV3605 datasheet here) and the laptop's SS TX/LFPS lands on the module's CAN transceiver pins. Neither tolerance was verified: UNRESOLVED. PROPOSED mitigations: (a) the ESP32 holds the LVDS fan-out buffer in a high-impedance/disabled state until VBUS and a CC reading show a 56 kohm Rp (a laptop advertises 1.5 or 3 A, or an ordinary DRP host); (b) AC-couple the module LVDS TX pins with 100 nF series capacitors (8b/10b is DC-balanced, so the link tolerates them), which also mirrors the USB convention that AC-coupling capacitors sit at the transmitter; the FPGA input then needs DC bias, to be settled in `ulx3s-lvds-input.md`; (c) the SBU AUX driver is held high-Z (the pull-down at least 950 kohm, TC Table 4-31 p.246) until the same detection passes.

USB-PD charger plugged into a module. The module has no USB PD stack and presents Rd 5.1 kohm, so it appears as an ordinary legacy sink. The charger sees Rd, supplies vSafe5V (VBUS, 5 V) at its advertised Rp current (1.5 or 3 A is far above the module's 0.3 A) and sends PD Source_Capabilities messages that the module does not answer; the module stays at 5 V and never receives a higher contract. This is the expected behaviour of a sink with no PD (TC 4.5, Table 4-10/4-11 p.162; the PD specification, which defines the no-response fallback, was not obtained here): PROPOSED and not tested; a hard-reset cycle that briefly removes VBUS (some chargers do this on no response) must be checked with a real charger in G1: UNRESOLVED. If the cable is e-marked (all full-featured cables are), the charger will also apply VCONN (3.0 to 5.5 V, TC p.155) to the module's unused CC pin through the 5.1 kohm Rd, about 1 mA; the module's CC network and TVS must tolerate 5.5 V (the TPDxE05U06 with VRWM 5.5 V does, section 4.4). Even if a charger had D+/D- charge-detection shorting, it would only short the ESP32 pair, which USBLC6-2SC6 and the 22 ohm series resistors tolerate (PROPOSED; not verified).

## 6. Not verified in this pass (all UNRESOLVED)

- USB Power Delivery specification behaviour (no-response fallback) and the Try.SRC/DRP details of real laptops (TC only).
- Amphenol 12401610E4#2A, Molex 2171790001, Wuerth 632723300112, Nexperia PESD5V0X4UF and ST ESD parts: no datasheet obtained.
- KiCad footprint geometry of USB4115 versus the GCT drawing; no footprint exists for the Wuerth part.
- CAN topology limits, CAN/LVDS crosstalk, laptop-side damage thresholds, module 5 V minimum vs cable drop.
- Whether the Tripp Lite U420-010 or the Newnex 3 m screw-lock cables are passive; the whole market check is from web search snippets and reseller pages (2026-10-09), not from vendor datasheets.
