"""dec_8b10b vs model/link8b10b.py (README section 9 row 1)."""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as m

SYMS = [(b, False) for b in range(256)] + [(b, True) for b in m.K_BYTES]
D0_1_NEG = m.encode(0x20, False, -1)[0]   # unbalanced, legal at rd-, leaves rd positive
D0_0_NEG = m.encode(0x00, False, -1)[0]   # unbalanced, legal at rd- only
D0_0_POS = m.encode(0x00, False, 1)[0]    # unbalanced, legal at rd+ only


class Ref:
    """Model-side state: running disparity -1/+1/None (unknown after code_err)."""
    def __init__(self):
        self.rd = -1

    def step(self, w):
        b, k, self.rd, ce, de = m.decode(w, self.rd)
        return (b, int(k), int(ce), int(de))


async def reset(dut):
    dut.rst.value = 1
    dut.symbol_valid.value = 0
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.symbol.value = 0
    dut.symbol_valid.value = 0
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


async def push(dut, w, valid=1):
    """Present one word; read the registered result at the next falling edge."""
    dut.symbol.value = w
    dut.symbol_valid.value = valid
    await FallingEdge(dut.clk)
    return (int(dut.data.value), int(dut.is_k.value), int(dut.code_err.value),
            int(dut.disp_err.value), int(dut.data_valid.value))


@cocotb.test()
async def all_1024_words_every_start_state(dut):
    """Each word at rd-, rd+ and unknown; then two probes that expose the resulting rd."""
    await start(dut)
    n_valid = 0
    for start_state in ("neg", "pos", "unk"):
        for w in range(1024):
            await reset(dut)
            ref = Ref()
            prime = {"neg": [], "pos": [D0_1_NEG], "unk": [0x000]}[start_state]
            for p in prime:
                exp = ref.step(p)
                got = await push(dut, p)
                assert got == exp + (1,), (start_state, p, got, exp)
            for i, word in enumerate((w, D0_0_NEG, D0_0_POS)):
                exp = ref.step(word)
                got = await push(dut, word)
                assert got[4] == 1
                assert got[:4] == exp, (start_state, w, word, got, exp)
                if i == 0 and start_state == "unk" and not got[2]:
                    n_valid += 1
    # exactly the words the encoder can emit decode without code_err
    assert n_valid == len(m.VALID_CODES), n_valid


@cocotb.test()
async def every_symbol_roundtrip_both_disparities(dut):
    await start(dut)
    for rd0 in (-1, 1):
        for b, k in SYMS:
            await reset(dut)
            rd = -1
            if rd0 == 1:
                await push(dut, D0_1_NEG)
                rd = 1
            w, _ = m.encode(b, k, rd)
            got = await push(dut, w)
            assert got == (b, int(k), 0, 0, 1), (b, k, rd0, got)


@cocotb.test()
async def random_valid_streams_with_gaps(dut):
    await start(dut)
    rng = random.Random(77)
    await reset(dut)
    rd = -1
    for i in range(10000):
        if rng.random() < 0.1:
            got = await push(dut, rng.randrange(1024), valid=0)
            assert got[2:] == (0, 0, 0), i
            continue
        b, k = rng.choice(SYMS)
        w, rd = m.encode(b, k, rd)
        got = await push(dut, w)
        assert got == (b, int(k), 0, 0, 1), (i, b, k, got)


@cocotb.test()
async def random_corrupted_streams(dut):
    """Bit flips and random words in an encoded stream, model tracks disparity and resync."""
    await start(dut)
    rng = random.Random(4242)
    await reset(dut)
    ref = Ref()
    rd = -1
    n_ce = n_de = 0
    for i in range(10000):
        b, k = rng.choice(SYMS)
        w, rd = m.encode(b, k, rd)
        r = rng.random()
        if r < 0.05:
            w ^= 1 << rng.randrange(10)
        elif r < 0.08:
            w = rng.randrange(1024)
        exp = ref.step(w)
        got = await push(dut, w)
        assert got == exp + (1,), (i, w, got, exp)
        n_ce += exp[2]
        n_de += exp[3]
    assert n_ce > 100 and n_de > 20, (n_ce, n_de)


@cocotb.test()
async def code_err_aligns_and_zeroes_data(dut):
    await start(dut)
    await reset(dut)
    got = await push(dut, 0x000)          # not a code word
    assert got == (0, 0, 1, 0, 1), got
    # resync: after the error an unbalanced symbol of either disparity is accepted without disp_err
    got = await push(dut, D0_0_POS)
    assert got == (0, 0, 0, 0, 1), got
    # rd is now negative again after D0.0 at rd+; D0.0 for rd+ again must flag
    got = await push(dut, D0_0_POS)
    ref = Ref()
    ref.step(0x000)
    ref.step(D0_0_POS)
    assert got[:4] == ref.step(D0_0_POS)
