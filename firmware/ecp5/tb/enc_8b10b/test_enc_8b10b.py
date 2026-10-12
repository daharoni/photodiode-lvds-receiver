"""enc_8b10b vs model/link8b10b.py (README section 9 row 1)."""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as m

SYMS = [(b, False) for b in range(256)] + [(b, True) for b in m.K_BYTES]


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.data.value = 0
    dut.is_k.value = 0
    dut.data_valid.value = 0
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


async def send(dut, byte, is_k, valid=1):
    """Drive one cycle at a falling edge; the rising edge in between registers it, so the
    outputs read at the next falling edge are the 1-cycle-latency result of THIS drive."""
    dut.data.value = byte
    dut.is_k.value = int(is_k)
    dut.data_valid.value = valid
    await FallingEdge(dut.clk)
    return int(dut.code.value), int(dut.code_valid.value), int(dut.enc_err.value)


@cocotb.test()
async def every_symbol_both_disparities(dut):
    await start(dut)
    for rd_start in (-1, 1):
        for byte, is_k in SYMS:
            dut.rst.value = 1
            await FallingEdge(dut.clk)
            dut.rst.value = 0
            rd = -1
            if rd_start == 1:                      # prime: D0.1 at rd- ends positive
                await send(dut, 0x20, False)
                _, rd = m.encode(0x20, False, rd)
                assert rd == 1
            code, valid, err = await send(dut, byte, is_k)
            exp, _ = m.encode(byte, is_k, rd)
            assert (code, valid, err) == (exp, 1, 0), (byte, is_k, rd_start, code, exp)


@cocotb.test()
async def invalid_k_gives_k285_and_flag(dut):
    await start(dut)
    for rd_start in (-1, 1):
        for byte in range(256):
            if m.is_valid_k(byte):
                continue
            dut.rst.value = 1
            await FallingEdge(dut.clk)
            dut.rst.value = 0
            rd = -1
            if rd_start == 1:
                await send(dut, 0x20, False)
                rd = 1
            code, valid, err = await send(dut, byte, True)
            exp, _ = m.encode(m.K28_5, True, rd)
            assert (code, valid, err) == (exp, 1, 1), (byte, rd_start)


@cocotb.test()
async def random_stream_with_gaps(dut):
    await start(dut)
    rng = random.Random(1234)
    rd = -1
    n_sym = 0
    for _ in range(12000):
        if rng.random() < 0.15:
            byte, is_k, valid = rng.randrange(256), rng.random() < 0.3, 0
        else:
            byte, is_k = rng.choice(SYMS)
            valid = 1
        code, v, err = await send(dut, byte, is_k, valid)
        assert v == valid and err == 0
        if valid:
            c, rd = m.encode(byte, is_k, rd)
            assert code == c, (n_sym, code, c)
            n_sym += 1
    assert n_sym > 9000


@cocotb.test()
async def reset_returns_to_negative(dut):
    await start(dut)
    await send(dut, 0x20, False)          # rd -> positive
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    code, valid, err = await send(dut, m.K28_5, True)
    assert code == m.encode(m.K28_5, True, -1)[0] and valid == 1 and err == 0
