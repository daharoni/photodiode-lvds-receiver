# Optical link budget: LED to PIN photodiode / APD and OPA857 TIA

Generated with `python3 tools/link_budget.py --sweep` and `--apd-sweep` (stdlib only; `--help` lists all parameters).
**2026-10-22: see "Revision 2026-10-22 (review A1, A2)" at the end.** The APD target-emitter power below is
energy-inconsistent (229 % wall-plug efficiency) and the 35 MHz noise bandwidth is not the built chain's ~70 MHz;
the sections below are kept unchanged for comparison only.
Goal: 50 Mbaud 8b/10b NRZ (UI 20 ns), 70 cm lateral coverage diameter (35 cm radius), receiver 50 cm above the
animal. Q = 6.0 is BER 1e-9 (design point); Q = 3.09 is BER 1e-3 (floor).

## Method

1. **LED intensity.** Red: mcd converted with I_e = I_v / (683 lm/W x V(625 nm)), V = 0.321 -> 530 mcd = 2.42 mW/sr.
2. **Irradiance.** Lambertian order m = -ln2 / ln(cos(half-angle)) (140 deg -> m = 0.646).
   E = I_e cos^m(theta) / d^2 x T_filter x cos(theta_rx); LED points up, receiver looks down, h = 50 cm.
3. **Collected power** P = E x A_detector x G_optics (G limited by etendue, below).
4. **Photocurrent** I_ph = R x P (x M for an APD). OOK: I_pp = I_on (1 - 1/ER), default ER = infinity.
5. **Noise.** Shot noise sqrt(2q(I_avg+I_dark+I_amb)B) (x M sqrt(F) for an APD) plus TIA noise. APD excess noise F = M^x (x = 0.3, Hamamatsu; default) or McIntyre kM + (2-1/M)(1-k) via
   `--excess-model mcintyre`; the output states which is used. TIA noise is
   i_rms(135 MHz) x sqrt(B/135 MHz), a **lower bound** at B = 35 MHz (flat density; DATASHEET-DERIVED), and the full
   15 nA (20k) / 25 nA (5k) as the **upper bound**; the true value lies between because the density rises with
   frequency (e_n x C term). Every Q is reported for both: **Q_lo** (low-noise bound, optimistic) and **Q_hi**.
6. **Q = (I_pp/2)/i_noise**, BER = 0.5 erfc(Q/sqrt2). TIA swing = I_pp x R_T versus ~1.2 V; VGA gain = 1 Vpp / swing.
7. **First-order bandwidth** f = 1/(2 pi R_T (C_pd + 1.5 pF)), flagged below 50 MHz. Indicator only.
8. **Emitter average electrical power** = I x V_f x 0.5 (NRZ 50% duty).

## Etendue limit (the key physics result)

A lossless concentrator or lens obeys A_in sin^2(theta_fov) <= A_d sin^2(90 deg) = A_d (detector in air), so
**G_optics <= 1 / sin^2(theta_fov)**. `etendue_max_gain()` implements it; the CLI refuses a larger `--gain`.

| FOV half-angle | +/-80 | +/-60 | +/-45 | +/-30 | +/-20 | +/-10 | +/-5 |
|---|---|---|---|---|---|---|---|
| Max optical gain | 1.0x | 1.3x | **2x** | **4x** | 8.5x | **33x** | 132x |

For a 1 mm diode, +/-45 deg caps gain at 2x (3 dB), +/-30 deg at 4x (6 dB), +/-10 deg at 33x (15 dB). Gain is bought
only by giving up field of view, which is why the earlier compound parabolic concentrator could not have helped at wide FOV.

## Assumptions

DATASHEET = vendor document; DATASHEET-DERIVED = scaled from one; ASSUMED = engineering estimate. Verify before sign-off.

| Item | Value | Label |
|---|---|---|
| Red Wurth 150060RS75003 | 530 mcd @ 20 mA, 140 deg, 30 mA cont.; V_f 2.0 V | DATASHEET (brief); V_f ASSUMED |
| V(625 nm); mcd to W/sr | 0.321; 2.42 mW/sr at 20 mA | ASSUMED (approx.) |
| NIR QT Brightek QBLP601-2IR4 | 1.0 mW/sr typ @ 20 mA (0.2 min), 140 deg, 50 mA cont.; V_f 1.5 V | DATASHEET (brief), typ not min; V_f ASSUMED |
| Intensity vs current | linear in I | ASSUMED (optimistic: droop, heating) |
| Beam pattern | cos^m from the viewing angle | ASSUMED |
| OSRAM SFH 4550 v1.8 (2021-11-18) | 1100 mW/sr typ @ 100 mA (710..2800), half angle 3 deg, IF max 100 mA, V_f 1.5 V, tr = tf = 12 ns; 1 A pulsed (tp <= 400 us, D <= 0.5%) 8500 mW/sr | DATASHEET |
| OSRAM SFH 4715AS | 900 mW/sr typ (710..1120) @ 1 A; rise 11 ns, fall 14 ns (Farnell) | DATASHEET (product page / distributor; PDF not retrieved) |
| SFH 4715AS beam, V_f, 1 A at 50% duty | +/-45 deg (sources say 80 or 90 full); V_f 3.2 V typ (DigiKey); duty allowed? | ASSUMED / UNVERIFIED |
| OPA857 noise, 135 MHz brickwall, Cs = 1.5 pF | 15 nA rms (20k), 25 nA rms (5k), SBOS630D | DATASHEET |
| OPA857 noise at 35 MHz | 7.64 nA (20k) / 12.7 nA (5k) low bound; 15 / 25 nA high bound | DATASHEET-DERIVED |
| OPA857 Fig. 9/10 at 6 pF | ~26 nA (20k), ~44 nA (5k) at 135 MHz | read visually from plot, +/-2 nA |
| OPA857 usable swing | ~1.2 V | ASSUMED |
| FDS010 | O1.02 mm, 0.43 A/W @ 630, 0.40 @ 765, 6 pF @ 10 V | DATASHEET (brief) |
| FDS010 R @ 850 nm; dark current | 0.50 A/W; 1 nA | ASSUMED |
| S5972 | O0.8 mm, 3 pF, 0.5 A/W @ 765 (0.40 @ 625, 0.55 @ 850) | DATASHEET approx.; 625/850 ASSUMED |
| Hypothetical PIN | O3 mm, 25 pF, 0.5 A/W @ 765, 5 nA dark | ASSUMED |
| Hamamatsu S12023-10 | O1.0 mm, 6 pF, 0.5 A/W @ 800 nm, M max 100, dark 0.2 nA total at M = 100, F = M^0.3 | DATASHEET (KAPD1007E19) |
| Hamamatsu R at 625/765/850 nm | 0.30 / 0.47 / 0.48 A/W (QE curve scaled to the 800 nm value) | GRAPH-READ + DERIVED |
| Hamamatsu S12023-05; S3884 | O0.5 mm, 2 pF, 0.1 nA dark; O1.5 mm, 10 pF, 0.5 nA dark; both M max 100, R as -10 | DATASHEET; R DERIVED |
| Excelitas C30902EH | O0.5 mm, 1.6 pF, 77 A/W @ 830 nm at M = 150 -> 0.51 A/W (used at all wavelengths; 625/765 NOT FOUND), dark 15 nA at M = 150, k = 0.02, M max 150 | DATASHEET; 0.51 DERIVED |
| APD excess noise; dark current | F = M^x, x = 0.3 (default); McIntyre k = 0.02 (alternative, always for C30902EH); total dark at datasheet M used as primary (pessimistic) | DATASHEET (x, Excelitas k); Hamamatsu k, dark use DERIVED |
| OPA857 noise with APD capacitance | Sweeps use the 1.5 pF bounds. At 6 pF (S12023-10, as for FDS010) the higher ~26 nA (135 MHz) applies; S12023-05 at 2 pF is near the 1.5 pF datasheet condition; S3884 at 10 pF is worse (~33 nA) | see Fig. 9 row |
| Parasitic C; noise bandwidth; filter T | 1.5 pF; 35 MHz (0.7 x bit rate); 0.9 | ASSUMED |
| Ambient photocurrent | 0 nA (`--ambient-nA`) | ASSUMED (optimistic) |
| Wall-plug efficiency for flux to electrical power | 30% | ASSUMED (optimistic) |
| Noise model | no 1/f, VGA or comparator noise | ASSUMED (optimistic) |
| Detector optics | bare, FOV 90 deg, gain 1x | ASSUMED |

## Single-point output (default run, red part)

```
--- Red Wurth 150060RS75003 (625 nm) @ 20 mA (I_e=2.417 mW/sr, m=0.646)
  Avg electrical power  :       20.0 mW  (I x Vf x 0.5)
  Irradiance E          :     4.2066 mW/m^2
  Collected power       :     3.4373 nW   (optical gain 1x)
  Photocurrent (on)     :     1.4780 nA   (R=0.43 A/W, M=1)
  TIA swing (pp)        :      29.56 uV   [ok vs 1.2 V]
  Noise (rms, input)    :      7.639 nA low bound .. 15.001 nA high bound
  Q = (Ipp/2)/i_n       :     0.0967 (low-noise) .. 0.0493 (high-noise)   need 6.00 for 1e-9, 3.09 for 1e-3
  BER (ideal NRZ)       :  4.615e-01 (low-noise) .. 4.804e-01 (high-noise)
  VGA gain for 1 Vpp    :    33828.5x = 90.6 dB  [ABOVE range; range 10-100x]
  1st-order TIA RC BW   :       1.06 MHz  [BELOW bit rate]
```

## Sweep output (verbatim)

Bare FDS010, 20k, 50 cm height, gain 1x. Tables 1 to 4: LEDs and emitter targets; 5: detectors (S12023-10 at M = 50, F = M^0.3);
6: power budgets; 7: noise at the real 6 pF. ">1e9" = unrealisable; negative dB = margin. Etendue: see above.

```
Q needed: BER 1e-9 -> 6.00; BER 1e-3 -> 3.09
Detector FDS010 (diam 1.02 mm), R_T=20k, height 50 cm, T=0.9, B=35 MHz, gain 1x, ER=inf, ambient 0 nA
TIA noise at 20k: low bound 7.64 nA (15 nA x sqrt(B/135 MHz)), high bound 15.00 nA (15 nA); Q_lo uses low bound, Q_hi uses high bound

TABLE 1: link budget vs lateral offset (Pavg = I x Vf x 0.5)
emitter  I(mA) Pavg(mW)  off   E(mW/m2)     P(nW)   Iph(nA)   Vpp(uV)  in_lo  in_hi     Q_lo     Q_hi    BER_lo    BER_hi   VGA(x)
----------------------------------------------------------------------------------------------------------------------------------
red         20       20    0        8.7      7.11      3.06      61.2   7.64  15.00      0.2    0.102  4.21e-01  4.59e-01 1.64e+04
red         20       20   10        8.1      6.62      2.85      56.9   7.64  15.00    0.186   0.0949  4.26e-01  4.62e-01 1.76e+04
red         20       20   20       6.64      5.43      2.33      46.7   7.64  15.00    0.153   0.0778  4.39e-01  4.69e-01 2.14e+04
red         20       20   35       4.21      3.44      1.48      29.6   7.64  15.00   0.0967   0.0493  4.61e-01  4.80e-01 3.38e+04
red         20       20   50       2.46      2.01     0.864      17.3   7.64  15.00   0.0566   0.0288  4.77e-01  4.89e-01 5.79e+04

red         30       30    0       13.1      10.7      4.59      91.7   7.64  15.00      0.3    0.153  3.82e-01  4.39e-01 1.09e+04
red         30       30   10       12.2      9.93      4.27      85.4   7.64  15.00    0.279    0.142  3.90e-01  4.43e-01 1.17e+04
red         30       30   20       9.96      8.14       3.5        70   7.64  15.00    0.229    0.117  4.09e-01  4.54e-01 1.43e+04
red         30       30   35       6.31      5.16      2.22      44.3   7.64  15.00    0.145   0.0739  4.42e-01  4.71e-01 2.26e+04
red         30       30   50       3.69      3.01       1.3      25.9   7.64  15.00   0.0849   0.0432  4.66e-01  4.83e-01 3.86e+04

nir         20       15    0        3.6      2.94      1.18      23.5   7.64  15.00    0.077   0.0392  4.69e-01  4.84e-01 4.25e+04
nir         20       15   10       3.35      2.74       1.1      21.9   7.64  15.00   0.0717   0.0365  4.71e-01  4.85e-01 4.56e+04
nir         20       15   20       2.75      2.24     0.898        18   7.64  15.00   0.0588   0.0299  4.77e-01  4.88e-01 5.57e+04
nir         20       15   35       1.74      1.42     0.569      11.4   7.64  15.00   0.0372    0.019  4.85e-01  4.92e-01 8.79e+04
nir         20       15   50       1.02     0.831     0.333      6.65   7.64  15.00   0.0218   0.0111  4.91e-01  4.96e-01  1.5e+05

nir         50       38    0          9      7.35      2.94      58.8   7.64  15.00    0.193    0.098  4.24e-01  4.61e-01  1.7e+04
nir         50       38   10       8.38      6.85      2.74      54.8   7.64  15.00    0.179   0.0913  4.29e-01  4.64e-01 1.83e+04
nir         50       38   20       6.87      5.61      2.24      44.9   7.64  15.00    0.147   0.0748  4.42e-01  4.70e-01 2.23e+04
nir         50       38   35       4.35      3.55      1.42      28.4   7.64  15.00   0.0931   0.0474  4.63e-01  4.81e-01 3.52e+04
nir         50       38   50       2.54      2.08     0.831      16.6   7.64  15.00   0.0544   0.0277  4.78e-01  4.89e-01 6.01e+04

sfh4550    100       75    0   3.96e+03  3.24e+03  1.62e+03  3.24e+04   8.21  15.30     98.5     52.9  0.00e+00  0.00e+00     30.9
sfh4550    100       75   10      0.185     0.151    0.0757      1.51   7.64  15.00  0.00495  0.00252  4.98e-01  4.99e-01 6.61e+05
sfh4550    100       75   20   1.63e-13  1.33e-13  6.65e-14  1.33e-12   7.64  15.00 4.35e-15 2.22e-15  5.00e-01  5.00e-01     >1e9
sfh4550    100       75   35   3.73e-41  3.04e-41  1.52e-41  3.04e-40   7.64  15.00 9.97e-43 5.07e-43  5.00e-01  5.00e-01     >1e9
sfh4550    100       75   50   1.18e-73  9.64e-74  4.82e-74  9.64e-73   7.64  15.00 3.15e-75 1.61e-75  5.00e-01  5.00e-01     >1e9

sfh4715   1000     1600    0   3.24e+03  2.65e+03  1.32e+03  2.65e+04   8.11  15.25     81.6     43.4  0.00e+00  0.00e+00     37.8
sfh4715   1000     1600   10   2.94e+03   2.4e+03   1.2e+03   2.4e+04   8.07  15.22     74.4     39.4  0.00e+00  0.00e+00     41.7
sfh4715   1000     1600   20   2.24e+03  1.83e+03       913  1.83e+04   7.97  15.17     57.3     30.1  0.00e+00 2.08e-199     54.7
sfh4715   1000     1600   35    1.2e+03       977       488  9.77e+03   7.82  15.09     31.2     16.2 1.12e-214  3.28e-59      102
sfh4715   1000     1600   50        573       468       234  4.68e+03   7.72  15.04     15.1     7.78  3.87e-52  3.70e-15      214

TABLE 2: on-axis radiant intensity (mW/sr) needed for Q = 6.0, bare FDS010, R_T=20k, gain 1x, 850 nm (R=0.5), T=0.9
  columns: low-noise bound / high-noise bound; LED points up, receiver at 50 cm height
full view      m    Ie@0cm lo           hi   Ie@35cm lo           hi   Ie@50cm lo           hi
----------------------------------------------------------------------------------------------
        6  505.4         62.6          123         >1e9         >1e9         >1e9         >1e9
       20   45.3         62.6          123     9.48e+05     1.86e+06         >1e9         >1e9
       40   11.1         62.6          123     1.05e+03     2.06e+03     8.42e+03     1.65e+04
       60    4.8         62.6          123          297          583          940     1.84e+03
       90    2.0         62.6          123          170          332          354          694
      140    0.6         62.6          123          129          254          221          434
  Ie = on-axis value required; >1e9 = not realisable (narrow beam pointed away).

TABLE 3: radiant flux and average electrical power for Q = 6.0 at 35 cm lateral (flux = Ie x 2pi/(m+1); Pel = on-flux / WPE x 0.5, WPE = 30% ASSUMED)
full view  flux lo(mW)  flux hi(mW)   Pel lo(mW)   Pel hi(mW)
-------------------------------------------------------------
       40          543     1.06e+03          905     1.77e+03
       60          321          629          535     1.05e+03
       90          355          696          592     1.16e+03
      140          494          968          824     1.61e+03

TABLE 4: shortfall to Q = 6.0 at 35 cm lateral (optical dB = 10log10(factor); photocurrent dB = 2x)
emitter  I(mA) Pavg(mW)     Q_lo     Q_hi short_lo(dB) short_hi(dB)  factor lo  factor hi    Ie need lo..hi(mW/sr)
------------------------------------------------------------------------------------------------------------------
red         20       20   0.0967   0.0493         17.9         20.9       62.3        122               150.5..295
red         30       30    0.145   0.0739         16.2         19.1       41.5       81.3               150.5..295
nir         20       15   0.0372    0.019         22.1         25.0        162        317             161.8..317.1
nir         50       38   0.0931   0.0474         18.1         21.0       64.7        127             161.8..317.1
sfh4550    100       75 9.97e-43 5.07e-43        300.0        300.0       >1e9       >1e9               >1e9..>1e9
sfh4715   1000     1600     31.2     16.2         -7.2         -4.3      0.188      0.369             169.6..332.3
  (factor applies equally to optical gain OR emitter intensity; negative dB = margin)

TABLE 5: detector trade at 35 cm lateral, max continuous current, gain 1x; APD at M = 50
det       emit       RT  A(mm2) C(pF)   Iph(nA)  in_lo  in_hi     Q_lo     Q_hi f_RC(MHz) BW>=bit
-------------------------------------------------------------------------------------------------
FDS010    nir        5k    0.82     6     1.422  12.73  25.00   0.0558   0.0284      4.24      NO
FDS010    nir       20k    0.82     6     1.422   7.64  15.00   0.0931   0.0474      1.06      NO
FDS010    sfh4715    5k    0.82     6     488.5  12.84  25.05       19     9.75      4.24      NO
FDS010    sfh4715   20k    0.82     6     488.5   7.82  15.09     31.2     16.2      1.06      NO
S5972     nir        5k    0.50     3     1.093  12.73  25.00   0.0429   0.0219      7.07      NO
S5972     nir       20k    0.50     3     1.093   7.64  15.00   0.0716   0.0364      1.77      NO
S5972     sfh4715    5k    0.50     3     330.5  12.80  25.04     12.9      6.6      7.07      NO
S5972     sfh4715   20k    0.50     3     330.5   7.76  15.06     21.3       11      1.77      NO
PIN3mm    nir        5k    7.07    25     15.38  12.73  25.00    0.604    0.307      1.20      NO
PIN3mm    nir       20k    7.07    25     15.38   7.65  15.00     1.01    0.512      0.30      NO
PIN3mm    sfh4715    5k    7.07    25      4648  13.72  25.52      169     91.1      1.20      NO
PIN3mm    sfh4715   20k    7.07    25      4648   9.19  15.85      253      147      0.30      NO
S12023-10 nir        5k    0.79     6     80.29  15.90  26.76     2.52      1.5      4.24      NO
S12023-10 nir       20k    0.79     6     80.29  12.22  17.77     3.29     2.26      1.06      NO
S12023-10 sfh4715    5k    0.79     6 2.254e+04 143.57 145.17     78.5     77.6      4.24      NO
S12023-10 sfh4715   20k    0.79     6 2.254e+04 143.21 143.79     78.7     78.4      1.06      NO
  f_RC = 1/(2 pi R_T (C_pd+1.5 pF)): first-order indicator only (pessimistic for a fast TIA).

TABLE 6: Q at 35 cm lateral (and 0 cm) for an AVERAGE emitter-power budget, bare FDS010, 20k, low/high noise
  I = P / (Vf x 0.5), capped at the continuous rating; 'spread140' = same radiant flux spread into a 140 deg cos^m beam
emitter  budget  I(mA)  Pavg Ie(mW/sr)   Q35 lo   Q35 hi    Q0 lo    Q0 hi  spread140 Q35 lo       hi
-----------------------------------------------------------------------------------------------------
sfh4550     50    66.7    50     733.3 6.64e-43 3.38e-43     67.2     35.5             0.111   0.0565
sfh4550    100*  100.0    75      1100 9.97e-43 5.07e-43     98.5     52.9             0.166   0.0847
sfh4715     50    31.2    50     28.12    0.998    0.509      2.7     1.38             0.718    0.366
sfh4715    100    62.5   100     56.25        2     1.02     5.39     2.75              1.43    0.731
  * budget exceeds the continuous current rating; drive capped (Pavg shown is the capped power).

TABLE 7: sensitivity to source capacitance: TIA noise from OPA857 Fig. 9 (20k) read at C_pd (READ VISUALLY, +/-2 nA)
  FDS010 C = 6 pF -> Fig. 9 reads 26 nA rms (135 MHz) vs 15 nA at Cs = 1.5 pF; 5k (Fig. 10) reads 44 nA vs 25 nA
emitter  I(mA)     Q_lo     Q_hi short_lo(dB) short_hi(dB)
----------------------------------------------------------
red         20   0.0563   0.0286         20.3         23.2
red         30   0.0844    0.043         18.5         21.5
nir         20   0.0216    0.011         24.4         27.4
nir         50   0.0541   0.0276         20.5         23.4
sfh4715   1000     18.4     9.45         -4.9         -2.0
```

## APD sweep output (verbatim, `--apd-sweep`)
Q as low / high noise bound; Table B: minimum M and average emitter electrical power.
```
APD SWEEP: 35 cm lateral, 50 cm height, 850 nm, R_T=20k, T=0.9, B=35 MHz, gain 1x, ER=inf, ambient 0 nA
Excess noise model: F = M^x (Hamamatsu, x per part); McIntyre k=0.02 for parts with no x (C30902EH)
TIA noise at 20k (OPA857 datasheet bounds at Cs = 1.5 pF): low 7.64 nA, high 15.00 nA; Q_lo = low-noise bound, Q_hi = high-noise bound
Target Q: 6.00 (BER 1e-9), 3.09 (BER 1e-3).  R at 850 nm for all emitters (NIR baseline is 765 nm; ~2% diff).
Emitters: NIR QBLP601 50 mA: Ie 2.5 mW/sr, 50.0 mA, Pavg 37.5 mW; 30 mW/sr 140deg: Ie 30 mW/sr, 33.3 mA, Pavg 25.0 mW; 100 mW/sr 140deg: Ie 100 mW/sr, 111.1 mA, Pavg 83.3 mW  (Vf 1.5 V, 50% duty; targets at 0.9 mW/sr/mA)
TABLE A: Q (low-noise bound / high-noise bound) vs avalanche gain M
APD          M     NIR QBLP601 50 mA       30 mW/sr 140deg      100 mW/sr 140deg
S12023-10   10      1.05 /    0.544      10.9 /     6.26      28.5 /       19
S12023-10   20      1.97 /     1.07      15.1 /     10.7      31.9 /       27
S12023-10   30      2.64 /     1.54        16 /     13.1      31.4 /       29
S12023-10   50      3.34 /      2.3      15.8 /     14.6      29.7 /     28.9
S12023-10   75      3.59 /     2.87      15.2 /     14.6      28.1 /     27.8
S12023-10  100      3.62 /     3.14      14.6 /     14.3        27 /     26.8
S12023-05   10     0.267 /    0.136      3.07 /     1.62      9.35 /     5.25
S12023-05   20     0.522 /    0.271      5.29 /     3.09      13.4 /     9.22
S12023-05   30     0.752 /    0.402      6.47 /     4.28      14.4 /     11.5
S12023-05   50      1.11 /    0.645      7.22 /     5.75      14.4 /     13.1
S12023-05   75      1.36 /    0.895      7.25 /     6.46      13.9 /     13.3
S12023-05  100      1.47 /     1.08       7.1 /     6.65      13.4 /     13.1
S3884       10      2.31 /     1.22      21.2 /     13.3      49.2 /     37.3
S3884       20      4.02 /     2.33      25.2 /     20.3      49.8 /     45.7
S3884       30      4.97 /     3.25      25.2 /     22.7      47.9 /     46.1
S3884       50       5.6 /     4.41      24.1 /     23.2      44.8 /     44.2
S3884       75      5.66 /        5      22.9 /     22.5      42.2 /       42
S3884      100      5.55 /     5.17        22 /     21.8      40.5 /     40.4
C30902EH    10     0.225 /    0.135      2.63 /      1.6      8.19 /     5.21
C30902EH    20     0.296 /    0.223      3.37 /     2.59      9.99 /     8.03
C30902EH    30     0.309 /    0.264      3.48 /     3.02      10.1 /     9.07
C30902EH    50     0.301 /    0.283      3.36 /     3.19      9.71 /     9.33
C30902EH    75     0.282 /    0.275      3.14 /     3.08      9.05 /     8.91
C30902EH   100     0.264 /    0.261      2.95 /     2.92      8.48 /     8.41
  M max (datasheet): S12023-10 100, S12023-05 100, S3884 100, C30902EH 150; excess noise per part: S12023-10 F = M^0.3, S12023-05 F = M^0.3, S3884 F = M^0.3, C30902EH McIntyre k=0.02

TABLE B: minimum M for Q = 6 and Q = 3.09 (lo / hi noise bound) and average emitter power
APD       emitter              I(mA) Pavg(mW)   Q6 lo   Q6 hi  3.09 lo  3.09 hi   Qmax lo (M)   Qmax hi (M)
-----------------------------------------------------------------------------------------------------------
S12023-10 NIR QBLP601 50 mA     50.0     37.5    none    none     40.4     93.4    3.62 (M93)   3.32 (M168)
S12023-10 30 mW/sr 140deg       33.3     25.0    4.82    9.54     2.42     4.75   16.07 (M35)   14.72 (M62)
S12023-10 100 mW/sr 140deg     111.1     83.3    1.41    2.77        1     1.42   31.94 (M21)   29.25 (M37)
S12023-05 NIR QBLP601 50 mA     50.0     37.5    none    none     none     none   1.53 (M158)   1.40 (M285)
S12023-05 30 mW/sr 140deg       33.3     25.0    25.1    55.8     10.1       20    7.28 (M62)   6.67 (M112)
S12023-05 100 mW/sr 140deg     111.1     83.3    5.84    11.6      2.9     5.72   14.55 (M38)   13.32 (M68)
S3884     NIR QBLP601 50 mA     50.0     37.5    none    none       14     28.1    5.67 (M65)   5.19 (M117)
S3884     30 mW/sr 140deg       33.3     25.0    2.09    4.12     1.07      2.1   25.40 (M24)   23.26 (M44)
S3884     100 mW/sr 140deg     111.1     83.3       1    1.22        1        1   50.49 (M14)   46.24 (M26)
C30902EH  NIR QBLP601 50 mA     50.0     37.5    none    none     none     none    0.31 (M32)    0.28 (M51)
C30902EH  30 mW/sr 140deg       33.3     25.0    none    none     14.3     33.4    3.48 (M31)    3.19 (M48)
C30902EH  100 mW/sr 140deg     111.1     83.3    6.04    12.1     2.79      5.5   10.16 (M28)    9.36 (M44)
  '!' = above that part's datasheet maximum M; 'none' = never reached for M <= 1000; Qmax = peak of Q(M), set by excess noise;
  1 = target already met at M = 1.

Ambient saturation (OPA857 20k linear range 60 uA): in-band ambient power on the die P_sat = 60 uA / (M x R850)
  S12023-10  R850 0.48 A/W: M=50: 2.50 uW, M=100: 1.25 uW
  S12023-05  R850 0.48 A/W: M=50: 2.50 uW, M=100: 1.25 uW
  S3884      R850 0.48 A/W: M=50: 2.50 uW, M=100: 1.25 uW
  C30902EH   R850 0.51 A/W: M=50: 2.35 uW, M=100: 1.18 uW
```

## What this means for the design

**Does a bare FDS010 close the 70 cm diameter link with the current LEDs? No.** At 35 cm lateral Q is 0.04 to 0.10
(low-noise bound) or 0.02 to 0.05 (high-noise bound), versus 6 needed. Shortfall to Q = 6 (Table 4, optical dB, a range over the
two noise bounds): **red 20 mA 17.9 to 20.9 dB; red 30 mA 16.2 to 19.1; NIR 20 mA 22.1 to 25.0; NIR 50 mA 18.1 to 21.0**
(photocurrent amplitude: double these). Using the larger noise the OPA857 actually shows at 6 pF source capacitance
(Table 7, Fig. 9 read), NIR 50 mA is 20.5 to 23.4 dB short. The BER 1e-3 floor (Q = 3.09) is still ~15 to 19 dB away.
The cause: photocurrent is 0.6 to 3 nA, TIA noise alone is 7.6 to 15 nA. Q = 6 needs about 90 to 180 nA peak-to-peak
(roughly 0.2 to 0.4 uW on the diode), against 1 to 3 nW received. This is why the old SiPM's internal gain mattered.

**OPA857 Fig. 9/10 check.** `pdftotext` gives only axis labels (0 to 100 nA rms vs 0 to 25 pF), no curve data; reading the
rendered plot gives about 26 nA (20k) and 44 nA (5k) at 135 MHz for a 6 pF source, versus 15 / 25 nA at 1.5 pF. So for FDS010 the
"high bound" of 15 nA is not an upper limit; the plausible range at 35 MHz is roughly 13 nA (26 x sqrt(35/135)) to 26 nA.

Levers, in order of leverage (numbers are at 35 cm lateral, 50 cm height):

1. **Emitter radiant intensity and power (primary; the headstage emitter is free to change).** Table 2 is the target for a bare
   FDS010 at 850 nm: on-axis **129 to 254 mW/sr (140 deg beam), 170 to 332 (90 deg), 297 to 583 (60 deg), 1050 to 2060 (40 deg)**;
   not realisable for 20 deg or narrower unless the receiver is overhead (Ie at 0 cm is 63 to 123 mW/sr for any angle). A
   narrow beam raises mW/sr but falls as cos^m off axis, so it needs the receiver roughly above the animal (SFH 4550, +/-3 deg:
   Q = 98/53 at 0 cm, 0.005 at 10 cm, 0 at 35 cm). **Power is the real constraint.** Table 3 converts the target to radiant
   flux: Q = 6 at 35 cm needs about **320 to 970 mW of optical flux** whatever the beam angle (minimum near 60 to 90 deg),
   i.e. ~0.5 to 1.6 W average electrical at 30% wall-plug efficiency, against about 200 mW average for the whole headstage
   (~500 mW wireless power). **A 1 A continuous emitter is not compatible with that budget**: SFH 4715AS at 1 A is 0.75 W average
   at V_f = 1.5 V and 1.6 W at its typical 3.2 V. (It reaches Q = 31/16 at 35 cm, but only by spending that power; 1 A at
   50% duty is also unverified.) Best mW/sr per mA found is SFH 4550 (11 mW/sr/mA, narrow beam); best wide-angle is SFH 4715AS (0.9 mW/sr/mA).
   Table 6, Q at 35 cm (low/high noise), bare FDS010:

   | Average power budget | SFH 4550 as is (+/-3 deg) | same flux spread to 140 deg | SFH 4715AS (+/-45 deg) |
   |---|---|---|---|
   | 50 mW (67 mA / 31 mA) | ~0 (Q = 67/35 at 0 cm) | 0.11 / 0.057 | **1.0 / 0.51** |
   | 100 mW (SFH 4550 capped at 100 mA = 75 mW) | ~0 (Q = 98/53 at 0 cm) | 0.17 / 0.085 | **2.0 / 1.0** |

   Neither budget reaches Q = 3.09 at 35 cm with a bare FDS010; the spread-beam figure is a flux-conserving cos^m estimate.
   Radiant intensity scales linearly with current here, which is optimistic at high drive.
2. **Receiver placement/redundancy.** Irradiance goes as 1/d^2, so halving distance gains 6 dB (scaling law, not scripted).
   Offset matters less than height: red 20 mA changes only ~3 dB between 0 and 35 cm (Q_lo 0.20 to 0.097). Smaller per-receiver
   radius with more receivers helps a few dB per halving; it does not alone replace 18 to 21 dB. Receivers must also be near
   the animal for narrow-beam emitters.
3. **Larger-area detector.** The 3 mm PIN has 8.7x the area (+9.4 dB), but 25 pF: first-order RC bandwidth 0.30 MHz at 20k
   (1.2 MHz at 5k) versus 1.06 / 4.2 MHz for FDS010, and noise at 25 pF would be much larger than the 1.5 pF datasheet figure (Fig. 9).
   Q_lo for NIR 50 mA is 1.0 (3 mm, 20k) versus 0.093 (FDS010). S5972 loses 2.1 dB of area. **Every detector fails the
   first-order 50 MHz check (Table 5)**; that formula is pessimistic (loop gain extends bandwidth) but bandwidth must be settled
   separately; all Q values assume B = 35 MHz is achieved.
4. **APD (datasheet parameters, `--apd-sweep`).** The baseline NIR LED at 50 mA (2.5 mW/sr, 37.5 mW) cannot reach Q = 6 with any
   S12023 at any M (S12023-10 peaks at Q = 3.6, M ~ 93; Q = 3.09 needs M = 40 to 93; S12023-05 peaks at 1.5).
   **S12023-10 is the variant that gets there (4x the area of -05): with a 30 mW/sr 140 deg emitter (33 mA, 25 mW average) Q = 6 needs
   M = 4.8 (low) to 9.5 (high noise) (Q = 3.09: 2.4 to 4.8); with 100 mW/sr (111 mA, 83 mW average) M = 1.4 to 2.8 (Q = 3.09 at M = 1 to 1.4).**
   S12023-05 needs M = 25 to 56 at 30 mW/sr and 5.8 to 11.6 at 100 mW/sr. S3884 (10 pF) needs M = 2.1 to 4.1 at 30 mW/sr but its
   capacitance hurts TIA noise and bandwidth (stretch); C30902EH needs M = 6.0 to 12.1 at 100 mW/sr and never reaches Q = 6 at 30 mW/sr.
   So an APD cuts the required emitter from the PIN's 129 to 254 mW/sr to ~30 mW/sr (25 mW average) at M ~ 5 to 10. The sweeps use the
   1.5 pF TIA bounds; at 6 pF the OPA857 noise is higher (~26 nA at 135 MHz), which raises these M values somewhat (not scripted).
   **Ambient saturation:** P_sat = 60 uA / (M x R) = **2.5 uW at M = 50, 1.25 uW at M = 100** (R = 0.48 A/W) of in-band light on the die
   (~12 to 25 uW at M = 5 to 10): filter, servo or AC-couple the DC ambient. Costs: 130 to 200 V bias, temperature compensation.
5. **Optics within the etendue limit.** 2x (3 dB) at +/-45 deg, 4x (6 dB) at +/-30 deg, 33x (15 dB) at +/-10 deg. Closing the
   62 to 122x (17.9 to 20.9 dB) for red 20 mA by optics alone needs ~+/-7 to 5 deg FOV, which covers only about 4.5 to 6 cm radius at 50 cm height.

Approximations affecting these numbers: linear intensity vs current; Lambertian beam; OPA857 noise bounds (scaling, and the
6 pF Fig. 9 read-off); ambient = 0; no 1/f/VGA/comparator noise; 850 nm responsivities; SFH 4715AS beam angle, V_f and duty;
WPE = 30%; flux-conserving beam spreading; APD x/k, graph-read responsivities and the C30902EH 0.51 A/W; the first-order bandwidth formula.
Sources: OSRAM SFH 4550 datasheet v1.8 (2021-11-18); ams-osram.com SFH 4715AS page (710..1120, typ 900 mW/sr at 1000 mA);
Farnell SFH 4715AS listing (rise 11 ns, fall 14 ns); TI OPA857 SBOS630D (`docs/datasheets/opa857.pdf`).

## Revision 2026-10-22 (review A1, A2)

Everything in this section is **PROPOSED**: estimates from datasheets, a cos^m beam model and a noise model.
Nothing here is measured, and nothing is simulated beyond the cited ngspice bandwidth runs. **The received optical
power has NOT been measured**; that is review item A4 (docs/review/2026-10-22-rev-a-review/README.md) and stays
open. The sections above are kept unchanged for comparison; where they conflict with this section, this section
supersedes them. Generated with `python3 tools/link_budget.py --apd-budget` and `--apd-sweep` (stdlib only, run
2026-10-23).

### What changed in `tools/link_budget.py`

1. `--bw-mhz` now defaults to **70 MHz**, the noise-equivalent bandwidth (NEB) of the built chain (Table R0), instead
   of 35 MHz (0.7 x bit rate). `--bw-mhz 35` reproduces the old Tables 1-7 exactly except the NIR Pavg column (item 4).
2. `--apd-sweep` uses the OPA857 Fig. 9 noise at each APD's capacitance by default (S12023-10 at 6 pF: 25.8 nA in
   135 MHz; SBOS630D Fig. 9, p.9, read visually +/-2 nA); `--tia-cs datasheet` restores 15 nA (1.5 pF).
3. The APD target emitters are costed from **radiant flux** (flux = Ie x 2 pi/(m+1)) and a wall-plug efficiency
   (WPE), not from 0.9 mW/sr/mA. Two WPEs are reported: 11.9 %, derived from the reference QBLP601-2IR4 (1.0 mW/sr
   at 20 mA, 140 deg, Vf 1.6 V typ; datasheet V1.0 2021-09-17, docs/research/link-components.md section 4; the flux
   is DERIVED with the cos^m beam, the datasheet gives no flux), and the existing 30 % (ASSUMED, optimistic).
4. The NIR QBLP601 Vf is now the datasheet 1.6 V typ (was 1.5 V ASSUMED); Pavg at 50 mA is 40 mW (was 37.5).
5. New mode `--apd-budget` (Tables R0-R5): chain NEB, energy check of the old targets, required Ie at the Q-optimal
   M, Q vs M sweep, dynamic range in optical dB (electrical dB alongside), and the weak-end margin row.
   Optical dB = 10 log10(P2/P1) = (20 log10(I2/I1)) / 2 = electrical dB / 2, because photocurrent is proportional
   to optical power (square-law detector).
6. `--m-min` (default 5, ASSUMED: the M floor at the 100 V bias minimum is UNRESOLVED) sets the strong-end range.

### Claim-by-claim check of review A1/A2

**Claim 1 (emitter energy). CONFIRMED.** The old `--apd-sweep` priced its 140 deg targets at 0.9 mW/sr/mA, which is
the SFH 4715AS figure (900 mW/sr at 1 A, assumptions table above; a +/-45 deg part per the same table, beam angle
ASSUMED/UNVERIFIED). Arithmetic (Table R1): m(140 deg) = -ln2/ln(cos 70 deg) = 0.646, so flux = Ie x 2 pi/1.646 =
Ie x 3.817 sr. 30 mW/sr -> 114.5 mW of optical flux in the on state, from 33.3 mA x 1.5 V = 50 mW electrical:
**WPE 229 %**, which is impossible (the 100 mW/sr case is the same 229 %). The reference QBLP601 gives 3.82 mW flux
from 32 mW, **11.9 %**. Even on its own part the 0.9 mW/sr/mA figure needs a narrow beam and a high Vf to be
physical: at +/-45 deg (m = 2.00, 2.094 sr) 900 mW/sr is 1885 mW of flux, 126 % WPE at Vf 1.5 V and 59 % at 3.2 V.
The SFH 4715AS datasheet is not in the repo (product page and distributor listing only), so its beam angle, flux
and Vf are **UNRESOLVED**; the corrected budget does not depend on them because it uses flux and WPE.

**Claim 2 (noise bandwidth). CONFIRMED; with an APD at its optimum M the penalty is larger than 1.5 dB.**
The chain is OPA857 20k (105 MHz at 1.5 pF, SBOS630D p.6, VERIFIED; 99 MHz at 6 pF, ngspice, SIMULATED,
docs/schematic/frontend.md) into the R56 49.9 ohm / C54 47 pF low-pass (67.9 MHz, frontend.md item 5); no 35 MHz
filter exists. Table R0 (2nd-order TIA, Q 0.707-0.8, times the one-pole low-pass): **NEB 65-73 MHz**. If the
datasheet's 135 MHz-brickwall figure already includes the OPA857 roll-off, the equivalent B in the
I135 x sqrt(B/135 MHz) scaling is 85-89 MHz, so 70 MHz is if anything optimistic (by about 0.4 dB optical). Effect:
- PIN / TIA-noise-limited: noise x sqrt(2) = 3.0 dB electrical = **1.5 dB optical** (the reviewer's figure). The
  `--sweep` Table 4 FDS010 low-bound shortfall moves from 17.9 dB (red 20 mA, 35 MHz) to 19.5 dB at 70 MHz (the
  high bound stays 20.9 dB because it is the full 135 MHz noise by construction).
- APD at the Q-optimal M: the excess-noise shot term also scales with B, so the required optical power rises about
  as B^0.88 (Q_opt is proportional to P^0.565 for F = M^0.3): **2.2-2.5 dB optical** for 35 -> 70 MHz at 1.5 pF
  (Table R2: 5.59 -> 9.98 mW/sr low bound, 6.51 -> 10.73 high bound). The 6 pF Fig. 9 noise adds another 0.5 dB
  (-> 11.25 / 12.12 mW/sr). From the old assumptions to the built chain: **2.7-3.0 dB optical** in total.

**Claim 3 (Q-optimal M). CONFIRMED: 83-112 for the built chain at the Q = 6 point (reviewer: 86-114).** The optimum
satisfies M^(2+x) = 2 i_tia^2 / (x 2q I_avg B): it depends on the signal and rises as the signal falls. The old
"M 35-62" (and architecture.md "Q(M) peaks at M 35-60") came from the 30 mW/sr target, whose signal was inflated
by the claim-1 error; at the sensitivity limit the optimum is set by the noise alone, and even the old 35 MHz /
1.5 pF assumptions give 69-117 (Table R2). The S12023-10 datasheet specifies its characteristics at M = 100
(KAPD1007E19 table, note 5; docs/research/apd-selection.md), which this budget treats as M max. The cap costs
almost nothing (Table R3: Q 6.00 at M 86 vs 5.97 at M 100, low bound; 5.75 vs 5.74, high bound) because the peak is
flat, but it leaves **no upward M headroom** at the weak end, and M ~ 100 is where the bias tempco and the VBR
spread (150 V typ / 200 V max) matter most.

**Claim 4 (range figures are electrical dB). CONFIRMED on units; the single-setting window is smaller than the
reviewer estimated.** "39 dB single-setting + 32 dB firmware" (decision 12) are 20 log I ratios, about 19.5 dB and
16 dB optical. Table R4 recomputes them for the built chain with the Q = 6 floor **including the APD excess shot
noise**: at the Q-optimal M the shot variance is 2/x = 6.7 times the TIA variance, so the floor is 0.61-0.80 uA pp
of multiplied photocurrent, not 0.22-0.29 uA (12 x TIA noise alone, the reviewer's floor).

| Window (built case; low / high noise bound) | Optical dB | Electrical dB |
|---|---|---|
| Q = 6 floor to post-amp clip (7.85-9.03 uA pp, 20k, M at the weak-end optimum 83 / 100) | 11.1-11.7 / 9.9-10.6 | 22-23 / 20-21 |
| Q = 6 floor to OPA857 saturation (60 uA; slicing through the post-amp clip, PROPOSED in post-amp-slicer.md) | 19.9 / 18.8 | 40 / 38 |
| Firmware: M 83-100 -> 5 (M floor ASSUMED) | 12.2-13.0 | 24-26 |
| Firmware: 20k -> 5k (post-amp clip 18.2k/4.5k; TIA saturation 240/60 uA) | 6.0-6.1 | 12 |
| Firmware extension at the **weak** end | **0** | 0 |

The old "39 dB" single-setting figure therefore matches the floor-to-TIA-saturation window in electrical dB (about
19 dB optical); the clean, unclipped window is only 10-12 dB optical. Every firmware knob lowers gain, so range
control extends only the strong end and the **fade margin equals the emitter margin** (Table R5). Post-amp clip
levels: Vswing 1.0 Vpp (VOL 1.15 V max, VOH 2.35 V min at 3.3 V, symmetric about 1.65 V; OPA855 SBOS622D p.7,
VERIFIED) to 1.15 Vpp (post-amp-slicer.md), divided by G = 7 x Rt_eff 18.2k / 4.5k (OPA857 SBOS630D p.6 note 4).
OPA857 saturation 60 / 240 uA (SBOS630D p.15, section 7.3.1).

### Headline numbers before and after (PROPOSED; 35 cm lateral, 50 cm height, 140 deg emitter, S12023-10, 20k)

| Quantity | Before (budget above) | After (this revision) |
|---|---|---|
| Noise bandwidth | 35 MHz (ASSUMED) | 70 MHz (built NEB 65-73 MHz) |
| TIA noise, low / high bound | 7.6 / 15 nA (1.5 pF) | 18.6 / 25.8 nA (6 pF, Fig. 9) |
| Emitter needed for Q = 6 | "30 mW/sr, Q = 6 at M 4.8-9.5" | **11.3-12.1 mW/sr** at M 83-100 (zero margin) |
| Its optical flux | not stated (114.5 mW implied for 30 mW/sr) | 43-46 mW |
| Its average electrical power | "25 mW" (229 % WPE) | **72-77 mW** at 30 % WPE (ASSUMED); **180-194 mW** at the QBLP601's 11.9 % |
| Q-optimal M | 35-62 (30 mW/sr case) | **83-112** (capped at 100) |
| Relative to the reference QBLP601 | "modestly brighter" | 4.5-4.8x (6.5-6.9 dB) its 50 mA maximum; 11-12x its 20 mA typ |
| Single-setting range | "~39 dB" (electrical) | 10-12 dB optical unclipped; about 19-20 dB optical to TIA saturation |
| Firmware range | "~32 dB" (electrical) | 18-19 dB optical, strong end only |
| Weak-end margin, QBLP601 at 50 mA | not stated | **-6.5 to -6.9 dB** optical vs Q = 6; -1.8 to -2.4 dB vs Q = 3.09 |
| Weak-end margin, 30 mW/sr | implied large | +3.9 to +4.3 dB vs Q = 6, at 191 mW (30 %) / 480 mW (11.9 %) average |

The ~200 mW whole-headstage power figure quoted in lever 1 above is not in requirements.md; its source is
UNRESOLVED. Against it, closing Q = 6 at 35 cm with zero margin takes 36-97 % of the headstage budget for the
emitter alone (30 % vs 11.9 % WPE, driver losses excluded). Decision 8 (APD) still stands: at 70 MHz the bare
FDS010 PIN needs 183-254 mW/sr (`--sweep` Table 2, 140 deg, 850 nm, 1.5 pF noise bounds), 15-23x more. What changes is the wording: the APD closes the link only
with an emitter about 5x the reference QBLP601 at 50 mA, and whether the headstage can power it is UNRESOLVED
(emitter co-design, requirements row 1b; measure the delivered power first, review A4).

Not in these numbers (all optimistic omissions): ambient (0 nA; its shot noise is multiplied by M sqrt(F)),
comparator offset (+/-5 mV max, review B1) and comparator noise, 1/f noise, ISI from the 0.97 dB 20k peaking at
6 pF (SIMULATED), LED rise time, tilt, shadowing, intensity droop with current and temperature, and driver losses.

### `--apd-budget` output (verbatim)

```
APD BUDGET (review A1/A2): S12023-10 (diam 1.0 mm, 6 pF, R850 0.48 A/W, F = M^0.3), OPA857 20k, 35 cm lateral, 50 cm height, T = 0.9, 850 nm, ER = inf, ambient 0 nA, M cap 100 (datasheet)
Q target 6.00 (BER 1e-9), floor 3.09 (BER 1e-3).  Optical dB = 10log(P ratio) = electrical (20log I) dB / 2.

TABLE R0: noise-equivalent bandwidth of the built chain: OPA857 2nd-order x one-pole 67.9 MHz low-pass (R56 49.9 / C54 47 pF)
f_TIA(MHz)  Q_TIA  NEB(MHz)  B_eq vs 135 MHz spec(MHz)
        99  0.707      64.9                       89.1
        99  0.800      70.9                       86.2
       106  0.707      66.9                       87.8
       106  0.800      72.9                       84.8
  Default --bw-mhz = 70 (NEB). B_eq applies if the datasheet 135 MHz brickwall figure already includes the
  OPA857 roll-off; then 70 MHz is optimistic by ~0.4 dB optical. One-pole 68 MHz alone has NEB 107 MHz.

TABLE R1: energy check of the old --apd-sweep targets (0.9 mW/sr/mA, Vf 1.5 V, 140 deg)
emitter                Ie(mW/sr)   I(mA) P_el,on(mW)  flux(mW)  implied WPE
30 mW/sr 140deg (old)         30    33.3        50.0     114.5         229%
100 mW/sr 140deg (old)       100   111.1       166.7     381.7         229%
QBLP601 20 mA                  1    20.0        32.0      3.82        11.9%
SFH 4715AS 1 A, Vf 1.5       900    1000        1500      1885         126%
SFH 4715AS 1 A, Vf 3.2       900    1000        3200      1885          59%
  flux = Ie x 2pi/(m+1): 140 deg (m 0.646) -> 3.817 sr; +/-45 deg (m 2.00) -> 2.094 sr.

TABLE R2: on-axis Ie needed at 35 cm lateral (140 deg beam) at the Q-optimal M (M <= 100); Pavg at WPE 11.9% (QBLP601-derived) and 30% (ASSUMED)
case                   bnd i_tia(nA)     Q  M_opt P_die(nW) Ie(mW/sr) flux(mW) Pavg@ref Pavg@30% M_opt free
-----------------------------------------------------------------------------------------------------------
old: 35 MHz, 1.5 pF     lo       7.6  6.00     69      7.64      5.59     21.3       89       36         69
old: 35 MHz, 1.5 pF     lo       7.6  3.09    100      2.69      1.97      7.5       31       13        101
old: 35 MHz, 1.5 pF     hi      15.0  6.00    100      8.90      6.51     24.9      104       41        117
old: 35 MHz, 1.5 pF     hi      15.0  3.09    100      3.34      2.44      9.3       39       16        175
70 MHz, 1.5 pF          lo      10.8  6.00     55     13.64      9.98     38.1      160       63         55
70 MHz, 1.5 pF          lo      10.8  3.09     84      4.58      3.35     12.8       54       21         85
70 MHz, 1.5 pF          hi      15.0  6.00     71     14.66     10.73     41.0      172       68         71
70 MHz, 1.5 pF          hi      15.0  3.09    100      4.91      3.60     13.7       58       23        110
BUILT: 70 MHz, 6 pF     lo      18.6  6.00     83     15.38     11.25     42.9      180       72         83
BUILT: 70 MHz, 6 pF     lo      18.6  3.09    100      5.22      3.82     14.6       61       24        128
BUILT: 70 MHz, 6 pF     hi      25.8  6.00    100     16.57     12.12     46.3      194       77        108
BUILT: 70 MHz, 6 pF     hi      25.8  3.09    100      5.92      4.33     16.5       69       28        169
  P_die = on-state power on the bare die: 1.367 nW per mW/sr of on-axis Ie at this geometry.
  'M_opt free' = optimum without the M <= 100 cap. Pavg (mW) = flux/WPE x 0.5 (emitter only; driver losses not included).

TABLE R3: Q (lo / hi bound) vs M, built case, for three emitters at 35 cm lateral
    M           QBLP601 50 mA         Ie 11.3 (Q6 lo)             Ie 30 mW/sr
   10        0.44 /     0.32         1.94 /     1.41         4.98 /     3.69 
   20        0.86 /     0.63         3.56 /     2.69         8.27 /     6.61 
   30        1.23 /     0.92         4.67 /     3.72         9.80 /     8.42 
   50        1.78 /     1.41         5.69 /     4.98        10.57 /     9.87 
   75        2.15 /     1.83         5.99 /     5.58        10.47 /    10.15 
   86        2.24 /     1.95         6.00 /     5.68        10.35 /    10.11 
  100        2.31 /     2.07         5.97 /     5.74        10.20 /    10.03 
  114        2.35 /     2.15!        5.93 /     5.75!       10.05 /     9.92!
  150        2.39 /     2.25!        5.78 /     5.68!        9.71 /     9.64!
  200        2.36 /     2.29!        5.59 /     5.54!        9.33 /     9.30!
  QBLP601 50 mA: Q-optimal M 150 (lo, Q 2.39) / 201 (hi, Q 2.29)
  Ie 11.3 (Q6 lo): Q-optimal M 83 (lo, Q 6.00) / 112 (hi, Q 5.75)
  Ie 30 mW/sr: Q-optimal M 55 (lo, Q 10.59) / 74 (hi, Q 10.15)
  '!' = above the datasheet M of 100. Q-optimum: M^(2+x) = 2 i_tia^2 / (x 2q I_avg B), so it rises as the signal falls.

TABLE R4: dynamic range, built case, in on-die optical power (on-state) and both dB conventions; firmware M floor 5 (ASSUMED)
level                                                bnd  I_pp(uA)  P_die(nW)  opt dB  el dB
--------------------------------------------------------------------------------------------
Q = 3.09 floor at M 83, 20k                           lo     0.216      5.409    -4.5   -9.1
Q = 6 floor (weak end) at M 83, 20k                   lo     0.614      15.38     0.0    0.0
post-amp clip 1 Vpp, M 83, 20k                        lo      7.85      196.6    11.1   22.1
post-amp clip 1.15 Vpp, M 83, 20k                     lo      9.03      226.1    11.7   23.3
OPA857 saturation 60 uA, M 83, 20k                    lo        60       1503    19.9   39.8
post-amp clip 1 Vpp, M 5, 5k (firmware)               lo      31.7  1.323e+04    29.3   58.7
post-amp clip 1.15 Vpp, M 5, 5k (firmware)            lo      36.5  1.521e+04    30.0   59.9
OPA857 saturation 240 uA, M 5, 5k (firmware)          lo       240      1e+05    38.1   76.3
  lo: single setting (M 83, 20k), Q = 6 to post-amp clip: 11.1 to 11.7 dB optical; to OPA857 saturation: 19.9 dB optical
  lo: firmware extension (strong end only): M 83 -> 5 = 12.2 dB optical; 20k -> 5k = 6.1 dB optical (post-amp clip), 6.0 dB (TIA saturation); weak-end extension 0 dB
Q = 3.09 floor at M 100, 20k                          hi     0.284      5.918    -4.5   -8.9
Q = 6 floor (weak end) at M 100, 20k                  hi     0.795      16.57     0.0    0.0
post-amp clip 1 Vpp, M 100, 20k                       hi      7.85      163.5     9.9   19.9
post-amp clip 1.15 Vpp, M 100, 20k                    hi      9.03      188.1    10.6   21.1
OPA857 saturation 60 uA, M 100, 20k                   hi        60       1250    18.8   37.6
post-amp clip 1 Vpp, M 5, 5k (firmware)               hi      31.7  1.323e+04    29.0   58.0
post-amp clip 1.15 Vpp, M 5, 5k (firmware)            hi      36.5  1.521e+04    29.6   59.3
OPA857 saturation 240 uA, M 5, 5k (firmware)          hi       240      1e+05    37.8   75.6
  hi: single setting (M 100, 20k), Q = 6 to post-amp clip: 9.9 to 10.6 dB optical; to OPA857 saturation: 18.8 dB optical
  hi: firmware extension (strong end only): M 100 -> 5 = 13.0 dB optical; 20k -> 5k = 6.1 dB optical (post-amp clip), 6.0 dB (TIA saturation); weak-end extension 0 dB
  Electrical (20log I) dB = 2 x optical dB. Firmware knobs (lower M, 5k) only LOWER gain: they move the
  strong end; the weak end is fixed by M <= 100 and 20k, so fade margin = emitter margin (row R5).

TABLE R5: weak-end margin, built case, optical dB above the Q = 6 and Q = 3.09 floors at the best M <= 100 (lo / hi bound)
emitter (140 deg)      Ie(mW/sr) Pavg@ref Pavg@30% off(cm) P_die(nW)  Q6 lo  Q6 hi Q3.09 lo Q3.09 hi
----------------------------------------------------------------------------------------------------
QBLP601 20 mA                  1       16        6      35      1.37  -10.5  -10.8     -5.8     -6.4
QBLP601 20 mA                  1       16        6       0      2.83   -7.4   -7.7     -2.7     -3.2
QBLP601 50 mA                2.5       40       16      35      3.42   -6.5   -6.9     -1.8     -2.4
QBLP601 50 mA                2.5       40       16       0      7.07   -3.4   -3.7      1.3      0.8
target 10 mW/sr               10      160       64      35      13.7   -0.5   -0.8      4.2      3.6
target 10 mW/sr               10      160       64       0      28.3    2.6    2.3      7.3      6.8
target 30 mW/sr               30      480      191      35        41    4.3    3.9      9.0      8.4
target 30 mW/sr               30      480      191       0      84.8    7.4    7.1     12.1     11.6
target 100 mW/sr             100     1600      636      35       137    9.5    9.2     14.2     13.6
target 100 mW/sr             100     1600      636       0       283   12.6   12.3     17.3     16.8
  Negative = short of the floor. Pavg in mW (emitter only). Margin excludes ambient (0), comparator offset
  and noise, 1/f, ISI, tilt, shadowing and the unmeasured received power (review A4).
```

### `--apd-sweep` output (verbatim; corrected emitters, 70 MHz, Fig. 9 noise)

Supersedes the "APD sweep output" block above, which is kept for comparison. The drive currents for the targets are
what an LED of QBLP601 efficiency would need; they exceed the QBLP601's 50 mA rating and serve only as a power
yardstick.

```
APD SWEEP: 35 cm lateral, 50 cm height, 850 nm, R_T=20k, T=0.9, B=70 MHz, gain 1x, ER=inf, ambient 0 nA
Excess noise model: F = M^x (Hamamatsu, x per part); McIntyre k=0.02 for parts with no x (C30902EH)
TIA noise at 20k, i135 per APD (OPA857 Fig. 9 read at the APD capacitance): S12023-10 25.8 nA -> low 18.6 nA, S12023-05 16.8 nA -> low 12.1 nA, S3884 33.0 nA -> low 23.8 nA, C30902EH 15.8 nA -> low 11.4 nA; Q_lo = low-noise bound (i135 sqrt(B/135 MHz)), Q_hi = high-noise bound (i135)
Target Q: 6.00 (BER 1e-9), 3.09 (BER 1e-3).  R at 850 nm for all emitters (NIR baseline is 765 nm; ~2% diff).
Emitters (140 deg, flux = Ie x 2pi/(m+1) = Ie x 3.817 sr; current at the QBLP601 WPE 11.9%, Vf 1.6 V; Pavg = flux/WPE x 0.5):
  NIR QBLP601 50 mA   Ie    2.5 mW/sr, flux    9.5 mW, I    50.0 mA, Pavg   40.0 mW at WPE 11.9% ( 15.9 mW at 30% ASSUMED)
  10 mW/sr 140deg     Ie     10 mW/sr, flux   38.2 mW, I   200.0 mA, Pavg  160.0 mW at WPE 11.9% ( 63.6 mW at 30% ASSUMED)
  30 mW/sr 140deg     Ie     30 mW/sr, flux  114.5 mW, I   600.0 mA, Pavg  480.0 mW at WPE 11.9% (190.9 mW at 30% ASSUMED)
  100 mW/sr 140deg    Ie    100 mW/sr, flux  381.7 mW, I  2000.0 mA, Pavg 1600.0 mW at WPE 11.9% (636.2 mW at 30% ASSUMED)
TABLE A: Q (low-noise bound / high-noise bound) vs avalanche gain M
APD          M     NIR QBLP601 50 mA       10 mW/sr 140deg       30 mW/sr 140deg      100 mW/sr 140deg
S12023-10   10      0.438 /    0.317      1.73 /     1.26      4.98 /     3.69      14.8 /     11.5
S12023-10   20      0.855 /    0.625      3.19 /     2.41      8.27 /     6.61        20 /     17.6
S12023-10   30       1.23 /    0.915      4.23 /     3.35       9.8 /     8.42        21 /     19.6
S12023-10   50       1.78 /     1.41      5.25 /     4.55      10.6 /     9.87      20.6 /     20.1
S12023-10   75       2.15 /     1.83      5.57 /     5.16      10.5 /     10.1      19.7 /     19.5
S12023-10  100       2.31 /     2.07      5.58 /     5.34      10.2 /       10        19 /     18.9
S12023-10  150!      2.39 /     2.25      5.42 /     5.32      9.71 /     9.64      17.9 /     17.9
S12023-05   10      0.169 /    0.122     0.669 /    0.485      1.96 /     1.44      6.05 /     4.59
S12023-05   20      0.331 /    0.241      1.27 /    0.943      3.46 /     2.67      9.04 /      7.6
S12023-05   30      0.481 /    0.355      1.75 /     1.35      4.34 /     3.58      9.95 /        9
S12023-05   50      0.722 /    0.558      2.32 /     1.93      4.98 /      4.5      10.1 /      9.7
S12023-05   75      0.908 /    0.748      2.58 /     2.31      5.07 /     4.83      9.76 /      9.6
S12023-05  100          1 /    0.871      2.64 /     2.47      4.99 /     4.85      9.43 /     9.35
S12023-05  150!      1.06 /    0.985       2.6 /     2.53      4.78 /     4.73      8.93 /      8.9
S3884       10      0.769 /    0.556      3.01 /      2.2      8.58 /     6.42      24.6 /     19.6
S3884       20       1.49 /     1.09      5.43 /     4.15      13.6 /     11.1      31.5 /     28.3
S3884       30        2.1 /     1.58      6.98 /     5.66      15.5 /     13.7      32.2 /     30.6
S3884       50       2.93 /     2.37      8.26 /     7.35      16.2 /     15.4      31.1 /     30.6
S3884       75       3.41 /     2.97      8.55 /     8.06      15.8 /     15.5      29.7 /     29.5
S3884      100       3.58 /     3.27      8.46 /     8.19      15.4 /     15.2      28.5 /     28.4
S3884      150!      3.61 /     3.46      8.15 /     8.04      14.6 /     14.5      26.9 /     26.9
C30902EH    10      0.154 /    0.122     0.611 /    0.484       1.8 /     1.43      5.63 /     4.59
C30902EH    20      0.206 /    0.183     0.813 /    0.724      2.35 /     2.11      6.99 /     6.39
C30902EH    30      0.217 /    0.204     0.853 /    0.803      2.44 /     2.31      7.14 /     6.84
C30902EH    50      0.212 /    0.207     0.831 /    0.813      2.37 /     2.33      6.85 /     6.75
C30902EH    75      0.199 /    0.197     0.779 /    0.773      2.22 /      2.2      6.39 /     6.36
C30902EH   100      0.187 /    0.186     0.731 /    0.728      2.08 /     2.08      5.99 /     5.98
C30902EH   150      0.167 /    0.167     0.655 /    0.654      1.87 /     1.86      5.36 /     5.36
  '!' = above datasheet M. M max (datasheet): S12023-10 100, S12023-05 100, S3884 100, C30902EH 150; excess noise per part: S12023-10 F = M^0.3, S12023-05 F = M^0.3, S3884 F = M^0.3, C30902EH McIntyre k=0.02

TABLE B: minimum M for Q = 6 and Q = 3.09 (lo / hi noise bound) and average emitter power at the QBLP601 WPE
APD       emitter              I(mA) Pavg(mW)   Q6 lo   Q6 hi  3.09 lo  3.09 hi   Qmax lo (M)   Qmax hi (M)
-----------------------------------------------------------------------------------------------------------
S12023-10 NIR QBLP601 50 mA     50.0     40.0    none    none     none     none   2.39 (M150)   2.29 (M200)
S12023-10 10 mW/sr 140deg      200.0    160.0    none    none     19.2     26.9    5.60 (M88)   5.36 (M116)
S12023-10 30 mW/sr 140deg      600.0    480.0    12.5    17.6     5.95     8.28   10.59 (M56)   10.15 (M73)
S12023-10 100 mW/sr 140deg    2000.0   1600.0    3.46    4.81     1.76     2.44   21.04 (M33)   20.16 (M44)
S12023-05 NIR QBLP601 50 mA     50.0     40.0    none    none     none     none   1.07 (M174)   1.02 (M232)
S12023-05 10 mW/sr 140deg      200.0    160.0    none    none     none     none   2.64 (M107)   2.53 (M143)
S12023-05 30 mW/sr 140deg      600.0    480.0    none    none     17.1     24.1    5.07 (M69)    4.86 (M92)
S12023-05 100 mW/sr 140deg    2000.0   1600.0    9.88    13.9     4.66     6.48   10.14 (M41)    9.71 (M55)
S3884     NIR QBLP601 50 mA     50.0     40.0    none    none     55.9     82.9   3.62 (M129)   3.47 (M172)
S3884     10 mW/sr 140deg      200.0    160.0    23.1    32.8     10.3     14.3    8.55 (M76)   8.19 (M101)
S3884     30 mW/sr 140deg      600.0    480.0    6.66    9.28     3.34     4.64   16.20 (M48)   15.52 (M64)
S3884     100 mW/sr 140deg    2000.0   1600.0    1.94     2.7        1     1.38   32.22 (M29)   30.86 (M38)
C30902EH  NIR QBLP601 50 mA     50.0     40.0    none    none     none     none    0.22 (M33)    0.21 (M42)
C30902EH  10 mW/sr 140deg      200.0    160.0    none    none     none     none    0.85 (M33)    0.82 (M41)
C30902EH  30 mW/sr 140deg      600.0    480.0    none    none     none     none    2.45 (M32)    2.35 (M39)
C30902EH  100 mW/sr 140deg    2000.0   1600.0    11.5    16.5     4.32     6.02    7.14 (M29)    6.88 (M35)
  '!' = above that part's datasheet maximum M; 'none' = never reached for M <= 1000; Qmax = peak of Q(M) over M <= 1000, set by excess noise;
  1 = target already met at M = 1.

Ambient saturation (OPA857 20k linear range 60 uA): in-band ambient power on the die P_sat = 60 uA / (M x R850)
  S12023-10  R850 0.48 A/W: M=50: 2.50 uW, M=100: 1.25 uW
  S12023-05  R850 0.48 A/W: M=50: 2.50 uW, M=100: 1.25 uW
  S3884      R850 0.48 A/W: M=50: 2.50 uW, M=100: 1.25 uW
  C30902EH   R850 0.51 A/W: M=50: 2.35 uW, M=100: 1.18 uW
```

### Collection credits and the emitter working point (2026-10-23)

Everything in this subsection is **PROPOSED**: beam, integrating-sphere and noise models with the inputs tagged
ASSUMED or UNRESOLVED below. **Nothing is measured**; review A4 (received power in the real arena) is the
measurement that settles it. Generated with `python3 tools/link_budget.py --credits` (defaults; flags `--arena-rho`,
`--arena-s`, `--arena-side-cm`, `--optics-gain`, `--led-vf`, `--led-wpe`, `--margin-db`). Context: Daniel's three
points of 2026-10-23: optics will sit in front of the APD, the APD's NIR quantum efficiency beats the old SiPM's (that
one is already in the numbers: 0.48 A/W at 850 nm), and the headstage runs in an enclosure with light-reflecting
walls, so the LED illuminates the arena rather than forming a point-to-point path. The revision above is the
**direct-path-only, bare-APD** case; its 11 to 12 mW/sr is therefore an upper bound on the emitter, not the
requirement. Three credits are added here, each as an explicit term.

**1. Optics on the direct path (Table C1).** A lossless concentrator or lens in air is etendue-limited to
G_max = 1/sin^2(half-angle): 2x at +/-45 deg (3.0 dB optical), 4x at +/-30 deg (6.0 dB), 8.5x at +/-20 deg (9.3 dB).
Real optics through the TO-18 window get part of this (losses and window geometry UNRESOLVED). In a reflective
arena a narrow field costs less than it would point-to-point because the diffuse light fills in. **Optics cannot
raise the diffuse term**: for a uniform diffuse field the collected power is L x etendue, and a lossless
concentrator conserves etendue (A_in sin^2 theta <= A_die), so the diffuse collection is fixed by the die area.
Choose the optic for the direct geometry and count the diffuse term on the bare die.

**2. Arena diffuse term (Table C2).** Integrating-sphere estimate E = flux x rho / (S x (1 - rho)) on the
0.785 mm^2 die, through the T = 0.9 filter. Inputs: a 50 cm cube with an open top, S = 1.25 m^2 of reflecting
surface (ASSUMED); wall reflectance rho at 850 nm 0.5 and 0.7 (**UNRESOLVED**, and it dominates the estimate).
Result: 0.57 (rho 0.5) to 1.32 (rho 0.7) nW on the die per mW of on-state flux, against 0.36 nW per mW for the
direct path at 35 cm lateral, i.e. **1.6x to 3.7x the direct term**. At the direct-only Q = 6 flux (43 mW) that is
24 to 57 nW of diffuse power on the die next to 15 nW direct. The diffuse term scales with total flux, not with
mW/sr or distance, favours the wide beam, and is immune to the animal's body shadowing the LED. Multipath tail:
mean free path 4V/S = 0.33 m, decay tau = mfp / (c x -ln rho) = 1.6 to 3.1 ns, short against the 20 ns UI.
Caution: the sphere formula treats the open top only through S; counting it as a sixth zero-reflectance face
(S = 1.5 m^2, rho x 5/6) halves the estimate (0.34 / 0.66 nW per mW). Ambient light is diffuse too and is
multiplied by M, so the optical bandpass filter stays mandatory and should be measured in the same arena.

**3. Tiling (Table C3).** Several receivers on one LED, merged in the FPGA. On the direct path the geometric
factor is (h/d)^(m+1)/d^2 with m = 0.646; height dominates d, so moving a receiver from 35 cm lateral to directly
overhead at 50 cm is only +3.2 dB, and a 35 cm grid pitch at the same height gains +1.4 dB at the worst cell
point (+2.2 dB at 17.5 cm). Tiling pays geometrically only if it lets receivers sit closer: directly overhead at
25 cm is +9.2 dB. Its main value is in the margin column: orientation, body shadowing and tilt are the terms
left out of the model, and a tiled set with FPGA selection removes most of them because some receiver sees the
LED near its axis and unshadowed at any moment. The merge is selection of validated 8b/10b copies (requirements
row 5), not combining, so there is no SNR gain from summing lanes. The diffuse term is near-uniform, so tiling
adds only redundancy there.

**4. Emitter working point (Tables C4a, C4b).** On-state flux for Q = 6 at 35 cm lateral with the credits
applied one at a time (optics gain on the direct term only; "3x" is an ASSUMED achieved gain for a +/-30 deg
optic), then the electrical cost at 50 % duty for a power LED with Vf 3.0 V and WPE 30 % (both ASSUMED: no
power-LED datasheet is in the repo; 11.9 % is the QBLP601-derived figure and is the wrong LED class for this).
Electrical columns use the hi (conservative) noise bound.

| Case (zero margin) | On-state flux, lo-hi | Pavg at 30 % | Pavg at 11.9 % | I_on at 3.0 V, 30 % |
|---|---|---|---|---|
| Direct path only, bare APD | 43-46 mW | 77 mW | 194 mW | 51 mA |
| +/-45 deg optics (2x) | 22-23 mW | 39 mW | 97 mW | 26 mA |
| Bare APD plus arena rho 0.5 | 17-18 mW | 30 mW | 75 mW | 20 mA |
| +/-30 optics (3x) plus arena 0.5 | 9-10 mW | 17 mW | 42 mW | 11 mA |
| +/-30 optics (3x) plus arena 0.7 | 6-7 mW | 12 mW | 29 mW | 8 mA |

Those are the floor. Tilt, shadowing, ambient shot noise through the filter, comparator offset, ISI and LED droop
with temperature are all outside the model and all eat weak-end margin that firmware cannot give back (Table R4).
With 6 dB optical margin (4x flux):

| Case (6 dB margin) | On-state flux, lo-hi | Pavg at 30 % | Pavg at 11.9 % | I_on at 3.0 V, 30 % |
|---|---|---|---|---|
| Direct path only, bare APD | 171-184 mW | 307 mW | 772 mW | 205 mA |
| +/-45 deg optics (2x) | 86-92 mW | 154 mW | 386 mW | 102 mA |
| Bare APD plus arena rho 0.5 | 66-71 mW | 119 mW | 299 mW | 79 mA |
| +/-30 optics (3x) plus arena 0.5 | 37-40 mW | 67 mW | 169 mW | 45 mA |
| +/-30 optics (3x) plus arena 0.7 | 26-28 mW | 46 mW | 116 mW | 31 mA |

**Working assumption for the headstage emitter (PROPOSED):** a 1 W class 850 nm LED run well below its rating,
**30 to 100 mA on-state (45 to 150 mW average electrical)** if the optics and the arena deliver what the models
say, **up to 200 mA (about 300 mW average)** if they do not; size the driver for 500 mA so the operating point is
set after A4. With tiling the 6 dB margin comes from receiver selection rather than from more current. The
on-state current is what the driver and LED see; the average is what the battery sees. The ~200 mW headstage
figure remains UNRESOLVED (no source in requirements.md). The arena measurement (A4: photocurrent at M = 1 with
the LED aimed at and away from the receiver, plus ambient, in the real enclosure) collapses these tables to one
row.

**Larger APD, evaluated and not adopted for Rev A (2026-10-23).** The S3884 (1.5 mm, 10 pF, same bias family)
would add 3.5 dB of area, but the OPA857 20k mode rings at 10 pF (SIMULATED: 2.2 dB peaking, 22 % overshoot,
2 % settling longer than one UI), so the net at 50 Mbps with this TIA is about zero; see docs/simulation/README.md
(10 pF run) and docs/research/apd-selection.md. It stays a Rev B option with a discrete TIA and/or a lower rate.

#### `--credits` output (verbatim)

```
COLLECTION CREDITS (2026-10-23): S12023-10 (diam 1.0 mm, 0.785 mm^2), OPA857 20k, 70 MHz NEB, Fig. 9 noise, 35 cm lateral, 50 cm height, 140 deg emitter, T = 0.9, 850 nm, M cap 100
Q target 6.00 (BER 1e-9). All PROPOSED: beam, sphere and noise models, nothing measured (review A4).

Q = 6 floor on the die (best M <= 100): 15.38 nW (lo, M 83) / 16.57 nW (hi, M 100).  Direct path: 1.367 nW per mW/sr = 0.358 nW per mW of flux (140 deg beam, 3.817 sr).

TABLE C1: etendue-limited optical gain on the DIRECT path, detector in air: G_max = 1/sin^2(half-angle)
 FOV half-angle  G_max  optical dB
           45 deg    2.0         3.0
           30 deg    4.0         6.0
           20 deg    8.5         9.3
  Real optics through the TO-18 window get part of G_max (losses, window geometry: UNRESOLVED).
  Optics cannot raise the DIFFUSE term: a lossless concentrator conserves etendue, so collected
  diffuse power is fixed by the die area (A_in sin^2 theta <= A_die).

TABLE C2: arena diffuse term, integrating-sphere estimate E = flux x rho / (S x (1 - rho)); S = 1.25 m^2 (50 cm cube, open top, 5 faces; ASSUMED), x T on the die
 rho (850 nm)   E per mW flux  nW/mW on die  vs direct  nW at Q6 flux  mfp(m)  tau(ns)
         0.50        0.80/m^2         0.565       1.6x           24.3    0.33      1.6
         0.70        1.87/m^2         1.319       3.7x           56.7    0.33      3.1
  'nW at Q6 flux' is for the direct-only Q = 6 flux of 42.9 mW (lo bound), to compare with the
  direct term 15.38 nW. rho at 850 nm is UNRESOLVED and dominates. mfp = 4V/S over all
  6 faces; tau = mfp / (c x -ln rho) is the multipath decay against the 20 ns UI. The open top is not
  a loss in the sphere formula: counting it as a 6th zero-reflectance face (S 1.5 m^2, rho x 5/6) gives
    rho 0.50: 0.337 nW/mW (0.60x of the row above)
    rho 0.70: 0.660 nW/mW (0.50x of the row above)
  Ambient light is diffuse too and is multiplied by M: the optical bandpass filter stays mandatory.

TABLE C3: tiling, direct-path geometry (h/d)^(m+1)/d^2, m = 0.646, relative to 35 cm lateral at 50 cm height
 lateral(cm) height(cm)  d(cm)    rel     dB
        35.0         50   61.0   1.00   +0.0
        25.0         50   55.9   1.38   +1.4
        17.5         50   53.0   1.68   +2.2
         0.0         50   50.0   2.07   +3.2
         0.0         25   25.0   8.28   +9.2
  A 35 cm grid pitch at 50 cm height gains ~1.4 dB at the worst point: height dominates d. Tiling pays
  geometrically only if receivers get closer (lower, or on the walls). Its main value is removing the
  orientation / shadowing terms from the margin: the FPGA selects validated copies (requirements row 5),
  it does not sum lanes, so there is no SNR gain from combining. The diffuse term is near-uniform, so
  tiling adds only redundancy there.

TABLE C4a: emitter working point, Q = 6 at 35 cm lateral, zero margin; 50 % duty; Vf 3 V and WPE 30% ASSUMED, 11.9% = QBLP601-derived
case                               flux lo-hi(mW)  Pavg@30% Pavg@11.9%  I_on(mA) I_avg(mA)
------------------------------------------------------------------------------------------
direct only, bare APD                 42.9-46.3          77        194        51        26
+/-45 deg optics (2x)                 21.5-23.1          39         97        26        13
bare APD + arena rho 0.5              16.7-17.9          30         75        20        10
+/-30 optics (3x) + arena 0.5          9.4-10.1          17         42        11         6
+/-30 optics (3x) + arena 0.7          6.4-6.9           12         29         8         4
  Electrical columns use the hi (conservative) noise bound. Pavg = flux/WPE x 0.5 (emitter only, no driver
  loss); I_on = flux/(WPE x Vf). Optics gain applies to the direct term only.

TABLE C4b: emitter working point, Q = 6 at 35 cm lateral, 6 dB optical margin (3.98x flux); 50 % duty; Vf 3 V and WPE 30% ASSUMED, 11.9% = QBLP601-derived
case                               flux lo-hi(mW)  Pavg@30% Pavg@11.9%  I_on(mA) I_avg(mA)
------------------------------------------------------------------------------------------
direct only, bare APD                171.0-184.2        307        772       205       102
+/-45 deg optics (2x)                 85.5-92.1         154        386       102        51
bare APD + arena rho 0.5              66.3-71.4         119        299        79        40
+/-30 optics (3x) + arena 0.5         37.3-40.2          67        169        45        22
+/-30 optics (3x) + arena 0.7         25.6-27.6          46        116        31        15
  Electrical columns use the hi (conservative) noise bound. Pavg = flux/WPE x 0.5 (emitter only, no driver
  loss); I_on = flux/(WPE x Vf). Optics gain applies to the direct term only.

  Omitted (all optimistic): ambient, comparator offset/noise, 1/f, ISI, tilt, shadowing, LED droop, driver
  loss. The arena measurement (review A4) collapses these tables to one row.
```
