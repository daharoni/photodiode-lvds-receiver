"""Analyse Sim 1 outputs (out/sim1_*). Run with a venv python that has numpy+matplotlib: python -I analyze_sim1.py"""
import json, os, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); PL = os.path.join(HERE, "..", "plots")
os.makedirs(PL, exist_ok=True)
VARS = {"rf301_rg49.9": "RF301/RG49.9 (as drawn)", "rf453_rg75": "RF453/RG75 (datasheet)",
        "rf200_rg49.9": "RF200/RG49.9", "rf453_rg49.9": "RF453/RG49.9", "rf200_rg33.2": "RF200/RG33.2"}
GAIN = {"rf301_rg49.9": 1 + 301 / 49.9, "rf453_rg75": 1 + 453 / 75, "rf200_rg49.9": 1 + 200 / 49.9,
        "rf453_rg49.9": 1 + 453 / 49.9, "rf200_rg33.2": 1 + 200 / 33.2}
M = {}

def cross(x, y, level, start=0, rising=False):
    for i in range(start, len(y) - 1):
        if (y[i] - level) * (y[i + 1] - level) <= 0 and y[i] != y[i + 1]:
            return x[i] + (level - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i])
    return float("nan")

def load_ac(tag):
    d = np.loadtxt(f"{OUT}/sim1_{tag}_ac.txt"); f = d[:, 0]
    return f, d[:, 1] + 1j * d[:, 2], d[:, 4] + 1j * d[:, 5]

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for tag, lab in VARS.items():
    f, o, s = load_ac(tag)
    r = {}
    for nm, v in (("OUT", o), ("SDET_P", s)):
        g = 20 * np.log10(abs(v)); ref = g[np.argmin(abs(f - 1e5))]
        ipk = np.argmax(g)
        r[nm] = {"passband_dB@100k": round(float(ref), 2), "peak_dB_rel": round(float(g[ipk] - ref), 2),
                 "f_peak_Hz": float(f[ipk]), "f3dB_Hz": float(cross(f, g - ref, -3, start=int(np.argmin(abs(f - 1e5)))))}
    d = np.loadtxt(f"{OUT}/sim1_{tag}_loop.txt"); fl = d[:, 0]
    ny = d[:, 1] + 1j * d[:, 2]; nx = d[:, 4] + 1j * d[:, 5]; T = -ny / nx
    Tdb = 20 * np.log10(abs(T)); ph = np.degrees(np.angle(T))
    fc = cross(fl, Tdb, 0.0)
    phc = float(np.interp(np.log10(fc), np.log10(fl), np.unwrap(np.radians(ph)) * 180 / np.pi)) if fc == fc else float("nan")
    phc_w = (phc + 180) % 360 - 180
    r["loop"] = {"fc_Hz": fc, "phase_at_fc_deg": round(phc_w, 1), "PM_deg": round(180 - abs(phc_w), 1),
                 "T_LF_dB@1kHz": round(float(Tdb[0]), 1), "T_LF_phase_deg": round(float(ph[0]), 1)}
    M[tag] = r
    ax[0].semilogx(f, 20 * np.log10(abs(o)), label=lab)
    ax[1].semilogx(f, 20 * np.log10(abs(s)), label=lab)
for a, t in zip(ax, ("OUT (op-amp pin)", "SDET_P (after R56/C54, C55)")):
    a.set_title("Closed loop, " + t); a.set_xlabel("Hz"); a.set_ylabel("dB (from OPA857 OUT source)"); a.grid(True, which="both", alpha=.3); a.set_ylim(-6, 20); a.set_xlim(1e3, 3e9)
ax[0].legend(fontsize=7); plt.tight_layout(); plt.savefig(f"{PL}/sim1_closed_loop_ac.png", dpi=130); plt.close()

fig, ax = plt.subplots(2, 1, figsize=(7, 7), sharex=True)
for tag, lab in VARS.items():
    d = np.loadtxt(f"{OUT}/sim1_{tag}_loop.txt"); fl = d[:, 0]; T = -(d[:, 1] + 1j * d[:, 2]) / (d[:, 4] + 1j * d[:, 5])
    ax[0].semilogx(fl, 20 * np.log10(abs(T)), label=lab); ax[1].semilogx(fl, np.degrees(np.angle(T)))
ax[0].axhline(0, color="k", lw=.5); ax[0].set_ylabel("|T| dB"); ax[1].set_ylabel("phase deg (as simulated)"); ax[1].set_xlabel("Hz")
ax[0].set_title("T = -V(NY)/V(NX), break at IN- (ngspice AC)")
for a in ax: a.grid(True, which="both", alpha=.3)
ax[0].legend(fontsize=7); plt.tight_layout(); plt.savefig(f"{PL}/sim1_loop_gain.png", dpi=130); plt.close()

def tran_metrics(tag, amp_mv, tr):
    d = np.loadtxt(f"{OUT}/sim1_{tag}_tran.txt"); t = d[:, 0]; o = d[:, 1]; s = d[:, 3]
    t0 = 1e-6; tw = 100e-9
    idle = float(np.interp(0.95e-6, t, o)); sidle = float(np.interp(0.95e-6, t, s))
    te = t0 + tr; tf = t0 + tr + tw  # end of leading edge, start of trailing edge (input)
    tret = t0 + 2 * tr + tw          # input fully returned
    plateau = float(np.interp(tf, t, o)); exc = plateau - idle
    m = (t > t0) & (t < tf)
    pk = float(o[m].min() if exc < 0 else o[m].max())
    os_lead = (pk - plateau) / exc * 100 if exc != 0 else float("nan")
    m2 = t > tf
    # trailing edge overshoot (opposite side of idle)
    tail = o[m2 & (t < tf + 1e-6)]
    trail_os = float((tail.max() - idle) if exc < 0 else (idle - tail.min()))
    # recovery: time after input returned for |v-idle| to stay within 10% of plateau excursion
    ptop = (t > tf - 30e-9) & (t < tf)
    osc_pp = float(o[ptop].max() - o[ptop].min())
    band = 0.1 * abs(pk - idle); mm = t >= tret
    tt = t[mm]; dev = abs(o[mm] - idle)
    bad = np.where(dev > band)[0]
    rec10 = float(tt[bad[-1] + 1] - tret) if len(bad) and bad[-1] + 1 < len(tt) else 0.0
    def rec(b):
        bad = np.where(dev > b)[0]
        return float(tt[bad[-1] + 1] - tret) if len(bad) and bad[-1] + 1 < len(tt) else 0.0
    rec1mV = rec(0.001); rec10mV = rec(0.010); rec41mV = rec(0.041)
    return {"in_mV": amp_mv, "idle_V": round(idle, 4), "plateau_exc_mV": round(exc * 1e3, 1), "peak_exc_mV": round((pk - idle) * 1e3, 1),
            "gain_plateau": round(exc / (-amp_mv * 1e-3), 2), "lead_overshoot_pct": round(os_lead, 1),
            "trail_overshoot_mV": round(trail_os * 1e3, 2), "rec_to_10pct_ns": round(rec10 * 1e9, 2), "rec_to_1mV_ns": round(rec1mV * 1e9, 2), "rec_to_10mV_ns": round(rec10mV * 1e9, 2), "rec_to_41mV_ns": round(rec41mV * 1e9, 2), "osc_pp_last30ns_mV": round(osc_pp * 1e3, 0),
            "v_min_V": round(float(o.min()), 3), "v_max_V": round(float(o.max()), 3), "sdet_exc_mV": round((float(s[(t > t0) & (t < tf)].min()) - sidle) * 1e3, 1)}

for tag in VARS:
    M[tag]["step10mV_20ns"] = tran_metrics(tag, 10, 20e-9)
for tag in VARS:
    M[tag]["step10mV_0.2ns"] = tran_metrics(tag + "_vfast", 10, 0.2e-9)
for base in ("rf301_rg49.9", "rf453_rg75"):
    M[base]["step10mV_2ns"] = tran_metrics(base + "_fast", 10, 2e-9)
    M[base]["large_20ns_edges"] = {a: tran_metrics(f"{base}_a{a}", a, 20e-9) for a in (30, 40, 50, 60, 70, 80, 90, 100, 200)}
    M[base]["overload_2ns_edges"] = {a: tran_metrics(f"{base}_ovl{a}", a, 2e-9) for a in (60, 100, 200)}

json.dump(M, open(f"{OUT}/sim1_metrics.json", "w"), indent=1, default=float)

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for tag in ("rf301_rg49.9", "rf453_rg75"):
    for k, (suf, tr) in enumerate((("", 20e-9), ("_fast", 2e-9))):
        d = np.loadtxt(f"{OUT}/sim1_{tag}{suf}_tran.txt"); t = (d[:, 0] - 1e-6) * 1e9; o = d[:, 1] - float(np.interp(0.95e-6, d[:, 0], d[:, 1]))
        ax[0].plot(t, o * 1e3, label=f"{VARS[tag]} {'20 ns' if k == 0 else '2 ns'} edge")
ax[0].set_xlim(-20, 200); ax[0].set_xlabel("ns"); ax[0].set_ylabel("OUT change, mV"); ax[0].set_title("10 mV step at TIA_OUT (negative-going)"); ax[0].legend(fontsize=7); ax[0].grid(alpha=.3)
for a_ in (30, 60, 100, 200):
    d = np.loadtxt(f"{OUT}/sim1_rf301_rg49.9_a{a_}_tran.txt"); t = (d[:, 0] - 1e-6) * 1e9
    ax[1].plot(t, d[:, 1], label=f"{a_} mV in")
ax[1].set_xlim(-20, 300); ax[1].set_ylim(0.7, 1.75); ax[1].set_xlabel("ns"); ax[1].set_ylabel("OUT, V"); ax[1].set_title("As drawn (RF301/RG49.9), 100 ns pulse, 20 ns edges"); ax[1].legend(fontsize=7); ax[1].grid(alpha=.3)
plt.tight_layout(); plt.savefig(f"{PL}/sim1_transient.png", dpi=130); plt.close()
print(json.dumps(M, indent=1, default=float))
