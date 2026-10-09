# One USB-C receptacle: 5 V input protection, source detection, breakout power budget

Date 2026-10-09. Scope: Daniel wants the 12-pin system cable and the 16-pin USB-C port replaced by ONE 24-pin full-featured USB-C receptacle (passive C-to-C cable; VBUS/GND 5 V, D+/D- to the ESP32, TX1+TX2 = module LVDS out, RX1+RX2 = CAN, SBU = AUX; 5 V comes from a lab breakout board, one Type-C source port per module, up to 14 modules, or from a laptop). Research and proposal only. Nothing in the generators, sheets, spec, decision log or firmware docs was edited. Nothing here was simulated or measured.

Labels: VERIFIED (checked against a cited document, revision and page), PROPOSED (design intent or arithmetic on cited numbers), UNRESOLVED (open). Page numbers are PDF pages, which equal the printed page numbers for every document cited here.

Documents (downloads in `docs/research/downloads/usbc-power/`, see MANIFEST.md there; all untrusted data, text-extracted in the scratchpad):
- "TC2.0": USB Type-C Cable and Connector Specification Release 2.0, August 2019 (usb.org). "TC2.5": Release 2.5, March 2026, already in `docs/research/downloads/usbc-connector/spec-extract/`, used only for cross-checks.
- "TPS2596": TI SLVSET8A (Aug 2019). "TPS2595": SLVSE57C (Apr 2018). "TPS25940": SLVSCF3A (Mar 2015). "TPS25947": SLVSFC9C (May 2026). "TPS2553": SLVS841F (Aug 2016). "TPS25810": SLVSCR1C (Jul 2017).
- "TPS2121": SLVSEA3F (Aug 2020, `docs/datasheets/tps2121.pdf`). "C6 DS": ESP32-C6 series datasheet v1.5. "TRM": ESP32-C6 TRM v1.2. "TPS799": SBVS056L (7.0 V abs max on IN, p.4, as quoted in `usb-standalone-power.md`; not re-read). "USP": `docs/research/usb-standalone-power.md`.

## Summary for decision 14

1. **Input protection (item 1): replace the TPS2121 mux with a single-channel TI TPS259631DDAR eFuse (U5 keeps its reference).** Fixed-input mux is no longer needed; what remains needed is overvoltage cut-off below the 7 V abs max of the 3V3 LDO, soft start, a real current limit, and an input undervoltage lockout. TPS259631 gives all four in an 8-pin SOIC-EP: adjustable OVLO (cuts off, 1.3 us typ), adjustable UVLO with hysteresis, current limit 0.125 to 2 A programmed by one resistor, dV/dt soft start, 21 V abs max on IN (TPS2596 p.1, p.5). Values: R35 357 k (IN to EN/UVLO), R36 43.2 k (EN/UVLO to OVLO), R37 100 k (OVLO to GND), all 1 %: OV cut-off 5.76 to 6.20 V rising, UV 4.06 to 4.32 V rising and 3.72 to 4.00 V falling (calculated with datasheet VOVLO/VUVLO tolerances and 1 % resistors). R38 1.21 k from ILM to GND: ILIM 0.68 / 0.76 / 0.84 A (min/typ/max, TPS2596 Eq. 5 and the stated -10.4/+10.4 % accuracy). C32 47 nF on dVdt: about 0.94 V/ms, 5.3 ms ramp, about 23 mA inrush into 25 uF. C33 4.7 uF 25 V X5R on VBUS. It needs one new lab-library symbol plus a footprint (a bundled KiCad footprint exists but its land pattern must be checked, section 1.4). Fallback if Daniel wants zero new library parts for Rev A: keep TPS2121 with IN2/OV2/PR1/CP2/ST tied to GND (section 1.2); it works on paper but its current limit is at least about 1 A, it has no UVLO adjustment and 10 of its 12 pins are wasted. A TVS plus polyfuse alone does not protect the 7 V part (section 1.3).
2. **Nets that disappear:** `+5V_CABLE` (Connector output, Power input), `PWR_SRC` (Power to Controller), the whole J50 power-pin pair, R39-R42 and C34, the PR1 divider and the `#FLG04` flag on `+5V_CABLE` (it returns to `VBUS`). Power sheet pins become: in `VBUS`, DAC_HV, HV_DIS; out 3V3, 3V3_D, APD_BIAS, HV_MON. VBUS_SENSE (IO4) is no longer needed: VBUS present is implied by the MCU running.
3. **Source detection (item 2): do not use the Rp class to decide anything; use CAN.** Recommended: read both CC pins on ESP32-C6 ADC1 channels 4 and 5 (IO4 and IO5, the pins freed by VBUS_SENSE and PWR_SRC; every other ADC1 pin IO0 to IO6 is already used). Each CC pin gets a 47 k series resistor and 100 nF to GND at the ADC; the 5.1 k Rd (use 1 %, Table 4-25 needs +/-10 % to detect advertisements) stays untouched on the receptacle side. Gives plug orientation and the advertised Rp class with spec thresholds 0.66 V and 1.23 V (TC2.0 Table 4-36 p.241). Breakout advertises 1.5 A (22 k class), not 3.0 A: the TPS25810 port controller gives a 1.7 A current limit with 1.5 A advertisement but 3.4 A with 3 A advertisement, and 3.4 A per port would not protect a shared brick (TPS25810 Table 3 p.14). The Rp class is a hint only (logged and shown in telemetry). The definitive indicators are firmware-side and already designed: LINK_ALL from the FPGA master on CAN means "system", USB_SERIAL_JTAG SOF interrupt means "laptop host present" (TRM section 32.5 p.1035). SBU presence signalling is rejected (SBU is AUX, and a port's SBU must be open or at least 950 kohm, TC2.0 p.139 and Table 4-28 p.236).
4. **Breakout (item 3):** 5 V/6 A brick (3.4 A for 14 modules at 0.24 A worst case, plus one port in a 1.7 A fault, 4.8 A), one TPS25810 per port (Type-C DFP attach detect, VBUS only after Rd is seen, VCONN for the e-marked cable, 1.7 A limit, FAULT and POL outputs, 3 x 4 mm WQFN-20), advertisement 1.5 A. Cable IR drop is bounded by the spec at 0.5 V VBUS plus 0.25 V GND at the cable's rated current (3 A), so at 0.3 A the cable costs at most 75 mV loop (arithmetic). The module UVLO (rising 4.06 to 4.32 V) leaves more than 0.3 V margin against a 4.75 V source.
5. **Two findings that change the cable assumption:** (a) the spec's informative cable table lists full-featured (SuperSpeed) C-to-C cables only up to 2 m (USB 3.2 Gen1) and 1 m (Gen2); the 4 m entry is USB 2.0 only, without SuperSpeed wires (TC2.0 Table 3-1 p.37; TC2.5 p.44). A "3 m full-featured passive cable" is outside the table: the LVDS and CAN signals on the SS pairs over 3 m are UNRESOLVED and need a measurement. (b) all full-featured cables are electronically marked (same table), so the breakout should supply VCONN (TPS25810 does).
6. **Firmware (item 4):** PWR_SRC and VBUS_SENSE are replaced by `cc_class`, `cc_orient`, `usb_host` (SOF seen) and the existing LINK_ALL listen, which now runs at every boot (section 4).

## 1. Module 5 V input protection with a single VBUS

### 1.1 What is still needed

| Need | Why | Basis |
|---|---|---|
| Overvoltage cut-off between 5.5 V and about 6.5 V | TPS79901 abs max 7.0 V on IN (TPS799 p.4 via USP); a non-compliant 9/12 V adapter or a faulty source must not reach it. A Type-C source only goes above 5 V after a USB PD request, which the module never sends, so this is protection against non-compliant or faulty supplies | TC2.0 p.141 (VBUS legacy light load up to 5.5 V maximum), p.218 (PD works over unmodified cables, which must tolerate 21 V, so a PD source may sit at up to 20 V). PROPOSED need |
| Soft start / inrush | module bulk capacitance is about 25 uF effective (USP section 1.3, estimate); Type-C limits VBUS capacitance of a sink that is not attached to 10 uF (Table 4-3 p.142) | the eFuse is off until VBUS exceeds UVLO, so the receptacle sees only the input capacitor (4.7 uF) before attach: PROPOSED |
| Current limit about 0.5 to 1 A | protects cable, breakout port and laptop port from a faulted HV stage; module budget is 0.19 A (0.24 A with margin, USP section 1.5) | PROPOSED |
| Input undervoltage lockout | stops brown-out chatter of the ESP32 and LDOs on a sagging cable; Type-C sinks treat VBUS below 3.67 V as detached (Table 4-3 p.142) | PROPOSED |
| Reverse-current blocking | not needed: only one source. Removing it is the one simplification | decision 14 premise |
| PWR_SRC / ST | not meaningful with one source | |

### 1.2 Option (a): keep the TPS2121 with IN2 unused

- VERIFIED that the mux logic selects IN1 when IN2 is invalid: Table 9-3 (TPS2121 p.18) row "IN2 <= UV, IN1 valid -> OUT = IN1, ST high, Invalid Input mode". The pin table says PR1, OV1, OV2, ST and CP2 are "connect to GND if not required" (TPS2121 p.4-5). The datasheet has no sentence on an unused IN2 itself (no "unused", "float" or "tie" text found): tying IN2 to GND is PROPOSED, justified by the leakage spec of at most 1 uA from OUT to IN for |VIN - VOUT| <= 5 V (TPS2121 p.7 as quoted in USP section 1.1).
- What it keeps: OV1 supervisor (R39 464 k / R40 100 k: trip 5.58 to 6.20 V, USP section 1.2; OV pin range 0 to 5.5 V, TPS2121 p.6), SS soft start (C32), 24 V abs max (p.6), ILM.
- What it does not give: the current limit cannot be set below RILM = 100 k, which the equation ILM = 65.2 / RILM^0.861 puts at 1.24 A typ (TPS2121 p.13; the datasheet table has no 100 k row, USP section 7 item 3), so it does not protect a 0.5 to 1 A port; UV rising 2.5 to 2.8 V and falling 2.4 to 2.7 V are fixed (p.7), so there is no brown-out protection for 3.3 V rails; ST is useless; IN2, OV2, CP2, PR1, ST are wasted pins; 300 to 400 uA quiescent (p.7).
- Edits if chosen: IN2 (pin 2), OV2 (4), CP2 (3), PR1 (6), ST (9) to GND; delete R35-R37, R41, R42, C34; keep R38, C32, C33, R39, R40. No library change.

### 1.3 Option (b): single-channel eFuse, and option (c)

| Part (datasheet) | Input / abs max | OV behaviour | Current limit | Soft start | Package | Verdict |
|---|---|---|---|---|---|---|
| **TPS259631** (TPS2596, SLVSET8A) | 2.7 to 19 V operating, 21 V abs max (p.5) | adjustable OVLO, cut-off, rising 1.17/1.20/1.22 V, falling 1.08/1.10/1.13 V, 1.3 us (p.7); FLT asserts on OVLO (Table 3 p.25) | 0.125 to 2 A, RILM 453 to 7869 ohm, RILM = 903/(ILIM - 0.0112) (Eq. 5 p.22), +/-10.4 % max (p.1) | dV/dt pin, CdVdt = 42000 / SR (Eq. 4 p.22); 2.11 uA charge (p.7) | 8-pin SOIC-EP (DDA), 4.91 x 3.9 mm | **recommended**: x1 = auto-retry after thermal shutdown (x0 = latch-off, Device Comparison p.3) |
| TPS259573 (TPS2595, SLVSE57C) | 2.7 to 18 V, 20 V abs max (p.1) | programmable OVLO, active-low EN, auto-retry (Device Comparison p.3) | 0.5 to 4 A (p.1) | dV/dt | 2 x 2 mm WSON-8 | works; the 2 x 2 mm WSON is harder to hand-build and the minimum limit is 0.5 A; second choice |
| TPS259620/21, TPS259530/31, TPS259535 | same families | fixed output clamp 3.8 / 5.7 / 13.8 V (pin or part selected): the output is held at the clamp while the input is high (TPS2596 p.20-21; Device Comparison p.3) | as above | as above | | rejected: with a sustained 12 V input the FET dissipates about (12 - 5.45) V x 0.24 A = 1.6 W in linear mode until thermal shutdown (arithmetic), and TPS2596 p.5 note 1 says the input must be limited to the clamp option |
| TPS25940A/L (SLVSCF3A) | 2.7 to 18 V, 20 V max (p.1) | adjustable +/-2 % OV and UV thresholds, reverse blocking (p.1) | 0.6 to 5.3 A | dVo/dt | 20-pin WQFN 3 x 4 mm | over-featured, limit floor 0.6 A; rejected |
| TPS25947 (SLVSFC9C) | 2.7 to 23 V, 28 V abs max (p.1) | OV clamp or adjustable OVLO, true reverse blocking | 0.5 to 6 A | dVdt | | over-featured (reverse blocking and 5.5 A are the wrong ratings for 0.24 A); rejected |
| TPS2553 (SLVS841F) | 2.5 to 6.5 V operating, 7 V abs max on IN, OUT, EN (p.5) | none | 75 mA to 1.7 A | built-in | SOT-23 / WSON | rejected: not 12 V tolerant, so it does not solve the stated problem |
| ON NCP/NIS and Diodes AP22xxx load switches | | | | | | NOT evaluated: no datasheets obtained in this session. UNRESOLVED; no claim made |
| (c) TVS clamp + polyfuse | | a 5 V-class TVS clamps at roughly 9 V at surge current (typical TVS behaviour, no TVS datasheet read here: PROPOSED) | polyfuse hold/trip depends on temperature and has a slow trip (seconds) | none | | rejected: the clamp voltage during a sustained 12 V fault is above the 7 V abs max of TPS79901 unless the polyfuse opens first, there is no soft start and no UVLO. May be added as a DNP footprint ahead of the eFuse for hot-plug spikes only (TPS2596 p.34 Figure 62 shows a TVS option) |

Recommendation: TPS259631DDAR. Reasons: the only requirement the TPS2121 meets poorly is the 0.5 to 1 A current limit and the brown-out lockout, and the eFuse has both for a smaller, cheaper, 8-pin package; the 21 V abs max also matches the 21 V DC a Type-C cable must tolerate (TC2.0 section 3.7.2.7 p.108; p.218). Cost: a new lab-library symbol and footprint PR; nothing else. The difference to option (a) is modest, so option (a) remains a legitimate Rev A shortcut if the library PR is a problem.

### 1.4 Values for TPS259631 and what changes on the Power sheet

Designators reuse the old U5 block to limit churn (all PROPOSED; none simulated):

| Ref | Value | Function and calculation |
|---|---|---|
| U5 | TPS259631DDAR | pin 1 GND, 2 dVdt, 3 EN/UVLO, 4 IN, 5 OUT, 6 FLT, 7 ILM, 8 OVLO, exposed pad GND (TPS2596 p.4) |
| R35 | 357 k 1 % | IN (VBUS) to EN/UVLO |
| R36 | 43.2 k 1 % | EN/UVLO to OVLO |
| R37 | 100 k 1 % | OVLO to GND |
| R38 | 1.21 k 1 % | ILM to GND: ILIM = 903/1210 + 0.0112 = 0.757 A typ (0.68 to 0.84 A with +/-10.4 %); ILM must never be open (open = shut down, Table 3 p.25) |
| C32 | 47 nF X7R 10 V | dVdt: SR = 2.11 uA x 20.93 V / C (IDVDT and GDVDT, p.7) = 0.94 V/ms, 5.3 ms for 5 V; inrush = Cout x SR = 25 uF x 0.94 V/ms = 23 mA (arithmetic; the cap must be rated 4 V or more, p.5) |
| C33 | 4.7 uF 25 V X5R 0805 | VBUS input capacitor (TI: more than 0.1 uF; 1 uF or more for EFT, p.34); 4.7 uF keeps the unattached VBUS capacitance under the 10 uF limit (TC2.0 Table 4-3 p.142) |
| R39 | 100 k | FLT pull-up to +5V (OUT) with a test point; FLT is open drain, asserts on OVLO and over-temperature but not on current limit (Table 3 p.25). Not routed to the ESP32: it is unpowered during a cut-off |
| TP | IMON | the ILM pin voltage is a load-current monitor, 0.656 mA/A typ across 1.21 k = about 0.79 V/A (GIMON 653 to 657 uA/A at 0.13 and 2 A, p.6-7): test point only |

Calculated thresholds (script in the scratchpad; VOVLO(R) 1.17 to 1.22 V, VUVLO(R) 1.18 to 1.22 V, falling 1.08 to 1.13 V, all from TPS2596 p.7; 1 % resistors, worst-case corners):

| Threshold | Min | Max | Requirement |
|---|---|---|---|
| OV cut-off, rising | 5.76 V | 6.20 V | above 5.5 V (legitimate VBUS, TC2.0 p.141), below 6.5 V recommended / 7.0 V abs max of TPS79901 |
| OV recovery, falling | 5.32 V | 5.74 V | hysteresis from the 1.2 / 1.1 V pin thresholds |
| UV, rising | 4.06 V | 4.32 V | below a 4.75 V Type-C source minus cable drop (4.66 V) |
| UV, falling | 3.72 V | 4.00 V | above the LDO dropout region (UNRESOLVED: TPS79901 and TPS7A2033 dropout not re-read) |
| EN/UVLO pin at 19 V / 21 V input | 5.44 V / 6.01 V | | recommended maximum 6 V, abs max 7 V (p.5) |
| Divider current at 5 V | 10 uA | | |

Footprint: KiCad bundled `Package_SO:HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm` (exposed pad matches the datasheet maximum 3.10 x 2.40 mm, TPS2596 p.45) and `Package_SO:TI_SO-PowerPAD-8` (its description names TI DDA0008B) both exist in the installed KiCad 10 library. UNRESOLVED: which one matches the DDA land pattern on TPS2596 p.46; compare the pad rows before layout. The lab library has no TPS259631 symbol and no PowerPAD SOIC footprint (its `AharoniLab_Package_SO.pretty` has only plain SOIC-8 variants), so a library PR is required.

Power-sheet edits (for the spec and generator, not done here):
- U5 block: replace TPS2121RUXR by TPS259631DDAR with the table above; delete R39 to R42 as the old OV/PR1 dividers and C34; the VBUS hierarchical input drives IN directly; U5 OUT stays the internal `+5V` rail (U1, U3 via L2, U4, C1, C2 unchanged).
- Hierarchical nets: remove `+5V_CABLE` (Connector output and Power input) and `PWR_SRC` (Power output, Controller input). `VBUS` remains a Power input, now sourced from the 24-pin receptacle. Move PWR_FLAG `#FLG04` to `VBUS`.
- Power-sheet pin list becomes in `VBUS`, DAC_HV, HV_DIS; out 3V3, 3V3_D, APD_BIAS, HV_MON.
- Do not tap VBUS ahead of the eFuse with the 0.6 divider: at a 12 V fault it would put 7.2 V on a 3.3 V pin (arithmetic); the divider is deleted anyway (section 2.4).
- Hot-plug: a compliant Type-C source keeps VBUS off until a sink is attached (TC2.0 p.141), so the cable ring-up is much smaller than with a legacy source (legacy hosts are exempt, same page). A TVS ahead of C33 is optional (DNP footprint, part UNRESOLVED).

## 2. Source detection with one connector

### 2.1 What the spec says (VERIFIED, TC2.0)

| Item | Value | Citation |
|---|---|---|
| Source Rp current advertisement | Default: 80 uA +/-20 % or 56 k +/-20 % to 4.75-5.5 V; 1.5 A: 180 uA +/-8 % or 22 k +/-5 %; 3.0 A: 330 uA +/-8 % or 10 k +/-5 % | Table 4-24, p.235 |
| Sink Rd | 5.1 k to GND; +/-20 % cannot detect power capability; +/-10 % can (max pin voltage 2.04 V) | Table 4-25, p.236 |
| Sink CC voltage detection (Rd +/-10 %) | vRa -0.25 to 0.15 V (threshold 0.2 V); vRd-Connect 0.25 to 2.04 V; vRd-USB 0.25 to 0.61 V (threshold 0.66 V); vRd-1.5 0.70 to 1.16 V (threshold 1.23 V); vRd-3.0 1.31 to 2.04 V | Table 4-36, p.241 |
| Same table in R2.5 (informative example) | vRd-USB 0.277 to 0.612; vRd-1.5 0.746 to 1.164; vRd-3.0 1.369 to 2.042; thresholds 0.613 to 0.745 and 1.165 to 1.368 V | TC2.5 section 4.11.3.2.2 Table 4-36, p.254 |
| Orientation | the sink finds the connected CC pin as the one that is in SNK.Rp state (above vRd-Connect); the other pin is open, Ra or Rd (below vRa) | Table 4-15 p.169; section 4.5.2.2.5.1 p.173 |
| VCONN is isolated from the other end of the cable | the sink's unused CC pin therefore sees only the cable plug's Ra (800 to 1200 ohm to GND) in parallel with the module's own Rd, never the source's VCONN | section 2.5 p.36; Table 4-26 p.236; VCONN pin description p.139 |
| Sink must not draw more than advertised | default 0.5 A (USB 2.0) or 0.9 A (USB 3.x); module worst case 0.24 A is under every class | sections 4.5.2.3.1.1 p.193, 4.6.2.1 p.218; USP section 1.4 |
| Rp while a USB PD explicit contract exists | follows PD 3.0 collision avoidance (1.5 A or 3.0 A toggling); the module never negotiates PD, so a source stays at its Type-C advertisement | section 4.6.2 p.222 (PD spec itself not read: UNRESOLVED) |
| Debounce | tCCDebounce 100 to 200 ms; tRpValueChange 10 to 20 ms (Sink, no BMC idle) | Table 4-31 p.239-240 |

Nominal CC voltages for Rd = 5.1 k (arithmetic): Rp 56 k to 5 V: 0.42 V; 22 k: 0.94 V; 10 k: 1.69 V; current sources 80 / 180 / 330 uA: 0.41 / 0.92 / 1.68 V. Worst case Rp 10 k +5 %, supply 5.5 V, Rd +10 % gives 2.04 V (matches the table). The ESP32 side is therefore never above about 2.04 V on a compliant source.

### 2.2 Decision logic: what the Rp class can and cannot tell the module

- The class is a current-capability advertisement, not an identity. A laptop port can advertise Default, 1.5 A or 3.0 A (TC2.0 p.235; which classes are common in the field is not verified here: PROPOSED that PD laptops commonly show 3.0 A). The 3.0 A signature suggested for the breakout is therefore weak, and it is also unattractive on the breakout because a 3.0 A advertisement means a 3.4 A port limit (TPS25810 Table 3 p.14) and a source "shall supply VBUS current at the level it advertises" (TC2.0 p.177) on a shared 5 V rail. A 1.5 A advertisement has a 1.7 A limit and is, in PROPOSED field experience, less common than 3.0 A on laptops. Neither is proof.
- The definitive identity signals are protocol-level: (i) the FPGA master transmits LINK_ALL (0x1F0, 20 Hz) on CAN; this is already in the firmware plan (`firmware/esp32/README.md` step 7, `docs/firmware/can-and-console-protocol.md` section 1.3); (ii) a laptop host produces SOF frames on D+/D-: USB_SERIAL_JTAG_SOF_INT is "triggered when SOF frame is received" (TRM section 32.5 p.1035), USB_BUS_RESET_INT likewise.
- Robust mapping (PROPOSED):

| LINK_ALL heard | SOF/bus reset seen | CC class | Meaning | Firmware mode |
|---|---|---|---|---|
| yes | no | any | FPGA system | `bus` |
| yes | yes | any | system plus a laptop on the console (breakout routes D+/D-) | `bus` (host console allowed) |
| no | yes | any | laptop only | `usb` (standalone, stepped HV start from USP section 4) |
| no | no | 1.5 A | breakout port, FPGA not talking yet | `usb` until LINK_ALL arrives, then `bus` (already specified: hearing LINK_ALL later switches to bus mode) |
| no | no | no Rp seen | bare 5 V source (non-Type-C) | `usb`, log a warning |

Rp class and orientation never gate HV. HV start still needs HV_DIS low from the verified-DAC sequence and a console or CAN command; unchanged.

### 2.3 SBU-based presence: not recommended

- SBU is wanted for AUX. The spec requires a port's SBU pins to be open or have a weak pull-down no stronger than zSBUTermination >= 950 kohm (TC2.0 section 4.3 p.139, Table 4-28 p.236), so a laptop leaves SBU open or very weakly pulled. A module pull-up test (for example 100 k to 3.3 V) would read high on a laptop and low only if the breakout pulled SBU down hard. It would work as a signature but it burns the AUX line and breaks the "open or >= 950 kohm" convention. Also, SBU1/SBU2 are cross-connected in the cable (same page), so which receptacle pin carries a given AUX line depends on the orientation of both plugs; a single logical AUX line needs the CC orientation at both ends, or tying SBU1 and SBU2 together at each end (one AUX line only). UNRESOLVED for the connector decision; the CC orientation reading proposed here is a prerequisite either way.
- DisplayPort alt mode would also use SBU as AUX, but it requires USB PD discovery, which the module does not implement (TC2.0 Appendix E, not read): not a risk if the module never replies, but unverified.

### 2.4 Pins and resistor networks

ESP32-C6 ADC1 is GPIO0 to GPIO6 = ADC1_CH0 to CH6, 12-bit, seven channels (C6 DS pin table p.23 and section 4.2.2.1 p.57; MINI-1 datasheet pin table, IO0 to IO6). All seven are in use today: IO0 HV_DIS, IO1 SHDN_N, IO2 SDA, IO3 SCL, IO6 LDAC, IO4 VBUS_SENSE, IO5 PWR_SRC (`docs/schematic/controller.md`). Only IO4 and IO5 are free for ADC once VBUS_SENSE and PWR_SRC go away. IO15 has no ADC; IO14, IO16, IO17, IO8 are not ADC pins.

| Net | Pin | Network | Notes |
|---|---|---|---|
| CC1_SENSE | IO4 (pad 9, ADC1_CH4) | CC1 to a 47 k series resistor to IO4; 100 nF from IO4 to GND at the pin | R215 reused (value 47 k), C205 reused (100 nF) |
| CC2_SENSE | IO5 (pad 10, ADC1_CH5) | CC2 to a 47 k series resistor to IO5; 100 nF from IO5 to GND | R216 reused (value 47 k), new 100 nF |
| Rd | | R200/R201 5.1 k stay on CC1/CC2 to GND at the receptacle, upgraded to 1 % | Table 4-25: +/-10 % needed to detect the advertisement |

Reasons and checks:
- The 47 k series resistor keeps the ADC tap from loading CC: CC sees a 47 k resistive tap at BMC frequencies instead of 100 nF (5 ohm at 300 kHz). The Type-C spec asks the receptacle to keep CC capacitance within cReceiver, which is defined in the USB PD specification (TC2.0 p.173 "to meet cReceiver as defined in USB PD"; the number itself, recalled as 200 to 600 pF, was NOT verified: UNRESOLVED), so no capacitor is placed directly on CC. Filter time constant 47 k x 100 nF = 4.7 ms, which averages PD BMC bursts; the DC error from 50 nA pin leakage (C6 DS Table 5-4 p.65, IIH/IIL max 50 nA) times 47 k is 2.4 mV.
- The C6 ADC datasheet figures were measured with a 100 nF capacitor on the ADC pin (C6 DS section 5.5 p.65), which is why the cap sits on the pin.
- Use ADC attenuation ATTEN2 (range 0 to 1.9 V, total error +/-23 mV after calibration, C6 DS Table 5-6 p.66). Compare to the thresholds: the nominal voltages 0.42 / 0.94 / 1.69 V are 0.24, 0.29 and 0.46 V from the two spec thresholds, and the 0.66 V threshold is 40 to 50 mV from the class range edges (0.61 and 0.70 V), so +/-23 mV is enough but thin; require three consecutive classifications over more than tRpValueChange before changing state. Readings at the ADC full scale mean "3.0 A class or above".
- Robustness against a bad source: the C6 datasheet gives no separate GPIO absolute maximum; the input high level maximum is VDD + 0.3 V (Table 5-4 p.65) and the input power pins are limited to 3.6 V (Table 5-1 p.64). A compliant source cannot exceed 2.04 V on CC. A non-compliant source or a damaged cable that puts 5 V on CC would drive the pin through 47 k: about (5 - 3.6) V / 47 k = 30 uA into the pin clamp (arithmetic). The C6 datasheet does not give a clamp-injection current rating: UNRESOLVED, so the series resistor is the only protection and the value should not be lowered. An additional DNP TVS on CC is not proposed.
- Strapping: IO4 and IO5 are MTMS and MTDI strapping pins that select SDIO sampling edges only (MINI-1 datasheet Table 4-4 p.14, per `controller.md`); the CC level at reset (0 to 1.7 V on a compliant source) can be an undefined logic level for a few ms because of the 4.7 ms filter and VIL/VIH of 0.25 / 0.75 VDD (C6 DS Table 5-4). SDIO is unused: PROPOSED harmless, not tested.
- Single-pin fallback: summing the two taps through two 100 k resistors gives half the connected CC voltage and no orientation; only needed if one ADC pin had to be given up. Not recommended.
- VBUS_SENSE: with one connector, "VBUS present" is implied by the MCU running (the eFuse feeds the MCU rail), so R215/R216/C205's old role disappears. If a supply monitor is wanted, tap the +5V node after the eFuse (never VBUS ahead of it) on ADS1115 AIN3 through a 0.6 divider: but `firmware/esp32/README.md` step 6 uses AIN3 as the ADC zero check, so it would lose that. Recommended: no monitor in Rev A; the eFuse ILM test point and the ADS1115 are enough.
- Laptop SuperSpeed lanes: a USB 3 host will try SuperSpeed receiver detection on the lanes the module uses for LVDS (module TX) and CAN (module RX). The module has no SuperSpeed endpoint; the host should fall back to USB 2.0 (D+/D-), but this was not checked and the CAN transceiver and LVDS driver voltages on a laptop's SS pins were not analysed: UNRESOLVED (put on the connector sheet review).

## 3. Breakout-side power budget and protection

| Item | Value | Basis |
|---|---|---|
| Per-module worst case | 0.24 A at 5 V (0.19 A plus 25 % margin) | USP section 1.5 (estimate, not measured) |
| 14 modules | 3.36 A | arithmetic |
| One port in a fault plus 13 normal | 1.7 + 13 x 0.24 = 4.8 A | TPS25810 short-circuit limit 1.58 / 1.7 / 1.82 A min/typ/max for the 1.7 A setting (Electrical Characteristics p.5; Table 3 p.14) |
| Supply | 5 V brick rated at least 6 A (add the ULX3S if it shares the supply; its current was not looked up) | PROPOSED. A 5 V barrel brick is simpler than a USB PD trigger: PD at 5 V gives no extra power, and 9/12 V PD would need an on-board 5 V buck of 6 A. UNRESOLVED: choose brick part |
| Per-port protection | one TI TPS25810 per port | VERIFIED features (TPS25810 p.1): Type-C DFP controller, attach and detach detection, VBUS applied only to an attached UFP, VBUS discharge, VCONN to an e-marked cable, 34 mohm (37 mohm max at 25 C) switch, 1.7 A or 3.4 A limit, FAULT output, POL output = which CC pin is connected, 0.7 uA unattached, 20-pin WQFN 3 x 4 mm, Active (orderable table) |
| Rp per port | 1.5 A: CHG = 1, CHG_HI = 0 gives 1.5 A advertisement with a 1.7 A limit (Table 3 p.14); CHG = 0 gives Default advertisement with 1.7 A. 3 A advertisement forces 3.4 A | Table 3 p.14. PROPOSED: 1.5 A |
| Why not a polyfuse and a plain Rp | a compliant source must keep VBUS off until a sink's Rd is seen (TC2.0 p.141) and must supply what it advertises (p.177); a bare Rp with an always-on VBUS is only allowed for legacy hosts (p.141); also no VCONN for the e-marked cable | PROPOSED choice; a polyfuse could still be added on the 5 V input of each port |
| Cable VBUS drop | the cable IR drop shall be at most 500 mV on VBUS and 250 mV on GND at the cable's maximum rated current, contacts included (TC2.0 section 4.4.1 p.140). For a 3 A cable that is 167 mohm + 83 mohm; at 0.3 A: 50 mV + 25 mV = 75 mV worst case | arithmetic on the spec limit; a real cable is likely better; 3 m full-featured cable length not covered by the spec table (Table 3-1 p.37) |
| Breakout drop | TPS25810 37 mohm max x 0.3 A = 11 mV; board distribution drop for 3.4 A should be limited to 50 mV (copper design) | PROPOSED |
| Source voltage | Type-C charger-class sources: 4.75 to 5.5 V no load, at least 4.0 V at 3 A (TC2.0 p.226); legacy up to 5.5 V (p.141) | Verified for chargers; for this breakout the TPS25810 IN1 range 4.5 to 6.5 V (p.1 schematic) |
| Module input at the receptacle | at least 4.75 - 0.075 - 0.011 = 4.66 V (arithmetic) | vs module UVLO rising 4.06 to 4.32 V: margin at least 0.34 V; and falling 3.72 to 4.00 V |
| Cable length and signal integrity | USB 3.2 Gen1 full-featured cable up to 2 m, Gen2 1 m, 4 m only for USB 2.0 cables without SS wires | TC2.0 Table 3-1 p.37; TC2.5 p.44 (informative). The requested 3 m full-featured passive cable is UNRESOLVED for the 50 Mbit/s LVDS and the 125 kbit/s CAN on the SS pairs; measure it |

## 4. Firmware implications (edit list, nothing edited here)

`firmware/esp32/README.md`:
- Pin table row "VBUS_SENSE / PWR_SRC": replace by "CC1_SENSE / CC2_SENSE: IO4 / IO5 (ADC1_CH4 / CH5), 47 k + 100 nF each, ATTEN2" and delete the (VBUS_SENSE, PWR_SRC) four-state sentence; keep "never a basis to clear HV_DIS by themselves", now for the CC class and orientation.
- Boot step 7 "Read the power source ... Unless USB-only, listen 1.5 s": drop "unless USB-only"; always listen 1.5 s (preferably a bit longer, because the breakout must first apply VBUS and the FPGA host may boot later) for LINK_ALL; add SOF detection (USB_SERIAL_JTAG_SOF_INT, TRM p.1035) and the CC read with three consecutive classifications; define modes by the table in section 2.2.
- Step 6 stays unchanged (AIN3 zero check) because no VBUS monitor is added.
- Add a note that the TPS259631 current limit (about 0.76 A) can reset the module on an overload: boot log should record a brown-out or power-on reason; the eFuse restarts automatically (x1 auto-retry).
- Remove all PWR_SRC and VBUS_SENSE mentions; the old `(0,0) cannot occur` reasoning is gone.

`docs/firmware/can-and-console-protocol.md`:
- Telemetry/console row (line ~173): `pwr` (values `cable`, `usb`, `both`) is replaced by `src` with values `system` (LINK_ALL heard), `host` (SOF seen, no LINK_ALL) or `unknown`, plus new keys `cc_class` (`default`, `1.5A`, `3.0A`, `none`) and `cc_orient` (`cc1`, `cc2`, `none`). `mode` stays `usb` or `bus`.
- TLM_STATE or TLM_SLOW: if a field is wanted on CAN, reserve 4 bits (class 2 bits, orientation 2 bits) in TLM_SLOW; the byte layout is the other agent's file.
- Cable-to-node association (section 1.3, AUX line, cable pin 12 / IO7): the J50 pin numbers go away. With SBU1/SBU2 cross-connected in the cable (TC2.0 p.139), AUX and AUX2 over SBU need the CC orientation reported by the module (`cc_orient`) so the master can interpret which module pin it is driving. Edit pending the connector decision.
- Console `get`/`status` examples (line ~159: `"mode":"usb","pwr":"usb"`): update key names.

Other repo documents that name the removed nets (listed, not edited): `docs/architecture.md` lines 11 and 18, `docs/schematic/rev-a-sheet-specs.md` revision 3 sections 1.1, 6, 7, `docs/schematic/power.md`, `controller.md`, `connector.md`, `docs/bringup/gates.md` G1 items on "U5 both-sources behaviour" and "VBUS_SENSE and PWR_SRC levels", and `docs/decision-log.md` entry 13 (superseded by decision 14).

Gate additions (PROPOSED): measure the TPS259631 OV cut-off and UV thresholds and the inrush with C32 47 nF (G1); measure the CC voltages with a real breakout port and with two or three laptops/hubs, with the 3 m cable (G1); scope the LVDS and CAN over the 3 m full-featured cable (G1).

## 5. UNRESOLVED and unverified

1. TPS259631 SOIC-EP land pattern versus KiCad bundled footprint (section 1.4); no lab-library symbol or footprint yet.
2. TPS79901 and TPS7A2033 dropout versus the UVLO falling range 3.72 to 4.00 V; not re-read.
3. Exact USB 2.0 and USB 3.2 VBUS limits at the device (4.40 or 4.45 V minimum, 5.25 V maximum) and the 100 mA unconfigured rule: the USB 2.0 and 3.2 specifications were not obtained; only the Type-C limits (4.75 to 5.5 V no load for chargers, 5.5 V legacy maximum) were verified.
4. cReceiver (CC capacitance limit) is defined in the USB PD specification, not obtained; the 200 to 600 pF figure is recalled only.
5. ON NCP/NIS and Diodes AP22xxx load switches were not evaluated (no datasheets obtained). TVS part for an optional hot-plug clamp not chosen.
6. ESP32-C6 clamp-injection current for a 5 V fault on a CC tap is not specified in the datasheet; no separate GPIO absolute maximum is listed (C6 DS Table 5-1 p.64).
7. Whether PD-capable laptops advertise 3.0 A, 1.5 A or Default at a given moment, and how often: not verified; the plan does not depend on it.
8. Behaviour of a laptop's USB 3 SuperSpeed receiver detection against the module's LVDS driver and CAN transceiver on the SS lanes; SBU cross-connection handling; and 3 m full-featured cable performance (Table 3-1 lists 2 m maximum for USB 3.2 Gen1 full-featured cables).
9. TPS2121 unused-IN2 handling is not stated in the datasheet; only the truth table and the "connect to GND if not required" pin notes (option (a)).
10. The 25 uF effective output capacitance behind the eFuse, the 0.24 A budget and every start-up time are estimates; nothing here was measured.
11. Breakout-board design (brick part, board copper, POL use, VCONN supply routing) is not done.
