#!/bin/sh
# Run after analyze_sim1.py, analyze_sim2.py and analyze_sim3.py: deletes bulky raw transient text that run_sim1.sh can regenerate.
cd "$(dirname "$0")" || exit 1
# Prune bulky raw text (regenerate with this script). Kept: AC/loop for the five R variants, key transients.
cd out || exit 1
rm -f ./*_a[0-9]*_ac.txt ./*_fast_ac.txt ./*_vfast_ac.txt ./*_ovl*_ac.txt
for f in ./sim1_*_a[0-9]*_tran.txt ./sim1_*_fast_tran.txt ./sim1_*_vfast_tran.txt ./sim1_*_ovl*_tran.txt; do
  case "$f" in
    ./sim1_rf301_rg49.9_a60_tran.txt|./sim1_rf301_rg49.9_a100_tran.txt|./sim1_rf301_rg49.9_ovl100_tran.txt|./sim1_rf453_rg75_ovl100_tran.txt|./sim1_rf301_rg49.9_fast_tran.txt) ;;
    *) rm -f "$f" ;;
  esac
done
# keep only the headline transients, compress them (np.loadtxt reads .gz); numbers live in out/sim*_metrics.json
for f in ./sim1_rf200_rg49.9_tran.txt ./sim1_rf200_rg33.2_tran.txt ./sim1_rf453_rg49.9_tran.txt ./sim3_r22_load0_tran.txt ./sim3_r47_load0_tran.txt; do rm -f "$f"; done
for f in ./sim*_tran.txt; do gzip -f "$f"; done
