"""Analyse Sim 3 outputs. Run: python -I analyze_sim3.py (venv with numpy+matplotlib)."""
import json, os, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); PL = os.path.join(HERE, "..", "plots"); os.makedirs(PL, exist_ok=True)
M = {}
fa, aa = plt.subplots(1, 2, figsize=(11, 4)); fl, al = plt.subplots(2, 1, figsize=(7, 7), sharex=True); ft, at = plt.subplots(1, 2, figsize=(11, 4))
def cross(x, y, lvl):
    for i in range(len(y) - 1):
        if (y[i] - lvl) * (y[i + 1] - lvl) <= 0 and y[i] != y[i + 1]: return x[i] + (lvl - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i])
    return float("nan")
for r in (0.01, 10, 22, 47):
    for l in (0,):
        k = f"r{r}_load{l}"; m = {}
        d = np.loadtxt(f"{OUT}/sim3_{k}_ac.txt"); f = d[:, 0]; go = 20 * np.log10(abs(d[:, 1] + 1j * d[:, 2])); gv = 20 * np.log10(abs(d[:, 4] + 1j * d[:, 5]))
        m["opout_peak_dB"] = round(float(go.max() - go[0]), 2); m["opout_f_peak_Hz"] = float(f[np.argmax(go)])
        m["vcm_peak_dB_rel_LF"] = round(float(gv.max() - gv[0]), 2); m["vcm_f_peak_Hz"] = float(f[np.argmax(gv)])
        d = np.loadtxt(f"{OUT}/sim3_{k}_loop.txt"); T = -(d[:, 1] + 1j * d[:, 2]) / (d[:, 4] + 1j * d[:, 5]); fT = d[:, 0]
        Tdb = 20 * np.log10(abs(T)); ph = np.degrees(np.unwrap(np.angle(T)))
        fc = cross(fT, Tdb, 0.0); phc = float(np.interp(np.log10(fc), np.log10(fT), ph)); phw = (phc + 180) % 360 - 180
        m["fc_Hz"] = fc; m["phase_at_fc_deg"] = round(phw, 1); m["PM_deg"] = round(180 - abs(phw), 1); m["T_10Hz_dB"] = round(float(Tdb[0]), 1)
        # minimum |1+T| over frequency (sensitivity peak)
        m["min_abs_1plusT"] = round(float(abs(1 + T).min()), 3); m["Ms_peak_dB"] = round(float(-20 * np.log10(abs(1 + T).min())), 2)
        d = np.loadtxt(f"{OUT}/sim3_{k}_tran.txt"); t = d[:, 0]; v = d[:, 3]; op = d[:, 1]
        pre = float(np.interp(0.999e-3, t, v))
        m1 = (t > 1e-3) & (t < 1.5e-3); plat = float(np.interp(1.495e-3, t, v)) - pre
        pk = float(v[m1].min() - pre if abs(v[m1].min() - pre) > abs(v[m1].max() - pre) else v[m1].max() - pre)
        dev = abs(v[m1] - pre - plat); tt = t[m1]
        def ts(b):
            bad = np.where(dev > b)[0]; return float((tt[bad[-1] + 1] - 1e-3) * 1e6) if len(bad) and bad[-1] + 1 < len(tt) else 0.0
        m.update({"vcm_pre_V": round(pre, 4), "vcm_plateau_shift_mV": round(plat * 1e3, 3), "vcm_peak_dev_mV": round(pk * 1e3, 3), "settle_to_0.05mV_us": round(ts(5e-5), 2), "settle_to_10pct_of_100mV_i.e_10mV_us": round(ts(1e-2), 3),
                  "opout_peak_dev_mV": round(float((op[m1] - np.interp(0.999e-3, t, op)).max() * 1e3 if abs((op[m1] - np.interp(0.999e-3, t, op)).max()) > abs((op[m1] - np.interp(0.999e-3, t, op)).min()) else (op[m1] - np.interp(0.999e-3, t, op)).min() * 1e3), 3)})
        # small-signal step at IN+ (10 mV at 20 us)
        base = float(np.interp(0.399e-3, t, v)); bo = float(np.interp(0.399e-3, t, op)); ms = (t > 0.4e-3) & (t < 0.8e-3)
        fin = float(np.interp(0.799e-3, t, v)) - base
        m["step10mV_vcm_overshoot_pct"] = round(float((v[ms].max() - base - fin) / fin * 100), 2)
        m["step10mV_opout_overshoot_pct"] = round(float((op[ms].max() - bo - (float(np.interp(0.799e-3, t, op)) - bo)) / (float(np.interp(0.799e-3, t, op)) - bo) * 100), 2)
        M[k] = m
        if l == 0 and r != 0.01:
            aa[0].semilogx(f, 20 * np.log10(abs(np.loadtxt(f"{OUT}/sim3_{k}_ac.txt")[:, 1] + 1j * np.loadtxt(f"{OUT}/sim3_{k}_ac.txt")[:, 2])), label=f"R102={r}")
            aa[1].semilogx(f, gv, label=f"R102={r}")
            al[0].semilogx(fT, Tdb, label=f"R102={r}"); al[1].semilogx(fT, ph)
            at[0].plot((t - 1e-3) * 1e6, (v - pre) * 1e3, label=f"R102={r}"); at[1].plot((t - 1e-3) * 1e6, (op - np.interp(0.999e-3, t, op)) * 1e3, label=f"R102={r}")
aa[0].set_title("Closed loop: op-amp pin / IN+ source"); aa[1].set_title("Closed loop: VCM_REF / IN+ source (R102+C101 low-pass, loads on)")
for a in aa: a.set_xlabel("Hz"); a.set_ylabel("dB"); a.grid(True, which="both", alpha=.3); a.legend(fontsize=7)
al[0].axhline(0, color="k", lw=.5); al[0].set_ylabel("|T| dB"); al[1].set_ylabel("phase deg"); al[1].set_xlabel("Hz"); al[0].legend(fontsize=7); al[0].set_title("OPA320 VCM_REF buffer loop gain (break at IN-)")
for a in al: a.grid(True, which="both", alpha=.3)
at[0].set_xlim(-5, 200); at[0].set_title("VCM_REF, 100 mV step via 1k at t=0"); at[1].set_xlim(-5, 200); at[1].set_title("op-amp OUT pin"); 
for a in at: a.set_xlabel("us"); a.set_ylabel("mV"); a.grid(alpha=.3); a.legend(fontsize=7)
for f_, n in ((fa, "sim3_closed_loop_ac"), (fl, "sim3_loop_gain"), (ft, "sim3_step")): f_.tight_layout(); f_.savefig(f"{PL}/{n}.png", dpi=130)
json.dump(M, open(f"{OUT}/sim3_metrics.json", "w"), indent=1)
for k, m in M.items(): print(k, m)
