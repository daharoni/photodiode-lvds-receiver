#!/bin/sh
# Sim 3 variants: R102 = 10 / 22 / 47 ohm with 3 x 1k loads to GND (LOADMODE 0 = spec case; 1 = 1k+10uF AC-only loads, not run: start-up too slow).
cd "$(dirname "$0")" || exit 1
python3 -I patch_models.py
for r in 0.01 10 22 47; do for l in 0; do
  for k in ac loop tran; do
    tag="r${r}_load${l}"
    sed -e "s/^\.param R102=.*/.param R102=$r LOADMODE=$l/" -e "s#sim3_${k}_out.txt#out/sim3_${tag}_${k}.txt#" sim3_$k.cir > _run.cir
    ngspice -b -o "out/sim3_${tag}_${k}.log" _run.cir
  done
done; done
rm -f _run.cir
