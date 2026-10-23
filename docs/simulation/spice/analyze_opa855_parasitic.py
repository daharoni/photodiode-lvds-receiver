"""Review P3 analysis. Same metrics as analyze_sim1.py (PM = 180-|angle T at |T|=1|, see README issue 1).
Run: python -I analyze_opa855_parasitic.py (numpy+matplotlib)"""
import json, os, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); O = H + "/out"; PL = H + "/../plots"
CASES = [(cp, cf) for cf in ("0", "0.1") for cp in ("0", "0.3", "0.5", "1.0")]
def cross(x, y, lv, s=0):
    for i in range(s, len(y) - 1):
        if (y[i] - lv) * (y[i + 1] - lv) <= 0 and y[i] != y[i + 1]:
            return x[i] + (lv - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i])
    return float("nan")
R = {}
fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
for cp, cf in CASES:
    tag = f"cp{cp}_cf{cf}"; lab = f"{cp} pF IN-/OUT" + (f" + {cf} pF Rf" if cf != "0" else "")
    d = np.loadtxt(f"{O}/opa855-parasitic_{tag}_20ns_ac.txt"); f = d[:, 0]; v = d[:, 1] + 1j * d[:, 2]
    g = 20 * np.log10(abs(v)); i0 = int(np.argmin(abs(f - 1e5))); ref = g[i0]; ipk = int(np.argmax(g))
    d = np.loadtxt(f"{O}/opa855-parasitic_{tag}_loop.txt"); fl = d[:, 0]
    T = -(d[:, 1] + 1j * d[:, 2]) / (d[:, 4] + 1j * d[:, 5]); Td = 20 * np.log10(abs(T))
    fc = cross(fl, Td, 0.0); ph = np.unwrap(np.angle(T)) * 180 / np.pi
    phc = float(np.interp(np.log10(fc), np.log10(fl), ph)); phw = (phc + 180) % 360 - 180
    # gain margin: |T| where phase (relative to -180 at LF) crosses -180 more => T angle crosses 0/-360 ; report min |1+T|
    S = 1 / abs(1 + T); 
    d = np.loadtxt(f"{O}/opa855-parasitic_{tag}_vfast_tran.txt"); t = d[:, 0]; o = d[:, 1]
    t0 = 1e-6; tr = 0.2e-9; tw = 100e-9; idle = float(np.interp(0.95e-6, t, o)); tf = t0 + tr + tw
    plat = float(np.interp(tf, t, o)); exc = plat - idle; m = (t > t0) & (t < tf); pk = float(o[m].min())
    R[tag] = {"CP_pF": float(cp), "CF_pF": float(cf), "PM_deg": round(180 - abs(phw), 1), "fc_GHz": round(fc / 1e9, 3),
              "passband_dB": round(float(ref), 2), "peaking_dB": round(float(g[ipk] - ref), 2), "f_peak_MHz": round(float(f[ipk]) / 1e6, 0),
              "f3dB_GHz": round(cross(f, g - ref, -3, i0) / 1e9, 3), "Ms_peak_dB": round(float(20 * np.log10(S.max())), 2),
              "overshoot_0.2ns_pct": round((pk - plat) / exc * 100, 1)}
    ax[0].semilogx(f, g, label=lab, ls="--" if cf != "0" else "-")
    ax[1].semilogx(fl, Td, label=lab, ls="--" if cf != "0" else "-"); ax[2].semilogx(fl, ph, ls="--" if cf != "0" else "-")
ax[0].set_ylim(10, 24); ax[0].set_xlim(1e6, 5e9); ax[0].set_title("Closed loop, v(OUT)/source"); ax[0].set_ylabel("dB")
ax[1].set_title("|T| (loop break at IN-)"); ax[1].set_ylim(-20, 40); ax[1].set_xlim(1e7, 5e9); ax[1].axhline(0, color="k", lw=.5)
ax[2].set_title("angle T (as simulated, see README issue 1)"); ax[2].set_xlim(1e7, 5e9)
for a in ax: a.grid(True, which="both", alpha=.3); a.set_xlabel("Hz")
ax[0].legend(fontsize=6); plt.tight_layout(); plt.savefig(PL + "/opa855-parasitic-ac.png", dpi=130); plt.close()
fig, ax = plt.subplots(figsize=(7, 4))
for cp, cf in CASES:
    if cf != "0": continue
    d = np.loadtxt(f"{O}/opa855-parasitic_cp{cp}_cf{cf}_vfast_tran.txt"); ax.plot((d[:, 0] - 1e-6) * 1e9, (d[:, 1] - np.interp(0.95e-6, d[:, 0], d[:, 1])) * 1e3, label=f"{cp} pF")
ax.set_xlim(-5, 40); ax.set_xlabel("ns"); ax.set_ylabel("OUT mV (10 mV step, 0.2 ns edge)"); ax.grid(alpha=.3); ax.legend(); ax.set_title("OPA855 step response, parasitic sweep")
plt.tight_layout(); plt.savefig(PL + "/opa855-parasitic-step.png", dpi=130)
json.dump(R, open(O + "/opa855-parasitic_metrics.json", "w"), indent=1)
for k, v in R.items(): print(k, v)
