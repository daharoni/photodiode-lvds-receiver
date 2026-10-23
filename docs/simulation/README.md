# Simulation (ngspice) of three open analog questions

Status of everything here: **SIMULATED (ngspice 47, TI vendor macromodels)**. It is not VERIFIED in the sense of CLAUDE.md rule 2: no hardware was measured, no PCB parasitics are included, supplies and VCM_REF are ideal in Sims 1 and 2. Datasheet values are cited only for comparison. Anything marked UNRESOLVED needs the board or a better model.

Reproduce: `cd spice`, run `run_sim1.sh`, `run_sim2.sh`, `run_sim3.sh`, `run_sim1_sine_check.sh`, then the three `analyze_simN.py` (venv python with numpy 2.0.2 and matplotlib 3.9.4; no global installs), then `prune_out.sh` (deletes/gzips bulky raw text). Metrics land in `spice/out/sim{1,2,3}_metrics.json`, plots in `plots/`. Each netlist states which schematic values it uses (`docs/schematic/frontend.md`, `control.md`, `gen/*.py`).

## Tools

- ngspice 47 (Homebrew bottle, `brew install ngspice`), batch mode `ngspice -b`. `spice/.spiceinit` sets `set ngbehavior=psa` (PSpice syntax with PSpice parameter handling); the TI models do not load without it.
- Python 3.9.6 venv (scratchpad) with numpy 2.0.2 / matplotlib 3.9.4 for metrics and PNGs. Downloaded model files were only read by ngspice and by `patch_models.py` as text (`python -I`); nothing from the download directory was executed.

## Model provenance (docs/research/downloads/spice-models/, untrusted data)

All downloads succeeded without a login. None is encrypted (plain-text SPICE). SHA-256 below.

| Part | URL | Archive sha256 | File used | File sha256 | Notes |
|---|---|---|---|---|---|
| OPA855 | https://www.ti.com/lit/zip/SBOMB43 | 2a0ebb55c1063ce7e6400357fe97ba54095e14b7ae71ea8d70a69054cb9bc339 | `opa855_pspice/opa855_a.lib` | fef48f9b6594deff28bfe160f4997411d50d5afaad32a08764b9e5bb6f411cf0 | PSpice macromodel "OPA855 Rev. A, 2020-06-04", GWL architecture. Pins IN+ IN- OUT VCC VEE: no FB pin, no PD pin, no package parasitics. |
| OPA857 | https://www.ti.com/lit/zip/SBOMBP8 | ea0d5dacde0be2dcaf420696933621817b18a9b1a33d164401a2d3e1169e386c | `opa857.lib` | 8d10d08a3b226aa06e9479c9e80f5c72b32304a38d32ce7341086f8366848111 | "OPA857 model v1.0, 12/13/2016, SBOS630D, released by WEBENCH". Behavioural: input switch selects the 20 k / 5 k feedback, CTRL high = 20 k (verified by the AC result). Pins CTRL GND IN OUT OUTN VS. Models "small signal bandwidth, slew, input current noise, overdrive recovery, output offset, input capacitance, PSRR"; not temperature or distortion. Other archives fetched, not used: SBOM864 (TINA-TI; cc0903ca...2050), SBOM931 (ADS; 037b644d...013f). `opa857.lib` and the SBOM864 `.LIB` differ only in blank lines/comment. |
| OPA320 / OPA2320 | https://www.ti.com/lit/zip/SBOM438 | d0478194a9914fe1813eb9675623a3127e0fc0c9ee2fe82e4988de710c12deaf | `OPAx320.LIB` | a3ecb23eb81d73b9d03cc4d44ef0e06ffdaadc995301bad1cb4882ba8a0f3b8c | "OPAx320 Final 1.6, 22JUL2021, SBOS513F, generic, single-core OPA320 = one channel of OPA2320". Pins IN+ IN- VCC VEE OUT. Also fetched, not used: SBOM437 (Q1 PSpice), SBOM822/823 (OPA320S). |

Derived copies for ngspice `.ac` only (made by `spice/patch_models.py`, stored in `docs/research/downloads/spice-models/ngspice-patched/`): `opa857_ac_nolimit.lib` (dd832657...5a), `opax320_ac_nolimit.lib` (49864ad4...aea). They replace `LIMIT(x,lo,hi)` by `x`. Reason: with the unmodified OPA857 model the ngspice AC linearisation has essentially zero open-loop gain (transimpedance came out 1 ohm instead of 20 k); with LIMIT removed the transimpedance is 19.5 k. The identical operating point is used. All transient runs use the TI files as shipped.

## Known model/simulator issues (read before using any number)

1. **OPA855 AC loop-gain polarity (UNRESOLVED, affects Sim 1 phase margin only).** In ngspice's small-signal analysis the OPA855 model has the opposite polarity from its DC and transient behaviour (DC sweep and transient: IN- inverts; AC: IN+ -> OUT = -6389, IN- -> OUT = +6389). The loop-gain probe therefore reads -180 deg at low frequency instead of 0. I could not find the cause (removing every `LIMIT()` did not change it; the OPA320 and OPA857 models do not show it). The closed-loop AC magnitude is nevertheless right: it matches a time-domain sine response at 0.3/0.8/1.5/2.5 GHz to 0.02 dB (`run_sim1_sine_check.sh`: 16.71/16.15/14.70/13.82 dB transient vs 16.73/16.17/14.71/13.83 dB AC). Phase margin below is read as the angle between T and -1 at |T| = 1, which reproduces the closed loop, but treat it as lower confidence than the transient overshoot numbers.
2. The TI OPA855 model is rail-limited at about 0.8 V on the low side. The datasheet gives VOL = 1.05 V typ / 1.15 V max (VS+ = 3.3 V, RL = 200 ohm; SBOS622D electrical characteristics, Output). So the model clips later than the datasheet says the real part does. Clipping/recovery results (Sim 1c) are therefore model-limited (UNRESOLVED for the real part).
3. The model's DC idle is 1.578 V at OUT (as drawn); `frontend.md` estimates 1.73 V. The model draws its 12 uA bias current INTO the pins (IN+ sits 12 mV below VCM_REF); the datasheet gives IB = -12 uA typ (-18.5 to -5) without stating the sign convention in the table (SBOS622D 6.5, PDF p.6). The 150 mV difference matters only for headroom (UNRESOLVED).
4. OPA857 model: the DC operating point starts at OUT 1.90 V and relaxes to 1.836 V within the first 100-200 ns; the pattern therefore starts at 300 ns. Transimpedance 19.5 k single-ended (OUT only) vs the datasheet 18.2 k.
5. OPA320 DC operating-point solver warnings ("gmin stepping failed") appear; the solution used is the one source stepping reaches and was checked (OUT 1.650 V, VCM_REF as expected from the loads).

## Sim 1: OPA855 post-amp as drawn (netlists `spice/sim1_postamp.cir`, `sim1_loop.cir`)

Circuit: C51 100 n / R51 1 k input, OPA855 non-inverting, RF = R53 (OUT to IN-), RG = R54 (IN- to PA_REF), PA_REF = VCM_REF through R60 10 ohm with C53 1 u, R56 49.9 + C54 47 p, C55 100 n, R59 1 k, 2 pF comparator load. Source: ideal source behind 25 ohm (the R4 = 25 ohm output resistor inside the OPA857 model); VCM_REF ideal 1.65 V. Because FB is internally the output (SBOS622D 8.3.2, p.17), RF is wired from the OUT node. Loop probe: large L (1 GH) opens the loop at the IN- pin, 1 GF injects the AC voltage at the pin, T = -V(feedback side)/V(pin) (single voltage injection into a high-impedance pin from a low-impedance network). Plots: [closed loop AC](plots/sim1_closed_loop_ac.png), [loop gain](plots/sim1_loop_gain.png), [transient](plots/sim1_transient.png).

### 1a. AC and stability (SIMULATED, ngspice 47, TI OPA855 Rev A)

| RF / RG | gain 1+RF/RG | OUT passband (100 kHz) | OUT peaking | OUT -3 dB | SDET_P -3 dB (after R56/C54) | T crossover | angle of T at crossover | PM (see issue 1) |
|---|---|---|---|---|---|---|---|---|
| 301 / 49.9 (as drawn) | 7.03 | 16.70 dB | 0.1 dB at 128 MHz | 2.13 GHz | 69.5 MHz, peaking 0.04 dB | 1.04 GHz | -102.9 deg | 77 deg |
| 453 / 75 (datasheet test values) | 7.04 | 16.72 dB | 0.12 dB at 347 MHz | 2.36 GHz | 69.4 MHz | 1.05 GHz | -102.9 deg | 77 deg |
| 200 / 49.9 | 5.01 | 13.75 dB | 6.1 dB at 3.1 GHz | 3.6 GHz | 69.3 MHz | 1.54 GHz | -108.8 deg | 71 deg |
| 453 / 49.9 | 10.08 | 19.82 dB | 0.1 dB | 1.04 GHz | 69.7 MHz | 0.71 GHz | -99.3 deg | 81 deg |
| 200 / 33.2 (gain 7 again) | 7.02 | 16.66 dB | 0.11 dB | 1.67 GHz | 69.8 MHz | 1.03 GHz | -102.9 deg | 77 deg |

Reading: in this model RF 301 and RF 453 at gain 7 are indistinguishable (PM 77 deg, no peaking), so the as-drawn 301/49.9 is no worse than the datasheet test values. The open-loop gain is flat 75 dB to about 150 kHz (datasheet 6.5: AOL typ 76 dB, GBWP 8 GHz, SBOS622D) and |T| crosses 0 dB near 1 GHz. At gain 5 (below the datasheet's minimum stable gain of 7, `frontend.md` / SBOS622D table) the model shows 6 dB peaking near 3 GHz and the largest pulse overshoot below; it is the weakest case, consistent with the datasheet warning, but the model's behaviour below gain 7 is not independently checked. The SDET_P -3 dB point is the R56/C54 low-pass (49.9 ohm, 47 pF: 68 MHz calculated), the amplifier adds nothing visible.

### 1b. Small-signal step (10 mV negative step at TIA_OUT, 20 ns edges, 100 ns wide) (SIMULATED)

| RF / RG | OUT step (plateau) | overshoot, 20 ns edges | overshoot, 2 ns edges | overshoot, 0.2 ns edges | trailing-edge overshoot, 0.2 ns edges |
|---|---|---|---|---|---|
| 301 / 49.9 | -68.3 mV (gain 6.83) | 0.4 % | 1.0 % | 3.2 % | 2.2 mV |
| 453 / 75 | -68.4 mV | 0.4 % | 1.2 % | 3.6 % | 2.5 mV |
| 200 / 49.9 | -48.7 mV | 0.4 % | not run | 8.2 % | 3.9 mV |
| 453 / 49.9 | -97.9 mV | 0.4 % | not run | 1.3 % | 1.3 mV |
| 200 / 33.2 | -68.2 mV | 0.5 % | not run | 3.0 % | 2.0 mV |

At the real edge speeds of this system (ns), overshoot is about 1 %, no ringing. The 0.2 ns edge is a stress case far faster than the TIA can deliver. A 1 % overshoot corresponds to a damping ratio near 0.8, i.e. PM of roughly 70 deg, which is consistent with the AC number (77 deg).

### 1c. Large-signal and clipping (SIMULATED; model-limited, see issue 2 and 3)

Model idle at OUT 1.578 V (1.576 V with 453/75). Input steps are negative (light on). OUT minimum and behaviour, 20 ns edges, 100 ns wide:

| input step | 301/49.9: OUT min | 453/75: OUT min | behaviour |
|---|---|---|---|
| 30 mV | 1.372 V | 1.370 V | linear, gain 6.8 |
| 60 mV | 1.169 V | 1.166 V | linear (the "about 60 mV" case): just above the datasheet VOL max 1.15 V, not clipped in the model |
| 80 mV | 1.051 V | 1.047 V | linear |
| 90 mV | 0.826 V, oscillating | 1.006 V, linear | onset between 80 and 100 mV |
| 100 mV | 0.806 V, oscillating | 0.803 V, oscillating | hard limit |
| 200 mV | 0.765 V, oscillating | 0.760 V, oscillating | hard limit |

Once the model reaches its low limit (about 0.8 V) OUT does not sit at a flat clip level: it enters a limit cycle of roughly 0.8 to 1.7 V peak-to-peak (about 0.85 V pp, period 0.5 to 1 ns, about 1 to 2 GHz) for as long as the input stays over the limit, with identical behaviour at both RF values. It is not a numerical artefact (same with `method=gear reltol=1e-4` and `reltol=1e-5`) but it is a property of this macromodel's saturation network (UNRESOLVED whether the real part does this; the datasheet states overdrive recovery 3 ns for 2x overdrive, SBOS622D p.6, and shows no oscillation). Recovery after the input returns (2 ns trailing edge, metric = time after the input is fully back to idle until OUT is within the band, held thereafter):

| overdrive | 301/49.9: within 41 mV (10 % of the 410 mV unclipped swing at 60 mV) | 301/49.9: within 10 mV | 453/75: within 41 mV | 453/75: within 10 mV |
|---|---|---|---|---|
| 100 mV | 0.02 ns | 0.1 ns | 0.01 ns | 0.11 ns |
| 200 mV | 0.27 ns | 0.91 ns | 0.07 ns | 0.50 ns |

Because the input edge itself takes 2 ns to return and OUT follows it, the recovery is under 1 ns after the input is back, well inside the 3 ns datasheet value and 20 ns UI. For the real part this number is UNRESOLVED: the model clips 0.25 to 0.35 V lower than the datasheet VOL, so it cannot say how the part recovers from clipping at 1.05-1.15 V, which is where about 60 mV of input actually puts it (1.578 V minus 7 x 60 mV is 1.16 V, using the model idle).

## Sim 2: OPA857 TIA with the APD capacitance (netlists `spice/sim2_ac.cir`, `sim2_tran.cir`, `sim2_core.inc`, `sim2_iph.inc` from `gen_pattern.py`)

APD = ideal current source (photocurrent into the IN pin) in parallel with CD, anode at IN, cathode node through C50 10 n and R50 10 k to an AC-quiet bias. Load on OUT: C51 100 n into R51 1 k. CD = 6 pF (decision: same 6 pF for S12023-10 and FDS010), 1.5 pF (the datasheet design point, SBOS630D p.1/p.6) and 10 pF (added 2026-10-23 for the S3884, see below). Pattern: 50 Mb/s NRZ, UI 20 ns, 5 uA peak, 2 ns edges; first 5 ones then 5 zeros, then 1010101, then short runs (35 bits). AC uses the derived no-limit model copy; transient uses the TI file. Plot: [sim2_tia.png](plots/sim2_tia.png).

SIMULATED, ngspice 47, TI OPA857 v1.0 model:

| mode, CD | Rt (OUT, 1 MHz) | -3 dB BW | peaking | overshoot on a 5-UI run | 10-90 % rise (input edge 2 ns) | settle to 2 % from edge start | rings? |
|---|---|---|---|---|---|---|---|
| 20 k, 6 pF | 19.5 k | 99 MHz | 0.97 dB at 54 MHz | 13.8 % (both edges) | 3.6 ns | 12.6 ns | one overshoot, then settled |
| 20 k, 1.5 pF | 19.5 k | 106 MHz | none | 1.7 % | 3.5 ns | 6.1 ns | no |
| 5 k, 6 pF | 4.88 k | 151 MHz | none | 1.7 % | 2.7 ns | 4.7 ns | no |
| 5 k, 1.5 pF | 4.88 k | 127 MHz | none | 0 % | 3.2 ns | 6.1 ns | no |
| 20 k, 10 pF | 19.5 k | 87.9 MHz | 2.19 dB at 51.9 MHz | 21.7 % (both edges) | 3.84 ns | 21.5 ns | 3 extrema above 2 % |
| 5 k, 10 pF | 4.87 k | 150.3 MHz | 0.20 dB at 62.4 MHz | 7.1 % | 2.63 ns | 8.1 ns | 1 extremum above 2 % |

2026-10-23, 10 pF case (SIMULATED, same TI OPA857 v1.0 model, ngspice): run to evaluate the Hamamatsu S3884 (1.5 mm, 10 pF) as a larger-area option (`docs/research/apd-selection.md`). In 20 k mode the 10 pF case settles to 2 % in 21.5 ns from edge start, more than one 20 ns UI, with 2.2 dB of peaking at 52 MHz and 3 ring extrema above 2 %. The peak lies below the 68 MHz low-pass, so the filter does not remove it. 5 k mode is fine (8.1 ns, 0.2 dB). Caveat: the model was characterised at 1.5 pF, so its accuracy at 10 pF is UNRESOLVED until measured. Metrics: `spice/out/sim2_metrics.json` (keys `20k_10p`, `5k_10p`).

Check against the datasheet: with 1.5 pF the model gives 106 MHz (20 k) and 127 MHz (5 k); the datasheet table gives 105 MHz (CTRL = 1) and 125 MHz (CTRL = 0) at 1.5 pF (SBOS630D 6.5, PDF p.6; the text in 8.2.2, p.21, quotes 130 MHz for 5 k and 105 MHz for 20 k). So the model reproduces its own datasheet at the design point, which supports, but does not prove, its behaviour at 6 pF (UNRESOLVED until the 6 pF case is measured). Larger CD raised the 5 k bandwidth from 127 to 151 MHz in the model (input capacitance peaking), which is plausible but is also model-dependent. Not modelled: APD series resistance, bias-dependent capacitance, noise, and the TIA's DC bias path.

What it means for the 50 Mb/s link: bandwidth is not the issue in either mode (the 20 ns UI needs about 35 MHz). At 6 pF in 20 k mode the model predicts about 1 dB peaking and a 14 % overshoot with one ring (12.6 ns to settle to 2 % of a 20 ns UI): this is signal-shaping, not instability, but it adds pattern-dependent ISI that the comparator slicer sees. 5 k mode at 6 pF is clean.

## Sim 3: VCM_REF buffer, OPA2320 half (netlists `spice/sim3_ac.cir`, `sim3_loop.cir`, `sim3_tran.cir`, `sim3_core.inc`)

R100/R101 10 k/10 k + C100 100 n to IN+, follower with feedback from the OUT pin, R102 into C101 1 u (VCM_REF), three 1 k loads from VCM_REF to ground (the spec case; DC 1.65 mA each, so the DC drop across R102 is large in this test and the "DC V" is not representative), RD 1 k from the disturbance source (parked at 1.65 V so it draws no DC). Loop probe at IN- as in Sim 1 (the loop includes R102, C101 and the loads). Supply 3.3 V ideal. AC uses the derived no-limit model copy, transients use the TI file. Plots: [closed loop AC](plots/sim3_closed_loop_ac.png), [loop gain](plots/sim3_loop_gain.png), [step](plots/sim3_step.png).

SIMULATED, ngspice 47, TI OPAx320 Final 1.6:

| R102 | op-amp pin peaking (closed loop) | loop crossover | PM | sensitivity peak (max 1/abs(1+T)) | 10 mV step at IN+: overshoot at VCM_REF / at op-amp pin | VCM_REF shift for the 100 mV step via 1 k (plateau) | settle to 0.05 mV |
|---|---|---|---|---|---|---|---|
| 0.01 ohm (control: no isolation) | 33.3 dB at 190 kHz | 190 kHz | 1.2 deg | 33 dB | 96 % (ringing) | n/a (ringing) | 230 us |
| 10 ohm (as drawn) | 0.05 dB at 62 kHz | 2.05 MHz | 87.6 deg | 0.25 dB | 0 % / 0.7 % | 0.96 mV | 28 us |
| 22 ohm | 0.01 dB | 4.0 MHz | 86.2 deg | 0.45 dB | 0 % / 0.1 % | 2.0 mV | 75 us |
| 47 ohm | 0 dB | 7.1 MHz | 84.1 deg | 0.67 dB | 0 % / 0.03 % | 3.9 mV | 172 us |

Loop gain at 10 Hz is about 123 dB. VCM_REF moves by about 1 % of the injected 100 mV, monotonically (first-order, tau about R102 x C101 = 10 us); the op-amp pin itself moves less than 10 uV; no ringing at 10, 22 or 47 ohm. The control row shows the isolation resistor is what stabilises the 1 uF load: without it the model's loop has about 1 deg of phase margin and rings at about 190 kHz, consistent with the datasheet's guidance that the unity-gain OPA320 is only stable to about 1 nF direct load (SBOS513F 7.3.8). So 10 ohm is sufficient in this model, with 84-88 deg of margin (and a sensitivity peak under 1 dB); no larger R is required. A larger R only costs DC accuracy and source impedance (3.9 mV per 100 uA of return current at 47 ohm). The simulation does not include the OPA2320's second channel or supply impedance, and the load is only resistive (no capacitive loads on the downstream nets).

## Limitations (all sims)

- Vendor macromodels, not silicon: bandwidth, slew, overdrive, output swing and bias polarity are what TI modelled (the OPA855 low limit and bias sign differ from the datasheet, see issues 2 and 3). No temperature or tolerance sweeps (RF/RG/C at 1 %, C at 10-20 %); no corner models.
- No PCB parasitics in Sims 1-3 (lumped 0.3 to 1.0 pF on the OPA855 IN- and OUT are covered in the review-P3 section below), no package parasitics on FB/IN-, no pad capacitance, ideal supplies and ideal VCM_REF (Sims 1, 2), ideal 3.3 V supply (Sim 3). The OPA855's recommended FB-to-IN- layout (SBOS622D p.17, p.29) is not represented as geometry.
- Sim 1 source is an ideal source behind 25 ohm: the real OPA857 output impedance, the R58 tap, the RSSI diode and the OPA855's own input capacitance (0.6 pF CM, 0.2 pF diff per datasheet) are not in the loop. The cascade OPA857 -> C51 -> OPA855 was not simulated end to end.
- Photodiode model in Sim 2 is capacitance only; no APD multiplication noise, dark current, series resistance or optical rise/fall beyond the 2 ns edges.
- Sim 3 settling numbers depend on the OPA320 model's output stage and on the 1 k loads; real return currents are microamps.
- The OPA855 AC phase polarity issue above (issue 1). The OPA855 and OPA320/OPA857 AC runs are partly built on patched or reinterpreted linearisations; the transient results are the more reliable evidence.

## Not done

- No end-to-end TIA -> post-amp -> comparator simulation, no noise or BER, no TLV3605 model (none obtained).
- No fix for the OPA855 AC polarity quirk; a PSpice/TINA run of the same netlist would settle whether it is ngspice-specific.
- Review P3: the parasitic values are the reviewer's hand estimates, not extracted from the board; no trace inductance or delay; the 2 ns system edges were not re-run with parasitics.

## OPA855 with layout parasitics (review P3, 2026-10-22)

Status: **PROPOSED (simulated, not measured)**. Same TI OPA855 Rev A macromodel, circuit and loop probe as Sim 1 (RF 301 / RG 49.9, gain 7.03), with lumped capacitors added: CP from the IN- pin node to ground and CP from OUT to ground (same value on both, a hand estimate from the review, not extracted from the board), and optionally CF = 0.1 pF across R53 (stray). The review (docs/review/2026-10-22-rev-a-review/README.md P3) asks for this because the board has no plane window under IN-, FB and OUT, contrary to the OPA855 layout guidance (SBOS622D section 9.4.1, Fig. 9-12), and the review's hand estimate was 10 to 15 degrees of phase-margin loss. CP sits on the op-amp side of the loop break. Metric: PM = 180 - |angle of T at |T| = 1|, with the lower-confidence caveat of issue 1 above (ngspice AC polarity quirk); peaking and -3 dB are on v(OUT) closed loop relative to 100 kHz (the closed-loop magnitude was checked against transient in Sim 1); overshoot is a 10 mV step with 0.2 ns edges (stress case) at OUT, Sim 1b method.

| CP (IN- and OUT) | CF across R53 | PM | T crossover | OUT closed-loop peaking | OUT -3 dB | overshoot, 0.2 ns edges |
|---|---|---|---|---|---|---|
| 0 (baseline = Sim 1) | 0 | 77.1 deg | 1.04 GHz | 0.10 dB @ 128 MHz | 2.13 GHz | 3.2 % |
| 0.3 pF | 0 | 76.1 deg | 1.04 GHz | 0.13 dB @ 276 MHz | 3.09 GHz | 3.4 % |
| 0.5 pF | 0 | 75.4 deg | 1.04 GHz | 0.37 dB @ 853 MHz | 2.82 GHz | 6.6 % |
| 1.0 pF | 0 | 73.7 deg | 1.05 GHz | 1.79 dB @ 1.11 GHz | 2.39 GHz | 16.6 % |
| 0 | 0.1 pF | 86.3 deg | 1.06 GHz | 0.08 dB | 1.32 GHz | 2.0 % |
| 0.3 pF | 0.1 pF | 85.3 deg | 1.07 GHz | 0.09 dB | 1.60 GHz | 2.7 % |
| 0.5 pF | 0.1 pF | 84.6 deg | 1.07 GHz | 0.10 dB | 1.84 GHz | 3.4 % |
| 1.0 pF | 0.1 pF | 82.9 deg | 1.07 GHz | 0.43 dB | 2.22 GHz | 5.8 % |

Reading (all SIMULATED, model-limited):

- In this model 0.5 pF on IN- and OUT costs about 1.7 degrees of PM (77.1 to 75.4), and 1.0 pF about 3.4 degrees; the review's 10 to 15 degree hand estimate is not reproduced. The loop crossover barely moves (about 1.04 GHz) because the capacitors load a low-impedance feedback node (RF || RG about 43 ohm) and a 25 ohm-class output; |T| flattens at about -4 dB between 2 and 3 GHz and does not recross 0 dB in any case.
- The visible effect is closed-loop peaking in the 0.8 to 1.1 GHz region: 0.37 dB at 0.5 pF and 1.8 dB at 1.0 pF, and a 0.2 ns-edge overshoot of 6.6 % and 16.6 % (3.2 % baseline). At the 2 ns-class edges this system actually sees (Sim 1b) the effect would be far smaller; that was not re-run here. Downstream, the 68 MHz R56/C54 low-pass removes this peaking from the comparator input, so the practical consequence is margin and not eye shape (reasoning, not simulated).
- CF = 0.1 pF across R53 adds PM (to about 85 deg at 0.5 pF) and removes the peaking, at the cost of OUT bandwidth (-3 dB 1.3 to 2.2 GHz, still far above the 68 MHz low-pass). It is a feedback-zero effect: it helps only if the real stray value is near 0.1 pF; the case is a bounding check, not a prediction, and should not be relied on as margin.
- Limits: lumped C only, no layout inductance or trace delay, no OPA855 package/pad capacitance beyond the macromodel (which has none, see the provenance table), ideal VCM_REF, ideal source behind 25 ohm. The OPA855 margin measured on the board (G1, small-signal and step at the post-amp output, with TP10 stub and without) is still required; nothing here is measured.

Files: decks `spice/opa855-parasitic-postamp.cir` (closed-loop AC and transient) and `spice/opa855-parasitic-loop.cir` (loop gain), parameters CP and CF; `spice/run_opa855_parasitic.sh` (sweep), `spice/analyze_opa855_parasitic.py` (metrics to `spice/out/opa855-parasitic_metrics.json`); plots [AC and loop gain](plots/opa855-parasitic-ac.png), [step](plots/opa855-parasitic-step.png). The Sim 1 decks are unmodified.

Commands (from `docs/simulation/spice`, venv python with numpy and matplotlib):

```
./run_opa855_parasitic.sh
python -I analyze_opa855_parasitic.py
```
