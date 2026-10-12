"""prbs (PRBS-15, x^15+x^14+1) vs model.prbs15_bytes (README section 9)."""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as m


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.seed.value = 0
    dut.load.value = 0
    dut.advance.value = 0
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


async def pull(dut, n, rng=None):
    out = []
    for _ in range(n):
        while rng is not None and rng.random() < 0.3:
            before = int(dut.data.value)
            dut.advance.value = 0
            await FallingEdge(dut.clk)
            assert int(dut.data.value) == before   # data holds without advance
        out.append(int(dut.data.value))
        dut.advance.value = 1
        await FallingEdge(dut.clk)
    dut.advance.value = 0
    # A write still pending when a test returns crashes Icarus+cocotb at shutdown (observed
    # here, vvp segfault); always end on an await.
    await FallingEdge(dut.clk)
    return out


async def load(dut, seed):
    dut.seed.value = seed
    dut.load.value = 1
    await FallingEdge(dut.clk)
    dut.load.value = 0


@cocotb.test()
async def first_64_bytes_after_reset(dut):
    await start(dut)
    assert await pull(dut, 64) == m.prbs15_bytes(0x7FFF, 64)


@cocotb.test()
async def seeds(dut):
    await start(dut)
    rng = random.Random(5)
    for seed in [1, 0x7FFF, 0x1234, 0x4000] + [rng.randrange(1, 0x8000) for _ in range(20)]:
        await load(dut, seed)
        assert await pull(dut, 64, rng) == m.prbs15_bytes(seed, 64), hex(seed)


@cocotb.test()
async def zero_seed_loads_all_ones(dut):
    await start(dut)
    await load(dut, 0)
    assert await pull(dut, 16) == m.prbs15_bytes(0x7FFF, 16)


@cocotb.test()
async def long_run_and_period(dut):
    await start(dut)
    n = 4200
    got = await pull(dut, n)
    assert got == m.prbs15_bytes(0x7FFF, n)
    # model sanity: maximal length, 2^15 - 1 = 32767 bits, no shorter period
    bits = [(b >> i) & 1 for b in m.prbs15_bytes(0x7FFF, 4100 + 16) for i in range(8)]
    assert len(bits) > 32767 + 64
    assert bits[:64] == bits[32767:32767 + 64]
    assert all(bits[:64] != bits[p:p + 64] for p in range(1, 32767))
