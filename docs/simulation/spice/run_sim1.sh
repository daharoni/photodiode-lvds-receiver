#!/bin/sh
# Runs all Sim 1 variants. Needs ngspice (tested 47) and a .spiceinit with "set ngbehavior=psa" in this directory.
cd "$(dirname "$0")" || exit 1
run() { # tag RF RG VAMP TR
  sed -e "s/^\.param RF=.*/.param RF=$2 RG=$3 VAMP=$4 TR=$5 TW=100n/" \
      -e "s#sim1_ac_out.txt#out/sim1_$1_ac.txt#" -e "s#sim1_tran_out.txt#out/sim1_$1_tran.txt#" \
      sim1_postamp.cir > _run.cir
  ngspice -b -o "out/sim1_$1.log" _run.cir
}
loop() { # tag RF RG
  sed -e "s/^\.param RF=.*/.param RF=$2 RG=$3/" -e "s#sim1_loop_out.txt#out/sim1_$1_loop.txt#" sim1_loop.cir > _run.cir
  ngspice -b -o "out/sim1_$1_loop.log" _run.cir
}
for v in "rf301_rg49.9 301 49.9" "rf453_rg75 453 75" "rf200_rg49.9 200 49.9" "rf453_rg49.9 453 49.9" "rf200_rg33.2 200 33.2"; do
  set -- $v
  run "$1" "$2" "$3" -0.010 20n
  loop "$1" "$2" "$3"
done
# fast-edge variants for all five R pairs (2 ns and 0.2 ns) to expose ringing
for v in "rf301_rg49.9 301 49.9" "rf453_rg75 453 75" "rf200_rg49.9 200 49.9" "rf453_rg49.9 453 49.9" "rf200_rg33.2 200 33.2"; do
  set -- $v
  run "$1_vfast" "$2" "$3" -0.010 0.2n
done
# transient variants: fast edge and large-signal amplitudes, as drawn and datasheet values
for v in "rf301_rg49.9 301 49.9" "rf453_rg75 453 75"; do
  set -- $v
  run "$1_fast" "$2" "$3" -0.010 2n
  for a in 30 60 100 200; do run "$1_a$a" "$2" "$3" "-$(awk "BEGIN{print $a/1000}")" 20n; done
done
# clipping onset (20 ns edges) and overload recovery (2 ns edges)
for v in "rf301_rg49.9 301 49.9" "rf453_rg75 453 75"; do
  set -- $v
  for a in 40 50 70 80 90; do run "$1_a$a" "$2" "$3" "-$(awk "BEGIN{print $a/1000}")" 20n; done
  for a in 60 100 200; do run "$1_ovl$a" "$2" "$3" "-$(awk "BEGIN{print $a/1000}")" 2n; done
done
rm -f _run.cir
