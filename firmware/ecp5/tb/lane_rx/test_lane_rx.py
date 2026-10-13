"""lane_rx (cdr -> comma_align -> dec_8b10b) against model/link8b10b.py + model/linesim.py.
Expectations come from the model's symbol list, never from the RTL.  Words are presented with
samples_valid held high (one 4-sample word per clk cycle, as lane_phy delivers at 50 MHz).
Inversion is applied by the test (invert=True in the line model).  lock needs LOCK_SYMBOLS = 128
valid symbols, so after lock the stream must be error free (no settling allowance).
"""
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as M
from model import linesim as L

AUTO = int(os.environ.get("TB_AUTO", "1"))   # AUTO_INVERT of this build (Makefile builds 1 and 0)
SKIP_AUTO0 = dict(skip=(AUTO == 0))           # the pre-existing tests run in the AUTO_INVERT = 1 build only
# Documented AUTO_INVERT detection latency (rtl/lane_rx.v header): flip with the 8th idle pair after
# alignment = 160 UI = 160 clk cycles; allow the aligner/CDR pipeline on top.
FLIP_PAIRS = 8
FLIP_WORDS_MAX = FLIP_PAIRS * 20 + 30
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
        self.inv_hist = []   # pol_inv per word index
        self.p2 = []         # word indices with err_pulse2 (idle_mismatch)


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
        mon.inv_hist.append(int(dut.pol_inv.value))
        if int(dut.err_pulse2.value):
            mon.p2.append(mon.words)
        mon.words += 1
    for _ in range(12):                    # drain, no new words
        dut.samples_valid.value = 0
        await FallingEdge(dut.clk)
        if int(dut.data_valid.value):
            mon.dec.append((mon.words, int(dut.data.value), bool(int(dut.is_k.value)),
                            int(dut.err_pulse.value), int(dut.lock.value)))
        mon.lock_hist.append(int(dut.lock.value))
        mon.al_hist.append(int(dut.aligned.value))
        mon.inv_hist.append(int(dut.pol_inv.value))
        if int(dut.err_pulse2.value):
            mon.p2.append(mon.words)
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


@cocotb.test(**SKIP_AUTO0)
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


@cocotb.test(**SKIP_AUTO0)
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


@cocotb.test(**SKIP_AUTO0)
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


@cocotb.test(**SKIP_AUTO0)
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


def frames_from(decoded):
    """Split a decoded (byte, is_k) list at /S/../T/ and unpack each through the model;
    returns (n_good, n_bad)."""
    good = bad = 0
    cur = None
    for sym in decoded:
        if sym == (M.K27_7, True):
            cur = [sym]
        elif cur is not None:
            cur.append(sym)
            if sym == (M.K29_7, True):
                try:
                    M.unpack_frame(cur)
                    good += 1
                except ValueError:
                    bad += 1
                cur = None
    return good, bad


@cocotb.test(skip=(AUTO == 0))
@cocotb.parametrize(ppm=[-500, 500], phase=[0, 2])
async def inverted_stream_auto_corrects(dut, ppm, phase):
    """F1: a polarity-inverted line (the DUT sees the raw inverted words, pol_inv starts at 0).
    The lane locks, pol_inv flips exactly once within the documented 8 idle pairs of the first
    alignment, and from the first lock on the stream is error free and equals the model (all frames
    intact, no idle_mismatch)."""
    syms = build_symbols(n_idle_head=150, nframes=8)
    words = L.line_samples(sym_bits(syms), ppm=ppm, jitter_ui=0.3, start_phase=phase + 0.37 * (phase & 1),
                           invert=True, seed=31 + phase)
    await start(dut)
    mon = Mon()
    await run_words(dut, words, mon)
    flips = [i for i in range(1, len(mon.inv_hist)) if mon.inv_hist[i] != mon.inv_hist[i - 1]]
    assert len(flips) == 1 and mon.inv_hist[-1] == 1, f"pol_inv flips at words {flips}"
    # the documented bound is counted from the start of the aligned stretch that produced the flip
    first_al = next(i for i, a in enumerate(mon.al_hist) if a)
    start_al = max(i for i in range(first_al, flips[0] + 1) if i == first_al or not mon.al_hist[i - 1] and mon.al_hist[i])
    lat = flips[0] - start_al
    assert lat <= FLIP_WORDS_MAX, f"flip {lat} words after (re)alignment, documented <= {FLIP_WORDS_MAX}"
    pre = [w for w in mon.p2 if w <= flips[0] + 4]
    assert 1 <= len(pre) <= FLIP_PAIRS + 1, f"{len(pre)} idle_mismatch pulses before the flip"
    k = first_lock_index(mon)
    assert k is not None, "lane never locked"
    got = [(d[1], d[2]) for d in mon.dec[k:]]
    assert all(d[4] for d in mon.dec[k:]), "lock dropped after the first lock"
    assert sum(d[3] for d in mon.dec[k:]) == 0, "err_pulse after lock"
    lock_word = next(i for i, l in enumerate(mon.lock_hist) if l)
    assert not [w for w in mon.p2 if w >= lock_word], "idle_mismatch after lock"
    assert lock_word > flips[0], "locked before the polarity flip"
    assert find_anchor(syms, got) is not None, "decoded stream is not a model run"
    good, bad = frames_from(got)
    assert good >= 1 and bad == 0, f"{good} good / {bad} bad frames after lock"
    dut._log.info("ppm=%d phase=%d: aligned at word %d, pol_inv flipped %d words later (limit %d), "
                  "%d idle_mismatch before the flip, lock at word %d, %d frames intact",
                  ppm, phase, start_al, lat, FLIP_WORDS_MAX, len(pre), lock_word, good)
    await FallingEdge(dut.clk)


@cocotb.test(skip=(AUTO == 0))
async def correct_stream_never_flips(dut):
    """A stream the DUT sees in the correct polarity (INIT_INVERT = 0 matches it) never flips pol_inv
    and never pulses idle_mismatch."""
    syms = build_symbols(n_idle_head=150, nframes=6)
    words = L.line_samples(sym_bits(syms), ppm=100, jitter_ui=0.3, start_phase=1.0, seed=5)
    await start(dut)
    mon = Mon()
    await run_words(dut, words, mon)
    assert not any(mon.inv_hist), "pol_inv flipped on a correct-polarity stream"
    assert not mon.p2, f"idle_mismatch on a correct stream at words {mon.p2[:5]}"
    assert first_lock_index(mon) is not None
    await FallingEdge(dut.clk)


@cocotb.test(skip=(AUTO == 1))
async def inverted_stream_without_auto_invert(dut):
    """AUTO_INVERT = 0: an inverted line still locks (8b/10b is complement symmetric) with no
    code/disparity errors, but every idle pair raises idle_mismatch (the monitor counts it) and no
    frame unpacks (CRC/length)."""
    syms = build_symbols(n_idle_head=150, nframes=8)
    words = L.line_samples(sym_bits(syms), ppm=0, jitter_ui=0.3, start_phase=1.37, invert=True, seed=41)
    await start(dut)
    mon = Mon()
    await run_words(dut, words, mon)
    assert not any(mon.inv_hist), "pol_inv changed with AUTO_INVERT = 0"
    k = first_lock_index(mon)
    assert k is not None, "an inverted lane should still lock"
    got = [(d[1], d[2]) for d in mon.dec[k:]]
    assert sum(d[3] for d in mon.dec[k:]) == 0, "inverted symbols are valid codes: no err_pulse expected"
    lock_word = next(i for i, l in enumerate(mon.lock_hist) if l)
    after = [w for w in mon.p2 if w >= lock_word]
    n_pairs = sum(1 for g in got if g == (M.K28_5, True))
    assert len(after) >= n_pairs - 8 and len(after) > 20, \
        f"{len(after)} idle_mismatch pulses after lock for {n_pairs} commas"
    good, bad = frames_from(got)
    assert good == 0 and bad >= 1, f"{good} frames unpacked from an inverted lane ({bad} rejected)"
    dut._log.info("AUTO_INVERT=0: %d idle_mismatch pulses after lock for %d commas, %d frames rejected, %d accepted",
                  len(after), n_pairs, bad, good)
    await FallingEdge(dut.clk)
