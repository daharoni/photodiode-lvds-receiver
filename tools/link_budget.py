#!/usr/bin/env python3
"""Parametric optical link-budget calculator for the headstage-LED -> PIN/APD + TIA receiver.

Chain: LED radiant intensity -> irradiance at receiver -> collected power
(detector area x optical gain, limited by etendue) -> photocurrent (x avalanche
gain for an APD) -> TIA swing and noise -> Q / BER -> required VGA gain.

Python 3 standard library only.  Modes: --sweep (tables 1-7), --apd-sweep (APD tables).  Run `python3 tools/link_budget.py --help`.
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
WPE = 0.30                     # wall-plug efficiency for flux->electrical estimates, ASSUMED


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
                   1.0e-3, 20.0, 50.0, 140.0, 1.5),                    # DATASHEET typ; Vf ASSUMED
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


def apd_sweep(args):
    """APD tables: Q vs M, minimum M, emitter power, ambient saturation (850 nm, 20k)."""
    h = args.height_cm / 100
    lat = args.lateral_cm / 100
    bw = args.bw_mhz * 1e6
    q9, q3 = q_for_ber(1e-9), q_for_ber(1e-3)
    lo_n, hi_n = tia_noise_bounds(20e3, bw)
    ms = (10, 20, 30, 50, 75, 100)
    per_ma = 0.9e-3      # W/sr per mA for the generic target emitters
    emitters = [("NIR QBLP601 50 mA", EMITTERS["nir"], 50.0)]
    for mw in (30, 100):
        cur = mw / (per_ma * 1e3)
        emitters.append((f"{mw} mW/sr 140deg", Emitter(f"Target emitter {mw} mW/sr", 850.0, mw * 1e-3,
                         cur, cur, 140.0, 1.5), cur))
    apds = [k for k, d in DETECTORS.items() if d.get("apd")]
    print(f"APD SWEEP: {lat*100:g} cm lateral, {args.height_cm:g} cm height, 850 nm, R_T=20k, T={args.filter_T}, "
          f"B={args.bw_mhz:g} MHz, gain 1x, ER=inf, ambient {args.ambient_nA:g} nA")
    print(f"Excess noise model: {'F = M^x (Hamamatsu, x per part)' if EXCESS_MODEL == 'power' else 'McIntyre F = kM + (2-1/M)(1-k)'}"
          f"{'; McIntyre k=0.02 for parts with no x (C30902EH)' if EXCESS_MODEL == 'power' else ''}")
    print(f"TIA noise at 20k (OPA857 datasheet bounds at Cs = 1.5 pF): low {lo_n*1e9:.2f} nA, high {hi_n*1e9:.2f} nA; "
          f"Q_lo = low-noise bound, Q_hi = high-noise bound")
    print(f"Target Q: 6.00 (BER 1e-9), {q3:.2f} (BER 1e-3).  R at 850 nm for all emitters (NIR baseline is 765 nm; ~2% diff).")
    kw0 = dict(lateral_m=lat, height_m=h, rt=20e3, filter_T=args.filter_T, er=args.er, bw=bw,
               ambient=args.ambient_nA * 1e-9, target_vpp=args.target_vpp)

    def kwf(em, det):
        return dict(i_e=None, view_deg=em.view_deg, wl_nm=850.0, det=det, **kw0)

    print("Emitters: " + "; ".join(f"{n}: Ie {em.intensity(c)*1e3:g} mW/sr, {c:.1f} mA, Pavg {em.avg_power_mW(c):.1f} mW"
                                  for n, em, c in emitters) + "  (Vf 1.5 V, 50% duty; targets at 0.9 mW/sr/mA)")
    print("TABLE A: Q (low-noise bound / high-noise bound) vs avalanche gain M")
    print(f"{'APD':<10}{'M':>4}" + "".join(f"{n:>22}" for n, _, _ in emitters))
    for dn in apds:
        d = DETECTORS[dn]
        for m in ms:
            row = f"{dn:<10}{m:>4}"
            for n, em, c in emitters:
                p = link_point(em.intensity(c), m_apd=float(m), **{k: v for k, v in kwf(em, d).items() if k != "i_e"})
                row += f"{p['Q']:>10.3g} /{p['Q_hi']:>9.3g}"
            print(row)
    print(f"  M max (datasheet): " + ", ".join(f"{k} {DETECTORS[k]['m_max']:g}" for k in apds)
          + "; excess noise per part: " + ", ".join(f"{k} {excess_label(DETECTORS[k])}" for k in apds) + "\n")
    print("TABLE B: minimum M for Q = 6 and Q = 3.09 (lo / hi noise bound) and average emitter power")
    hdr = (f"{'APD':<10}{'emitter':<19}{'I(mA)':>7}{'Pavg(mW)':>9}{'Q6 lo':>8}{'Q6 hi':>8}{'3.09 lo':>9}{'3.09 hi':>9}"
           f"{'Qmax lo (M)':>14}{'Qmax hi (M)':>14}")
    print(hdr)
    print("-" * len(hdr))

    def mfmt(m, mmax):
        return "none" if m is None else (f"{m:.3g}" + ("!" if m > mmax else ""))

    for dn in apds:
        d = DETECTORS[dn]
        for n, em, c in emitters:
            kw = dict(i_e=em.intensity(c), **{k: v for k, v in kwf(em, d).items() if k != "i_e"})
            r6 = {b: apd_m_needed(q9, b, **kw) for b in ("lo", "hi")}
            r3 = {b: apd_m_needed(q3, b, **kw) for b in ("lo", "hi")}
            mm = d["m_max"]
            qm = [f"{r6[b][1]:.2f} (M{r6[b][2]:.0f})" for b in ("lo", "hi")]
            print(f"{dn:<10}{n:<19}{c:>7.1f}{em.avg_power_mW(c):>9.1f}{mfmt(r6['lo'][0], mm):>8}{mfmt(r6['hi'][0], mm):>8}"
                  f"{mfmt(r3['lo'][0], mm):>9}{mfmt(r3['hi'][0], mm):>9}{qm[0]:>14}{qm[1]:>14}")
    print("  '!' = above that part's datasheet maximum M; 'none' = never reached for M <= 1000; "
          "Qmax = peak of Q(M), set by excess noise;\n  1 = target already met at M = 1.\n")
    lin = 60e-6
    print("Ambient saturation (OPA857 20k linear range 60 uA): in-band ambient power on the die "
          "P_sat = 60 uA / (M x R850)")
    for dn in apds:
        r = DETECTORS[dn]["resp"][850]
        print(f"  {dn:<10} R850 {r:.2f} A/W: " + ", ".join(
            f"M={m}: {lin/(m*r)*1e6:.2f} uW" for m in (50, 100)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", action="store_true", help="print the sweep tables")
    ap.add_argument("--apd-sweep", action="store_true", help="print the APD tables (Q vs M, minimum M, ambient)")
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
    ap.add_argument("--bw-mhz", type=float, default=35.0, help="noise bandwidth, MHz")
    ap.add_argument("--ambient-nA", type=float, default=0.0, help="ambient DC photocurrent, nA")
    ap.add_argument("--target-vpp", type=float, default=1.0, help="slicer target, Vpp")
    ap.add_argument("--tia-swing", type=float, default=1.2, help="OPA857 usable output swing, V (ASSUMED)")
    ap.add_argument("--vga-min", type=float, default=10.0)
    ap.add_argument("--vga-max", type=float, default=100.0)
    args = ap.parse_args(argv)
    global EXCESS_MODEL
    EXCESS_MODEL = args.excess_model
    if args.apd_sweep:
        apd_sweep(args)
    elif args.sweep:
        sweep(args)
    else:
        single_point(args)


if __name__ == "__main__":
    main()
