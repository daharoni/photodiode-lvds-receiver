"""Bit-level line model for the CDR and alignment tests (README section 9).

Independent of model/link8b10b.py (written by another agent); everything
here is derived from the problem statement and IEEE 802.3 clause 36 tables
for the two idle symbols.  Label: PROPOSED (executable definition of the
test stimulus; nothing measured).

line_samples(bits, ...) returns the list of 4-samples-per-clock words the RTL
sees: word bit i is sample i of that 100 MHz cycle, bit 0 is the OLDEST.
Conventions:
  * One bit nominally spans `oversample` samples.
  * ppm > 0 means the transmitter bit rate is HIGHER than nominal by that
    many ppm (bit period = oversample / (1 + ppm*1e-6) samples).
  * Jitter is uniform in [-jitter_ui, +jitter_ui] of a UI, applied
    independently to every bit boundary (boundary 0 of a segment is exact).
  * start_phase (samples, may be fractional) delays the first boundary of
    the first segment; before it the line sits at the level of bits[0].
  * gaps: list of (bit_index, cycles, level).  Before bit `bit_index` the line
    is held constant for `cycles` clock cycles at `level` (0, 1, or None =
    keep the previous level), then the next segment restarts with a random
    sub-sample phase (this is what a real silence looks like).
  * invert flips every output sample (a test for the CALLER, not the CDR).
"""
import bisect
import random

COMMA_RDN = [0, 0, 1, 1, 1, 1, 1, 0, 1, 0]   # K28.5, RD-, transmit order (a b c d e i f g h j)
COMMA_RDP = [1, 1, 0, 0, 0, 0, 0, 1, 0, 1]   # K28.5, RD+
# D16.2: 5b/6b D16 = 011011 (RD-) / 100100 (RD+); 3b/4b .2 = 0101 (neutral).
# K28.5 sent at RD- ends with RD+ (001111 has four ones), so D16.2 goes out at
# RD+: 100100 0101, which returns RD to negative (clause 36 /I2/ ordered set).
D16_2_RDP = [1, 0, 0, 1, 0, 0, 0, 1, 0, 1]
IDLE_PAIR = COMMA_RDN + D16_2_RDP             # 20 bits, RD- before and after


def idle_bits(npairs):
    return IDLE_PAIR * npairs


def random_runlimited_bits(n, max_run=5, seed=0):
    """n random bits with every run of equal bits <= max_run."""
    rng = random.Random(seed)
    out = []
    run = 0
    last = None
    for _ in range(n):
        b = rng.getrandbits(1)
        if b == last and run >= max_run:
            b ^= 1
        run = run + 1 if b == last else 1
        last = b
        out.append(b)
    return out


def contains_comma(bits, start=0):
    """Index of the first position >= start where a K28.5 pattern (either
    disparity) begins, or -1."""
    for i in range(start, len(bits) - 9):
        w = bits[i:i + 10]
        if w == COMMA_RDN or w == COMMA_RDP:
            return i
    return -1


def comma_free_random_bits(n, max_run=5, seed=0, history=()):
    """Random run-limited bits containing no K28.5 pattern but still full of
    comma-like fragments (for instance 0011111 not followed by 010).  The bit
    that would complete a comma is flipped; the flip never breaks the run
    limit because the comma's 9th and 10th bits alternate.  `history` is the
    bits that precede the returned ones (for example the 9 zeros a receiver
    shift register holds after reset), included in the comma check."""
    rng = random.Random(seed)
    out = []
    run = 0
    last = None
    for _ in range(n):
        b = rng.getrandbits(1)
        if b == last and run >= max_run:
            b ^= 1
        ctx = list(history) + out
        if len(ctx) >= 9 and (ctx[-9:] + [b] in (COMMA_RDN, COMMA_RDP)):
            b ^= 1
        run = run + 1 if b == last else 1
        last = b
        out.append(b)
    return out


def _segment(bits, os_, ppm, jitter_ui, offset, rng):
    """Samples (list of int) for one gap-free segment, ending with its last
    bit period; first boundary at `offset` samples."""
    p = os_ / (1.0 + ppm * 1e-6)
    n = len(bits)
    edges = []
    for j in range(1, n):
        e = offset + j * p + rng.uniform(-jitter_ui, jitter_ui) * os_
        edges.append(e)
    # edges are monotonic as long as jitter_ui < 0.5 - ppm effects
    end = int(offset + n * p)
    out = []
    for s in range(end):
        k = bisect.bisect_right(edges, s)   # number of boundaries passed
        out.append(bits[k])
    return out


def line_samples(bits, oversample=4, ppm=0.0, jitter_ui=0.0, invert=False,
                 start_phase=0.0, gaps=(), seed=0):
    rng = random.Random(seed)
    gaps = sorted(gaps, key=lambda g: g[0])
    cuts = [0] + [g[0] for g in gaps] + [len(bits)]
    samples = []
    for si in range(len(cuts) - 1):
        seg = bits[cuts[si]:cuts[si + 1]]
        if si == 0:
            off = start_phase
        else:
            gi = gaps[si - 1]
            level = gi[2]
            if level is None:
                level = samples[-1] if samples else seg[0]
            samples += [level] * (gi[1] * oversample)
            off = rng.uniform(0, oversample)
        if not seg:
            continue
        samples += _segment(seg, oversample, ppm, jitter_ui, off, rng)
    pad = (-len(samples)) % oversample
    samples += [samples[-1]] * pad
    if invert:
        samples = [s ^ 1 for s in samples]
    words = []
    for w in range(0, len(samples), oversample):
        v = 0
        for i in range(oversample):
            v |= samples[w + i] << i
        words.append(v)
    return words


def words_to_samples(words, oversample=4):
    return [(w >> i) & 1 for w in words for i in range(oversample)]
