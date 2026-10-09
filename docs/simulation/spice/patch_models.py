"""Makes AC-only derived copies of the TI models for ngspice (run: python3 -I patch_models.py).
Reason: in ngspice 47 the small-signal (.ac) linearisation of the OPA857 model gives ~0 open-loop gain because of its
LIMIT() source; replacing LIMIT(x,lo,hi) by x is exact for small signals about an operating point inside the limits.
Transient runs use the UNMODIFIED TI files. Derived files go to docs/research/downloads/spice-models/ngspice-patched/."""
import os
H = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(H, "..", "..", "research", "downloads", "spice-models")
def rd(p): return open(os.path.join(D, p), encoding="latin-1").read()
def wr(p, t): open(os.path.join(D, "ngspice-patched", p), "w", encoding="latin-1").write(t)
t = rd("opa857/SBOMBP8/opa857.lib")
old = "LIMIT(V(NET041,NET065)*188e-3, -1e-3, 1e-3)"; assert old in t
wr("opa857_ac_nolimit.lib", "* DERIVED FROM TI opa857.lib (SBOMBP8): LIMIT() removed for ngspice .ac only\n" + t.replace(old, "V(NET041,NET065)*188e-3"))

t = rd("opa320/SBOM438/OPAx320.LIB")
import re
n = 0
def strip(m):
    global n; n += 1; return m.group(1)
# LIMIT(first_arg, lo, hi) where first_arg is GAIN*V(a,b) -> first_arg
t2 = re.sub(r"LIMIT\((GAIN\*V\([^)]*\)),[^}]*?\)\}", lambda m: strip(m) + "}", t)
wr("opax320_ac_nolimit.lib", "* DERIVED FROM TI OPAx320.LIB (SBOM438): LIMIT() removed for ngspice .ac only\n" + t2)
print("OPAx320: LIMIT() replaced:", n, "remaining:", t2.upper().count("LIMIT("))
