"""comma_align against model/linesim.py helpers (README section 9, row 4).
Expected symbols are computed from the transmitted bit list only.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from model import linesim as L


def to_int(bits10):
    return sum(b << i for i, b in enumerate(bits10))      # bit 0 = first received


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.bits.value = 0
    dut.nbits.value = 0
    dut.realign.value = 0
    dut.invalid_pulse.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


def chunk(bits, mode, rng):
    """Split the stream into (bits, nbits) cycles.  mode: 'one', 'two', 'rand'."""
    cyc = []
    i = 0
    while i < len(bits):
        if mode == "one":
            n = 1
        elif mode == "two":
            n = 2
        else:
            n = rng.choice([0, 1, 1, 2, 2])
        n = min(n, len(bits) - i)
        v = 0
        for k in range(n):
            v |= bits[i + k] << k
        cyc.append((v, n, 0, 0))
        i += n
    return cyc


async def run(dut, cycles, tail=6):
    """cycles: list of (bits, nbits, invalid_pulse, realign).  Returns list of
    (symbol_valid, symbol, aligned), one per cycle, each read one edge after
    its inputs were applied (registered outputs)."""
    obs = []
    for b, n, inv, ra in cycles + [(0, 0, 0, 0)] * tail:
        dut.bits.value = b
        dut.nbits.value = n
        dut.invalid_pulse.value = inv
        dut.realign.value = ra
        await RisingEdge(dut.clk)       # read right after the edge returns the values
                                        # registered at the PREVIOUS edge (one clk lag)
        obs.append((int(dut.symbol_valid.value), int(dut.symbol.value), int(dut.aligned.value)))
    return obs


def symbols_seen(obs):
    return [s for v, s, _ in obs if v]


def expected_symbols(stream, i0):
    return [to_int(stream[i:i + 10]) for i in range(i0, len(stream) - 9, 10)]


@cocotb.test()
@cocotb.parametrize(lead=list(range(0, 40, 1)), mode=["rand"])
async def aligns_from_every_bit_phase(dut, lead, mode):
    """Every lead length 0..39 (all 10 bit phases, 4 symbol offsets) with random
    comma-like fragments in the lead; then idle pairs; every symbol after the
    first comma is delivered in order."""
    await start(dut)
    rng = random.Random(1000 + lead)
    pre = L.comma_free_random_bits(lead, seed=lead, history=[0] * 9) if lead else []
    stream = pre + L.idle_bits(12)
    stream = stream + L.comma_free_random_bits(100, seed=77 + lead)   # data-like tail
    i0 = L.contains_comma(stream)
    assert i0 >= lead and i0 - lead < 10
    obs = await run(dut, chunk(stream, mode, rng))
    got = symbols_seen(obs)
    exp = expected_symbols(stream, i0)
    assert got == exp, f"lead={lead}: {len(got)} symbols vs {len(exp)} expected, first mismatch " \
        f"{next((k for k in range(min(len(got), len(exp))) if got[k] != exp[k]), None)}"
    assert obs[-1][2] == 1, "aligned not set"


@cocotb.test()
@cocotb.parametrize(mode=["one", "two"])
async def chunking_modes(dut, mode):
    """Constant 1 bit/clk and constant 2 bits/clk (odd and even comma phases)."""
    for lead in (0, 1, 2, 3, 7):
        await start(dut)
        pre = L.comma_free_random_bits(lead, seed=lead + 5, history=[0] * 9) if lead else []
        stream = pre + L.idle_bits(6) + L.comma_free_random_bits(60, seed=9)
        i0 = L.contains_comma(stream)
        obs = await run(dut, chunk(stream, mode, random.Random(1)))
        assert symbols_seen(obs) == expected_symbols(stream, i0), f"mode {mode} lead {lead}"
        # reset between sub-cases
        dut.rst.value = 1
        await RisingEdge(dut.clk)
        dut.rst.value = 0
        await RisingEdge(dut.clk)


@cocotb.test()
async def both_disparities_align(dut):
    """A lone K28.5 RD+ (1100000101) and a lone RD- each align."""
    for pat in (L.COMMA_RDP, L.COMMA_RDN):
        await start(dut)
        stream = L.comma_free_random_bits(13, seed=3, history=[0] * 9) + pat + L.comma_free_random_bits(50, seed=4)
        i0 = L.contains_comma(stream)
        assert stream[i0:i0 + 10] == pat
        obs = await run(dut, chunk(stream, "rand", random.Random(4)))
        assert symbols_seen(obs) == expected_symbols(stream, i0)
        dut.rst.value = 1
        await RisingEdge(dut.clk)
        dut.rst.value = 0
        await RisingEdge(dut.clk)


@cocotb.test()
async def no_comma_no_alignment(dut):
    """Comma-free random data (full of 0011111 / 1100000 fragments): never aligns."""
    await start(dut)
    stream = L.comma_free_random_bits(20000, seed=5, history=[0] * 9)
    obs = await run(dut, chunk(stream, "rand", random.Random(5)))
    assert not any(v for v, _, _ in obs), "symbol emitted without a comma"
    assert not any(a for _, _, a in obs), "aligned without a comma"


@cocotb.test()
async def realign_drops_and_reacquires(dut):
    """realign clears aligned; a shifted stream is re-aligned on its own comma."""
    await start(dut)
    rng = random.Random(8)
    s1 = L.comma_free_random_bits(7, seed=1, history=[0] * 9) + L.idle_bits(5)
    obs = await run(dut, chunk(s1, "one", rng), tail=0)
    assert obs[-1][2] == 1
    # realign pulse, then 3 extra bits so the new comma has a different phase
    s2 = L.comma_free_random_bits(3, seed=2) + L.idle_bits(8) + L.comma_free_random_bits(50, seed=6)
    cyc = [(0, 0, 0, 1)] + chunk(s2, "rand", rng)
    obs2 = await run(dut, cyc)
    assert obs2[1][2] == 0 and obs2[1][0] == 0, "realign must drop alignment"
    # find where the new alignment is expected: the search resumes with the
    # bit history of s1 still in the window, but s1's tail idles contain commas
    # only at s1's phase; the first NEW comma (in s2) fixes the new phase.
    i0 = L.contains_comma(s2)
    got = symbols_seen(obs2)
    exp = expected_symbols(s2, i0)
    # the window may find a comma straddling s1/s2 only if one exists; check suffix
    assert got[-len(exp):] == exp, "symbols after realign do not follow the new comma"
    assert obs2[-1][2] == 1


def invalid_schedule(stream, i0, bad_slots):
    """One-bit-per-clk schedule with an invalid_pulse two clocks after the
    symbol_valid of each slot in bad_slots (slot 0 = the first comma)."""
    cyc = chunk(stream, "one", None)
    cyc = [list(c) for c in cyc]
    for k in bad_slots:
        c = i0 + 10 * k + 9 + 2          # cycle index == bit index with 1 bit/clk
        cyc[c][2] = 1
    return [tuple(c) for c in cyc]


@cocotb.test()
@cocotb.parametrize(case=[
    ("four_in_16_exact", [1, 6, 11, 16], True),
    ("four_consecutive", [2, 3, 4, 5], True),
    ("three_only", [1, 6, 11], False),
    ("four_in_17", [1, 6, 11, 17], False),
    ("spaced_6", [1, 7, 13, 19, 25, 31], False),
    ("repeated_pulse_same_slot", [3, 3, 3, 3], False),
])
async def invalid_rule(dut, case):
    """Realign on 4 invalid symbols within the last 16 (and not on 3, nor on 4
    spread over 17).  Two pulses in the same slot count once."""
    name, bad, should_drop = case
    await start(dut)
    n_pairs = 40 if not should_drop else (max(bad) + 2) // 2
    stream = L.idle_bits(n_pairs) + L.comma_free_random_bits(300, seed=12)
    i0 = 0
    sched = invalid_schedule(stream, i0, sorted(set(bad)))
    if name == "repeated_pulse_same_slot":
        sched = invalid_schedule(stream, i0, [3])
        c = i0 + 10 * 3 + 9 + 3
        sched[c] = (sched[c][0], sched[c][1], 1, 0)     # second pulse in the same slot
    obs = await run(dut, sched)
    n_sym = len(symbols_seen(obs))
    if should_drop:
        last = max(bad)
        assert obs[-1][2] == 0, "alignment not dropped"
        assert n_sym == last + 1, f"{n_sym} symbols emitted, expected to stop after slot {last}"
    else:
        assert obs[-1][2] == 1, "alignment dropped on a non-qualifying pattern"
        assert n_sym == (len(stream) // 10), f"{n_sym} symbols"
