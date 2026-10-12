"""lane_phy 200 -> 50 MHz handoff (rtl/lane_phy.v header).  The pad is driven with random bits on
clk_s FALLING edges (half a clk_s period away from the capture edge) and its level at every clk_s
rising edge E(n) is recorded as p(n).  At each clk_c rising edge (coincident with E(m)) the word
must be p(m-4..m-1), oldest first in samples[0], and consecutive words must tile the pad stream:
no overlap, no gap.  Expectations come from the recorded pad levels, never from the RTL.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


@cocotb.test()
async def words_are_consecutive_non_overlapping(dut):
    cocotb.start_soon(Clock(dut.clk25, 40, unit="ns").start())
    dut.pad.value = 0
    rng = random.Random(7)
    p = []                 # p[n]: pad level at the n-th clk_s rising edge (n counted from 0)
    words = []             # (m, plain, inv) at each clk_c rising edge, m = index of that edge in clk_s

    async def drive():
        while True:
            await FallingEdge(dut.clk_s)
            dut.pad.value = rng.getrandbits(1)

    async def record():
        while True:
            await RisingEdge(dut.clk_s)
            p.append(int(dut.pad.value))

    await Timer(100, unit="ns")
    cocotb.start_soon(drive())
    cocotb.start_soon(record())
    # skip the first clk_c edges (flops unknown), then collect words; read 1 ns after the edge
    nwords = 400
    for _ in range(nwords + 3):
        await RisingEdge(dut.clk_c)
        await Timer(1, unit="ns")
        m = len(p) - 1                     # the clk_c edge coincides with the latest clk_s edge E(m)
        words.append((m, int(dut.s_plain.value), int(dut.s_inv.value)))
    assert words[-1][0] - words[0][0] == 4 * (len(words) - 1), "clk_c is not clk_s/4 (edge index spacing)"
    assert all((w[0] - words[0][0]) % 4 == 0 for w in words), "clk_c edges not on every 4th clk_s edge"
    checked = 0
    for m, plain, inv in words[3:]:        # words from the 4th edge on: the c0..c3 chain is full
        exp = p[m - 4:m]                    # oldest first
        got = [(plain >> k) & 1 for k in range(4)]
        assert got == exp, f"word at E({m}): got {got}, pad stream says {exp}"
        got_i = [(inv >> k) & 1 for k in range(4)]
        assert got_i == [1 - b for b in exp], f"INVERT word at E({m}): {got_i}"
        checked += 1
    # tiling: concatenated words reproduce the stream with no gap or overlap
    stream = []
    for m, plain, inv in words[3:]:
        stream += [(plain >> k) & 1 for k in range(4)]
    m0 = words[3][0]
    assert stream == p[m0 - 4:m0 - 4 + len(stream)], "concatenated words do not tile the pad stream"
    dut._log.info("%d words checked: samples[0] oldest, no overlap, no gap, INVERT flips all four", checked)
    await Timer(1, unit="ns")
