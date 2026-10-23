#!/usr/bin/env python3
"""Parametric optical link-budget calculator for the headstage-LED -> PIN/APD + TIA receiver.

Chain: LED radiant intensity -> irradiance at receiver -> collected power
(detector area x optical gain, limited by etendue) -> photocurrent (x avalanche
gain for an APD) -> TIA swing and noise -> Q / BER -> required VGA gain.

Python 3 standard library only.  Modes: --sweep (tables 1-7), --apd-sweep (APD tables),
--apd-budget (review A1/A2 tables R0-R5: chain noise bandwidth, energy check, required
emitter, Q vs M, range in optical dB, weak-end margin).  Run `python3 tools/link_budget.py --help`.

Revision 2026-10-22 (review A1, A2): default noise bandwidth is the as-built ~70 MHz
(OPA857 ~100 MHz into the 68 MHz R56/C54 low-pass), not 0.7 x bit rate; APD tables use
the OPA857 Fig. 9 noise at the detector capacitance by default; target emitters are
costed from radiant FLUX and a wall-plug efficiency (WPE), not from the SFH 4715AS
0.9 mW/sr/mA figure (a +/-45 deg part) applied to a 140 deg beam.
Range figures: photocurrent is proportional to optical power, so
optical dB = 10 log10(P2/P1) = (20 log10(I2/I1)) / 2 = electrical dB / 2.
Values tagged DATASHEET come from vendor documents; DATASHEET-DERIVED are scaled
from them; ASSUMED are engineering guesses.  See docs/calculations/link-budget.md.

TIA noise: OPA857 SBOS630D gives equivalent input-referred noise with a 135 MHz
brickwall of 15 nA rms (20k) / 25 nA rms (5k) at Cs = 1.5 pF.  For a bandwidth B:
  low-noise bound  = I135 * sqrt(B/135 MHz)   (flat density; DATASHEET-DERIVED)
  high-noise bound = I135                      (all of the 135 MHz noise)
The true value lies between: density rises with frequency (e_n*C term).
Q is reported for both bounds (Q_lo uses the low-noise bound = optimistic).
"""
import argparse
import math
import sys
from dataclasses import dataclass

Q_E = 1.602176634e-19          # electron charge, C
LM_PER_W = 683.0               # luminous efficacy at 555 nm, lm/W (DATASHEET: CIE)
V_625 = 0.321                  # photopic V(625 nm), ASSUMED from CIE table (approx.)
BIT_RATE = 50e6                # baud, 8b/10b NRZ, UI = 20 ns
BW_REF = 135e6                 # OPA857 noise-spec brickwall, Hz
DUTY = 0.5                     # NRZ average duty for electrical power
WPE = 0.30                     # wall-plug efficiency for flux->electrical estimates, ASSUMED (optimistic)
BW_BUILT_MHZ = 70.0            # as-built noise-equivalent bandwidth, PROPOSED (see chain_neb())
F_LPF = 1 / (2 * math.pi * 49.9 * 47e-12)   # R56 49.9 ohm / C54 47 pF = 67.9 MHz (frontend.md item 5)
# OPA857 20k closed-loop -3 dB: 105 MHz at 1.5 pF (SBOS630D p.6, DATASHEET); 99 MHz at 6 pF (ngspice, SIMULATED)
F_TIA_RANGE = (99e6, 106e6)
# Clip / saturation levels of the built chain, peak-to-peak photocurrent at the TIA input (after M):
# post-amp clip = Vswing / (G x Rt_eff), G = 7, Rt_eff 18.2k (20k) / 4.5k (5k) (OPA857 SBOS630D p.6 note 4);
# Vswing 1.0 Vpp (symmetric about the 1.65 V baseline: VOL 1.15 V max, VOH 2.35 V min at 3.3 V,
# OPA855 SBOS622D p.7) .. 1.15 Vpp (docs/research/post-amp-slicer.md).  TIA saturation 60 / 240 uA
# (OPA857 SBOS630D p.15, section 7.3.1).
G_POST = 7.0
RT_EFF = {20e3: 18.2e3, 5e3: 4.5e3}
POST_SWING_VPP = (1.0, 1.15)
TIA_SAT = {20e3: 60e-6, 5e3: 240e-6}
# Reference NIR emitter QBLP601-2IR4 (link-components.md section 4, datasheet V1.0 2021-09-17):
# 1.0 mW/sr typ at 20 mA, 140 deg, Vf 1.6 V typ.  WPE implied by a cos^m beam is computed in
# wpe_reference() (DATASHEET-DERIVED; the datasheet gives no radiant flux).
QBLP_IE_20MA = 1.0e-3
QBLP_VF = 1.6


# --------------------------------------------------------------------------
# Emitters and detectors
# --------------------------------------------------------------------------
@dataclass
class Emitter:
    name: str
    wavelength_nm: float
    i_e_ref: float        # radiant intensity on axis at i_ref_mA, W/sr
    i_ref_mA: float
    i_max_cont_mA: float
    view_deg: float       # full viewing angle (to half-intensity)
    vf: float = 1.5       # forward voltage, V

    def intensity(self, current_mA):
        """On-axis radiant intensity (W/sr) at drive current.

        APPROXIMATION: linear in current (real LEDs droop/saturate and slow
        down with heating; linear is optimistic at high current).
        """
        return self.i_e_ref * current_mA / self.i_ref_mA

    def avg_power_mW(self, current_mA, vf=None):
        """Average electrical power (mW) for 50 % duty NRZ: I x Vf x 0.5."""
        return current_mA * (self.vf if vf is None else vf) * DUTY


def mcd_to_w_per_sr(mcd, v_lambda=V_625):
    """Convert luminous intensity (mcd) to radiant intensity (W/sr).

    I_e = I_v / (683 lm/W * V(lambda)).  V(625 nm) ~ 0.321 is ASSUMED/approx.
    """
    return (mcd * 1e-3) / (LM_PER_W * v_lambda)


EMITTERS = {
    "red": Emitter("Red Wurth 150060RS75003 (625 nm)", 625.0,
                   mcd_to_w_per_sr(530.0), 20.0, 30.0, 140.0, 2.0),   # DATASHEET + V(l); Vf ASSUMED
    "nir": Emitter("NIR QT Brightek QBLP601-2IR4 (765 nm)", 765.0,
                   1.0e-3, 20.0, 50.0, 140.0, 1.6),                    # DATASHEET typ (Ie, Vf 1.6 V typ)
    # OSRAM SFH 4550 v1.8 (2021-11-18): Ie typ 1100 mW/sr @100 mA (710..2800 bins),
    # half angle typ 3 deg, IF max 100 mA, Vf typ 1.5 V, tr/tf typ 12 ns.  Pulsed 1 A
    # (tp<=400us, D<=0.5%) gives 8500 mW/sr typ -- NOT usable for continuous NRZ.
    "sfh4550": Emitter("OSRAM SFH 4550 (850 nm, +/-3 deg)", 850.0,
                       1.1, 100.0, 100.0, 6.0, 1.5),
    # ams OSRAM SFH 4715AS: Ie 900 mW/sr typ (710..1120) @1000 mA (product page);
    # Vf ~3.2 V typ at 1 A (DigiKey listing; ASSUMED); beam angle listings conflict
    # (80 vs 90 deg full): +/-45 used (ASSUMED).  1 A at 50 % duty UNVERIFIED.
    "sfh4715": Emitter("OSRAM SFH 4715AS (860 nm, +/-45 deg)", 860.0,
                       0.9, 1000.0, 1000.0, 90.0, 3.2),
}

# responsivity (A/W) keyed by nearest wavelength; "ASSUMED" entries flagged in doc
DETECTORS = {
    "FDS010": dict(diam_mm=1.02, c_pf=6.0, resp={625: 0.43, 765: 0.40, 850: 0.50}, dark_nA=1.0),
    "S5972":  dict(diam_mm=0.80, c_pf=3.0, resp={625: 0.40, 765: 0.50, 850: 0.55}, dark_nA=0.1),
    "PIN3mm": dict(diam_mm=3.00, c_pf=25.0, resp={625: 0.45, 765: 0.50, 850: 0.55}, dark_nA=5.0),
    # APDs.  Parameters from docs/research/apd-selection.md Part 4.  x = Hamamatsu excess-noise
    # index (F = M^x); k = McIntyre ionisation ratio (DERIVED for Hamamatsu, DATASHEET for
    # Excelitas).  m_max = datasheet maximum gain.  dark_nA is the TOTAL dark current at the
    # datasheet gain (pessimistic when used as primary dark; negligible vs TIA noise).
    # Responsivity R(M=1): 625/765/850 GRAPH-READ from the QE curve scaled to the 0.5 A/W @800 nm
    # table value (DERIVED).
    "S12023-10": dict(diam_mm=1.0, c_pf=6.0, resp={625: 0.30, 765: 0.47, 850: 0.48},
                      dark_nA=0.2, apd=True, M=50.0, m_max=100.0, x=0.3, k=0.02),    # DATASHEET + GRAPH-READ
    "S12023-05": dict(diam_mm=0.5, c_pf=2.0, resp={625: 0.30, 765: 0.47, 850: 0.48},
                      dark_nA=0.1, apd=True, M=50.0, m_max=100.0, x=0.3, k=0.02),    # DATASHEET; R same die, DERIVED
    "S3884":     dict(diam_mm=1.5, c_pf=10.0, resp={625: 0.30, 765: 0.47, 850: 0.48},
                      dark_nA=0.5, apd=True, M=50.0, m_max=100.0, x=0.3, k=0.02),    # DATASHEET; R same family, DERIVED
    # Excelitas C30902EH: 77 A/W @830 nm at M=150 -> 0.51 A/W (DERIVED); 625/765 NOT FOUND, so
    # the 850 value is used at every wavelength.  x=None: Excelitas states k=0.02 (DATASHEET),
    # so McIntyre is always used for this part, whatever --excess-model says.
    "C30902EH":  dict(diam_mm=0.5, c_pf=1.6, resp={850: 0.51},
                      dark_nA=15.0, apd=True, M=100.0, m_max=150.0, x=None, k=0.02),
}

# OPA857 equivalent input-referred noise, 135 MHz brickwall, Cs=1.5 pF  (DATASHEET SBOS630D)
TIA_IRMS_135 = {5e3: 25e-9, 20e3: 15e-9}

# OPA857 Fig. 9 (20k) and Fig. 10 (5k): rms input noise (nA, 135 MHz) vs source capacitance
# (pF).  READ VISUALLY from the plots (+/- ~2 nA); pdftotext does not expose curve data.
FIG_NOISE_VS_CS = {
    20e3: [(0, 12), (5, 24), (10, 33), (15, 38), (20, 42), (22, 45)],
    5e3: [(0, 21), (5, 40), (10, 58), (15, 68), (22, 82)],
}


def tia_noise_fig(rt, cs_pf):
    """i_rms(135 MHz) in A from the read-off Fig. 9/10 curves at source capacitance cs_pf."""
    pts = FIG_NOISE_VS_CS[rt]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= cs_pf <= x1:
            return (y0 + (y1 - y0) * (cs_pf - x0) / (x1 - x0)) * 1e-9
    return pts[-1][1] * 1e-9


def responsivity(det, wavelength_nm):
    """Responsivity (A/W, before avalanche gain) at the nearest tabulated wavelength."""
    k = min(det["resp"], key=lambda w: abs(w - wavelength_nm))
    return det["resp"][k]


def detector_area_m2(det):
    """Active area in m^2 for a circular detector."""
    return math.pi * (det["diam_mm"] * 1e-3 / 2) ** 2


EXCESS_MODEL = "power"   # "power": F = M^x (Hamamatsu, default); "mcintyre": F = kM + (2-1/M)(1-k)


def excess_noise_factor(m, k=0.02, x=0.3, model=None):
    """APD excess noise factor.

    power   : F = M**x, x = 0.3 for Hamamatsu Si APDs (DATASHEET).
    mcintyre: F = k M + (2 - 1/M)(1 - k), k = 0.02 for Si.
    x=None (Excelitas part, k stated) forces McIntyre.
    """
    model = EXCESS_MODEL if model is None else model
    if model == "power" and x is not None:
        return m ** x
    return k * m + (2 - 1 / m) * (1 - k)


def excess_label(det):
    """Text naming the excess-noise form used for a detector."""
    if EXCESS_MODEL == "power" and det.get("x") is not None:
        return f"F = M^{det['x']:g}"
    return f"McIntyre k={det['k']:g}"


# --------------------------------------------------------------------------
# Optics
# --------------------------------------------------------------------------
def lambertian_order(view_deg):
    """Lambertian order m = -ln2 / ln(cos(half-angle)); half-angle = view/2."""
    return -math.log(2) / math.log(math.cos(math.radians(view_deg / 2)))


def beam_flux_factor(view_deg):
    """Solid-angle equivalent (sr): flux = I_e * 2 pi/(m+1) for a cos^m beam."""
    return 2 * math.pi / (lambertian_order(view_deg) + 1)


def geometry(lateral_m, height_m):
    """Return (distance d, angle off LED axis theta in radians).

    LED points straight up, receiver looks straight down, so the receiver
    angle of incidence equals the transmit angle (parallel planes).
    """
    return math.hypot(lateral_m, height_m), math.atan2(lateral_m, height_m)


def irradiance(i_e, view_deg, lateral_m, height_m, filter_T=0.9, rx_cos=True):
    """Irradiance (W/m^2): E = I_e cos^m(theta_tx)/d^2 * T_filter * cos(theta_rx)."""
    d, th = geometry(lateral_m, height_m)
    m = lambertian_order(view_deg)
    e = i_e * math.cos(th) ** m / d ** 2 * filter_T
    return e * (math.cos(th) if rx_cos else 1.0)


def etendue_max_gain(theta_fov_deg):
    """Maximum lossless optical gain G = A_in/A_d for a field-of-view half-angle.

    Etendue conservation: A_in sin^2(theta_fov) <= A_d sin^2(90 deg) = A_d,
    so G <= 1/sin^2(theta_fov).  (Detector in air, accepting up to 90 deg.)
    """
    s = math.sin(math.radians(theta_fov_deg))
    return 1.0 / (s * s)


def collected_power(e, det, g_optics=1.0):
    """P = E * A_eff, A_eff = A_detector * G_optics (W)."""
    return e * detector_area_m2(det) * g_optics


# --------------------------------------------------------------------------
# Electrical
# --------------------------------------------------------------------------
def ook_levels(i_on, er=math.inf):
    """Return (I_pp, I_avg) for OOK with extinction ratio er (inf = full modulation)."""
    low = 0.0 if math.isinf(er) else i_on / er
    return i_on - low, (i_on + low) / 2


def tia_noise_bounds(rt, bw, i135=None):
    """(low, high) TIA input-referred noise currents (A rms) at bandwidth bw.

    low = I135 sqrt(bw/135 MHz) (flat density; lower bound), high = I135.
    """
    i135 = TIA_IRMS_135[rt] if i135 is None else i135
    lo = i135 * math.sqrt(bw / BW_REF)
    return lo, max(lo, i135)


def noise_rms(rt, i_avg_pri, bw, dark=0.0, ambient=0.0, bound="lo", m=1.0, f=1.0, i135=None):
    """Input-referred RMS noise (A): TIA bound plus shot noise.

    Shot term is sqrt(2 q (I_avg_primary + I_dark + I_amb) B) * M * sqrt(F)
    (M=F=1 for a PIN).  Ignores 1/f, VGA and comparator noise (optimistic).
    """
    lo, hi = tia_noise_bounds(rt, bw, i135)
    i_tia = lo if bound == "lo" else hi
    shot = math.sqrt(2 * Q_E * (i_avg_pri + dark + ambient) * bw) * m * math.sqrt(f)
    return math.hypot(i_tia, shot)


def q_factor(i_pp, i_n):
    """Q = (I_pp/2)/i_noise (decision distance is half the swing)."""
    return (i_pp / 2) / i_n


def ber_from_q(q):
    """Ideal NRZ BER = 0.5 erfc(Q/sqrt2)."""
    return 0.5 * math.erfc(q / math.sqrt(2))


def q_for_ber(target):
    """Invert BER(Q) by bisection."""
    lo, hi = 0.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if ber_from_q(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def tia_bw_first_order(rt, c_pd_pf, c_par_pf=1.5):
    """First-order R_T*C_total pole f = 1/(2 pi R_T C_total) in Hz.

    Rough indicator only: loop gain moves the real input pole up, so this is
    pessimistic for a fast op-amp.
    """
    return 1.0 / (2 * math.pi * rt * (c_pd_pf + c_par_pf) * 1e-12)


def required_vga_gain(i_pp, rt, target_vpp=1.0):
    """Linear VGA gain needed to bring the TIA swing up to target_vpp."""
    return target_vpp / (i_pp * rt) if i_pp > 0 else math.inf


def db(x, k=10):
    return k * math.log10(x) if x > 0 else float("-inf")


def big(x, w=16, spec=".3g"):
    """Right-aligned number, or '>1e9' for unrealisable magnitudes."""
    return f"{'>1e9' if x > 1e9 else format(x, spec):>{w}}"


# --------------------------------------------------------------------------
# One full point
# --------------------------------------------------------------------------
def link_point(i_e, view_deg, wl_nm, det, lateral_m, height_m, rt=20e3,
               filter_T=0.9, gain=1.0, er=math.inf, bw=0.7 * BIT_RATE,
               ambient=0.0, dark=None, target_vpp=1.0, m_apd=None, i135=None):
    """Compute the whole chain for one geometry; returns a dict.

    Keys: Q / BER use the LOW-noise TIA bound (optimistic); Q_hi / BER_hi the
    HIGH bound.  I_on / I_pp include avalanche gain for an APD.
    """
    dark = det["dark_nA"] * 1e-9 if dark is None else dark
    m = 1.0
    f = 1.0
    if det.get("apd"):
        m = det["M"] if m_apd is None else m_apd
        f = excess_noise_factor(m, det["k"], det.get("x"))
    e = irradiance(i_e, view_deg, lateral_m, height_m, filter_T)
    p = collected_power(e, det, gain)
    r = responsivity(det, wl_nm)
    i_on_pri = r * p
    pp_pri, avg_pri = ook_levels(i_on_pri, er)
    i_pp = pp_pri * m
    n_lo = noise_rms(rt, avg_pri, bw, dark, ambient, "lo", m, f, i135)
    n_hi = noise_rms(rt, avg_pri, bw, dark, ambient, "hi", m, f, i135)
    q_lo, q_hi = q_factor(i_pp, n_lo), q_factor(i_pp, n_hi)
    return dict(E=e, P=p, R=r, I_on=i_on_pri * m, I_pp=i_pp, V_pp=i_pp * rt,
                i_n=n_lo, i_n_hi=n_hi, Q=q_lo, Q_hi=q_hi,
                BER=ber_from_q(q_lo), BER_hi=ber_from_q(q_hi),
                vga=required_vga_gain(i_pp, rt, target_vpp),
                f_tia=tia_bw_first_order(rt, det["c_pf"]), M=m, F=f)


def gain_needed_for_q(q_target, bound="lo", **kw):
    """Scale factor on collected power (= optical gain or LED intensity multiplier)
    needed to reach q_target for the given noise bound ('lo' or 'hi')."""
    i_e = kw.pop("i_e")
    g0 = kw.pop("gain", 1.0)
    key = "Q" if bound == "lo" else "Q_hi"
    lo, hi = 1e-3, 1e30
    for _ in range(300):
        mid = math.sqrt(lo * hi)
        if link_point(i_e, gain=g0 * mid, **kw)[key] < q_target:
            lo = mid
        else:
            hi = mid
    return hi


def apd_m_needed(q_target, bound="lo", m_max=1000.0, **kw):
    """Smallest avalanche gain M reaching q_target (None if never).

    Q(M) rises then falls (excess noise), so also returns the maximum Q over
    1 <= M <= m_max and the M at which it occurs: (M_needed, Q_max, M_at_Qmax).
    """
    key = "Q" if bound == "lo" else "Q_hi"
    grid = [10 ** (i * math.log10(m_max) / 600) for i in range(601)]
    best_q, best_m, prev, found = -1.0, 1.0, 1.0, None
    for mm in grid:
        q = link_point(m_apd=mm, **kw)[key]
        if q > best_q:
            best_q, best_m = q, mm
        if found is None and q >= q_target:
            lo, hi = prev, mm
            for _ in range(60):
                mid = (lo + hi) / 2
                if link_point(m_apd=mid, **kw)[key] >= q_target:
                    hi = mid
                else:
                    lo = mid
            found = hi
        prev = mm
    return found, best_q, best_m


# --------------------------------------------------------------------------
# Review A1/A2 helpers (2026-10-22): energy, bandwidth, M optimum, optical-dB ranges
# --------------------------------------------------------------------------
def wpe_reference():
    """WPE of the reference QBLP601-2IR4 at 20 mA: flux (cos^m, 140 deg) / (I x Vf).

    1.0 mW/sr x 2 pi/(m+1) = 3.82 mW optical from 20 mA x 1.6 V = 32 mW -> ~12 %
    (DATASHEET-DERIVED: the beam shape is the cos^m assumption, not a datasheet flux).
    """
    return QBLP_IE_20MA * beam_flux_factor(140.0) / (20e-3 * QBLP_VF)


def emitter_cost(i_e, view_deg, wpe):
    """(on-state flux W, average electrical W at 50 % duty) for on-axis intensity i_e (W/sr)."""
    flux = i_e * beam_flux_factor(view_deg)
    return flux, flux / wpe * DUTY


def chain_neb(f_tia, q_tia=0.7071, f_lpf=F_LPF, f_max=3e9, n=60000):
    """Noise-equivalent bandwidth (Hz) of OPA857 (2nd-order, f_tia, Q) x one-pole low-pass.

    Also returns the 'equivalent B' for the flat-density scaling I135 sqrt(B/135 MHz), if the
    datasheet 135 MHz brickwall figure already includes the OPA857's own roll-off.
    Model only (PROPOSED): real response at 6 pF shows ~1 dB peaking (frontend.md, SIMULATED).
    """
    def h2_tia(f):
        x = f / f_tia
        return 1 / ((1 - x * x) ** 2 + (x / q_tia) ** 2)

    def h2_lpf(f):
        return 1 / (1 + (f / f_lpf) ** 2)

    def integ(g, fmax):
        df = fmax / n
        return sum(g((i + 0.5) * df) for i in range(n)) * df

    full = integ(lambda f: h2_tia(f) * h2_lpf(f), f_max)
    to135 = integ(h2_tia, BW_REF)
    return full, BW_REF * full / to135


def tia_i135(rt, cs_pf, mode):
    """OPA857 i_rms in a 135 MHz brickwall: 'datasheet' = 1.5 pF table value, else Fig. 9/10 read at cs_pf."""
    if mode == "datasheet":
        return TIA_IRMS_135[rt]
    return tia_noise_fig(rt, cs_pf)


def q_apd_power(p_on, det, wl_nm, m, rt, bw, i135, bound="lo", er=math.inf, ambient=0.0):
    """Q for on-state optical power p_on (W) on the die, avalanche gain m."""
    r = responsivity(det, wl_nm)
    pp, avg = ook_levels(r * p_on, er)
    f = excess_noise_factor(m, det["k"], det.get("x")) if det.get("apd") else 1.0
    n = noise_rms(rt, avg, bw, det["dark_nA"] * 1e-9, ambient, bound, m, f, i135)
    return q_factor(pp * m, n)


def m_grid(m_hi, pts=400):
    return [10 ** (i * math.log10(m_hi) / pts) for i in range(pts + 1)]


def best_m_for_power(p_on, m_cap, **kw):
    """(Q_max, M at Q_max) over 1 <= M <= m_cap."""
    best = (-1.0, 1.0)
    for mm in m_grid(m_cap):
        q = q_apd_power(p_on, m=mm, **kw)
        if q > best[0]:
            best = (q, mm)
    return best


def p_floor(q_target, m=None, m_cap=100.0, **kw):
    """Smallest on-state optical power (W) on the die reaching q_target.

    m given: at that fixed M.  m None: at the best M <= m_cap (the weak-end setting).
    Returns (P, M used).
    """
    def ok(p):
        if m is not None:
            return q_apd_power(p, m=m, **kw) >= q_target, m
        q, mb = best_m_for_power(p, m_cap, **kw)
        return q >= q_target, mb
    lo, hi = 1e-15, 1e-3
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        if ok(mid)[0]:
            hi = mid
        else:
            lo = mid
    return hi, ok(hi)[1]


def die_power(i_e, view_deg, lateral_m, height_m, det, filter_T):
    """On-state optical power on the bare die (W) for on-axis intensity i_e."""
    return collected_power(irradiance(i_e, view_deg, lateral_m, height_m, filter_T), det, 1.0)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def summary(label, p, args, gain_used, pavg):
    swing_flag = "CLIPS" if p["V_pp"] > args.tia_swing else "ok"
    vga_flag = ("in range" if args.vga_min <= p["vga"] <= args.vga_max
                else ("ABOVE range" if p["vga"] > args.vga_max else "below range"))
    bw_flag = "OK" if p["f_tia"] >= BIT_RATE else "BELOW bit rate"
    print(f"--- {label}")
    print(f"  Avg electrical power  : {pavg:10.1f} mW  (I x Vf x 0.5)")
    print(f"  Irradiance E          : {p['E']*1e3:10.4f} mW/m^2")
    print(f"  Collected power       : {p['P']*1e9:10.4f} nW   (optical gain {gain_used:g}x)")
    print(f"  Photocurrent (on)     : {p['I_on']*1e9:10.4f} nA   (R={p['R']:.2f} A/W, M={p['M']:g})")
    print(f"  TIA swing (pp)        : {p['V_pp']*1e6:10.2f} uV   [{swing_flag} vs {args.tia_swing} V]")
    print(f"  Noise (rms, input)    : {p['i_n']*1e9:10.3f} nA low bound .. {p['i_n_hi']*1e9:.3f} nA high bound")
    print(f"  Q = (Ipp/2)/i_n       : {p['Q']:10.4f} (low-noise) .. {p['Q_hi']:.4f} (high-noise)"
          f"   need {q_for_ber(1e-9):.2f} for 1e-9, {q_for_ber(1e-3):.2f} for 1e-3")
    print(f"  BER (ideal NRZ)       : {p['BER']:10.3e} (low-noise) .. {p['BER_hi']:.3e} (high-noise)")
    print(f"  VGA gain for 1 Vpp    : {big(p['vga'],10,'.1f')}x = {db(p['vga'],20):.1f} dB  [{vga_flag}; "
          f"range {args.vga_min:g}-{args.vga_max:g}x]")
    print(f"  1st-order TIA RC BW   : {p['f_tia']/1e6:10.2f} MHz  [{bw_flag}]")


def build_emitters(args):
    if args.led_intensity is not None:
        cur = args.current or 20.0
        vf = args.vf if args.vf is not None else 1.5
        return [("custom", Emitter("Custom LED upgrade", args.led_wavelength,
                                   args.led_intensity * 1e-3, cur, cur, args.led_view, vf), cur)]
    keys = [args.emitter] if args.emitter else ["red", "nir", "sfh4550", "sfh4715"]
    out = []
    for k in keys:
        e = EMITTERS[k]
        out.append((k, e, args.current if args.current else (20.0 if k in ("red", "nir") else e.i_ref_mA)))
    return out


def resolve_gain(args):
    g = args.gain
    lim = etendue_max_gain(args.fov)
    if g > lim * (1 + 1e-9):
        print(f"WARNING: requested optical gain {g:g}x exceeds the etendue limit "
              f"{lim:.2f}x for +/-{args.fov:g} deg FOV (1/sin^2). Refusing; using {lim:.2f}x.",
              file=sys.stderr)
        g = lim
    return g


def single_point(args):
    det = DETECTORS[args.detector]
    rt = 5e3 if args.rt == "5k" else 20e3
    gain = resolve_gain(args)
    print(f"Detector {args.detector}: diam {det['diam_mm']} mm, {det['c_pf']} pF"
          + (f", APD M={args.apd_m:g} ({excess_label(det)})" if det.get("apd") else "")
          + f"; R_T={args.rt}; lateral {args.lateral_cm} cm, height {args.height_cm} cm; "
          f"filter T={args.filter_T}; B={args.bw_mhz} MHz; ER={args.er}")
    print(f"Etendue limit at +/-{args.fov:g} deg FOV: {etendue_max_gain(args.fov):.2f}x")
    for key, em, cur in build_emitters(args):
        i_e = em.intensity(cur) if key != "custom" else em.i_e_ref
        if key != "custom" and cur > em.i_max_cont_mA:
            print(f"WARNING: {cur} mA exceeds {em.i_max_cont_mA} mA continuous rating "
                  f"(8b/10b NRZ is ~50% duty; pulsed ratings do not apply).", file=sys.stderr)
        p = link_point(i_e, em.view_deg, em.wavelength_nm, det, args.lateral_cm / 100,
                       args.height_cm / 100, rt, args.filter_T, gain, args.er,
                       args.bw_mhz * 1e6, args.ambient_nA * 1e-9, None, args.target_vpp, args.apd_m)
        summary(f"{em.name} @ {cur:g} mA (I_e={i_e*1e3:.3f} mW/sr, m={lambertian_order(em.view_deg):.3f})",
                p, args, gain, em.avg_power_mW(cur, args.vf))


def sweep(args):
    det = DETECTORS[args.detector]
    h = args.height_cm / 100
    bw = args.bw_mhz * 1e6
    amb = args.ambient_nA * 1e-9
    offsets = [0, 10, 20, 35, 50]
    q9, q3 = q_for_ber(1e-9), q_for_ber(1e-3)
    lo_n, hi_n = tia_noise_bounds(20e3, bw)
    print(f"Q needed: BER 1e-9 -> {q9:.2f}; BER 1e-3 -> {q3:.2f}")
    print(f"Detector {args.detector} (diam {det['diam_mm']} mm), R_T=20k, height {args.height_cm:g} cm, "
          f"T={args.filter_T}, B={args.bw_mhz:g} MHz, gain 1x, ER=inf, ambient {args.ambient_nA:g} nA")
    print(f"TIA noise at 20k: low bound {lo_n*1e9:.2f} nA (15 nA x sqrt(B/135 MHz)), "
          f"high bound {hi_n*1e9:.2f} nA (15 nA); Q_lo uses low bound, Q_hi uses high bound\n")
    print("TABLE 1: link budget vs lateral offset (Pavg = I x Vf x 0.5)")
    hdr = (f"{'emitter':<8}{'I(mA)':>6}{'Pavg(mW)':>9}{'off':>5}{'E(mW/m2)':>11}{'P(nW)':>10}{'Iph(nA)':>10}"
           f"{'Vpp(uV)':>10}{'in_lo':>7}{'in_hi':>7}{'Q_lo':>9}{'Q_hi':>9}{'BER_lo':>10}{'BER_hi':>10}{'VGA(x)':>9}")
    print(hdr)
    print("-" * len(hdr))
    cases = []
    for k in ("red", "nir"):
        em = EMITTERS[k]
        for cur in (20.0, em.i_max_cont_mA):
            cases.append((k, em, cur))
    for k in ("sfh4550", "sfh4715"):
        cases.append((k, EMITTERS[k], EMITTERS[k].i_max_cont_mA))
    for k, em, cur in cases:
        for off in offsets:
            p = link_point(em.intensity(cur), em.view_deg, em.wavelength_nm, det, off / 100, h,
                           20e3, args.filter_T, 1.0, args.er, bw, amb, None, args.target_vpp, args.apd_m)
            print(f"{k:<8}{cur:>6g}{em.avg_power_mW(cur):>9.0f}{off:>5}{p['E']*1e3:>11.3g}{p['P']*1e9:>10.3g}"
                  f"{p['I_on']*1e9:>10.3g}{p['V_pp']*1e6:>10.3g}{p['i_n']*1e9:>7.2f}{p['i_n_hi']*1e9:>7.2f}"
                  f"{p['Q']:>9.3g}{p['Q_hi']:>9.3g}{p['BER']:>10.2e}{p['BER_hi']:>10.2e}"
                  f"{big(p['vga'],9,'.3g')}")
        print()
    # Table 2: required on-axis Ie
    r850 = det["resp"][850]
    print(f"TABLE 2: on-axis radiant intensity (mW/sr) needed for Q = {q9:.1f}, bare {args.detector}, "
          f"R_T=20k, gain 1x, 850 nm (R={r850}), T={args.filter_T}")
    print("  columns: low-noise bound / high-noise bound; LED points up, receiver at 50 cm height")
    hdr2 = f"{'full view':>9}{'m':>7}" + "".join(f"{'Ie@'+str(o)+'cm lo':>13}{'hi':>13}" for o in (0, 35, 50))
    print(hdr2)
    print("-" * len(hdr2))
    need35 = {}
    for vw in (6, 20, 40, 60, 90, 140):
        row = f"{vw:>9}{lambertian_order(vw):>7.1f}"
        for off in (0, 35, 50):
            for bd in ("lo", "hi"):
                kw = dict(view_deg=vw, wl_nm=850.0, det=det, lateral_m=off / 100, height_m=h, rt=20e3,
                          filter_T=args.filter_T, er=args.er, bw=bw, ambient=amb, target_vpp=args.target_vpp)
                need = gain_needed_for_q(q9, bd, i_e=1.0e-3, **kw)
                row += big(need, 13 if bd == "lo" or off else 13)
                if off == 35:
                    need35[(vw, bd)] = need * 1e-3
        print(row)
    print("  Ie = on-axis value required; >1e9 = not realisable (narrow beam pointed away).\n")
    print(f"TABLE 3: radiant flux and average electrical power for Q = {q9:.1f} at 35 cm lateral "
          f"(flux = Ie x 2pi/(m+1); Pel = on-flux / WPE x 0.5, WPE = {WPE:.0%} ASSUMED)")
    hdr3 = f"{'full view':>9}{'flux lo(mW)':>13}{'flux hi(mW)':>13}{'Pel lo(mW)':>13}{'Pel hi(mW)':>13}"
    print(hdr3)
    print("-" * len(hdr3))
    for vw in (40, 60, 90, 140):
        fl = {bd: need35[(vw, bd)] * beam_flux_factor(vw) * 1e3 for bd in ("lo", "hi")}
        print(f"{vw:>9}" + "".join(big(fl[b], 13) for b in ("lo", "hi"))
              + "".join(big(fl[b] / WPE * DUTY, 13) for b in ("lo", "hi")))
    print()
    print(f"TABLE 4: shortfall to Q = {q9:.1f} at 35 cm lateral (optical dB = 10log10(factor); "
          f"photocurrent dB = 2x)")
    hdr4 = (f"{'emitter':<8}{'I(mA)':>6}{'Pavg(mW)':>9}{'Q_lo':>9}{'Q_hi':>9}{'short_lo(dB)':>13}"
            f"{'short_hi(dB)':>13}{'factor lo':>11}{'factor hi':>11}{'Ie need lo..hi(mW/sr)':>25}")
    print(hdr4)
    print("-" * len(hdr4))
    for k, em, cur in cases:
        kw = dict(view_deg=em.view_deg, wl_nm=em.wavelength_nm, det=det, lateral_m=0.35, height_m=h,
                  rt=20e3, filter_T=args.filter_T, er=args.er, bw=bw, ambient=amb,
                  target_vpp=args.target_vpp)
        p = link_point(em.intensity(cur), **kw)
        nl = gain_needed_for_q(q9, "lo", i_e=em.intensity(cur), **kw)
        nh = gain_needed_for_q(q9, "hi", i_e=em.intensity(cur), **kw)
        ie = em.intensity(cur) * 1e3
        rng = f"{big(ie*nl,0,'.4g')}..{big(ie*nh,0,'.4g')}"
        print(f"{k:<8}{cur:>6g}{em.avg_power_mW(cur):>9.0f}{p['Q']:>9.3g}{p['Q_hi']:>9.3g}"
              f"{db(nl):>13.1f}{db(nh):>13.1f}{big(nl,11)}{big(nh,11)}{rng:>25}")
    print("  (factor applies equally to optical gain OR emitter intensity; negative dB = margin)\n")
    # Table 6 detectors
    print(f"TABLE 5: detector trade at 35 cm lateral, max continuous current, gain 1x; "
          f"APD at M = {args.apd_m:g}")
    hdr6 = (f"{'det':<10}{'emit':<9}{'RT':>4}{'A(mm2)':>8}{'C(pF)':>6}{'Iph(nA)':>10}{'in_lo':>7}{'in_hi':>7}"
            f"{'Q_lo':>9}{'Q_hi':>9}{'f_RC(MHz)':>10}{'BW>=bit':>8}")
    print(hdr6)
    print("-" * len(hdr6))
    for dn in ("FDS010", "S5972", "PIN3mm", "S12023-10"):
        d = DETECTORS[dn]
        for k in ("nir", "sfh4715"):
            em = EMITTERS[k]
            for rtn, rt in (("5k", 5e3), ("20k", 20e3)):
                p = link_point(em.intensity(em.i_max_cont_mA), em.view_deg, em.wavelength_nm, d,
                               0.35, h, rt, args.filter_T, 1.0, args.er, bw, amb, None, args.target_vpp,
                               args.apd_m)
                ok = "yes" if p["f_tia"] >= BIT_RATE else "NO"
                print(f"{dn:<10}{k:<9}{rtn:>4}{detector_area_m2(d)*1e6:>8.2f}{d['c_pf']:>6g}"
                      f"{p['I_on']*1e9:>10.4g}{p['i_n']*1e9:>7.2f}{p['i_n_hi']*1e9:>7.2f}"
                      f"{p['Q']:>9.3g}{p['Q_hi']:>9.3g}{p['f_tia']/1e6:>10.2f}{ok:>8}")
    print("  f_RC = 1/(2 pi R_T (C_pd+1.5 pF)): first-order indicator only (pessimistic for a fast TIA).\n")
    # Table 7 emitter power budgets
    print("TABLE 6: Q at 35 cm lateral (and 0 cm) for an AVERAGE emitter-power budget, bare FDS010, 20k, "
          "low/high noise")
    print("  I = P / (Vf x 0.5), capped at the continuous rating; 'spread140' = same radiant flux "
          "spread into a 140 deg cos^m beam")
    hdr8 = (f"{'emitter':<8}{'budget':>7}{'I(mA)':>7}{'Pavg':>6}{'Ie(mW/sr)':>10}{'Q35 lo':>9}{'Q35 hi':>9}"
            f"{'Q0 lo':>9}{'Q0 hi':>9}{'spread140 Q35 lo':>18}{'hi':>9}")
    print(hdr8)
    print("-" * len(hdr8))
    for k in ("sfh4550", "sfh4715"):
        em = EMITTERS[k]
        for bud in (50.0, 100.0):
            cur = min(bud / (em.vf * DUTY), em.i_max_cont_mA)
            ie = em.intensity(cur)
            kw = dict(det=det, height_m=h, rt=20e3, filter_T=args.filter_T, er=args.er, bw=bw,
                      ambient=amb, target_vpp=args.target_vpp)
            p35 = link_point(ie, em.view_deg, em.wavelength_nm, lateral_m=0.35, **kw)
            p0 = link_point(ie, em.view_deg, em.wavelength_nm, lateral_m=0.0, **kw)
            flux = ie * beam_flux_factor(em.view_deg)
            ie_w = flux / beam_flux_factor(140.0)
            pw = link_point(ie_w, 140.0, em.wavelength_nm, lateral_m=0.35, **kw)
            cap = "*" if cur >= em.i_max_cont_mA - 1e-9 and bud / (em.vf * DUTY) > cur else " "
            print(f"{k:<8}{bud:>6g}{cap}{cur:>7.1f}{em.avg_power_mW(cur):>6.0f}{ie*1e3:>10.4g}{p35['Q']:>9.3g}"
                  f"{p35['Q_hi']:>9.3g}{p0['Q']:>9.3g}{p0['Q_hi']:>9.3g}{pw['Q']:>18.3g}{pw['Q_hi']:>9.3g}")
    print("  * budget exceeds the continuous current rating; drive capped (Pavg shown is the capped power).\n")
    # Table 8 noise sensitivity with Fig 9/10 value at the detector capacitance
    print("TABLE 7: sensitivity to source capacitance: TIA noise from OPA857 Fig. 9 (20k) read at C_pd "
          "(READ VISUALLY, +/-2 nA)")
    c = det["c_pf"]
    i135 = tia_noise_fig(20e3, c)
    print(f"  FDS010 C = {c:g} pF -> Fig. 9 reads {i135*1e9:.0f} nA rms (135 MHz) vs 15 nA at Cs = 1.5 pF; "
          f"5k (Fig. 10) reads {tia_noise_fig(5e3, c)*1e9:.0f} nA vs 25 nA")
    hdr9 = f"{'emitter':<8}{'I(mA)':>6}{'Q_lo':>9}{'Q_hi':>9}{'short_lo(dB)':>13}{'short_hi(dB)':>13}"
    print(hdr9)
    print("-" * len(hdr9))
    for k, em, cur in cases:
        kw = dict(view_deg=em.view_deg, wl_nm=em.wavelength_nm, det=det, lateral_m=0.35, height_m=h,
                  rt=20e3, filter_T=args.filter_T, er=args.er, bw=bw, ambient=amb,
                  target_vpp=args.target_vpp, i135=i135)
        if k == "sfh4550":
            continue
        p = link_point(em.intensity(cur), **kw)
        nl = gain_needed_for_q(q9, "lo", i_e=em.intensity(cur), **kw)
        nh = gain_needed_for_q(q9, "hi", i_e=em.intensity(cur), **kw)
        print(f"{k:<8}{cur:>6g}{p['Q']:>9.3g}{p['Q_hi']:>9.3g}{db(nl):>13.1f}{db(nh):>13.1f}")


def target_emitters(wpe_ref):
    """Reference QBLP601 at 50 mA plus 140 deg targets costed from flux / WPE (review A1 fix).

    Drive current for a target = (flux / WPE_ref) / Vf: what a QBLP601-efficiency LED would
    need; it is NOT the 0.9 mW/sr/mA SFH 4715AS figure (a +/-45 deg part) used before.
    """
    out = [("NIR QBLP601 50 mA", EMITTERS["nir"], 50.0)]
    for mw in (10, 30, 100):
        flux, _ = emitter_cost(mw * 1e-3, 140.0, wpe_ref)
        cur = flux / wpe_ref / QBLP_VF * 1e3
        out.append((f"{mw} mW/sr 140deg", Emitter(f"Target emitter {mw} mW/sr", 850.0, mw * 1e-3,
                                                  cur, cur, 140.0, QBLP_VF), cur))
    return out


def apd_sweep(args):
    """APD tables: Q vs M, minimum M, emitter power, ambient saturation (850 nm, 20k)."""
    h = args.height_cm / 100
    lat = args.lateral_cm / 100
    bw = args.bw_mhz * 1e6
    q9, q3 = q_for_ber(1e-9), q_for_ber(1e-3)
    ms = (10, 20, 30, 50, 75, 100, 150)
    wref = wpe_reference()
    emitters = target_emitters(wref)
    apds = [k for k, d in DETECTORS.items() if d.get("apd")]
    print(f"APD SWEEP: {lat*100:g} cm lateral, {args.height_cm:g} cm height, 850 nm, R_T=20k, T={args.filter_T}, "
          f"B={args.bw_mhz:g} MHz, gain 1x, ER=inf, ambient {args.ambient_nA:g} nA")
    print(f"Excess noise model: {'F = M^x (Hamamatsu, x per part)' if EXCESS_MODEL == 'power' else 'McIntyre F = kM + (2-1/M)(1-k)'}"
          f"{'; McIntyre k=0.02 for parts with no x (C30902EH)' if EXCESS_MODEL == 'power' else ''}")
    print("TIA noise at 20k, i135 per APD (" + ("OPA857 datasheet value at Cs = 1.5 pF" if args.tia_cs == "datasheet"
          else "OPA857 Fig. 9 read at the APD capacitance") + "): " + ", ".join(
          f"{k} {tia_i135(20e3, DETECTORS[k]['c_pf'], args.tia_cs)*1e9:.1f} nA -> low "
          f"{tia_noise_bounds(20e3, bw, tia_i135(20e3, DETECTORS[k]['c_pf'], args.tia_cs))[0]*1e9:.1f} nA"
          for k in apds) + "; Q_lo = low-noise bound (i135 sqrt(B/135 MHz)), Q_hi = high-noise bound (i135)")
    print(f"Target Q: 6.00 (BER 1e-9), {q3:.2f} (BER 1e-3).  R at 850 nm for all emitters (NIR baseline is 765 nm; ~2% diff).")
    kw0 = dict(lateral_m=lat, height_m=h, rt=20e3, filter_T=args.filter_T, er=args.er, bw=bw,
               ambient=args.ambient_nA * 1e-9, target_vpp=args.target_vpp)

    def kwf(em, det):
        return dict(view_deg=em.view_deg, wl_nm=850.0, det=det,
                    i135=tia_i135(20e3, det["c_pf"], args.tia_cs), **kw0)

    print(f"Emitters (140 deg, flux = Ie x 2pi/(m+1) = Ie x {beam_flux_factor(140.0):.3f} sr; current at the "
          f"QBLP601 WPE {wref:.1%}, Vf {QBLP_VF} V; Pavg = flux/WPE x 0.5):")
    for n, em, c in emitters:
        flux, pa = emitter_cost(em.intensity(c), em.view_deg, wref)
        _, pa30 = emitter_cost(em.intensity(c), em.view_deg, WPE)
        print(f"  {n:<19} Ie {em.intensity(c)*1e3:6.3g} mW/sr, flux {flux*1e3:6.1f} mW, I {c:7.1f} mA, "
              f"Pavg {pa*1e3:6.1f} mW at WPE {wref:.1%} ({pa30*1e3:5.1f} mW at {WPE:.0%} ASSUMED)")
    print("TABLE A: Q (low-noise bound / high-noise bound) vs avalanche gain M")
    print(f"{'APD':<10}{'M':>4}" + "".join(f"{n:>22}" for n, _, _ in emitters))
    for dn in apds:
        d = DETECTORS[dn]
        for m in ms:
            row = f"{dn:<10}{m:>4}" + ("!" if m > d["m_max"] else " ")
            for n, em, c in emitters:
                p = link_point(em.intensity(c), m_apd=float(m), **kwf(em, d))
                row += f"{p['Q']:>10.3g} /{p['Q_hi']:>9.3g}"
            print(row)
    print(f"  '!' = above datasheet M. M max (datasheet): " + ", ".join(f"{k} {DETECTORS[k]['m_max']:g}" for k in apds)
          + "; excess noise per part: " + ", ".join(f"{k} {excess_label(DETECTORS[k])}" for k in apds) + "\n")
    print("TABLE B: minimum M for Q = 6 and Q = 3.09 (lo / hi noise bound) and average emitter power at the QBLP601 WPE")
    hdr = (f"{'APD':<10}{'emitter':<19}{'I(mA)':>7}{'Pavg(mW)':>9}{'Q6 lo':>8}{'Q6 hi':>8}{'3.09 lo':>9}{'3.09 hi':>9}"
           f"{'Qmax lo (M)':>14}{'Qmax hi (M)':>14}")
    print(hdr)
    print("-" * len(hdr))

    def mfmt(m, mmax):
        return "none" if m is None else (f"{m:.3g}" + ("!" if m > mmax else ""))

    for dn in apds:
        d = DETECTORS[dn]
        for n, em, c in emitters:
            kw = dict(i_e=em.intensity(c), **kwf(em, d))
            r6 = {b: apd_m_needed(q9, b, **kw) for b in ("lo", "hi")}
            r3 = {b: apd_m_needed(q3, b, **kw) for b in ("lo", "hi")}
            mm = d["m_max"]
            pa = emitter_cost(em.intensity(c), em.view_deg, wref)[1] if n != "NIR QBLP601 50 mA" \
                else em.avg_power_mW(c) * 1e-3
            qm = [f"{r6[b][1]:.2f} (M{r6[b][2]:.0f})" for b in ("lo", "hi")]
            print(f"{dn:<10}{n:<19}{c:>7.1f}{pa*1e3:>9.1f}{mfmt(r6['lo'][0], mm):>8}{mfmt(r6['hi'][0], mm):>8}"
                  f"{mfmt(r3['lo'][0], mm):>9}{mfmt(r3['hi'][0], mm):>9}{qm[0]:>14}{qm[1]:>14}")
    print("  '!' = above that part's datasheet maximum M; 'none' = never reached for M <= 1000; "
          "Qmax = peak of Q(M) over M <= 1000, set by excess noise;\n  1 = target already met at M = 1.\n")
    lin = 60e-6
    print("Ambient saturation (OPA857 20k linear range 60 uA): in-band ambient power on the die "
          "P_sat = 60 uA / (M x R850)")
    for dn in apds:
        r = DETECTORS[dn]["resp"][850]
        print(f"  {dn:<10} R850 {r:.2f} A/W: " + ", ".join(
            f"M={m}: {lin/(m*r)*1e6:.2f} uW" for m in (50, 100)))


def apd_budget(args):
    """Review A1/A2 tables R0-R5 for the built S12023-10 + OPA857 20k chain."""
    det = DETECTORS["S12023-10"]
    h = args.height_cm / 100
    lat = args.lateral_cm / 100
    q9, q3 = q_for_ber(1e-9), q_for_ber(1e-3)
    wref = wpe_reference()
    mcap = det["m_max"]
    print(f"APD BUDGET (review A1/A2): S12023-10 (diam {det['diam_mm']} mm, {det['c_pf']:g} pF, R850 "
          f"{det['resp'][850]} A/W, F = M^{det['x']}), OPA857 20k, {lat*100:g} cm lateral, {args.height_cm:g} cm "
          f"height, T = {args.filter_T}, 850 nm, ER = inf, ambient {args.ambient_nA:g} nA, M cap {mcap:g} (datasheet)")
    print(f"Q target {q9:.2f} (BER 1e-9), floor {q3:.2f} (BER 1e-3).  Optical dB = 10log(P ratio) = electrical "
          "(20log I) dB / 2.\n")

    # R0 chain noise bandwidth
    print(f"TABLE R0: noise-equivalent bandwidth of the built chain: OPA857 2nd-order x one-pole "
          f"{F_LPF/1e6:.1f} MHz low-pass (R56 49.9 / C54 47 pF)")
    print(f"{'f_TIA(MHz)':>10}{'Q_TIA':>7}{'NEB(MHz)':>10}{'B_eq vs 135 MHz spec(MHz)':>27}")
    for ft in F_TIA_RANGE:
        for qt in (0.707, 0.8):
            neb, beq = chain_neb(ft, qt)
            print(f"{ft/1e6:>10.0f}{qt:>7.3f}{neb/1e6:>10.1f}{beq/1e6:>27.1f}")
    print(f"  Default --bw-mhz = {BW_BUILT_MHZ:g} (NEB). B_eq applies if the datasheet 135 MHz brickwall figure "
          "already includes the\n  OPA857 roll-off; then 70 MHz is optimistic by ~0.4 dB optical. One-pole "
          "68 MHz alone has NEB 107 MHz.\n")

    # R1 energy check of the old target emitters
    print("TABLE R1: energy check of the old --apd-sweep targets (0.9 mW/sr/mA, Vf 1.5 V, 140 deg)")
    print(f"{'emitter':<22}{'Ie(mW/sr)':>10}{'I(mA)':>8}{'P_el,on(mW)':>12}{'flux(mW)':>10}{'implied WPE':>13}")
    for mw in (30, 100):
        cur = mw / 0.9
        flux = mw * beam_flux_factor(140.0)
        pel = cur * 1.5
        print(f"{str(mw)+' mW/sr 140deg (old)':<22}{mw:>10g}{cur:>8.1f}{pel:>12.1f}{flux:>10.1f}{flux/pel:>13.0%}")
    flux = 1.0 * beam_flux_factor(140.0)
    print(f"{'QBLP601 20 mA':<22}{1.0:>10g}{20.0:>8.1f}{20*QBLP_VF:>12.1f}{flux:>10.2f}{flux/(20*QBLP_VF):>13.1%}")
    f45 = 900 * beam_flux_factor(90.0)
    for vf in (1.5, 3.2):
        print(f"{'SFH 4715AS 1 A, Vf '+str(vf):<22}{900:>10g}{1000:>8.0f}{1000*vf:>12.0f}{f45:>10.0f}"
              f"{f45/(1000*vf):>13.0%}")
    print(f"  flux = Ie x 2pi/(m+1): 140 deg (m {lambertian_order(140):.3f}) -> {beam_flux_factor(140):.3f} sr; "
          f"+/-45 deg (m {lambertian_order(90):.2f}) -> {beam_flux_factor(90):.3f} sr.\n")

    # R2 required intensity at the weak-end optimum
    print(f"TABLE R2: on-axis Ie needed at {lat*100:g} cm lateral (140 deg beam) at the Q-optimal M (M <= {mcap:g}); "
          f"Pavg at WPE {wref:.1%} (QBLP601-derived) and {WPE:.0%} (ASSUMED)")
    hdr = (f"{'case':<22}{'bnd':>4}{'i_tia(nA)':>10}{'Q':>6}{'M_opt':>7}{'P_die(nW)':>10}{'Ie(mW/sr)':>10}"
           f"{'flux(mW)':>9}{'Pavg@ref':>9}{'Pavg@30%':>9}{'M_opt free':>11}")
    print(hdr)
    print("-" * len(hdr))
    g = die_power(1.0, 140.0, lat, h, det, args.filter_T)     # W on die per W/sr
    cases = [("old: 35 MHz, 1.5 pF", 35e6, "datasheet"), ("70 MHz, 1.5 pF", 70e6, "datasheet"),
             ("BUILT: 70 MHz, 6 pF", args.bw_mhz * 1e6, "fig")]
    req = {}
    for name, bw, mode in cases:
        i135 = tia_i135(20e3, det["c_pf"], mode)
        for bd in ("lo", "hi"):
            kw = dict(det=det, wl_nm=850.0, rt=20e3, bw=bw, i135=i135, bound=bd, er=args.er,
                      ambient=args.ambient_nA * 1e-9)
            lo_n, hi_n = tia_noise_bounds(20e3, bw, i135)
            for qt in (q9, q3):
                p, mo = p_floor(qt, m_cap=mcap, **kw)
                pf, mf = p_floor(qt, m_cap=1000.0, **kw)
                ie = p / g
                flux, pa = emitter_cost(ie, 140.0, wref)
                pa30 = emitter_cost(ie, 140.0, WPE)[1]
                req[(name, bd, round(qt, 2))] = (p, mo, ie)
                print(f"{name:<22}{bd:>4}{(lo_n if bd == 'lo' else hi_n)*1e9:>10.1f}{qt:>6.2f}{mo:>7.0f}{p*1e9:>10.2f}"
                      f"{ie*1e3:>10.2f}{flux*1e3:>9.1f}{pa*1e3:>9.0f}{pa30*1e3:>9.0f}{mf:>11.0f}")
    print(f"  P_die = on-state power on the bare die: {g*1e6:.3f} nW per mW/sr of on-axis Ie at this geometry.\n"
          f"  'M_opt free' = optimum without the M <= {mcap:g} cap. Pavg (mW) = flux/WPE x 0.5 "
          "(emitter only; driver losses not included).\n")

    # R3 Q vs M for the built case at the Q = 6 intensity
    name = "BUILT: 70 MHz, 6 pF"
    bw = args.bw_mhz * 1e6
    i135 = tia_i135(20e3, det["c_pf"], "fig")
    ie6 = req[(name, "lo", round(q9, 2))][2]
    print(f"TABLE R3: Q (lo / hi bound) vs M, built case, for three emitters at {lat*100:g} cm lateral")
    ems = [("QBLP601 50 mA", EMITTERS["nir"].intensity(50.0)), (f"Ie {ie6*1e3:.1f} (Q6 lo)", ie6),
           ("Ie 30 mW/sr", 30e-3)]
    print(f"{'M':>5}" + "".join(f"{n:>24}" for n, _ in ems))
    for m in (10, 20, 30, 50, 75, 86, 100, 114, 150, 200):
        row = f"{m:>5}"
        for _, ie in ems:
            p = die_power(ie, 140.0, lat, h, det, args.filter_T)
            ql = q_apd_power(p, det, 850.0, m, 20e3, bw, i135, "lo", args.er, args.ambient_nA * 1e-9)
            qh = q_apd_power(p, det, 850.0, m, 20e3, bw, i135, "hi", args.er, args.ambient_nA * 1e-9)
            row += f"{ql:>12.2f} /{qh:>9.2f}" + ("!" if m > mcap else " ")
        print(row)
    for n, ie in ems:
        p = die_power(ie, 140.0, lat, h, det, args.filter_T)
        bl = best_m_for_power(p, 1000.0, det=det, wl_nm=850.0, rt=20e3, bw=bw, i135=i135, bound="lo")
        bh = best_m_for_power(p, 1000.0, det=det, wl_nm=850.0, rt=20e3, bw=bw, i135=i135, bound="hi")
        print(f"  {n}: Q-optimal M {bl[1]:.0f} (lo, Q {bl[0]:.2f}) / {bh[1]:.0f} (hi, Q {bh[0]:.2f})")
    print("  '!' = above the datasheet M of 100. Q-optimum: M^(2+x) = 2 i_tia^2 / (x 2q I_avg B), so it rises as "
          "the signal falls.\n")

    # R4 range in optical dB
    mmin = args.m_min
    print(f"TABLE R4: dynamic range, built case, in on-die optical power (on-state) and both dB conventions; "
          f"firmware M floor {mmin:g} (ASSUMED)")
    hdr = f"{'level':<52}{'bnd':>4}{'I_pp(uA)':>10}{'P_die(nW)':>11}{'opt dB':>8}{'el dB':>7}"
    print(hdr)
    print("-" * len(hdr))
    r850 = det["resp"][850]
    for bd in ("lo", "hi"):
        kw = dict(det=det, wl_nm=850.0, rt=20e3, bw=bw, i135=i135, bound=bd, er=args.er,
                  ambient=args.ambient_nA * 1e-9)
        p6, mw = p_floor(q9, m_cap=mcap, **kw)
        p3, _ = p_floor(q3, m=mw, **kw)
        mw_r = mw
        rows = [(f"Q = 3.09 floor at M {mw_r:.0f}, 20k", p3 * r850 * mw_r, p3),
                (f"Q = 6 floor (weak end) at M {mw_r:.0f}, 20k", p6 * r850 * mw_r, p6)]
        for sw in POST_SWING_VPP:
            ic = sw / (G_POST * RT_EFF[20e3])
            rows.append((f"post-amp clip {sw:g} Vpp, M {mw_r:.0f}, 20k", ic, ic / (r850 * mw_r)))
        rows.append((f"OPA857 saturation 60 uA, M {mw_r:.0f}, 20k", TIA_SAT[20e3], TIA_SAT[20e3] / (r850 * mw_r)))
        for sw in POST_SWING_VPP:
            ic = sw / (G_POST * RT_EFF[5e3])
            rows.append((f"post-amp clip {sw:g} Vpp, M {mmin:g}, 5k (firmware)", ic, ic / (r850 * mmin)))
        rows.append((f"OPA857 saturation 240 uA, M {mmin:g}, 5k (firmware)", TIA_SAT[5e3], TIA_SAT[5e3] / (r850 * mmin)))
        for lab, ipp, p in rows:
            od = db(p / p6)
            print(f"{lab:<52}{bd:>4}{ipp*1e6:>10.3g}{p*1e9:>11.4g}{od:>8.1f}{2*od:>7.1f}")
        clip_lo = POST_SWING_VPP[0] / (G_POST * RT_EFF[20e3]) / (r850 * mw_r)
        clip_hi = POST_SWING_VPP[1] / (G_POST * RT_EFF[20e3]) / (r850 * mw_r)
        print(f"  {bd}: single setting (M {mw_r:.0f}, 20k), Q = 6 to post-amp clip: {db(clip_lo/p6):.1f} to "
              f"{db(clip_hi/p6):.1f} dB optical; to OPA857 saturation: {db(TIA_SAT[20e3]/(r850*mw_r)/p6):.1f} dB optical")
        print(f"  {bd}: firmware extension (strong end only): M {mw_r:.0f} -> {mmin:g} = {db(mw_r/mmin):.1f} dB optical; "
              f"20k -> 5k = {db(RT_EFF[20e3]/RT_EFF[5e3]):.1f} dB optical (post-amp clip), "
              f"{db(TIA_SAT[5e3]/TIA_SAT[20e3]):.1f} dB (TIA saturation); weak-end extension 0 dB")
    print("  Electrical (20log I) dB = 2 x optical dB. Firmware knobs (lower M, 5k) only LOWER gain: they move the\n"
          "  strong end; the weak end is fixed by M <= 100 and 20k, so fade margin = emitter margin (row R5).\n")

    # R5 weak-end margin
    print(f"TABLE R5: weak-end margin, built case, optical dB above the Q = 6 and Q = 3.09 floors at the best "
          f"M <= {mcap:g} (lo / hi bound)")
    hdr = (f"{'emitter (140 deg)':<22}{'Ie(mW/sr)':>10}{'Pavg@ref':>9}{'Pavg@30%':>9}{'off(cm)':>8}{'P_die(nW)':>10}"
           f"{'Q6 lo':>7}{'Q6 hi':>7}{'Q3.09 lo':>9}{'Q3.09 hi':>9}")
    print(hdr)
    print("-" * len(hdr))
    floors = {}
    for bd in ("lo", "hi"):
        kw = dict(det=det, wl_nm=850.0, rt=20e3, bw=bw, i135=i135, bound=bd, er=args.er,
                  ambient=args.ambient_nA * 1e-9)
        floors[(bd, 6)] = p_floor(q9, m_cap=mcap, **kw)[0]
        floors[(bd, 3)] = p_floor(q3, m_cap=mcap, **kw)[0]
    for n, ie in (("QBLP601 20 mA", 1.0e-3), ("QBLP601 50 mA", 2.5e-3), ("target 10 mW/sr", 10e-3),
                  ("target 30 mW/sr", 30e-3), ("target 100 mW/sr", 100e-3)):
        pa = emitter_cost(ie, 140.0, wref)[1]
        pa30 = emitter_cost(ie, 140.0, WPE)[1]
        for off in (35, 0):
            p = die_power(ie, 140.0, off / 100, h, det, args.filter_T)
            print(f"{n:<22}{ie*1e3:>10.3g}{pa*1e3:>9.0f}{pa30*1e3:>9.0f}{off:>8}{p*1e9:>10.3g}"
                  f"{db(p/floors[('lo', 6)]):>7.1f}{db(p/floors[('hi', 6)]):>7.1f}"
                  f"{db(p/floors[('lo', 3)]):>9.1f}{db(p/floors[('hi', 3)]):>9.1f}")
    print("  Negative = short of the floor. Pavg in mW (emitter only). Margin excludes ambient (0), comparator offset\n"
          "  and noise, 1/f, ISI, tilt, shadowing and the unmeasured received power (review A4).")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", action="store_true", help="print the sweep tables")
    ap.add_argument("--apd-sweep", action="store_true", help="print the APD tables (Q vs M, minimum M, ambient)")
    ap.add_argument("--apd-budget", action="store_true",
                    help="review A1/A2 tables R0-R5 (built chain: NEB, energy check, required Ie, M optimum, "
                         "optical-dB range, weak-end margin)")
    ap.add_argument("--tia-cs", choices=["fig", "datasheet"], default="fig",
                    help="APD sweep TIA noise: fig = OPA857 Fig. 9 at the APD capacitance (default, built); "
                         "datasheet = 15 nA at 1.5 pF (pre-2026-10-22 behaviour)")
    ap.add_argument("--m-min", type=float, default=5.0, help="lowest usable APD gain for range tables (ASSUMED)")
    ap.add_argument("--excess-model", choices=["power", "mcintyre"], default="power",
                    help="APD excess noise: power = F = M^x (Hamamatsu, default); mcintyre = kM + (2-1/M)(1-k)")
    ap.add_argument("--emitter", choices=list(EMITTERS), help="default: all four emitters")
    ap.add_argument("--current", type=float, dest="current",
                    help="drive current, mA (default 20 for red/nir, rated ref. current otherwise)")
    ap.add_argument("--vf", type=float, help="forward voltage override for power column, V")
    ap.add_argument("--led-intensity", type=float, help="LED upgrade: on-axis radiant intensity, mW/sr")
    ap.add_argument("--led-wavelength", type=float, default=765.0, help="upgrade LED wavelength, nm")
    ap.add_argument("--led-view", type=float, default=140.0, help="upgrade LED full viewing angle, deg")
    ap.add_argument("--detector", choices=list(DETECTORS), default="FDS010")
    ap.add_argument("--apd-m", type=float, default=50.0, help="APD avalanche gain M (APD detectors only)")
    ap.add_argument("--rt", choices=["5k", "20k"], default="20k")
    ap.add_argument("--lateral-cm", type=float, default=35.0)
    ap.add_argument("--height-cm", type=float, default=50.0)
    ap.add_argument("--filter-T", type=float, default=0.9, help="optical filter transmission")
    ap.add_argument("--gain", type=float, default=1.0, help="optical gain G_optics (etendue-checked)")
    ap.add_argument("--fov", type=float, default=90.0, help="optic FOV half-angle, deg (sets etendue cap)")
    ap.add_argument("--er", type=float, default=math.inf, help="extinction ratio (default inf)")
    ap.add_argument("--bw-mhz", type=float, default=BW_BUILT_MHZ,
                    help="noise bandwidth, MHz (default: as-built ~70 MHz NEB; pre-2026-10-22 runs used 35)")
    ap.add_argument("--ambient-nA", type=float, default=0.0, help="ambient DC photocurrent, nA")
    ap.add_argument("--target-vpp", type=float, default=1.0, help="slicer target, Vpp")
    ap.add_argument("--tia-swing", type=float, default=1.2, help="OPA857 usable output swing, V (ASSUMED)")
    ap.add_argument("--vga-min", type=float, default=10.0)
    ap.add_argument("--vga-max", type=float, default=100.0)
    args = ap.parse_args(argv)
    global EXCESS_MODEL
    EXCESS_MODEL = args.excess_model
    if args.apd_budget:
        apd_budget(args)
    elif args.apd_sweep:
        apd_sweep(args)
    elif args.sweep:
        sweep(args)
    else:
        single_point(args)


if __name__ == "__main__":
    main()
