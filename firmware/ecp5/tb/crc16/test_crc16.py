"""crc16 vs model/link8b10b.crc16_ccitt_false (README section 9 row 2)."""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as m


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.init.value = 0
    dut.data.value = 0
    dut.data_valid.value = 0
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


async def run(dut, data, rng=None):
    """init, then feed bytes (optionally with idle gaps); return crc the cycle after the last byte."""
    dut.init.value = 1
    dut.data_valid.value = 0
    await FallingEdge(dut.clk)
    assert int(dut.crc.value) == 0xFFFF
    dut.init.value = 0
    for b in data:
        while rng is not None and rng.random() < 0.2:
            dut.data.value = rng.randrange(256)   # garbage with data_valid low must be ignored
            dut.data_valid.value = 0
            await FallingEdge(dut.clk)
        dut.data.value = b
        dut.data_valid.value = 1
        await FallingEdge(dut.clk)
    dut.data_valid.value = 0
    dut.data.value = 0x5A
    await FallingEdge(dut.clk)
    return int(dut.crc.value)


@cocotb.test()
async def check_value(dut):
    await start(dut)
    assert m.crc16_ccitt_false(b"123456789") == 0x29B1
    assert await run(dut, b"123456789") == 0x29B1


@cocotb.test()
async def reset_and_init_value(dut):
    await start(dut)
    assert int(dut.crc.value) == 0xFFFF
    dut.data.value = 0x31
    dut.data_valid.value = 1
    await FallingEdge(dut.clk)
    assert int(dut.crc.value) == m.crc16_ccitt_false(b"1")
    dut.init.value = 1            # init wins over data_valid in the same cycle
    await FallingEdge(dut.clk)
    assert int(dut.crc.value) == 0xFFFF
    dut.init.value = 0
    dut.data_valid.value = 0
    await FallingEdge(dut.clk)
    assert int(dut.crc.value) == 0xFFFF


@cocotb.test()
async def random_frames(dut):
    await start(dut)
    rng = random.Random(99)
    for i in range(1000):
        n = rng.randrange(1, 257)
        frame = m.pack_frame(rng.randrange(65536), rng.randrange(256), bytes(rng.randrange(256) for _ in range(n)))
        body = bytes(b for b, k in frame if not k)     # seq, type, len, payload, crc
        covered, crc_tx = body[:-2], body[-2] | (body[-1] << 8)
        got = await run(dut, covered, rng if i % 2 else None)
        assert got == m.crc16_ccitt_false(covered) == crc_tx, (i, hex(got))
