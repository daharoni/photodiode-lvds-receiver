#!/usr/bin/env python3
"""APD bias supply, Rev A: LT8365 boost + one charge-pump doubler, 5 V in -> 140 V (100-220 V).

Python 3 standard library only.  Prints component values and checks used by
docs/calculations/apd-bias-design.md.  Labels: DS = DATASHEET (LT8365 Rev. A page cited),
DER = DERIVED here, ASM = ASSUMED (not from a document).  Edit the PARAMS block and rerun.
"""
import cmath
import math

# ----------------------------------------------------------------------------- parameters
P = dict(
    vin_nom=5.0, vin_tol=0.05,             # board rail 5 V +/-5 %                     (requirement)
    vout=140.0, vout_min=100.0, vout_max=220.0,
    iload=1.0e-3,                          # total load budget                          (requirement)
    f_nom=500e3,                           # DS p.1/p.11: 100-500 kHz is the whole range
    rt_k=84.5,                             # DS p.11 Table 1 value for 500 kHz
    f_tol_hi=535 / 500,                    # DS p.3: RT=84.5k -> 465/500/535 kHz
    toff_max=115e-9, ton_max=200e-9,       # DS p.3 (min off-time max, min on-time max, VIN=24 V test)
    ilim_min=1.5, ilim_typ=2.0,            # DS p.3 switch current limit 1.5/2/2.7 A
    i_burst=0.325,                         # DS p.10 Burst Mode current limit "approximately 325 mA"
    vsw_abs=150.0, vd=0.5,                 # DS p.2; Schottky Vf at ~1 mA/hot ASM
    eta=0.70,                              # ASM (demo is 77 % at 10 mA/250 V, DS DC2838A p.1)
    ring=1.20,                             # ASM switch-node overshoot factor
    L=10e-6,                               # DS DC2838A p.4 (74437324100)
    c_pump=0.1e-6, c_pump_derate=0.5,      # ASM: X7R 200 V part keeps ~50 % at ~110 V
    vfb=1.600, vfb_lo=1.568, vfb_hi=1.636, # DS p.3
    ifbx=10e-9,                            # DS p.3 max
    # FBX network
    rt=8.2e6, rd=160e3, rp=274e3,          # top chain (4 x 2.05M), DAC leg (R13 10k + R14 150k since 2026-10-22, was 452k), pot leg
    pot_fitted=False,                      # RV1/R15 are DNP in production (review S2, 2026-10-22); True = bench build with the pot leg
    ntc_r25=10e3, ntc_beta=3950.0, rs_fix=86.6e3,
    vtrim_mid=1.65, vtrim_max=3.3,         # MCP4728 DAC with VDD (3.3 V) reference / pot rail
    tc_target=0.65,                        # V/degC, S12023 dVBR/dT (apd-selection.md)
    # cathode filter
    r1=27e3, c1=10e-9, r2=10e3, c2=10e-9,
    cj=6e-12, esl=1.2e-9, esr=0.05, cpar_r=0.15e-12, cpar_q=3.0e-12,   # ASM parasitics
    cj_tia_noise=26e-9,                    # A rms, project figure (OPA857 @6 pF, 135 MHz)
    i_apd_max=100e-6, iabs_tia=10e-3,      # requirement; OPA857 abs max, PDF p.5
    v_fault=235.0,                         # 220 V + 2.2 % Vfb tol + overshoot margin   DER
    # clamp
    rs_clamp=4.0e3, rb_clamp=10e6, vbe=0.60, vbe_tc=-2.0e-3,   # ASM textbook BJT
    # EN / SS
    en_top=200e3, en_bot=200e3, c_ss=0.22e-6,
    # noise sources at HV_RAW (ASM)
    ripple_pp=1.0, f_wpt=6.63e6, v_wpt=10e-3, t_edge=20e-9,
)
E96 = [1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30, 1.33, 1.37, 1.40, 1.43, 1.47,
       1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74, 1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10, 2.15, 2.21,
       2.26, 2.32, 2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09, 3.16, 3.24, 3.32,
       3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12, 4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99,
       5.11, 5.23, 5.36, 5.49, 5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32, 7.50,
       7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76]
checks = []


def e96(x):
    d = math.floor(math.log10(x))
    return min((v * 10 ** d for dec in (0, 1) for v in [e * 10 ** dec for e in E96]), key=lambda c: abs(math.log(c / x)))


def eng(x, u=""):
    for s, p in ((1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "u"), (1e-9, "n"), (1e-12, "p")):
        if abs(x) >= s:
            return f"{x / s:.4g} {p}{u}"
    return f"{x:.3g} {u}"


def chk(name, ok, detail):
    checks.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def ntc(t_c, r25=None, beta=None):
    r25 = r25 or P['ntc_r25']; beta = beta or P['ntc_beta']
    t = t_c + 273.15
    return r25 * math.exp(beta * (1 / t - 1 / 298.15))


def vout_net(rb, vdac, vw=None, vfb=None, pot=None):
    """FBX summing divider. vw = pot wiper voltage; the pot leg is only in the sum when fitted (production: DNP)."""
    vfb = vfb or P['vfb']
    pot = P['pot_fitted'] if pot is None else pot
    gp = P['rt'] / P['rp'] if pot else 0.0
    vw = P['vtrim_mid'] if vw is None else vw
    return (vfb * (1 + P['rt'] / rb + P['rt'] / P['rd'] + gp)
            - vdac * P['rt'] / P['rd'] - vw * gp)


# ----------------------------------------------------------------------------- 3a. converter
def converter():
    print("== 3a. Converter: LT8365 boost -> V1, one charge-pump doubler -> Vout = 2*V1 - Vd")
    vmin, vmax = P['vin_nom'] * (1 - P['vin_tol']), P['vin_nom'] * (1 + P['vin_tol'])
    f_hi = P['f_nom'] * P['f_tol_hi']
    f_rt = (45.2e3 / P['rt_k']) ** (1 / 1.009)   # DS p.11: RT=45.2k/f^1.009 (kOhm, kHz)
    print(f"  RT = {P['rt_k']} k -> f_osc(formula, DS p.11) = {f_rt:.0f} kHz; table value 500 kHz; max {f_hi/1e3:.0f} kHz (DS p.3)")
    print(f"  RT for exactly 500 kHz by formula = {45.2 / 500 ** 1.009 * 1e3:.2f} k ; for 300 kHz = {45.2 / 300 ** 1.009 * 1e3:.1f} k")
    dmax_allow = 1 - P['toff_max'] * f_hi
    dmin_allow = P['ton_max'] * f_hi
    print(f"  Duty limits (DS p.12): Dmax_allowed = 1 - 115ns*{f_hi/1e3:.0f}kHz = {dmax_allow:.3f}; Dmin_allowed = 200ns*f = {dmin_allow:.3f}")
    print("  Vout   V1     Vsw_pk  Vsw_pk*ring  margin  D_ccm(4.75V)  D_ccm(5.25V)  [CCM duty vs limits]")
    for vo in (P['vout_min'], P['vout'], P['vout_max']):
        v1 = (vo + P['vd']) / 2
        dccm_hi = 1 - vmin / (v1 + P['vd'])
        dccm_lo = 1 - vmax / (v1 + P['vd'])
        vsw = v1 + P['vd']
        print(f"  {vo:5.0f}  {v1:5.1f}  {vsw:6.1f}  {vsw*P['ring']:10.1f}  {P['vsw_abs']-vsw*P['ring']:6.1f}  {dccm_hi:11.3f}  {dccm_lo:12.3f}"
              f"   Dmax {'OK' if dccm_hi < dmax_allow else 'EXCEEDS'}")
    vo = P['vout_max']; v1 = (vo + P['vd']) / 2
    chk("switch node at 220 V incl. 20 % ring < 150 V abs max (DS p.2)", (v1 + P['vd']) * P['ring'] < P['vsw_abs'],
        f"{(v1 + P['vd']) * P['ring']:.0f} V")
    print("  Operation is discontinuous (DCM): at 1 mA the duty is set by energy, not by 1-Vin/V1.")
    print("  Vout   Pin(W)  Ipk_fixedf(A)  ton(ns)  treset(ns)  Dsw   Ipk_crit_CCM(A)  Pin_crit(W)  I_L_avg(mA)")
    for vo, il in ((P['vout_min'], P['iload']), (P['vout'], P['iload']), (P['vout_max'], P['iload']), (P['vout'], 100e-6)):
        v1 = (vo + P['vd']) / 2; vs = v1 + P['vd']
        pin = vo * il / P['eta']
        ipk = math.sqrt(2 * pin / (P['L'] * P['f_nom']))
        ton = P['L'] * ipk / vmin; tr = P['L'] * ipk / (vs - vmin)
        icrit = (1 / P['f_nom']) / (P['L'] * (1 / vmin + 1 / (vs - vmin)))
        pcrit = 0.5 * P['L'] * icrit ** 2 * P['f_nom']
        print(f"  {vo:5.0f}  {pin:6.3f}  {ipk:12.3f}  {ton*1e9:7.0f}  {tr*1e9:9.0f}  {ton*P['f_nom']:.2f}  {icrit:14.2f}  {pcrit:10.2f}  {pin/vmin*1e3:10.1f}  (Iload {il*1e3:.1f} mA)")
    pin = P['vout_max'] * P['iload'] / P['eta']
    ipk = math.sqrt(2 * pin / (P['L'] * P['f_nom']))
    chk("worst-case Ipk (220 V, 1 mA, every cycle) well below ILIM(min) 1.5 A (DS p.3)", ipk < 0.5 * P['ilim_min'], f"{ipk:.3f} A")
    icrit = (1 / P['f_nom']) / (P['L'] * (1 / vmin + 1 / (v1 + P['vd'] - vmin)))
    pcrit = 0.5 * P['L'] * icrit ** 2 * P['f_nom']
    chk("deep DCM at 1 mA, 220 V: Pin < 20 % of CCM-boundary power", pin < 0.2 * pcrit, f"{pin:.2f} W vs {pcrit:.2f} W")
    # min on-time
    ipk_min = vmax * P['ton_max'] / P['L']
    p_min = 0.5 * P['L'] * ipk_min ** 2 * f_hi * P['eta']
    print(f"  Min on-time pulse (200 ns max, DS p.3 tested at VIN=24 V; 5 V value NOT specified): Ipk_min = {ipk_min*1e3:.0f} mA,"
          f" delivers >= {p_min*1e3:.1f} mW = {p_min/P['vout']*1e6:.0f} uA at 140 V if every cycle fires -> below that the part must skip pulses.")
    e_b = 0.5 * P['L'] * P['i_burst'] ** 2 * P['eta']
    print(f"  Burst Mode (325 mA pulses, DS p.10): E/pulse {e_b*1e9:.0f} nJ -> pulse rate {P['vout']*100e-6/e_b/1e3:.0f} kHz at 0.1 mA, {P['vout']*1e-3/e_b/1e3:.0f} kHz at 1 mA (140 V)")
    ceff = P['c_pump'] * P['c_pump_derate'] / 2     # C5, C6 in series across Vout
    print(f"  Pulse step on Vout: skip-mode min pulse {p_min/f_hi/(ceff*P['vout'])*1e3:.1f} mV; Burst pulse {e_b/(ceff*P['vout'])*1e3:.0f} mV"
          f"  (Ceff = {ceff*1e9:.0f} nF, ASM)")
    print("  Diode/cap stress (all = V1 at 220 V):")
    v1 = (P['vout_max'] + P['vd']) / 2
    print(f"    D1..D4 reverse ~{v1+P['vd']:.0f} V vs 150 V (DFLS1150, DS p.16): margin x{150/(v1+P['vd']):.2f};  C5/C6/C7 ~{v1:.0f} V vs 200 V: x{200/v1:.2f}")
    chk("diode VR >= 1.3 x stress", 150 >= 1.3 * (v1 + P['vd']), f"{150/(v1+P['vd']):.2f}x")
    chk("pump caps VR >= 1.5 x stress", 200 >= 1.5 * v1, f"{200/v1:.2f}x")
    # UVLO, SS
    k = 1 + P['en_top'] / P['en_bot']
    print(f"  EN/UVLO divider {eng(P['en_top'],'')}/{eng(P['en_bot'],'')}: rising {1.576*k:.2f}/{1.68*k:.2f}/{1.90*k:.2f} V, falling {1.545*k:.2f}/{1.60*k:.2f}/{1.645*k:.2f} V (min/typ/max, DS p.4)")
    chk("EN rising max < 4.75 V rail minimum", 1.90 * (1 + P['en_top'] / P['en_bot']) < 4.75, f"{1.90*(1+P['en_top']/P['en_bot']):.2f} V")
    print(f"  SS: 2 uA charge (DS p.4), C_SS = {P['c_ss']*1e9:.0f} nF -> dV/dt = {2e-6/P['c_ss']:.1f} V/s (1.6 V full-scale would take {1.6*P['c_ss']/2e-6*1e3:.0f} ms, ASM upper bound; "
          "DS Fig.3 p.13 is drawn at 10 ms/DIV)")
    print(f"  Input current at 140 V/1 mA: {P['vout']*P['iload']/P['eta']/P['vin_nom']*1e3:.0f} mA + ~1.2 mA active IQ (DS p.3); stored energy in pump caps follows in 4.")


# ----------------------------------------------------------------------------- 3b. FBX divider
def divider():
    pot = P['pot_fitted']
    print("\n== 3b. FBX divider: Vout = Vfb*(1+Rt/Rb+Rt/Rd[+Rt/Rp]) - Vdac*Rt/Rd[- Vw*Rt/Rp] ; Rb = Rs + NTC(T)"
          f"   [pot leg {'FITTED (bench)' if pot else 'DNP (production: RV1/R15 not fitted)'}]")
    rt, rd, rp = P['rt'], P['rd'], P['rp']
    mid, vmax_dac = P['vtrim_mid'], P['vtrim_max']
    span_req = P['vout_max'] - P['vout_min']
    rd_req = vmax_dac * rt / span_req
    print(f"  Rt = {eng(rt,'ohm')} (4 x 2.05M, <=55 V each); DAC leg Rd = {eng(rd,'ohm')} (R13 10k + R14 {eng(rd-10e3,'ohm')})"
          f"{'; pot leg Rp = ' + eng(rp,'ohm') if pot else '; pot leg absent'}")
    print(f"  DAC span = Vdac_max*Rt/Rd: {P['vout_min']:.0f}-{P['vout_max']:.0f} V needs Rd <= {eng(rd_req,'ohm')}; with Rd = {eng(rd,'ohm')} the span is {vmax_dac*rt/rd:.1f} V,"
          f" LSB(12-bit) = {vmax_dac/4096*rt/rd*1e3:.1f} mV")
    # Rb for code 0 (Vdac = 0) = vout_max  (pot, if fitted, at mid)
    k = P['vout_max'] / P['vfb'] - rt / rd - ((rt / rp) * (1 - mid / P['vfb']) if pot else 0.0)   # = 1 + Rt/Rb
    rb_req = rt / (k - 1)
    alpha = -P['ntc_beta'] / 298.15 ** 2
    v_mid_nom = vout_net(rb_req, mid)
    alpha_req = -P['tc_target'] / (P['vfb'] * rt / rb_req)
    print(f"  Needed Rb(25C) for {P['vout_max']:.0f} V at Vdac = 0: {eng(rb_req,'ohm')};  needed alpha_Rb = {alpha_req*100:.3f} %/C;"
          f" NTC alpha(25C) = {alpha*100:.3f} %/C -> NTC fraction {alpha_req/alpha:.3f} -> NTC25 = {alpha_req/alpha*rb_req/1e3:.2f} k (fitted: {P['ntc_r25']/1e3:.0f} k)")
    def worst(rs_):
        v25_ = vout_net(rs_ + ntc(25), mid)
        return max(abs(vout_net(rs_ + ntc(t), mid) - v25_ - P['tc_target'] * (t - 25)) for t in range(15, 36))
    def top_err(rs_):
        return abs(vout_net(rs_ + ntc(25), 0.0) - P['vout_max'])
    cands = [e * 10 ** d for d in (4,) for e in E96]
    rs_fit = min(cands, key=top_err)
    print(f"  Rs (E96) that puts code 0 closest to {P['vout_max']:.0f} V: {eng(rs_fit,'ohm')} -> {vout_net(rs_fit+ntc(25),0.0):.1f} V; tempco error with it {worst(rs_fit):.2f} V (max over 15-35 C)")
    print("  Note: dVout/dT = -Vfb*Rt*(dRb/dT)/Rb^2 does not depend on Rd, so the DAC leg sets the span and Rb/NTC set the tempco independently;"
          " Rb is kept at the tempco-optimised value and Rd alone is lowered to reach vout_max at code 0.")
    rs = P['rs_fix']
    rb25 = rs + ntc(25)
    v25 = vout_net(rb25, mid)
    print(f"  Chosen Rs = {eng(rs,'ohm')} (E96) + NTC {P['ntc_r25']/1e3:.0f}k b={P['ntc_beta']:.0f}: Rb(25C) = {eng(rb25,'ohm')};  Vout(25C, Vdac = mid {mid} V) = {v25:.2f} V")
    print("   T(C)  NTC(k)   Rb(k)   Vout(V)  ideal(V)  err(V)   [Vdac = mid; ideal = Vout(25)+0.65*(T-25)]")
    errs = []
    for t in (15, 20, 25, 30, 35):
        vo = vout_net(rs + ntc(t), mid)
        ideal = v25 + P['tc_target'] * (t - 25)
        errs.append(vo - ideal)
        print(f"   {t:3d}  {ntc(t)/1e3:7.3f}  {(rs+ntc(t))/1e3:7.2f}  {vo:7.2f}  {ideal:7.2f}  {vo-ideal:+6.2f}")
    sl = (vout_net(rs + ntc(26), mid) - vout_net(rs + ntc(24), mid)) / 2
    slb = (vout_net(rs + ntc(35), mid) - vout_net(rs + ntc(15), mid)) / 20
    half = (max(errs) - min(errs)) / 2
    print(f"  Slope at 25C (central diff) = {sl:.3f} V/C; 15-35C average = {slb:.3f} V/C (target 0.65); error span {min(errs):+.2f}..{max(errs):+.2f} V"
          f" -> +/-{half:.2f} V if the 25C trim is re-centred (= +/-{half*7:.0f} % gain at M~100, DER 7 %/V)")
    for r25_alt in (6.8e3, 8.2e3, 10e3, 12e3):
        rs_alt = min(cands, key=lambda r: abs(vout_net(r + ntc(25, r25=r25_alt), 0.0) - P['vout_max']))
        sl_alt = (vout_net(rs_alt + ntc(35, r25=r25_alt), mid) - vout_net(rs_alt + ntc(15, r25=r25_alt), mid)) / 20
        print(f"    NTC {r25_alt/1e3:4.1f}k with Rs {eng(rs_alt,'ohm')}: slope {sl_alt:.3f} V/C, code 0 -> {vout_net(rs_alt+ntc(25,r25=r25_alt),0.0):.1f} V")
    chk("band-average tempco within 5 % of 0.65 V/C", abs(slb / 0.65 - 1) < 0.05, f"{slb:.3f} V/C")
    chk("re-centred error over 15-35 C <= +/-0.75 V (beta/NTC tolerance excluded)", half <= 0.75, f"+/-{half:.2f} V")
    for lab, kw in (("beta +/-1 %", dict(beta=3950 * 1.01)),):
        v35 = vout_net(rs + ntc(35, beta=kw['beta']), mid)
        v15 = vout_net(rs + ntc(15, beta=kw['beta']), mid)
        print(f"  Sensitivity {lab}: slope {(v35-v15)/20:.3f} V/C (vs {slb:.3f})")
    dvfb = 26e-6 * (1 + rt / rb25)
    print(f"  Vfb tempco (GRAPH-READ DS p.5, ~+26 uV/C) adds {dvfb*1e3:.1f} mV/C at Vout (negligible); Vfb tol {P['vfb_lo']}-{P['vfb_hi']} V "
          f"-> {vout_net(rb25,mid,vfb=P['vfb_lo'])-v25:+.1f}/{vout_net(rb25,mid,vfb=P['vfb_hi'])-v25:+.1f} V -> per-unit trim REQUIRED")
    print(f"  FBX current +/-10 nA (DS p.3) x Rt||Rb = +/-{P['ifbx']*rt*rb25/(rt+rb25)*(rt/rb25+1)*1e3:.0f} mV at Vout")
    print("  Set-point vs DAC (pot " + ("at mid" if pot else "absent") + "):")
    print("   T(C)   Vdac=0 (code 0, MCP4728 power-up)   Vdac=1.65   Vdac=3.3 (code 4095)")
    for t in (15, 25, 35):
        rb_t = rs + ntc(t)
        print(f"   {t:3d}   {vout_net(rb_t,0.0):7.1f} V{' '*27}{vout_net(rb_t,mid):7.1f} V   {vout_net(rb_t,vmax_dac):7.1f} V")
    v0, vfs = vout_net(rb25, 0.0), vout_net(rb25, vmax_dac)
    chk(f"code 0 (blank DAC) within {P['vout_max']-5:.0f}-{P['vout_max']+5:.0f} V", P['vout_max'] - 5 <= v0 <= P['vout_max'] + 5, f"{v0:.1f} V")
    chk(f"full scale <= {P['vout_min']+5:.0f} V (firmware limits codes to >= {P['vout_min']:.0f} V)", vfs <= P['vout_min'] + 5, f"{vfs:.1f} V")
    chk("switch node at code 0: (Vout+Vd)/2 x ring < 150 V", (v0 + P['vd']) / 2 * P['ring'] < P['vsw_abs'], f"{(v0+P['vd'])/2*P['ring']:.0f} V")
    print(f"  Bench build with the pot leg fitted (Rp = {eng(rp,'ohm')}, same Rb): Vw = 0, Vdac = 0 -> {vout_net(rb25,0.0,0.0,pot=True):.1f} V;"
          f" Vw = 3.3, Vdac = 3.3 -> {vout_net(rb25,vmax_dac,vmax_dac,pot=True):.1f} V; Vw = mid, Vdac = mid -> {vout_net(rb25,mid,mid,pot=True):.1f} V"
          f" (the pot adds +/-{vmax_dac*rt/rp/2:.0f} V about mid; firmware code bounds must then come from HV_MON, not from the code alone)")
    ibot = P['vout'] / (rt + rb25)
    print(f"  Divider/bleeder current at 140 V = {ibot*1e6:.1f} uA ({ibot*P['vout']*1e3:.2f} mW); at 220 V = {P['vout_max']/(rt+rb25)*1e6:.1f} uA")
    return rb25


# ----------------------------------------------------------------------------- 4. cathode filter
def ladder(f, r1, c1, r2, c2, cj, with_par=True):
    """Voltage transfer HV_RAW -> cathode (node 3) incl. ESL/ESR of C1,C2, parasitic bypass, Cj to AC ground."""
    w = 2 * math.pi * f; s = 1j * w
    zc1 = P['esr'] + s * P['esl'] + 1 / (s * c1)
    zc2 = P['esr'] + s * P['esl'] + 1 / (s * c2)
    y = lambda z: 1 / z
    z1 = r1 if not with_par else 1 / (1 / r1 + s * (P['cpar_r'] + P['cpar_q']))
    z2 = r2 if not with_par else 1 / (1 / r2 + s * P['cpar_r'])
    zl = 1 / (s * cj)                              # cathode node loaded by Cj to the TIA virtual ground
    za = 1 / (y(zc2) + y(zl))
    zb = 1 / (y(zc1) + y(z2 + za))
    h = (zb / (z1 + zb)) * (za / (z2 + za))
    return h


def step_settle(r1, c1, r2, c2, frac):
    # poles of the unloaded 2-stage ladder: s^2*R1C1R2C2 + s*(R1C1+R2C2+R1C2) + 1 = 0
    a = r1 * c1 * r2 * c2; b = r1 * c1 + r2 * c2 + r1 * c2
    d = math.sqrt(b * b - 4 * a)
    tau_slow, tau_fast = (2 * a) / (b - d), (2 * a) / (b + d)
    # step response y = 1 - (t1 e^{-t/t1} - t2 e^{-t/t2})/(t1-t2)
    t1, t2 = tau_slow, tau_fast
    t = 0.0
    while t < 50 * t1:
        y = 1 - (t1 * math.exp(-t / t1) - t2 * math.exp(-t / t2)) / (t1 - t2)
        if 1 - y < frac:
            return t, t1, t2
        t += t1 / 2000
    return t, t1, t2


def filt():
    r1, c1, r2, c2, cj = P['r1'], P['c1'], P['r2'], P['c2'], P['cj']
    print("\n== 4. Cathode filter: HV_RAW -R1-[C1]-R2-[C2 at cathode]  (no series R after C2: it would form a pole with Cj)")
    print(f"  R1={eng(r1,'ohm')} C1={eng(c1,'F')}  R2={eng(r2,'ohm')} C2={eng(c2,'F')};  corners {1/(2*math.pi*r1*c1):.0f} Hz, {1/(2*math.pi*r2*c2):.0f} Hz")
    fs = P['f_nom']
    print("   f           ideal 2xRC (dB)   with parasitics+ESL (dB)")
    for f in (100e3, 30e3 * 0 + 300e3, fs, fs * 1.2, P['f_wpt'], 30e6, 100e6):
        hi = ladder(f, r1, c1, r2, c2, cj, with_par=False)
        hp = ladder(f, r1, c1, r2, c2, cj, with_par=True)
        tag = " <- f_sw" if f == fs else (" <- 6.63 MHz WPT" if f == P['f_wpt'] else "")
        print(f"  {f/1e6:8.3f} MHz   {20*math.log10(abs(hi)):9.1f}        {20*math.log10(abs(hp)):9.1f}{tag}")
    # noise at cathode
    vfund = P['ripple_pp'] / (2 * math.sqrt(2))
    print(f"  Source (ASM): ripple {P['ripple_pp']:.1f} Vpp at f_sw ({vfund*1e3:.0f} mV rms fundamental; DS DC2838A p.1 shows 1 V ripple at 10 mA), 1/n harmonics to"
          f" 1/(pi*t_edge) = {1/(math.pi*P['t_edge'])/1e6:.0f} MHz then 1/n^2; plus {P['v_wpt']*1e3:.0f} mV rms at 6.63 MHz.")
    tot2 = 0.0; itot2 = 0.0
    n = 1
    while n * fs <= 100e6:
        f = n * fs
        amp = vfund / n * (1 if f < 1 / (math.pi * P['t_edge']) else (1 / (math.pi * P['t_edge']) / f))
        if f >= 100e3:
            h = abs(ladder(f, r1, c1, r2, c2, cj))
            v = amp * h
            tot2 += v * v; itot2 += (2 * math.pi * f * cj * v) ** 2
        n += 1
    h6 = abs(ladder(P['f_wpt'], r1, c1, r2, c2, cj)); v6 = P['v_wpt'] * h6
    print(f"  Cathode rms from converter ripple (100k-100M): {math.sqrt(tot2)*1e9:.3g} nV; at f_sw alone: {vfund*abs(ladder(fs,r1,c1,r2,c2,cj))*1e9:.3g} nV;"
          f" at 6.63 MHz: {v6*1e9:.3g} nV")
    print(f"  Injected current i=2*pi*f*Cj*v: converter {math.sqrt(itot2)*1e12:.3g} pA rms; 6.63 MHz {2*math.pi*P['f_wpt']*cj*v6*1e12:.3g} pA rms;"
          f" vs TIA {P['cj_tia_noise']*1e9:.0f} nA rms")
    # thermal noise of R1, R2 at the cathode (integrate 100k..100M, log grid)
    kt4 = 4 * 1.380649e-23 * 300
    acc = 0.0; f = 100e3; df = 1.01
    while f < 100e6:
        w = 2 * math.pi * f; s = 1j * w
        zc1 = P['esr'] + s * P['esl'] + 1 / (s * c1); zc2 = P['esr'] + s * P['esl'] + 1 / (s * c2); zl = 1 / (s * cj)
        # transfer from R2 series voltage noise to cathode, and from R1 (via ladder)
        za = 1 / (1 / zc2 + 1 / zl)
        h2 = za / (r2 + za) * 0 + (za / (r2 + za))
        h1 = abs(ladder(f, r1, c1, r2, c2, cj, with_par=False))
        acc += (kt4 * r1 * h1 ** 2 + kt4 * r2 * abs(h2) ** 2) * f * (df - 1)
        f *= df
    print(f"  Thermal noise of R1,R2 at cathode, 100k-100M: {math.sqrt(acc)*1e9:.3g} nV rms")
    chk("cathode noise (ripple) < 10 uV rms", math.sqrt(tot2) < 10e-6, f"{math.sqrt(tot2)*1e6:.4f} uV")
    chk("cathode noise at 6.63 MHz < 10 uV rms", v6 < 10e-6, f"{v6*1e6:.5f} uV")
    need = 10e-6 / vfund
    print(f"  Required attenuation at f_sw for 10 uV: {20*math.log10(need):.1f} dB; ideal gives {20*math.log10(abs(ladder(fs,r1,c1,r2,c2,cj,False))):.1f} dB"
          f" -> layout/coupling margin {-20*math.log10(abs(ladder(fs,r1,c1,r2,c2,cj,True)))+20*math.log10(need):.0f} dB")
    # DC, short, energy, time
    print("  DC / fault:")
    print(f"   DC drop at {P['i_apd_max']*1e6:.0f} uA = {P['i_apd_max']*(r1+r2):.2f} V (+ clamp ~1.2 V); at 10 uA = {10e-6*(r1+r2):.2f} V; APD gain ~7 %/V near M~100 (apd-selection.md)")
    for v in (P['vout_max'], P['v_fault']):
        print(f"   Hard short (cathode node -> TIA input) steady current at {v:.0f} V via R1+R2 = {v/(r1+r2)*1e3:.2f} mA vs OPA857 abs max {P['iabs_tia']*1e3:.0f} mA (PDF p.5): {v/(r1+r2)/P['iabs_tia']*100:.0f} %")
    chk("steady short current < 70 % of OPA857 10 mA at 235 V", P['v_fault'] / (r1 + r2) < 0.7 * P['iabs_tia'], f"{P['v_fault']/(r1+r2)*1e3:.2f} mA")
    print(f"   Capacitor dump: C2 = {c2*1e9:.0f} nF at {P['vout_max']:.0f} V holds {c2*P['vout_max']*1e6:.2f} uC / {0.5*c2*P['vout_max']**2*1e6:.0f} uJ, NOT limited by R1/R2 (its loop sees only"
          f" ESR/trace) -> OPEN RISK; C1 dump limited by R2 only: {P['vout_max']/r2*1e3:.1f} mA peak, tau {r2*c1*1e6:.0f} us")
    e_f = 0.5 * (c1 + c2) * P['vout_max'] ** 2
    ceff_nom = P['c_pump']
    v1 = (P['vout_max'] + P['vd']) / 2
    e_p = 3 * 0.5 * ceff_nom * v1 ** 2
    print(f"  Stored energy at 220 V: filter {e_f*1e6:.0f} uJ; pump caps (3 x {ceff_nom*1e9:.0f} nF at {v1:.0f} V, nominal C) {e_p*1e3:.2f} mJ; total {(e_f+e_p)*1e3:.2f} mJ")
    t99, ts, tf = step_settle(r1, c1, r2, c2, 0.01)
    t999, _, _ = step_settle(r1, c1, r2, c2, 0.001)
    print(f"  Time constants (unloaded ladder): {ts*1e3:.2f} ms and {tf*1e6:.0f} us; step settles to 1 % in {t99*1e3:.2f} ms, 0.1 % in {t999*1e3:.2f} ms"
          f"  (startup is paced by SS, tens of ms)")
    ceff = P['c_pump'] * P['c_pump_derate'] / 2 + c1 + c2
    print(f"  Discharge after disable (only the divider bleeds): tau ~ {ceff*(P['rt']+P['rs_fix']+ntc(25)):.2f} s (Ceff {ceff*1e9:.0f} nF ASM); 220 V -> 60 V in {ceff*(P['rt']+P['rs_fix']+ntc(25))*math.log(220/60):.2f} s")


# ----------------------------------------------------------------------------- clamp
def clamp():
    print("\n== 5. APD current clamp (2-BJT limiter, upstream of R1; Q1 HV NPN pass, Q2 sense across Rs)")
    print(f"  Rs = {eng(P['rs_clamp'],'ohm')}, Rb = {eng(P['rb_clamp'],'ohm')} (HV_RAW -> Q1 base); Vbe = {P['vbe']} V @25C, {P['vbe_tc']*1e3:.0f} mV/C (ASM)")
    print("   T(C)   Vbe(V)   Iclamp(uA)   short I = Iclamp + HV/Rb at 220 V (uA)")
    ok = True
    for t in (-20, 25, 60, 85):
        vbe = P['vbe'] + P['vbe_tc'] * (t - 25)
        ic = vbe / P['rs_clamp']
        print(f"  {t:4d}   {vbe:6.3f}   {ic*1e6:8.0f}      {(ic + P['vout_max']/P['rb_clamp'])*1e6:8.0f}")
        if t in (-20, 60):
            ok &= (ic + P['vout_max'] / P['rb_clamp'] < 200e-6) if t == -20 else (ic > P['i_apd_max'])
    chk("clamp passes 100 uA at +60 C and fault current < S12023 Ir max 200 uA at -20 C", ok, "see table (soft knee not modelled)")
    print(f"  Q1 fault dissipation = 220 V x ~{(P['vbe']/P['rs_clamp'])*1e6:.0f} uA = {P['vout_max']*P['vbe']/P['rs_clamp']*1e3:.0f} mW (SOT-23 class OK, ASM)")


if __name__ == "__main__":
    print(f"APD bias supply Rev A design check: Vin {P['vin_nom']} V +/-{P['vin_tol']*100:.0f} %, Vout {P['vout']:.0f} V ({P['vout_min']:.0f}-{P['vout_max']:.0f}), "
          f"Iload <= {P['iload']*1e3:.0f} mA, f_sw {P['f_nom']/1e3:.0f} kHz, L {P['L']*1e6:.0f} uH\n")
    converter()
    divider()
    filt()
    clamp()
    print(f"\nSUMMARY: {sum(checks)}/{len(checks)} checks passed")
