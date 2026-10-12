# tb: cocotb tests

One directory per RTL block, `tb/<name>/Makefile` + `test_<name>.py`, Icarus Verilog via
cocotb 2.1. Every expectation is derived from the Python golden model
`model/link8b10b.py` (8b/10b tables, CRC-16, PRBS-15, frame pack/unpack), never from the RTL.
Labels: the tests are VERIFIED by the runs recorded in the commit/report that added them;
the line protocol they check is PROPOSED (README section 3).

## Run

```
source tools/fpga-env.sh                 # repo root; yosys, iverilog, verilator, cocotb on PATH
python3 -m model.link8b10b               # (from firmware/ecp5) model self-check
cd firmware/ecp5/tb/enc_8b10b && make   # likewise dec_8b10b, crc16, prbs
make check                               # re-parses results.xml, exit 1 on any failure/error
make clean                               # (cocotb target) removes sim_build and results.xml
```

`PYTHONPATH` is set by each Makefile to `firmware/ecp5` so `from model import link8b10b` works.
The Makefiles use `COCOTB_TEST_MODULES` (the cocotb 2.1 name; `MODULE` is the 1.x name).

## Exit codes

cocotb 2.1's `Makefile.sim` already makes `make` exit nonzero when a test fails (checked
2026-10-12 by breaking one expectation in each of the four directories: `make` exits 2).
`make check` is a second guard that parses `results.xml` for `<failure>`/`<error>`.

## Conventions

- Clock 10 ns (`Clock(dut.clk, 10, unit="ns")`) for the pure-logic blocks (cycle counts only); the tests that tie
  cycles to real time use the 50 MHz core clock, 20 ns (tb/uart, tb/system) and tb/lane_phy runs the
  clocks.v model (clk_s 5 ns, clk_c 20 ns, coincident rising edges). Inputs are driven on the falling edge and
  outputs are read on the next falling edge, so one registered stage = one `push`.
- Gotcha (observed): a signal write still pending when a test returns makes `vvp` segfault at
  shutdown under Icarus 14 + cocotb 2.1 (results.xml is then deleted and make fails). End each
  test with an `await` after its last write.

## Contents

| Dir | Tests |
|---|---|
| enc_8b10b | all 256 data and 12 K codes at both disparities; invalid K requests give K28.5 and `enc_err` at both disparities; 12000-cycle random stream with gaps; reset returns disparity to negative |
| dec_8b10b | all 1024 words from disparity -, + and unknown, each followed by two probes that reveal the resulting disparity (model tracks disparity and resync); exactly 464 words decode without `code_err`; round trip of every symbol at both disparities; 10000 random valid symbols with gaps; 10000 symbols with bit flips and random words |
| crc16 | check value 0x29B1; reset/init value, init priority over data_valid; CRC of 1000 random frames (header + payload, half with idle gaps and garbage on `data` while `data_valid` is low) equals the model and the CRC the model's `pack_frame` put on the wire |
| prbs | first 64 bytes after reset and after loading 24 seeds (with advance gaps), zero seed, 4200-byte run, model check of the 32767-bit period |

| lane_phy | the 200 -> 50 MHz handoff: 400 words, each equal to the four consecutive pad samples recorded at the clk_s edges (samples[0] oldest), tiling the pad stream with no overlap and no gap, INVERT flips all four |

Other agents add `cdr_oversample`, `comma_align`, `lane_monitor`, `watchdog`, `uart` (see top-level README section 9).
