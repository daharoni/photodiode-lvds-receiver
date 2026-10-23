#!/bin/sh
# Sim 2 variants: CTRL 3.3 (20k) / 0 (5k) x CD 6p / 1.5p / 10p (10p added 2026-10-23). Needs .spiceinit "set ngbehavior=psa" in this directory.
cd "$(dirname "$0")" || exit 1
python3 -I patch_models.py
python3 -I gen_pattern.py sim2_iph.inc
for m in "20k 3.3" "5k 0"; do for c in 6p 1.5p 10p; do
  set -- $m $c
  for k in ac tran; do
    sed -e "s/^\.param CD=.*/.param CD=$3 CTRLV=$2/" -e "s#sim2_${k}_out.txt#out/sim2_$1_$3_${k}.txt#" sim2_$k.cir > _run.cir
    ngspice -b -o "out/sim2_$1_$3_${k}.log" _run.cir
  done
done; done
rm -f _run.cir
