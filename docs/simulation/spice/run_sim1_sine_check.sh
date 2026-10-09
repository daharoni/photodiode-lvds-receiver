#!/bin/sh
# Prints gain (dB, relative to a 20 mV pk-pk input) from a time-domain sine at four frequencies; compare with sim1 AC |v(OUT)| incl. the 25 ohm/R51 source divider
cd "$(dirname "$0")" || exit 1
for f in 3e8 8e8 1.5e9 2.5e9; do
  sed "s/^\.param RF=.*/.param RF=301 RG=49.9 FREQ=$f/" sim1_sine_check.cir > _run.cir
  ngspice -b -o out/sim1_sine_$f.log _run.cir
  awk -v f=$f '/^vmx/{mx=$3} /^vmn/{mn=$3} END{printf "%s Hz: tran gain %.2f dB\n", f, 20*log((mx-mn)/0.02)/log(10)}' out/sim1_sine_$f.log
done
rm -f _run.cir
