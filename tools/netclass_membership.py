#!/usr/bin/env python3
"""Resolve the .kicad_pro netclass patterns against the nets in the .kicad_pcb and print class membership.
Usage: python3 tools/netclass_membership.py [hardware/pcb/receiver-module/receiver-module]
KiCad matches patterns as case-sensitive wildcards (* and ?) against the full net name."""
import re, sys, json, fnmatch, collections
base = sys.argv[1] if len(sys.argv) > 1 else "hardware/pcb/receiver-module/receiver-module"
pcb = open(base + ".kicad_pcb").read()
pro = json.load(open(base + ".kicad_pro"))
nets = sorted(set(re.findall(r'\(net "([^"]+)"\)', pcb)))
pats = pro["net_settings"]["netclass_patterns"]
prio = {c["name"]: c["priority"] for c in pro["net_settings"]["classes"]}
members = collections.defaultdict(list)
for n in nets:
    hit = [p["netclass"] for p in pats if fnmatch.fnmatchcase(n, p["pattern"])]
    members[hit and min(hit, key=lambda c: prio[c]) or "Default"].append((n, hit))
for c in [x["name"] for x in pro["net_settings"]["classes"]]:
    m = members.get(c, [])
    print(f"{c} ({len(m)} nets)" + ("" if c == "Default" else ":"))
    if c != "Default":
        for n, hit in m:
            print("   ", n, "  [MULTI: %s]" % hit if len(hit) > 1 else "")
unmatched = [p["pattern"] for p in pats if not any(fnmatch.fnmatchcase(n, p["pattern"]) for n in nets)]
print("patterns matching no net:", unmatched or "none")
