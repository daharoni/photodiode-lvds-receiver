"""Analyse Sim 2 outputs. Run: python -I analyze_sim2.py (venv with numpy+matplotlib)."""
import json, os, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); PL = os.path.join(HERE, "..", "plots"); os.makedirs(PL, exist_ok=True)
T0, UI, IPK = 300e-9, 20e-9, 5e-6
M = {}; fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
for m in ("20k", "5k"):
    for c in ("6p", "1.5p"):
        k = f"{m}_{c}"; r = {}
        d = np.loadtxt(f"{OUT}/sim2_{k}_ac.txt"); f = d[:, 0]; o = d[:, 1] + 1j * d[:, 2]; g = 20 * np.log10(abs(o))
        i1 = int(np.argmin(abs(f - 1e6))); ref = g[i1]; ipk = int(np.argmax(g[i1:])) + i1
        f3 = float("nan")
        for j in range(i1, len(f) - 1):
            if g[j] >= ref - 3 > g[j + 1]: f3 = f[j] + (ref - 3 - g[j]) * (f[j + 1] - f[j]) / (g[j + 1] - g[j]); break
        r["Rt_1MHz_ohm"] = round(float(abs(o[i1])), 0); r["peaking_dB"] = round(float(g[ipk] - ref), 2); r["f_peak_MHz"] = round(float(f[ipk] / 1e6), 1); r["f3dB_MHz"] = round(f3 / 1e6, 1)
        ax[0].semilogx(f, g, label=k)
        _p = f"{OUT}/sim2_{k}_tran.txt"; d = np.loadtxt(_p if os.path.exists(_p) else _p + ".gz"); t = d[:, 0]; v = d[:, 1]
        idle = float(np.interp(T0 - 5e-9, t, v))
        # first bit: 5 ones at T0..T0+100n, 5 zeros after
        m1 = (t > T0) & (t < T0 + 5 * UI); pl = float(np.interp(T0 + 5 * UI - 1e-9, t, v)); amp = idle - pl
        mn = float(v[m1].min()); ov = (pl - mn) / amp * 100
        m0 = (t > T0 + 5 * UI) & (t < T0 + 10 * UI); mx = float(v[m0].max()); ov0 = (mx - idle) / amp * 100
        # ring count: extrema after the first peak with |dev from final| > 2% amp
        seg = v[m1] - pl; sgn = np.sign(np.diff(seg)); ext = np.where(np.diff(sgn) != 0)[0]
        ring = int(sum(abs(seg[e + 1]) > 0.02 * amp for e in ext))
        lo, hi = idle - 0.9 * amp, idle - 0.1 * amp; tt = t[m1]; vv = v[m1]
        t10 = float(np.interp(-hi, -vv[:int(np.argmin(vv)) + 1], tt[:int(np.argmin(vv)) + 1])) if True else 0
        t90 = float(np.interp(-lo, -vv[:int(np.argmin(vv)) + 1], tt[:int(np.argmin(vv)) + 1]))
        dv = abs(v[m1] - pl) / amp; bad = np.where(dv > 0.02)[0]; tset = float((t[m1][bad[-1] + 1] - T0) * 1e9) if len(bad) else 0.0
        r.update({"settle_2pct_ns_from_edge_start": round(tset, 1), "idle_V": round(idle, 4), "plateau_5UI_V": round(pl, 4), "amp_mV": round(amp * 1e3, 1), "Rt_tran_ohm": round(amp / IPK, 0),
                  "lead_overshoot_pct": round(ov, 1), "release_overshoot_pct": round(ov0, 1), "ring_extrema_gt2pct": ring, "tr_10_90_ns": round((t90 - t10) * 1e9, 2)})
        M[k] = r
        ax[1].plot((t - T0) * 1e9, (v - idle) * 1e3, label=k)
        ax[2].plot((t - T0) * 1e9, (v - idle) * 1e3, label=k)
ax[0].set_xlim(1e6, 3e9); ax[0].set_ylim(40, 90); ax[0].set_xlabel("Hz"); ax[0].set_ylabel("dBohm  (|OUT/Iph|)"); ax[0].set_title("Transimpedance (AC, linearised model copy)"); ax[0].legend(fontsize=7); ax[0].grid(True, which="both", alpha=.3)
ax[1].set_xlim(-10, 720); ax[1].set_ylim(-140, 30); ax[1].set_xlabel("ns"); ax[1].set_ylabel("OUT - idle, mV"); ax[1].set_title("5 uA NRZ 50 Mb/s (TI model, transient)"); ax[1].legend(fontsize=7); ax[1].grid(alpha=.3)
ax[2].set_xlim(0, 100); ax[2].set_ylim(-140, 30); ax[2].set_xlabel("ns"); ax[2].set_title("First 5 ones, zoom"); ax[2].grid(alpha=.3)
plt.tight_layout(); plt.savefig(f"{PL}/sim2_tia.png", dpi=130); plt.close()
json.dump(M, open(f"{OUT}/sim2_metrics.json", "w"), indent=1)
for k, r in M.items(): print(k, r)
