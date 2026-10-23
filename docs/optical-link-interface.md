# Headstage-to-receiver optical link interface

Status: PROPOSED (2026-10-23, review item A3, decision 31 context). This page is the single statement of what the
headstage transmitter must do for this receiver to work, and what the receiver guarantees in return. Nothing on
it is measured. Numbers come from the receiver's as-built values (docs/schematic/frontend.md, slicer.md), the
gateware README (firmware/ecp5/README.md section 3 and 5, the executable definition), the link budget
(docs/calculations/link-budget.md, revision 2026-10-22) and the eye budget tool `tools/eye_budget.py`.
Requirements row 1 and open item 3 point here. The headstage design must reference this page.

Labels: VERIFIED = against a cited datasheet or the executable gateware model; PROPOSED = derived here;
UNRESOLVED = needs a measurement or a headstage decision.

## 1. Physical layer

| Item | Requirement on the headstage | Basis |
|---|---|---|
| Wavelength | 850 nm class NIR (the receiver bandpass filter and the S12023-10 responsivity 0.48 A/W are set for it). A change of emitter wavelength changes the filter. | link-budget.md; KAPD1007E19 (PROPOSED choice) |
| Modulation | On-off keying of the LED current: light on = logic one on the line. The receiver's slicer sits at the AC baseline, so only the peak-to-peak optical swing matters, not the absolute level. | decision 12; slicer.md polarity note |
| Extinction | LED fully off in the zero state. Extinction ratio >= 10 dB. A finite ratio reduces the swing: penalty 10 log((ER + 1)/(ER - 1)) = 0.9 dB optical at 10 dB, 0.4 dB at 13 dB. The budget assumes infinite ER. | PROPOSED |
| Duty | 8b/10b gives 50 % ones on average, so average optical power is half the on-state power. The driver and LED see the on-state current, the battery sees the average. | VERIFIED (8b/10b property) |
| On-state optical power at the receiver (weak end) | Q = 6 (BER 1e-9) needs about 15 to 17 nW of on-state power on the 0.785 mm^2 die through the filter at the APD's best gain (M 83 to 100, OPA857 20k). The emitter working point that delivers this at 35 cm lateral is in link-budget.md "Collection credits and the emitter working point": 1 W class LED at 30 to 100 mA on-state with optics and the reflective arena, up to 200 mA without. | PROPOSED, link-budget.md Table R4 and credits tables |
| On-state optical power at the receiver (strong end) | 100 uW on the die saturates the OPA857 (240 uA input at M = 5, 5k). The receiver firmware lowers M and selects 5k; both only lower gain. Total on-die range: 15 nW to 100 uW, 38 dB optical, with 10 to 12 dB per fixed setting. | PROPOSED, link-budget.md Table R4 |
| Optical edge speed | 10-90 rise and fall of the light at the APD <= 8 ns, preferably <= 5 ns. See section 4: at 11 to 14 ns the eye at the slicer closes before the amplitude budget does. Pre-emphasis in the LED driver counts; what matters is the optical edge. | PROPOSED, tools/eye_budget.py |
| Edge symmetry | Rise and fall within 2 ns of each other at the APD. Asymmetry becomes duty-cycle distortion that the AC baseline cannot remove. | PROPOSED |
| Ambient | The receiver blocks ambient DC through its AC couplings, but ambient shot noise is multiplied by M and the comparator sees it. The optical bandpass filter is mandatory and the ambient level in the arena is UNRESOLVED (requirements open item 1). | decision 8 consequence |

## 2. Line coding and framing

The executable definition is firmware/ecp5/README.md section 3 and `firmware/ecp5/model/link8b10b.py`
(VERIFIED by 257 cocotb tests against the model, nothing run on silicon). Summary of the obligations:

| Item | Requirement | Basis |
|---|---|---|
| Line rate | 50 Mbps, UI = 20 ns. The gateware v0 fixes OVERSAMPLE = 4 at 200 MHz; other rates need a PLL change. | requirements row 1; README section 4 |
| Code | 8b/10b (IEEE 802.3 clause 36 tables), running disparity maintained across frames and idle. | README section 3 |
| Idle | The ordered set K28.5 D16.2 repeated, continuously, whenever no frame is being sent. The receiver aligns on either disparity of K28.5. | README section 3 |
| Frame | K27.7, seq u16 LE, type u8, len u8, payload 1 to 256 bytes, CRC-16/CCITT-FALSE u16 LE, K29.7. Maximum 262 bytes = 2620 UI = 52.4 us. | README section 3 |
| Sequence | u16 per frame, incrementing, wraps; every receiver lane carries the same stream (requirements row 5). | README section 3 and 6 |
| Run length | 8b/10b bounds runs to 5 UI. The transmitter must not emit anything outside the code (no raw gaps, no unencoded preamble). | VERIFIED (8b/10b property) |
| Clock tolerance | Transmitter bit clock within +-100 ppm of 50 MHz. The CDR absorbs the offset in its frequency register and is tested at +-500 ppm with 0.3 UI jitter. | README section 9 (host-tested, PROPOSED margin) |
| Polarity | Light on = one. The cable SSTXp is high for a one after the fan-out inversion; the gateware auto-detects inversion, but the headstage must not rely on that. | README section 2 |

## 3. Continuity: no dark gaps

Two AC couplings sit in the receiver signal path, C51 100 nF into R51 1 k (TIA to post-amp) and C55 100 nF into
R59 1 k (post-amp to comparator), each 100 us (1.6 kHz) (frontend.md items 3 and 6, VERIFIED values). Their
consequences, PROPOSED arithmetic:

- Running 8b/10b data moves the baseline by at most about 0.1 % of the swing (a 5 UI run is 100 ns against
  100 us). No obligation beyond staying in code.
- Any transmitter silence (LED held off or held on) longer than a few microseconds lets both stages relax toward
  the new mean: 5 us is 5 % of the swing, 50 us is 40 %, 300 us is 95 %. On resumption the data sits offset by up
  to half the swing until both stages re-settle, about 3 tau each, 0.3 to 0.6 ms, during which the slicer makes
  errors and the lanes report invalid symbols.
- The gateware then needs 8 edges to re-acquire the CDR phase after silence, one comma to align and 128 valid
  symbols (25.6 us) to declare lock (README section 5). The watchdog declares loss of signal after 1 ms without a
  transition (README section 5).

Obligations:

1. The LED is modulated with the idle ordered set at all times the link is meant to be up, including between
   frames and while the headstage has nothing to send. The inter-frame gap is idle pairs, never darkness.
2. If the headstage must stop the LED (power saving, a sleep state, a brown-out), it must send at least 1 ms of
   idle before the first frame after resuming (0.6 ms settling plus CDR and lock), and the receiver side must
   expect a loss-of-signal event. Frames sent earlier are discarded by CRC; the sequence-number merge
   (README section 6) counts them as lost.
3. No unencoded preamble, training pattern or DC level is sent before or between frames.
4. The emitter must not droop within a frame: the budget treats the on-state level as constant over the 52.4 us
   maximum frame. A thermal or supply droop of more than about 10 % within a frame appears as baseline wander
   that the 100 us couplings pass. UNRESOLVED until the emitter and driver are chosen.

## 4. Timing, eye and jitter budget

The receiver's clock recovery is a blind 4x oversampler at 200 MHz: samples are 5 ns apart, the chosen sample
sits within +-2.5 ns (+-0.125 UI) of the eye centre before any analog impairment (README section 5, VERIFIED as
built). The analog edge at the comparator is the LED's optical edge convolved with the receiver's own response:
OPA857 at 20k and 6 pF, 3.6 ns 10-90 (SIMULATED, docs/simulation/README.md Sim 2); the R56/C54 68 MHz
low-pass, 5.1 ns (0.35/f, one pole); the OPA855 at about 1 GHz, 0.35 ns. The TLV3605's 0.8 ns propagation delay
is a delay, not an edge, and does not enter.

`tools/eye_budget.py` (stdlib, PROPOSED model: Gaussian edges summed in quadrature, white noise, crossing jitter
= voltage noise / slope at the crossing, duty distortion from the comparator's +-5 mV maximum offset over the
28 mVpp swing at the Q = 6 floor from post-amp-slicer.md, no ISI from the simulated 14 % TIA overshoot, no
transmitter clock jitter, no hysteresis delay) gives, at the Q = 6 amplitude floor:

| Optical 10-90 edge at the APD | Edge at the comparator | Isolated-bit amplitude | Crossing sigma from noise | Duty distortion from offset | Margin to the sample point | BER from jitter alone, per transition |
|---|---|---|---|---|---|---|
| 3 ns | 7.0 ns | 100 % | 0.57 ns | +-1.2 ns | 6.3 ns = 11.1 sigma | 1e-28 |
| 5 ns | 8.0 ns | 100 % | 0.65 ns | +-1.4 ns | 6.1 ns = 9.3 sigma | 7e-21 |
| 8 ns | 10.2 ns | 99 % | 0.83 ns | +-1.8 ns | 5.7 ns = 6.9 sigma | 3e-12 |
| 11 ns | 12.7 ns | 96 % | 1.03 ns | +-2.2 ns | 5.3 ns = 5.1 sigma | 1.5e-7 |
| 14 ns | 15.3 ns | 91 % | 1.25 ns | +-2.7 ns | 4.8 ns = 3.9 sigma | 6e-5 |
| 18 ns | 19.1 ns | 82 % | 1.55 ns | +-3.3 ns | 4.2 ns = 2.7 sigma | 4e-3 |

Margin to the sample point = 0.5 UI minus the 2.5 ns quantisation minus the duty distortion. Reading: with an
LED edge of 8 ns or faster, timing costs nothing at the Q = 6 point. With the 11 to 14 ns edges the reviewer quoted
for 1 W class SFH parts (datasheets not in the repo, UNRESOLVED), timing is the limiting mechanism: holding
1e-9 from jitter alone needs Q = 7.0 at 11 ns and Q = 9.3 at 14 ns at the eye centre, which at the APD's
optimum (optical power rises about as Q^1.77) is 1.2 dB and 3.4 dB more optical power than the amplitude budget
asks for. That is why section 1 requires <= 8 ns and prefers <= 5 ns. The comparator offset term halves once
firmware trims DAC_TH (decision 12), which is worth about 0.4 sigma at 11 ns, not enough to change the requirement.

Jitter allocation at the comparator output (PROPOSED, peak-to-peak at BER 1e-9, UI = 20 ns):

| Term | Allocation | Note |
|---|---|---|
| CDR sampling quantisation | 5.0 ns (0.25 UI) | fixed by 4x oversampling, VERIFIED as built |
| Random jitter from receiver noise at Q = 6 | 12 sigma = 7.8 ns at a 5 ns LED edge, 10.0 ns at 8 ns | from the table above |
| Duty distortion, comparator offset | 2.8 ns at 5 ns LED edge, 3.6 ns at 8 ns | +-5 mV untrimmed; about half after DAC_TH trim |
| Data-dependent jitter, receiver ISI | 1.0 ns | 14 % TIA overshoot and the 1 dB peaking at 6 pF (SIMULATED); not in the tool, allocation only |
| Transmitter: clock jitter, driver, LED edge asymmetry | 2.0 ns | headstage budget, UNRESOLVED |
| Sum (worst case, not RSS) | 18.6 ns at a 5 ns edge; 21.6 ns at 8 ns | against 20 ns: 5 ns edges leave 1.4 ns; 8 ns edges are at the limit worst case and fine on an RSS basis |

The budget is only as good as its inputs: the TIA edge and overshoot are simulated with a model validated at
1.5 pF, the LED edge is a datasheet-class figure, nothing is measured. Gate G1's optical eye measurement at the
fixed post-amp gain is where this table gets its first real numbers.

## 5. What the receiver guarantees

- Signal path APD to LVDS is analog and runs with the ESP32 unprogrammed at 20k; the APD bias does not (decisions
  20, 21), so an unprovisioned module is dark.
- Per-lane lock within 128 symbols plus one comma after a clean idle; loss of signal declared after 1 ms without
  a transition; CDR tracks +-500 ppm (host-tested).
- One fixed setting covers 10 to 12 dB optical unclipped; the firmware trim loop moves the strong end by 18 to
  19 dB over tens to hundreds of ms (decision 12, decision 31; the HV down-slew is 50 to 200 ms, review B2).
- Lanes are merged by sequence number, first valid copy wins, duplicates dropped, gaps counted (README section 6).
  Skew between lanes is bounded only by the frame buffer: a lane more than one frame behind loses frames as
  duplicates. Maximum lane skew remains UNRESOLVED (requirements open item 4).

## 6. Open items

1. Measured optical edge of the candidate LED and driver at the operating current (with the A4 power measurement).
2. Arena ambient level through the filter (requirements open item 1).
3. Headstage power-saving behaviour: whether the LED ever stops, and the resume preamble (section 3, item 2).
4. Maximum lane skew and whether the merge needs a reorder window (requirements open item 4).
5. Emitter droop within a frame (section 3, item 4).
