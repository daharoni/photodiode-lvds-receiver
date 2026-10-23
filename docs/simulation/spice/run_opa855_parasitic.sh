#!/bin/sh
# Review P3: OPA855 post-amp with layout parasitics. Needs ngspice and .spiceinit (ngbehavior=psa) in this dir.
cd "$(dirname "$0")" || exit 1
mkdir -p out
for cp in 0 0.3 0.5 1.0; do for cf in 0 0.1; do
  tag="cp${cp}_cf${cf}"
  for amp in "0.2n:vfast" "20n:20ns"; do tr=${amp%%:*}; nm=${amp##*:}
  sed -e "s/CP=0.5p CF=0/CP=${cp}p CF=${cf}p/" -e "s/TR=20n/TR=$tr/" -e "s#par_ac_out#out/opa855-parasitic_${tag}_${nm}_ac#" -e "s#par_tran_out#out/opa855-parasitic_${tag}_${nm}_tran#" opa855-parasitic-postamp.cir > _par.cir
  ngspice -b -o "out/opa855-parasitic_${tag}_${nm}.log" _par.cir; done
  sed -e "s/CP=0.5p CF=0/CP=${cp}p CF=${cf}p/" -e "s#par_loop_out#out/opa855-parasitic_${tag}_loop#" opa855-parasitic-loop.cir > _par.cir
  ngspice -b -o "out/opa855-parasitic_${tag}_loop.log" _par.cir
done; done
rm -f _par.cir
