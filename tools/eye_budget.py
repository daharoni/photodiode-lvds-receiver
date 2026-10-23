"""Eye and jitter budget at the TLV3605 slicer versus the optical edge speed at the APD (review A3, 2026-10-23).

PROPOSED model, nothing measured: Gaussian edges summed in quadrature (LED optical edge, OPA857 20k at 6 pF 3.6 ns
10-90 SIMULATED, R56/C54 68 MHz one-pole 5.1 ns, OPA855 ~1 GHz 0.35 ns); white noise at the Q = 6 floor
(sigma = Vpp / 2Q); crossing jitter = sigma_v / slope at the crossing; duty distortion from the TLV3605 +-5 mV
maximum offset over the 28 mVpp swing at the Q = 6 floor (post-amp-slicer.md); 4x blind oversampling CDR at
200 MHz quantises the sample point to +-2.5 ns (firmware/ecp5/README.md section 5). Not in the model: ISI from
the simulated 14 % TIA overshoot, transmitter clock jitter, hysteresis delay, LED edge asymmetry.
Run: python3 -I tools/eye_budget.py [--q 6] [--offset-mv 5] [--swing-mv 28]. See docs/optical-link-interface.md.
"""
import argparse, math

UI = 20.0; OVERSAMPLE = 4
TIA_TR, LPF_TR, PA_TR = 3.6, 0.35 / 68e6 * 1e9, 0.35 / 1.0  # 10-90 ns

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", type=float, default=6.0, help="Q at the eye centre (6 = BER 1e-9)")
    ap.add_argument("--offset-mv", type=float, default=5.0, help="comparator offset, +- mV")
    ap.add_argument("--swing-mv", type=float, default=28.0, help="swing at the comparator at the Q floor, mVpp")
    ap.add_argument("--edges", type=str, default="3,5,8,11,14,18", help="LED optical 10-90 edges, ns")
    a = ap.parse_args()
    q_ui = UI / OVERSAMPLE / 2
    print(f"UI {UI} ns, {OVERSAMPLE}x oversampling: sample within +-{q_ui} ns. Receiver edges 10-90: TIA {TIA_TR} ns (SIM), "
          f"LPF {LPF_TR:.2f} ns, post-amp {PA_TR:.2f} ns. Q = {a.q}, offset +-{a.offset_mv} mV over {a.swing_mv} mVpp. PROPOSED.")
    print("LED_tr  comp_tr  iso_bit_amp  slope(Vpp/ns)  sigma_t(ns)  DDJ(+-ns)  margin(ns)  n_sigma  BER_jitter  Q_req(1e-9)  extra_opt_dB")
    for led in [float(x) for x in a.edges.split(",")]:
        tr = math.sqrt(led ** 2 + TIA_TR ** 2 + LPF_TR ** 2 + PA_TR ** 2)
        sig_e = tr / 2.563
        amp = math.erf(UI / 2 / (sig_e * math.sqrt(2)))
        slope = 1 / (sig_e * math.sqrt(2 * math.pi))
        sig_t = (1 / (2 * a.q)) / slope
        ddj = a.offset_mv / a.swing_mv / slope
        margin = UI / 2 - q_ui - ddj
        n = margin / sig_t
        ber = 0.5 * math.erfc(n / math.sqrt(2))
        q_req = 1 / (2 * (margin / 6.0) * slope)
        extra = 10 * math.log10((max(q_req, a.q) / a.q) ** 1.77)  # P_opt ~ Q^1.77 at the APD optimum (link-budget.md)
        print(f"{led:5.0f}  {tr:7.1f}  {amp:11.2f}  {slope:13.4f}  {sig_t:11.2f}  {ddj:9.2f}  {margin:10.1f}  {n:7.2f}  {ber:10.1e}  {q_req:11.2f}  {extra:12.1f}")

if __name__ == "__main__":
    main()
