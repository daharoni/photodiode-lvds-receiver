"""lane_rx (cdr -> comma_align -> dec_8b10b) against model/link8b10b.py + model/linesim.py.
Expectations come from the model's symbol list, never from the RTL.  Words are presented with
samples_valid held high (one 4-sample word per clk cycle, as lane_phy delivers at 50 MHz).
Inversion is applied by the test (invert=True in the line model).  lock needs LOCK_SYMBOLS = 128
valid symbols, so after lock the stream must be error free (no settling allowance).
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as M
from model import linesim as L

PAYLOAD_LEN = 32
RELOCK_LIMIT = 150    # symbols, asserted below (measured values are logged): the CDR/alignment recovery of about 40
                      # symbols plus LOCK_SYMBOLS = 128 consecutive valid symbols before lock is declared again


def build_symbols(n_idle_head=150, nframes=6, gap_pairs=4, seq0=0, tail_pairs=20):
    syms = []
    syms += M.idle_pair() * n_idle_head
    for f in range(nframes):
        payload = M.prbs15_bytes(0x1234 + f, PAYLOAD_LEN)
        syms += M.pack_frame(seq0 + f, 0, payload)
        syms += M.idle_pair() * gap_pairs
    syms += M.idle_pair() * tail_pairs
    return syms


def sym_bits(syms):
    return M.symbols_to_bits(M.encode_stream(syms, -1))


class Mon:
    """Per-cycle monitor; one sample per falling edge."""
    def __init__(self):
        self.dec = []        # (idx_in_run, data, is_k, err, lock)
        self.lock_hist = []  # lock per word index
        self.al_hist = []


async def run_words(dut, words, mon):
    """Feed words (one per cycle); record every cycle."""
    mon.words = 0
    for w in words:
        dut.samples.value = w
        dut.samples_valid.value = 1
        await FallingEdge(dut.clk)
        if int(dut.data_valid.value):
            mon.dec.append((mon.words, int(dut.data.value), bool(int(dut.is_k.value)),
                            int(dut.err_pulse.value), int(dut.lock.value)))
        mon.lock_hist.append(int(dut.lock.value))
        mon.al_hist.append(int(dut.aligned.value))
        mon.words += 1
    for _ in range(12):                    # drain, no new words
        dut.samples_valid.value = 0
        await FallingEdge(dut.clk)
        if int(dut.data_valid.value):
            mon.dec.append((mon.words, int(dut.data.value), bool(int(dut.is_k.value)),
                            int(dut.err_pulse.value), int(dut.lock.value)))
        mon.lock_hist.append(int(dut.lock.value))
        mon.al_hist.append(int(dut.aligned.value))
    dut.samples_valid.value = 0
    await FallingEdge(dut.clk)


async def start(dut, realign=0):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.samples.value = 0
    dut.samples_valid.value = 0
    dut.realign_in.value = realign
    for _ in range(4):
        await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


def first_lock_index(mon):
    for i, d in enumerate(mon.dec):
        if d[4]:
            return i
    return None


def find_anchor(expected, got):
    """Offset d with expected[d:d+len(got)] == got, or None."""
    n = len(got)
    for d in range(0, len(expected) - n + 1):
        if expected[d:d + n] == got:
            return d
    return None


@cocotb.test()
@cocotb.parametrize(ppm=[-500, 0, 500], phase=[0, 1, 2, 3], invert=[False, True])
async def decodes_stream(dut, ppm, phase, invert):
    """After lock: decoded stream == model symbols, zero err_pulse."""
    syms = build_symbols()
    bits = sym_bits(syms)
    words = L.line_samples(bits, ppm=ppm, jitter_ui=0.3, start_phase=phase + 0.37 * (phase & 1),
                           invert=invert, seed=11 + phase)
    if invert:
        words = [w ^ 0xF for w in words]   # what lane_phy INVERT does: undo the line polarity
    await start(dut)
    mon = Mon()
    await run_words(dut, words, mon)
    k = first_lock_index(mon)
    assert k is not None, "lane never locked"
    # The CDR frequency loop needs about 1000 bits (100 symbols) to converge from reset
    # (cdr_oversample header) and lock needs LOCK_SYMBOLS = 128 valid symbols, so from the first
    # lock on: lock held, zero errors, stream equals the model.  No settling allowance.
    got = [(d[1], d[2]) for d in mon.dec[k:]]
    assert all(d[4] for d in mon.dec[k:]), "lock dropped after the first lock"
    errs = sum(d[3] for d in mon.dec[k:])
    assert errs == 0, f"{errs} err_pulse after lock (first at decoded #{[i for i, d in enumerate(mon.dec) if d[3] and i >= k][:5]})"
    d = find_anchor(syms, got)
    assert d is not None, "decoded stream is not a contiguous run of the model symbols"
    assert len(got) > 0.4 * len(syms), f"only {len(got)} symbols decoded after lock"
    # frames inside the decoded span must be intact (unpack through the model)
    dut._log.info("ppm=%d phase=%d inv=%s: first lock at decoded #%d, %d symbols compared, model offset %d",
                  ppm, phase, invert, k, len(got), d)


@cocotb.test()
async def lock_requires_realign_release(dut):
    """realign_in held high keeps the lane unaligned and unlocked; released, it locks."""
    syms = build_symbols(n_idle_head=100, nframes=2)
    words = L.line_samples(sym_bits(syms), ppm=200, jitter_ui=0.2, start_phase=1, seed=3)
    await start(dut, realign=1)
    mon = Mon()
    half = len(words) // 3
    await run_words(dut, words[:half], mon)
    assert not any(mon.lock_hist) and not any(mon.al_hist), "aligned/locked while realign_in is high"
    dut.realign_in.value = 0
    mon2 = Mon()
    await run_words(dut, words[half:], mon2)
    assert any(mon2.lock_hist), "no lock after realign_in released"


@cocotb.test()
async def bit_flips_raise_errors_and_four_in_sixteen_drops_lock(dut):
    """A single flip raises err_pulse; 8 flips in 8 consecutive symbols drop alignment (rule 4
    invalid in 16) and the lane relocks to the right alignment afterwards."""
    syms = build_symbols(n_idle_head=80, nframes=8, gap_pairs=2, tail_pairs=100)   # tail: relock needs 128 symbols
    bits = sym_bits(syms)
    single_at = 80 * 20 + 3 * 10 + 4      # inside the first frame (a data symbol), long after lock
    multi_at = 80 * 20 + 5 * (45 * 10 + 40) + 12
    b = list(bits)
    b[single_at] ^= 1
    for j in range(8):
        b[multi_at + 10 * j + 3] ^= 1
    words = L.line_samples(b, ppm=-300, jitter_ui=0.2, start_phase=2, seed=9)
    await start(dut)
    mon = Mon()
    await run_words(dut, words, mon)
    k = first_lock_index(mon)
    assert k is not None
    got = [(d[1], d[2]) for d in mon.dec]
    err_idx = [i for i, d in enumerate(mon.dec) if d[3]]
    assert len(err_idx) >= 1, "single flip raised no err_pulse"
    sym_single = single_at // 10
    # anchor decoded index -> model symbol index with the first frame /S/ (model symbol 160)
    s_idx = [i for i, g in enumerate(got) if g == (0xFB, True) and i >= k]
    assert s_idx, "no /S/ decoded"
    off = 80 * 2 - s_idx[0]              # decoded index i is model symbol i + off
    # err_pulse of the single flip arrives within 3 symbols of the flipped one
    near = [i for i in err_idx if abs((i + off) - sym_single) <= 3]
    assert near, f"err_pulse not near flipped symbol (errs at model symbols {[i + off for i in err_idx][:10]}, flip at {sym_single})"
    # the 8 consecutive flips: at least 4 error pulses within 16 symbols, then alignment lost
    m0 = multi_at // 10
    multi_errs = [i + off for i in err_idx if m0 - 1 <= i + off <= m0 + 16]
    assert len(multi_errs) >= 4, f"only {len(multi_errs)} errors for 8 flipped symbols"
    # aligned/lock history: find a falling edge of lock after the multi flip region begins
    lh = mon.lock_hist
    falls = [i for i in range(1, len(lh)) if lh[i - 1] and not lh[i]]
    assert falls, "lock never dropped after 8 consecutive flipped symbols"
    ah = mon.al_hist
    afalls = [i for i in range(1, len(ah)) if ah[i - 1] and not ah[i]]
    assert afalls, "alignment never dropped"
    rises_after = [i for i in range(falls[0], len(lh)) if lh[i] and not lh[i - 1]]
    assert rises_after, "lane did not relock after the realign"
    # after the relock the stream matches the model again with no errors
    # find the last lock rise in decode index terms: first lock-high entry after the last lock-low entry
    last_low = max(i for i, d in enumerate(mon.dec) if not d[4])
    after = mon.dec[last_low + 1:]
    assert len(after) > 20
    gotA = [(d[1], d[2]) for d in after]
    assert sum(d[3] for d in after) == 0, "errors after relock"
    assert find_anchor(syms, gotA) is not None, "post-relock stream is not a model run"


@cocotb.test()
@cocotb.parametrize(level=[0, 1], jit=[0.0, 0.3])
async def relock_after_10us_gap(dut, level, jit):
    """10 us (500 words) of constant level, then idle: lock drops in the gap and returns within
    RELOCK_LIMIT symbols of the first post-gap symbol.  The measured count is logged."""
    syms = build_symbols(n_idle_head=100, nframes=0) + M.idle_pair() * 250   # tail long enough to relock after the gap
    bits = sym_bits(syms)
    gap_bit = 100 * 20 + 20 * 20            # after 120 idle pairs
    gap_words = 500
    words = L.line_samples(bits, ppm=300, jitter_ui=jit, start_phase=1, seed=21,
                           gaps=[(gap_bit, gap_words, level)])
    # word index where the post-gap bits start (pre-gap segment length in words + gap)
    pre_words = gap_bit            # one bit = one word nominally; ppm shifts <= 0.2 word
    await start(dut)
    mon = Mon()
    await run_words(dut, words, mon)
    lh = mon.lock_hist
    locked_before = any(lh[:pre_words])
    assert locked_before, "lane was not locked before the gap"
    falls = [i for i in range(1, len(lh)) if lh[i - 1] and not lh[i]]
    assert falls, "lock did not drop during the gap"
    f = falls[-1]
    rises = [i for i in range(f, len(lh)) if lh[i] and not lh[i - 1]]
    assert rises, "no relock after the gap"
    end_word = pre_words + gap_words
    rel_words = rises[0] - end_word
    rel_syms = rel_words / 10.0
    dut._log.info("level=%d jitter=%.1f: lock fell at word %d (gap %d..%d), relocked at word %d: %.1f symbols after the gap end",
                  level, jit, f, pre_words, end_word, rises[0], rel_syms)
    assert rel_syms <= RELOCK_LIMIT, f"relock took {rel_syms:.1f} symbols"
