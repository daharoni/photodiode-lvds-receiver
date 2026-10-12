"""cdr_oversample against model/linesim.py (README section 9, row 3).
Expectations come from the model's transmitted bit list, never from the RTL.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from model import linesim as L

NBITS = 100_000
SETTLE = 2_000      # lock-in bits skipped before counting errors (f converges in ~1000)


async def drive(dut, words, valid_mode="const", drain=0, start_clock=True):
    """Feed one word per valid cycle; return per-cycle (bits, nbits) list
    (the drain cycles are NOT included so counts are not polluted).
    valid_mode "const": samples_valid = 1 every cycle; "alt": every other cycle
    (the old 100 MHz lane condition, kept as a hold-state test; the 50 MHz design ties it high)."""
    if start_clock:
        cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.samples.value = 0
    dut.samples_valid.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    out = []
    for w in words:
        dut.samples.value = w
        dut.samples_valid.value = 1
        await RisingEdge(dut.clk)
        out.append((int(dut.bits.value), int(dut.nbits.value)))
        if valid_mode == "alt":
            dut.samples.value = 0xA   # junk while invalid: must be ignored
            dut.samples_valid.value = 0
            await RisingEdge(dut.clk)
            out.append((int(dut.bits.value), int(dut.nbits.value)))
    for _ in range(drain):
        await RisingEdge(dut.clk)
        out.append((int(dut.bits.value), int(dut.nbits.value)))
    return out


def flatten(out):
    rec = []
    for b, n in out:
        assert n in (0, 1, 2), f"nbits={n}"
        if n >= 1:
            rec.append(b & 1)
        if n == 2:
            rec.append((b >> 1) & 1)
    return rec


def find_offset(rec, tx, k, span=64, lo=-1500, hi=1500):
    ref = rec[k:k + span]
    for d in range(lo, hi):
        if k + d >= 0 and tx[k + d:k + d + span] == ref:
            return d
    return None


@cocotb.test()
@cocotb.parametrize(ppm=[-500, 0, 500], jit=[0.0, 0.15, 0.3], phase=[0, 1, 2, 3])
async def recovers_stream(dut, ppm, jit, phase):
    """Zero bit errors after lock-in over 1e5 bits; bit count within +-2."""
    tx = L.random_runlimited_bits(NBITS, seed=100 + phase)
    words = L.line_samples(tx, ppm=ppm, jitter_ui=jit, start_phase=phase,
                           seed=5 + phase)
    rec = flatten(await drive(dut, words, drain=0))
    d = find_offset(rec, tx, SETTLE)
    assert d is not None, "could not align recovered stream to the transmitted one"
    seg = tx[SETTLE + d:SETTLE + d + len(rec) - SETTLE]
    n = min(len(seg), len(rec) - SETTLE)
    errs = [i for i in range(n) if rec[SETTLE + i] != seg[i]]
    assert not errs, f"{len(errs)} bit errors, first at recovered index {SETTLE + errs[0]}"
    assert abs(len(rec) - NBITS) <= 2, f"recovered {len(rec)} bits, sent {NBITS}"
    dut._log.info("ppm=%d jit=%.2f phase=%d: %d bits, offset %d, 0 errors", ppm, jit, phase, len(rec), d)


@cocotb.test()
@cocotb.parametrize(jit=[0.0, 0.15, 0.3], level=[0, 1])
async def reacquires_after_gap(dut, jit, level):
    """10 us (1000 cycles) of constant level mid-stream; clean again within 100 bits."""
    n1, n2, gap_cycles, ppm = 20_000, 5_000, 1000, 300
    tx1 = L.random_runlimited_bits(n1, seed=11)
    tx2 = L.random_runlimited_bits(n2, seed=12)
    tx = tx1 + tx2
    words = L.line_samples(tx, ppm=ppm, jitter_ui=jit, start_phase=1,
                           gaps=[(n1, gap_cycles, level)], seed=3)
    out = await drive(dut, words, drain=0)
    # first cycle after the gap: end of segment 1 plus the gap
    seg1_samples = int(n1 * 4 / (1 + ppm * 1e-6))
    g_end = (seg1_samples + gap_cycles * 4) // 4
    rec2 = flatten(out[g_end + 2:])
    d = find_offset(rec2, tx2, 100, lo=-12, hi=12)
    assert d is not None, "no alignment to the post-gap stream within 100 bits"
    seg = tx2[100 + d:]
    n = min(len(seg), len(rec2) - 100)
    errs = [i for i in range(n) if rec2[100 + i] != seg[i]]
    assert not errs, f"{len(errs)} errors after reacquisition, first at post-gap bit {100 + errs[0]}"


@cocotb.test()
async def transition_flag_tracks_edges(dut):
    """transition is high exactly when the model says a word contains an edge
    (one cycle of latency), and stays low on constant input."""
    tx = L.random_runlimited_bits(2000, seed=21) + [1] * 200
    words = L.line_samples(tx, start_phase=2, gaps=[(1000, 100, 0)], seed=2)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.samples.value = 0
    dut.samples_valid.value = 1
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    samples = L.words_to_samples(words)
    prev = 0
    exp, got = [], []
    for i, w in enumerate(words):
        s = samples[4 * i:4 * i + 4]
        seq = [prev] + s
        exp.append(int(any(seq[j] != seq[j + 1] for j in range(4))))
        prev = s[3]
        dut.samples.value = w
        await RisingEdge(dut.clk)
        got.append(int(dut.transition.value))
    # compare with one cycle of latency, skipping the first words (reset prev)
    assert got[2:] == exp[1:-1], "transition flag does not match the model"


@cocotb.test()
@cocotb.parametrize(ppm=[-500, 0, 500])
async def valid_every_other_matches_constant(dut, ppm):
    """samples_valid every other cycle (real condition) gives bit-for-bit the
    same recovered stream as samples_valid held at 1; invalid cycles report
    nbits = 0 and transition = 0 and ignore the junk on samples."""
    tx = L.random_runlimited_bits(20_000, seed=77)
    words = L.line_samples(tx, ppm=ppm, jitter_ui=0.3, start_phase=2, seed=9)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    a = await drive(dut, words, "const", drain=0, start_clock=False)
    b = await drive(dut, words, "alt", drain=0, start_clock=False)
    ra, rb = flatten(a), flatten(b)
    diff = [i for i in range(min(len(ra), len(rb))) if ra[i] != rb[i]]
    # alt mode reads one more output at the end (latency): allow a 1-bit tail
    assert 0 <= len(rb) - len(ra) <= 1
    rb = rb[:len(ra)]
    assert ra == rb, f"recovered bits differ (const {len(ra)}, alt {len(rb)}, first diff {diff[:3]})"
    assert len(ra) > 19_900
    # In "alt" mode the reads taken at valid edges see the output of the
    # preceding invalid edge (reads are pre-update), which must be nbits = 0.
    assert all(n == 0 for _, n in b[0::2]), "nbits != 0 on a cycle without samples_valid"
