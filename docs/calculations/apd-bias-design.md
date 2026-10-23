# APD bias supply, Rev A design (LT8365 boost + charge-pump doubler, 5 V in, 100-220 V out)

Date 2026-10-08. Companion to `docs/research/apd-bias-supply.md` and `apd-selection.md`. Numbers come from `tools/apd_bias_design.py` (output pasted in section 5).
Labels: **DS** = DATASHEET (page = PDF page; LT8365 Rev. A page numbers equal printed numbers), **DER** = DERIVED here, **ASM** = ASSUMED (no document), **GR** = read by eye from a plot.
Image-only items: LT8365 curves (pp.5-6, GR), the typical-application drawings (pp.20-27, 30) and the DC2838A schematic. For the schematic and p.30 the text layer only gives labels,
so I rendered the pages and traced connectivity by eye; stage structure is therefore DER-by-inspection, not a statement in the manual.

## 0. Result in brief

- Topology: LT8365 boost to V1 = (Vout+Vd)/2 (70 V at 140 V, 110 V at 220 V), one diode-capacitor doubler to Vout = 2*V1 - Vd. Loop closed on the final node through FBX. f_sw = 500 kHz (RT 84.5 k), L = 10 uH, pulse-skipping/DCM.
- Boost at 5 V cannot do 220 V alone (150 V switch, p.2), so the doubler is required for the top of the range; it also means a short on Vout never creates a DC path VIN-L-D1-short (p.13-14: boost is not short-circuit protected).
- Duty/current (DER): CCM duty 0.933 at 140 V and 0.957 at 220 V (4.75 V in), but the part runs in deep DCM at <= 1 mA: duty 0.30, Ipk 0.283 A (140 V, 1 mA), worst 0.355 A (220 V, 1 mA) vs ILIM min 1.5 A.
- Filter: 27 k/10 nF + 10 k/10 nF, C2 at the cathode: -108 dB at 500 kHz, -142 dB at 6.63 MHz (with parasitics), -81 dB at 100 kHz. Cathode noise ~1.4 uV rms (ASM 1 Vpp source) vs 10 uV target.
- Hard-short steady current into the TIA: 5.95 mA at 220 V, 6.35 mA at 235 V through R1+R2 (OPA857 abs max 10 mA, PDF p.5); with the clamp upstream it is ~0.17 mA. **Open risk: C2 capacitor dump (section 4).**
- Stored energy at 220 V: 2.3 mJ total (0.48 mJ in the filter caps).

## 1. LT8365 key parameters (Rev. A)

| Item | Value | Page |
|---|---|---|
| VIN range / abs max | 2.8-60 V operating; VIN, EN/UVLO, BIAS abs max 60 V; SYNC 6 V; FBX +/-4 V; VC 4 V | 1, 2, 3 |
| Switch | SW abs max 150 V; RDS(on) 700 mohm (0.5 A); leakage 0.1 typ/1 uA max at 150 V | 2, 3 |
| Current limit | 1.5 / 2 / 2.7 A (min/typ/max); overcurrent fault 3 A (1.5x max limit) discharges SS | 3, 9, 12 |
| FBX (positive out) | 1.568 / 1.600 / 1.636 V over temp; negative 0.80 V; pin current -10..+10 nA; line reg 0.005 %/V typ | 3 |
| FBX vs T | ~1.597 V (-50 C) to ~1.602 V (125 C), about +26 uV/C (GR) | 5 |
| f_sw | 100-500 kHz only (RT=432k/143k/84.5k: 100/300/500 kHz, 92-113 / 279-321 / 465-535 kHz); sync 100-500 kHz | 1, 3, 11 |
| RT | RT[kohm] = 45.2 / f_osc[kHz]^1.009; Table 1: 400 kHz 107 k, 450 kHz 95.3 k, 500 kHz 84.5 k (formula gives 85.5 k, 1.2 % off) | 11 |
| On/off time | min on 110 typ / 200 ns max (VIN=24 V test, Note 6; value at 5 V not given); min off 100 / 115 ns max | 3, 4 |
| Duty limits | Dmin = ton(max)*f_max, Dmax = 1 - toff(max)*f_max; CCM boost D = 1 - VIN/(VOUT+VD); DCM allowed when CCM limits are violated | 12 |
| Burst / ripple | Burst IQ 9 uA; "typical output ripple below 15 mV"; burst current limit ~325 mA; output C up -> ripple down proportionally; Burst at SYNC<0.14 V; pulse-skip (SYNC floating) costs "hundreds of uA"; external clock forces pulse-skip | 1, 9, 10, 11 |
| SSFM | +20 % triangle (500 -> 600 kHz), rate f_osc/256; SYNC 100 k to GND = Burst+SSFM, >1.7 V = skip+SSFM | 11 |
| SS | 2 uA charge, 220 ohm discharge; all datasheet examples use 0.22 uF | 4, 7 |
| EN/UVLO | rising 1.576 / 1.68 / 1.90 V, falling 1.545 / 1.60 / 1.645 V, 80 mV hysteresis; pin current +/-50 nA; <0.2 V gives VIN current <1 uA | 4, 7, 10 |
| INTVCC | internal LDO, 1 uF min ceramic, no external load; rising 2.65 V, falling 2.5 V. Level is "3.8 V" on p.7 and "3.2 V" on p.11 (datasheet inconsistency) | 7, 11 |
| BIAS | 4.4 V <= BIAS <= VIN supplies INTVCC (rising 4.4/4.65 V); tie to GND if unused | 3, 7 |
| Quiescent | shutdown 1 uA; sleep 9 uA (15 max); active not switching 1200 uA (BIAS=0 V) or 22 uA (BIAS=5 V) | 3 |
| Package | MSE16(12), 16-lead MSOP with 4 pins removed, theta-JA 45, theta-JC 10 C/W; exposed pad (17) is PGND and GND, must be soldered to PCB | 2, 7, 13 |
| Pinout | 1 EN/UVLO, 3 VIN, 5 INTVCC, 6 NC, 7 BIAS, 8 VC, 9 FBX, 10 RT, 11 SS, 12 SYNC/MODE, 14 SW2, 16 SW1, 17 PGND/GND pad (pins 2, 4, 13, 15 removed) | 2 |
| Inductor | choose dI_SW ~0.6 A; L = VIN(min)/(dI*f)*Dmax; saturate above 2.7 A; lower L allowed in DCM; do not exceed 1.5 A in steady state | 14 |
| Diode | Schottky, low leakage, VR above need; DFLS1150 1 A / 150 V / 2 uA leakage, RB068L150TE25 2 A / 150 V / 3 uA, DFLS2100 | 16 |
| Capacitors | input 4.7-10 uF X5R/X7R (ring to 2x VIN on hot plug, AN88); output X5R/X7R, 1-2.2 uF for very low current, "for high-voltage DCM smaller values may be sufficient"; ceramics are piezoelectric in Burst (audio noise) | 15, 16 |
| Layout | GND pad solder to plane; SW trace area minimal; power ground components at pad near EN/SW, signal ground (RT, SS, FBX, VC) at pad near FBX | 7, 16 |
| Thermal lockout | 170 C, resume 5 C lower | 9, 13 |

## 2. DC2838A topology (manual Rev. 0; schematic REV02)

- Spec (manual p.1): VIN 9-30 V, 250 V (245-255 V) at 10 mA, f_sw 400 kHz, efficiency 77 % and **ripple 1 V** (12 V in, 10 mA), max 10 mA at VIN = 9 V. "Component selection restricts the input voltage to 30 V" (IC itself 60 V). No ripple/noise number with spectrum is given; radiated EMI plots only (pp.3-4, image-only, 12 V in, SSFM on).
- Structure (schematic, DER by tracing): L1 10 uH from VIN to SW. **Stage 1 (boost):** D1 (SW -> C14, no series resistor) charges C14 0.22 uF/200 V to V1 ~125 V; R10 20 ohm runs from V1 to the D3 anode, i.e. it is in the pump-charge path, not the boost rectifier path (re-read 2026-10-22, DC2838A REV02 and LT8365 Rev. A p.30 R8 agree; the earlier reading here put R10 in series with D1 and the Rev A schematic copied that until review item S1). **Stage 2 (one charge-pump doubler):** C2 0.1 uF/200 V couples SW to NET1; D3 charges it from V1; D4 passes NET1 to C15 0.22 uF/200 V stacked on C14, so Vout = V(C14)+V(C15) = 2*V1 - Vd ~ 250 V. Switch peak is only ~V1 (125 V < 150 V). Output R12 47 ohm and C17 1 nF/500 V. D1, D3, D4 = DFLS1150.
- "Optional third charge pump stage" (manual p.1): remove R14 (0 ohm), fit C3, D5, D6, R11, C16 (NET1-NET3 chain, drawing) for higher Vout (x3, ~375 V DER).
- FBX: R4 + R13 = 499 k + 499 k over R5 6.49 k -> 1.6*(1 + 998/6.49) = 247.7 V (DER). RT R7 107 k (400 kHz). VC: R6 84.5 k + C9 1 nF C0G (C8 option). SS C6 0.22 uF. INTVCC C7 1 uF. VIN C10 1 uF/50 V, plus 2x4.7 uF + 10 uF + 68 uF with L2 0.47 uH pi filter. EN/UVLO R1 1 M / R3 287 k -> turn-on 1.68*(1+1000/287) = 7.5 V (DER); JP1 selects SYNC / Burst (default) / Burst+SSFM / skip / skip+SSFM. Parts: manual p.4.
- Datasheet p.30 is closer to us: "400 kHz, 3 V to 6 V Input, 250 V Output Boost Converter" **1.5 mA**, L1 3.3 uH (74437324033), DFLS1150 x4 (D1-D3 as above, plus D4 anode GND/cathode SW, purpose not stated), C5-C7 0.22 uF X7T 200 V, R8 20 ohm, R6/R5 1 M/6.49 k, RT 107 k. Same 3-capacitor doubler. This is the 5 V-in precedent (read from rendered image).
- What changes for 5 V in: (a) EN divider rescaled (7.5 V turn-on would never start); (b) L lower or load tiny (here 10 uH is fine because the load is 1 mA); (c) V1 only needs 110 V max, so 200 V parts are plenty; (d) CCM duty becomes 0.93-0.96, near the Dmax limit, so the converter must live in DCM; (e) 10 mA -> 1 mA lets the pump caps shrink; (f) ripple 1 V is unacceptable at the cathode without the RC filter.

## 3. Rev A circuit

### 3.1 Choice
Option A (boost to ~110-120 V + one doubler, chosen) vs option B (single boost to 140 V). B puts the switch node at >= 140.5 V (168 V with the same 20 % ring allowance) against the 150 V abs max (p.2), needs CCM duty 0.966 > the 0.938 limit, cannot reach 150-220 V for VBR = 200 V units (bias ~185 V), and a Vout short has a DC path through L/D1. A reaches 220 V with 17 V margin on the switch node after a 20 % ring allowance (ASM). Cost: 3 more diodes/caps, no matter at 1 mA.
Frequency: the datasheet maximum is 500 kHz, so the requested >= 1 MHz is **not available** (pp.1, 11). Use 500 kHz (RT 84.5 k) and put attenuation in the filter. Keep SSFM off (a spread of 500-600 kHz smears the line and exceeds the nominal frequency). Min on-time (200 ns max) gives a 105 mA minimum pulse = >= 147 uA of output power at 140 V if every cycle fired, so below that the part skips pulses; that is why light-load behaviour is pulse-skipping rather than fixed-rate.
Mode: default SYNC/MODE floating (pulse-skip, clock-aligned pulses, "hundreds of uA" extra, p.9), with 0 ohm footprints to GND (Burst) and 100 k (Burst+SSFM) and a pad for an external clock >= 500 kHz. Reason (DER): Burst pulses are 106 mV steps at 38-379 kHz and wander into the 100 kHz band, while a skip-mode min pulse is ~11 mV at <= 500 kHz. Verify on the bench.

### 3.2 Component values
| Function | Value | Basis |
|---|---|---|
| L1 | 10 uH, Isat >= 1.5 A (Wurth 74437324100) | DS p.14 formula gives ~15 uH for CCM at full rated load; DCM at 1 mA allows less (p.12). Ipk 0.36 A worst |
| V1 diode/caps | D1-D4 DFLS1150 (150 V), C5, C6, C7 0.1 uF X7R 200 V; stress 111 V = 1.35x diode, 1.81x cap | DER; DS p.16 |
| Pump R (R8) 20 ohm, R_out 47 ohm | as DC2838A R10, R12; R8/R10 sits between V1 and the pump diode anode (our R7, HV_V1 to D3 anode since 2026-10-22) | manual p.4; LT p.30 |
| RT | 84.5 k (500 kHz; 465-535 kHz) | DS p.11 |
| VC | 84.5 k + 1 nF C0G, optional 2.2-22 pF | DS p.13, demo p.4; **tune on bench** |
| SS | 0.22 uF (2 uA/0.22 uF = 9.1 V/s on SS; 176 ms is an upper bound for 1.6 V, ASM) | DS p.4, examples |
| EN/UVLO | 200 k / 200 k: on 3.15-3.80 V, off 3.09-3.29 V (max rising 3.80 < 4.75 V min rail; Rtop/Rbot must stay below 1.5). EN also pulled low by an open-drain GPIO to hold bias off until the TIA rail is up | DS p.4 |
| BIAS | to GND (0 ohm option to VIN) | DS p.7 |
| Input | 10 uF 50 V + 4.7 uF 50 V + 0.47 uH/10 uF pi filter from the 5 V rail | demo p.4 |
| Rt (FBX top) | 4 x 2.05 M in series = 8.2 M (55 V each at 220 V) | DER |
| Rb (FBX bottom) | 86.6 k (E96) + 10 k NTC (beta 3950): Rb(25C) = 96.6 k | DER |
| Rd (DAC leg) | 150 k (R14; was 442 k until 2026-10-22, review S2) from DAC through 10 k + 100 nF filter: Rd = 160 k | DER |
| Rp (pot leg) | 1 M (was 274 k) from wiper of 50 k pot across 3.3 V (DNP in production). With Rd = 160 k a 274 k pot leg at wiper 0 V would reach 267 V (switch node over 150 V); 1 M limits the pot to +/-13.5 V about the DAC set-point | DER |

Divider equation (FBX current +/-10 nA gives +/-82 mV, negligible):
`Vout = Vfb*(1 + Rt/Rb + Rt/Rd + Rt/Rp) - Vdac*Rt/Rd - Vw*Rt/Rp`, with `Rb = Rs + R_ntc(T)`, `R_ntc = R25*exp(beta*(1/T - 1/298.15))`.
Tempco: dVout/dT = -Vfb*(Rt/Rb)*(1/Rb)dRb/dT, needs alpha_Rb = -0.65/(Vfb*(Rt/Rb)) = -0.462 %/C, NTC alpha = -beta/T^2 = -4.44 %/C, so NTC share = 10.4 % of Rb (Rb 93 k, NTC 9.7 k); the 10 k NTC therefore fits Rt = 8.2 M. Trim legs do not change the tempco (derivative is through Rb only).
Worked result (DER): slope 0.625 V/C at 25 C, **0.642 V/C averaged over 15-35 C**; error vs 0.65 V/C line spans -1.40..0 V, i.e. **+/-0.70 V if the 25 C trim is re-centred** (about +/-5 % gain at M~100, 7 %/V from apd-selection.md); Rs = 82.5 k would give 1.92 V worst error. NTC beta +/-1 % moves the slope 0.642 -> 0.649 V/C. Vfb temperature drift only +2 mV/C. Vfb tolerance (-4.3/+4.8 V) and VBR spread demand a per-unit trim. Smaller NTC (2.2 k) would allow Rt ~1.8 M but not checked in the script run.
Range (T=25 C, production build: RV1/R15 not fitted, DAC leg only, Rd = 160 k since 2026-10-22): DAC code 0 (0 V) = **219.4 V hardware maximum**, mid (1.65 V) = 134.9 V, full scale (3.3 V) = 50.3 V (firmware limits codes to >= 100 V); span 169 V, LSB 41.3 mV (12-bit). At 15/35 C the code-0 value is 211.7/224.5 V. Covers VBR 150 typ -> bias ~135-140 V and VBR 200 max -> ~190 V from the DAC alone. The MCP4728 powers up at code 0 (internal EEPROM default, DS22187E Table 4-2), i.e. at the maximum: see decision 19 and review S3. Earlier text (until 2026-10-22, review S2) assumed the pot leg fitted at mid and quoted 104-215 V with the DAC adding +/-31 V; with the pot leg DNP and Rd = 452 k the real production range was only 106.6-166.5 V, which cannot bias a 200 V VBR unit. Lowering Rd alone fixes it because the tempco depends only on Rb (see above), so R12/TH1 stay. Bench build with the pot leg fitted (R15 now 1 M): pot adds +/-13.5 V about the DAC set-point. Divider load 17 uA at 140 V, 27 uA at 220 V.

## 4. Cathode filter and protection (HV_RAW -> clamp -> R1 -> C1 -> R2 -> C2 at cathode)
- R1 27 k, C1 10 nF, R2 10 k, C2 10 nF **C0G/NP0 or film, rated >= 400 V** (220 V is 88 % of a 250 V part; with 235 V fault level the requested 250 V part has no margin). C2 within 3 mm of the cathode pad, 100 pF C0G in parallel optional for >30 MHz (ESL ASM 1.2 nH). **No resistor between C2 and the cathode**: R in series with Cj (6 pF) low-passes the signal at 1/(2 pi R Cj) (47 k -> 560 kHz) and R thermal noise (4kT/R current) adds ~6-30 nA (hand calc, 47 k to 1 k), comparable with the TIA's 26 nA (DER).
- Attenuation, DC drop, short current, energy, time constants: section 5 output. 100 kHz: -81 dB; 500 kHz: -108 dB (17 dB above the -91 dB needed for 10 uV from a 1 Vpp source); 6.63 MHz: -142 dB incl. 0.15 pF resistor bypass, 3 pF clamp Ccb, ESL/ESR (ASM). Real cathode noise will be limited by layout coupling, not by this ladder.
- DC drop at 100 uA: 3.7 V + ~1.2 V clamp (about 30 % gain at M~100 worst case; 0.37 V at 10 uA). Settling 2.8 ms to 1 %; startup is set by SS.
- **Short-circuit:** steady current limited by R1+R2 to 5.95 mA at 220 V, 6.35 mA at 235 V (64 % of the 10 mA abs max; protection diodes "typically 30 mA continuous", PDF p.16) -- passes. R1+R2 need >= 200 V rating (1206). The clamp reduces the steady fault to ~0.17 mA.
  **Open risk:** C2 sits at the cathode, so a cathode-to-TIA short dumps 2.2 uC / 242 uJ with only trace/ESR resistance, and C1 dumps through R2 at up to 22 mA. A series R after C2 would fix it but breaks the signal path (above). Options to test: C2 -> 2.2-4.7 nF (cuts the dump 2-4.5x, costs 7-13 dB: -101 to -95 dB at f_sw, so ~4 dB margin with the 1 Vpp source), keep C2 off the TIA side with a guard, and sacrifice a TIA in G1 test (section 7). Not resolved on paper.
- **APD current clamp** (upstream of R1): 2-BJT limiter, Q1 HV NPN (Vceo >= 300 V) pass, Q2 senses Rs = 4.02 k; Iclamp = Vbe/Rs ~150 uA at 25 C (172 uA at -20 C, 132 uA at 60 C, ASM Vbe -2 mV/C), Rb = 10 M from HV_RAW to Q1 base adds HV/Rb to the fault current (172 uA at 220 V). Passes the 100 uA worst case up to ~60 C and stays under S12023 Ir max 200 uA (apd-selection.md) at -20 C; soft knee near 100 uA not modelled. Q1 sits upstream of C1 so its noise is filtered; its 3 pF Ccb is in the ladder model.
- Stored energy at 220 V (DER, nominal C, X7R DC-bias loss lowers it): pump caps 3 x 0.6 mJ = 1.82 mJ, filter 0.48 mJ, total 2.3 mJ; discharges in ~0.5 s through the divider (tau 0.37 s). Add a 2-5 M bleeder if a faster discharge is wanted for service.
- 3 x 100 nF X7R/200 V loses capacitance with DC bias (typ. tens of percent at 110 V, ASM 50 %); the HV filter caps must be C0G/film.


## 5. Script output (`python3 tools/apd_bias_design.py`, verbatim)

```
APD bias supply Rev A design check: Vin 5.0 V +/-5 %, Vout 140 V (100-220), Iload <= 1 mA, f_sw 500 kHz, L 10 uH

== 3a. Converter: LT8365 boost -> V1, one charge-pump doubler -> Vout = 2*V1 - Vd
  RT = 84.5 k -> f_osc(formula, DS p.11) = 506 kHz; table value 500 kHz; max 535 kHz (DS p.3)
  RT for exactly 500 kHz by formula = 85.48 k ; for 300 kHz = 143.1 k
  Duty limits (DS p.12): Dmax_allowed = 1 - 115ns*535kHz = 0.938; Dmin_allowed = 200ns*f = 0.107
  Vout   V1     Vsw_pk  Vsw_pk*ring  margin  D_ccm(4.75V)  D_ccm(5.25V)  [CCM duty vs limits]
    100   50.2    50.8        60.9    89.1        0.906         0.897   Dmax OK
    140   70.2    70.8        84.9    65.1        0.933         0.926   Dmax OK
    220  110.2   110.8       132.9    17.1        0.957         0.953   Dmax EXCEEDS
  [PASS] switch node at 220 V incl. 20 % ring < 150 V abs max (DS p.2): 133 V
  Operation is discontinuous (DCM): at 1 mA the duty is set by energy, not by 1-Vin/V1.
  Vout   Pin(W)  Ipk_fixedf(A)  ton(ns)  treset(ns)  Dsw   Ipk_crit_CCM(A)  Pin_crit(W)  I_L_avg(mA)
    100   0.143         0.239      503         52  0.25            0.86        1.85        30.1  (Iload 1.0 mA)
    140   0.200         0.283      595         43  0.30            0.89        1.96        42.1  (Iload 1.0 mA)
    220   0.314         0.355      746         33  0.37            0.91        2.07        66.2  (Iload 1.0 mA)
    140   0.020         0.089      188         14  0.09            0.89        1.96         4.2  (Iload 0.1 mA)
  [PASS] worst-case Ipk (220 V, 1 mA, every cycle) well below ILIM(min) 1.5 A (DS p.3): 0.355 A
  [PASS] deep DCM at 1 mA, 220 V: Pin < 20 % of CCM-boundary power: 0.31 W vs 1.96 W
  Min on-time pulse (200 ns max, DS p.3 tested at VIN=24 V; 5 V value NOT specified): Ipk_min = 105 mA, delivers >= 20.6 mW = 147 uA at 140 V if every cycle fires -> below that the part must skip pulses.
  Burst Mode (325 mA pulses, DS p.10): E/pulse 370 nJ -> pulse rate 38 kHz at 0.1 mA, 379 kHz at 1 mA (140 V)
  Pulse step on Vout: skip-mode min pulse 11.0 mV; Burst pulse 106 mV  (Ceff = 25 nF, ASM)
  Diode/cap stress (all = V1 at 220 V):
    D1..D4 reverse ~111 V vs 150 V (DFLS1150, DS p.16): margin x1.35;  C5/C6/C7 ~110 V vs 200 V: x1.81
  [PASS] diode VR >= 1.3 x stress: 1.35x
  [PASS] pump caps VR >= 1.5 x stress: 1.81x
  EN/UVLO divider 200 k/200 k: rising 3.15/3.36/3.80 V, falling 3.09/3.20/3.29 V (min/typ/max, DS p.4)
  [PASS] EN rising max < 4.75 V rail minimum: 3.80 V
  SS: 2 uA charge (DS p.4), C_SS = 220 nF -> dV/dt = 9.1 V/s (1.6 V full-scale would take 176 ms, ASM upper bound; DS Fig.3 p.13 is drawn at 10 ms/DIV)
  Input current at 140 V/1 mA: 40 mA + ~1.2 mA active IQ (DS p.3); stored energy in pump caps follows in 4.

== 3b. FBX divider: Vout = Vfb*(1+Rt/Rb+Rt/Rd[+Rt/Rp]) - Vdac*Rt/Rd[- Vw*Rt/Rp] ; Rb = Rs + NTC(T)   [pot leg DNP (production: RV1/R15 not fitted)]
  Rt = 8.2 Mohm (4 x 2.05M, <=55 V each); DAC leg Rd = 160 kohm (R13 10k + R14 150 kohm); pot leg absent
  DAC span = Vdac_max*Rt/Rd: 100-220 V needs Rd <= 225.5 kohm; with Rd = 160 kohm the span is 169.1 V, LSB(12-bit) = 41.3 mV
  Needed Rb(25C) for 220 V at Vdac = 0: 96.19 kohm;  needed alpha_Rb = -0.477 %/C; NTC alpha(25C) = -4.444 %/C -> NTC fraction 0.107 -> NTC25 = 10.32 k (fitted: 10 k)
  Rs (E96) that puts code 0 closest to 220 V: 86.6 kohm -> 219.4 V; tempco error with it 1.40 V (max over 15-35 C)
  Note: dVout/dT = -Vfb*Rt*(dRb/dT)/Rb^2 does not depend on Rd, so the DAC leg sets the span and Rb/NTC set the tempco independently; Rb is kept at the tempco-optimised value and Rd alone is lowered to reach vout_max at code 0.
  Chosen Rs = 86.6 kohm (E96) + NTC 10k b=3950: Rb(25C) = 96.6 kohm;  Vout(25C, Vdac = mid 1.65 V) = 134.86 V
   T(C)  NTC(k)   Rb(k)   Vout(V)  ideal(V)  err(V)   [Vdac = mid; ideal = Vout(25)+0.65*(T-25)]
    15   15.837   102.44   127.12   128.36   -1.24
    20   12.535    99.14   131.38   131.61   -0.22
    25   10.000    96.60   134.86   134.86   +0.00
    30    8.037    94.64   137.67   138.11   -0.43
    35    6.506    93.11   139.95   141.36   -1.40
  Slope at 25C (central diff) = 0.625 V/C; 15-35C average = 0.642 V/C (target 0.65); error span -1.40..+0.00 V -> +/-0.70 V if the 25C trim is re-centred (= +/-5 % gain at M~100, DER 7 %/V)
    NTC  6.8k with Rs 88.7 kohm: slope 0.449 V/C, code 0 -> 221.0 V
    NTC  8.2k with Rs 88.7 kohm: slope 0.525 V/C, code 0 -> 219.0 V
    NTC 10.0k with Rs 86.6 kohm: slope 0.642 V/C, code 0 -> 219.4 V
    NTC 12.0k with Rs 84.5 kohm: slope 0.769 V/C, code 0 -> 219.6 V
  [PASS] band-average tempco within 5 % of 0.65 V/C: 0.642 V/C
  [PASS] re-centred error over 15-35 C <= +/-0.75 V (beta/NTC tolerance excluded): +/-0.70 V
  Sensitivity beta +/-1 %: slope 0.649 V/C (vs 0.642)
  Vfb tempco (GRAPH-READ DS p.5, ~+26 uV/C) adds 2.2 mV/C at Vout (negligible); Vfb tol 1.568-1.636 V -> -4.4/+4.9 V -> per-unit trim REQUIRED
  FBX current +/-10 nA (DS p.3) x Rt||Rb = +/-82 mV at Vout
  Set-point vs DAC (pot absent):
   T(C)   Vdac=0 (code 0, MCP4728 power-up)   Vdac=1.65   Vdac=3.3 (code 4095)
    15     211.7 V                             127.1 V      42.6 V
    25     219.4 V                             134.9 V      50.3 V
    35     224.5 V                             140.0 V      55.4 V
  [PASS] code 0 (blank DAC) within 215-225 V: 219.4 V
  [PASS] full scale <= 105 V (firmware limits codes to >= 100 V): 50.3 V
  [PASS] switch node at code 0: (Vout+Vd)/2 x ring < 150 V: 132 V
  Bench build with the pot leg fitted (Rp = 274 kohm, same Rb): Vw = 0, Vdac = 0 -> 267.3 V; Vw = 3.3, Vdac = 3.3 -> -0.6 V; Vw = mid, Vdac = mid -> 133.4 V (the pot adds +/-49 V about mid; firmware code bounds must then come from HV_MON, not from the code alone)
  Divider/bleeder current at 140 V = 16.9 uA (2.36 mW); at 220 V = 26.5 uA

== 4. Cathode filter: HV_RAW -R1-[C1]-R2-[C2 at cathode]  (no series R after C2: it would form a pole with Cj)
  R1=27 kohm C1=10 nF  R2=10 kohm C2=10 nF;  corners 589 Hz, 1592 Hz
   f           ideal 2xRC (dB)   with parasitics+ESL (dB)
     0.100 MHz       -80.6            -80.6
     0.300 MHz       -99.6            -99.5
     0.500 MHz      -108.5           -108.2 <- f_sw
     0.600 MHz      -111.7           -111.3
     6.630 MHz      -153.8           -142.4 <- 6.63 MHz WPT
    30.000 MHz      -189.1           -164.6
   100.000 MHz      -177.6           -140.2
  Source (ASM): ripple 1.0 Vpp at f_sw (354 mV rms fundamental; DS DC2838A p.1 shows 1 V ripple at 10 mA), 1/n harmonics to 1/(pi*t_edge) = 16 MHz then 1/n^2; plus 10 mV rms at 6.63 MHz.
  Cathode rms from converter ripple (100k-100M): 1.39e+03 nV; at f_sw alone: 1.37e+03 nV; at 6.63 MHz: 0.754 nV
  Injected current i=2*pi*f*Cj*v: converter 27.3 pA rms; 6.63 MHz 0.189 pA rms; vs TIA 26 nA rms
  Thermal noise of R1,R2 at cathode, 100k-100M: 65 nV rms
  [PASS] cathode noise (ripple) < 10 uV rms: 1.3864 uV
  [PASS] cathode noise at 6.63 MHz < 10 uV rms: 0.00075 uV
  Required attenuation at f_sw for 10 uV: -91.0 dB; ideal gives -108.5 dB -> layout/coupling margin 17 dB
  DC / fault:
   DC drop at 100 uA = 3.70 V (+ clamp ~1.2 V); at 10 uA = 0.37 V; APD gain ~7 %/V near M~100 (apd-selection.md)
   Hard short (cathode node -> TIA input) steady current at 220 V via R1+R2 = 5.95 mA vs OPA857 abs max 10 mA (PDF p.5): 59 %
   Hard short (cathode node -> TIA input) steady current at 235 V via R1+R2 = 6.35 mA vs OPA857 abs max 10 mA (PDF p.5): 64 %
  [PASS] steady short current < 70 % of OPA857 10 mA at 235 V: 6.35 mA
   Capacitor dump: C2 = 10 nF at 220 V holds 2.20 uC / 242 uJ, NOT limited by R1/R2 (its loop sees only ESR/trace) -> OPEN RISK; C1 dump limited by R2 only: 22.0 mA peak, tau 100 us
  Stored energy at 220 V: filter 484 uJ; pump caps (3 x 100 nF at 110 V, nominal C) 1.82 mJ; total 2.31 mJ
  Time constants (unloaded ladder): 0.59 ms and 45 us; step settles to 1 % in 2.79 ms, 0.1 % in 4.15 ms  (startup is paced by SS, tens of ms)
  Discharge after disable (only the divider bleeds): tau ~ 0.37 s (Ceff 45 nF ASM); 220 V -> 60 V in 0.49 s

== 5. APD current clamp (2-BJT limiter, upstream of R1; Q1 HV NPN pass, Q2 sense across Rs)
  Rs = 4 kohm, Rb = 10 Mohm (HV_RAW -> Q1 base); Vbe = 0.6 V @25C, -2 mV/C (ASM)
   T(C)   Vbe(V)   Iclamp(uA)   short I = Iclamp + HV/Rb at 220 V (uA)
   -20    0.690        172           194
    25    0.600        150           172
    60    0.530        132           154
    85    0.480        120           142
  [PASS] clamp passes 100 uA at +60 C and fault current < S12023 Ir max 200 uA at -20 C: see table (soft knee not modelled)
  Q1 fault dissipation = 220 V x ~150 uA = 33 mW (SOT-23 class OK, ASM)

SUMMARY: 15/15 checks passed
```

## 6. Bill of materials, bias block (availability and price NOT CHECKED for every line)

Example MPNs marked (M p.4) are from the DC2838A parts list, (D p.N) from the LT8365 datasheet; their datasheets were not opened. Others: generic, no MPN found in the provided documents.

| Ref | Generic value | Example MPN | Note |
|---|---|---|---|
| U1 | LT8365, MSE16(12) | LT8365EMSE#PBF (D p.2) | -40..125 C grade |
| L1 | 10 uH, Isat >= 1.5 A, low DCR | Wurth 74437324100 (M p.4) | DC2838A part |
| L2 / C_IN | 0.47 uH 2.1 A; 10 uF 50 V; 4.7 uF 50 V | 74479876147; TDK C3216JB1H106K160AB; AVX 12105C475KAT2A (M p.4) | 5 V pi filter, one or two caps enough |
| D1-D4 | 150 V Schottky, 1 A | Diodes Inc. DFLS1150-7 (M p.4, D p.16) | leakage 2 uA max at 150 V |
| C5, C6, C7 | 0.1 uF X7R 200 V 1206 | AVX 12062C104KAT2A (M p.4) | demo used 0.22 uF X7T TDK CGJ5L3X7T2D224K160AA |
| R_pump / R_out | 20 ohm / 47 ohm 0805 | Yageo RC0805JR-0720RL / Vishay CRCW080547R0JNEA (M p.4) | |
| C_VIN, C_INTVCC, C_SS | 1 uF 50 V X5R; 1 uF 25 V X5R; 0.22 uF 25 V X7R, 0603 | Taiyo Yuden UMK107ABJ105KAHT; AVX 06033D105KAT2A; AVX 06033C224KAT2A (M p.4) | |
| R_T, R_C | 84.5 k 1 % 0603 | NIC NRC06F8452TRF (M p.4, same value) | |
| C_C | 1 nF C0G 100 V | TDK CGA3E2C0G2A102J080AA (M p.4) | |
| R_EN | 2 x 200 k 1 % 0603 | none | |
| Rt | 4 x 2.05 M 1 % 0603 (<= 55 V each), or 0805 | Vishay CRCW0603 series (499 k used in M p.4; 2.05 M NOT CHECKED) | guard ring, no vias under |
| Rb_clamp (R17+R18), HV_MON (R20+R32) | 2 x 4.99 M 1 % 0805, 110 V each at 220 V | Yageo RC0805FR-074M99L: 150 V max working, 300 V overload (docs/datasheets/yageo-rc0805.pdf, spec V0 2016-07-26 p.3, VERIFIED); 0603 of the same family is 75 V | changed from 0603 2026-10-22 (review S5, decision 22) |
| Rs, Rd, Rp, R_df, C_df | 86.6 k, 150 k, 1 M (DNP) 0.1-1 %, 10 k, 100 nF X7R 16 V | none | |
| U6, R21/R45, R22/R23 (OVP limiter) | TLV431A SOT-23; 45.3 k + 54.9 k 1 % 0603; 2 x 20 k 1 % 0603 | TI TLV431AIDBZR (docs/datasheets/tlv431.pdf SLVS139Z) | decision 23 |
| NTC | 10 k at 25 C, beta ~3950, 1 % 0603 | none | on APD can ground tab / thermal link |
| P1 | 50 k multi-turn cermet pot (bench only) | e.g. Bourns 3296W-1-503LF, NOT CHECKED | DNP in production |
| R1, R2 | 27 k, 10 k thick/thin film 1206, >= 200 V | none | each sees up to 170 V / 65 V in a short |
| C1, C2 | 10 nF C0G/NP0 or film, >= 400 V | none (1210 C0G 10 nF/500 V class expected; NOT CHECKED) | |
| C_HF | 100 pF C0G 250 V, optional at cathode | none | |
| Q1, Q2 | HV NPN Vceo >= 300 V SOT-23; small-signal NPN | none (MMBTA42 / MMBT3904 class, from memory) | |
| R_s,clamp, R_b,clamp | 4.02 k 1 %; 2 x 4.99 M 1 % | none | Iclamp ~149 uA at Vbe 0.6 V |
| Shield, ferrite | can over U1/L1/D/C5-7; bead on 5 V | none | 6.63 MHz |

## 6b. Over-voltage limiter (added 2026-10-22, review S6, decision 23)

Failure: an open resistor in the 8.2 M FBX chain, or an FBX short to ground, makes the LT8365 see zero feedback and run at its limit. The output node holds about 50 nF (C7 stacked on C5 plus C25); at 0.55 uJ per cycle and 500 kHz it rises about 25 V/ms from 220 V, so the 150 V diodes avalanche (output near 300 V) about 3 ms after the fault (DER, not simulated). Firmware polling HV_MON cannot react in time and with J1 fitted it does not react at all. The LT8365 has no OVP pin.

Limiter: R21 is split into 45.3k (top) and 54.9k (bottom) so the tap OVP_REF is 0.548 x HV_MON; U6 TLV431A (VREF 1.24 V, 1 %) with REF on the tap and cathode on EN/UVLO pulls EN to 1.24 V, below the 1.545 V minimum falling threshold (LT p.4), when HV_MON reaches 2.263 V, i.e. HV_OUT = 2.263 x (9.98 M + 100.2 k)/100.2 k = 228 V. The converter stops, SS resets, the output decays through the ladder and the load, EN releases, and the supply sawtooths at the trip level. Error budget: VREF 1 % (2.3 V), I_ref 0.5 uA max into the 24.8 k tap source (0.7 V), resistor 1 % (about 2 V): roughly +/-3 V. At 228 V the switch node is 114 V plus the 20 % ring allowance = 137 V, inside 150 V. R22/R23 go from 200k to 20k so the EN node can source the TLV431 minimum cathode current (80 uA max; 125 uA available), ratio unchanged. Nothing measured; G1 item 5b verifies the trip.

Rejected: a Zener string from HV_OUT into FBX (review suggestion). Zener leakage into the FBX summing node moves the set-point by 8 V per uA through the 8.2 M chain, and it would drift with temperature.

## 7. Safety, layout and G1 test plan

Layout and safety rules
1. Clearance for <= 250 V (235 V worst): IPC-2221B 171-250 V row = **0.2 mm internal, 1.25 mm external uncoated, 0.4 mm external coated** (secondary source: Altair Pollex page as copied in apd-bias-supply.md; column meanings and the standard itself not opened; IPC-2221 is not a safety standard). Rule used: >= 1.5 mm external, >= 0.5 mm inner, >= 2 mm from the TIA input node and anode trace.
2. Put the HV net on one inner layer or bottom with a ground pour under the supply; no HV copper on the top layer under or near the OPA857; slot or guard-ring the HV pads; no HV via under a pad.
3. Switching loop (VIN cap - L1 - SW - D1 - C14 equivalent, and the C7-D2-D3 pump loop) minimal area at the end of the board opposite the TIA, SW copper as small as possible (p.7, p.16), exposed pad soldered to ground plane, power ground at the pad near EN/SW, signal ground (RT, SS, FBX, VC) at the pad near FBX.
4. Shield can over the converter; ferrite + 10 uF on the 5 V feed; no shared ground return with the TIA input reference.
5. FBX node high-impedance (Rt||Rb 90 k): short trace, guard ring, no HV or clock neighbours, 6.63 MHz pickup is the exposure.
6. C2 at the cathode pad (<= 3 mm), return straight to the TIA-side ground; cathode trace from C2 to the pin as short as possible.
7. Ramp the DAC slowly (cathode step injects Cj*dV/dt); sequence EN after the TIA rail; never hot-plug the APD with bias on.
8. Stored energy 2.3 mJ at 220 V (4.5 mJ with the 0.22 uF demo caps, DER): label the HV area and test points; discharge time ~0.5 s through the divider.
9. Keep Rt as four separate parts (each <= 55 V), and derate every HV resistor and capacitor to >= 1.5x its stress.
10. Output short survival: Vout shorted to GND leaves D1/C14 untouched (no DC path from VIN); fault current from the pump is bounded by R_out 47 ohm and DFLS1150 surge (NOT CHECKED); the input is not protected against V1 shorts (p.13-14), add a polyfuse or current-limited 5 V switch if the rail can source amps.

G1 test plan
1. Bring-up with a 10 Mohm/1 Mohm dummy load: check f_sw (465-535 kHz), SW waveform peak (expect ~V1 + ring < 135 V), Ipk (current probe on L1, expect ~0.3 A), startup overshoot at 5.25 V and 4.75 V in, with SS 0.22 uF and with EN toggled by GPIO.
2. Set-point vs temperature: chamber or heater/cold spray over 15-35 C (extend 0-50 C), NTC thermally coupled to a dummy APD can; record Vout at HV_RAW each 2 C; compare with 0.65 V/C line; fit slope and span, set pot/DAC at 25 C; criteria slope 0.62-0.68 V/C, span <= +/-0.75 V re-centred.
3. Range: sweep DAC code 0-4095 (0-3.3 V) with the pot leg not fitted; confirm about 219 V at code 0 and about 50 V at full scale (25 C), LSB ~41 mV; record the HV_MON reading at both ends. Note the code-0 (blank DAC) value is the maximum: do the first sweep downward from full scale.
3c. OVP limiter (review S6): with a dummy load, raise the DAC code toward 0 and past it by lifting R8 (or shorting FBX through 1 M to ground); confirm EN drops and the output holds near 228 V (sawtooth), record the trip level at 15/25/35 C; confirm HV_MON ratio 1/101.2 after the R21 split.
3b. Clamp drop (review S5b): inject 10-250 uA at the APD node with HV at 150 V and 220 V; record HV_MON, HV_CLAMP and the APD-side bias (R19/C8 node) versus current; the slope of (HV_OUT - APD bias) against current gives Rb_clamp/hFE, and the knee gives the limit. Repeat at 15 and 35 C.
4. Ripple at the cathode with the TIA running and APD attached: 50-ohm-terminated or active-probe ground spring on C2, then a spectrum (100 kHz-100 MHz, RBW 10 kHz); check f_sw line, harmonics, burst subharmonics; criterion < 10 uV rms in band; repeat with the 6.63 MHz wireless-power field on at full power and the shield on/off, and with SYNC modes (skip, Burst, Burst+SSFM, external clock). Also read TIA output rms with the APD dark.
5. Photocurrent: inject 10, 50, 100, 150, 250 uA from a source in place of the APD; confirm clamp knee 100-170 uA, drop across R1/R2 matches 37 k, no oscillation.
6. Short-circuit survival: with a current-limited bench supply feeding HV_RAW, short cathode node to a **sacrificial** OPA857 input through a mechanical contact; measure peak current and recovery; repeat Vout (pump) to GND, with scope on SW and VIN. Decide C2 value (10 / 4.7 / 2.2 nF) here.
7. Startup/overshoot of Vout and cathode with 0.22 uF SS: criterion no overshoot > 5 V above set-point at 4.75 V and 5.25 V in; check there is no 6 pF * dV/dt event at the TIA.
8. Efficiency and input current at 140 V/1 mA (expect ~40 mA), burst audio noise (X7R pump caps), thermal check of Q1 under a held fault.

## 8. Gaps

- Not simulated (no LTspice model run): loop stability with the 8.2 M divider and doubler; VC network is a datasheet default (p.13 says tune); Cff across Rt not evaluated.
- Min on-time and Vsw/Idiode ring at 5 V in not specified (Note 6 tests at 24 V); 20 % ring, 70 % efficiency, ripple source (1 Vpp, 1/n harmonics, 20 ns edge), 10 mV at 6.63 MHz, ESL/ESR/Cpar values, X7R bias loss (50 %), BJT Vbe values are ASM. TIA noise 26 nA is the project figure; OPA857 datasheet p.6 gives 25 nA (5 k, 1.5 pF source, 135 MHz).
- C2 capacitor-dump into a cathode-to-TIA short is unbounded by resistance; OPA857 pulse withstand (only 10 mA abs max and "30 mA continuous" diodes, PDF pp.5, 16) is not specified.
- INTVCC level (3.8 V vs 3.2 V) and SS-to-VC ramp time not specified; datasheet gives no formula for SS time.
- VBR minimum spec and per-unit tempco spread not available (apd-selection.md has only 150 typ/200 max, 0.65 V/C); the 100 V lower end is a guess. DAC reference accuracy (SAMD51) not checked; the 3.3 V pot leg inherits the rail error.
- Burst/skip/SSFM spectral behaviour at 1 mA, and DC2838A ripple with real spectrum, not available (only 1 V ripple, EMI plots).
- DFLS1150 surge current, 150 V Schottky leakage at 100 C, 10 nF 400-500 V C0G existence/price (the HV 0603 resistor rating was resolved 2026-10-22 by moving R17/R18/R20/R32 to 0805, 150 V, decision 22), NTC beta/MPN, and all availability are NOT CHECKED. Standards for stored-energy classification not consulted.
- Datasheet curves (FBX tempco, p.5) are GR; p.30 and the DC2838A connectivity were traced from rendered images and should be re-checked against the ADI design files.
