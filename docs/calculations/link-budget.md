# Optical link budget: LED to PIN photodiode / APD and OPA857 TIA

Generated with `python3 tools/link_budget.py --sweep` and `--apd-sweep` (stdlib only; `--help` lists all parameters).
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
