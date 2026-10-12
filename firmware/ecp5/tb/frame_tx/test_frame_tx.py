"""frame_tx testbench (cocotb 2.1). Parameters from env TX_LEN, TX_GAP, DIV (see Makefile).

Every expectation is derived from model/link8b10b.py. Each test ends on an await.
"""
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as m

TX_LEN = int(os.environ["TX_LEN"])
TX_GAP = int(os.environ["TX_GAP"])
DIV = int(os.environ["DIV"])

K285_BITS = m.symbols_to_bits([m.encode(m.K28_5, True, -1)[0]])
K285_BITS_POS = m.symbols_to_bits([m.encode(m.K28_5, True, +1)[0]])


async def setup(dut, enable=0):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.enable.value = enable
    for _ in range(4):
        await FallingEdge(dut.clk)
    dut.rst.value = 0


async def capture(dut, n_bits, spacing=None):
    """Collect tx_bit on tx_strobe; record the clk spacing between strobes."""
    bits = []
    since = None
    while len(bits) < n_bits:
        await FallingEdge(dut.clk)
        if since is not None:
            since += 1
        if int(dut.tx_strobe.value):
            if since is not None and spacing is not None:
                spacing.append(since)
            since = 0
            bits.append(int(dut.tx_bit.value))
    return bits


def runlen(bits):
    best = cur = 0
    prev = None
    for b in bits:
        cur = cur + 1 if b == prev else 1
        prev = b
        best = max(best, cur)
    return best


def to_symbols(bits):
    """Align on the first K28.5, split into 10-bit codes, decode with disparity checking."""
    off = None
    for i in range(len(bits) - 10):
        w = bits[i:i + 10]
        if w == K285_BITS or w == K285_BITS_POS:
            off = i
            break
    assert off is not None, "no K28.5 found"
    syms = []
    rd = None
    for i in range(off, len(bits) - 9, 10):
        code = sum(b << k for k, b in enumerate(bits[i:i + 10]))
        byte, is_k, rd, cerr, derr = m.decode(code, rd)
        assert not cerr, f"code error at bit {i}"
        assert not derr, f"disparity error at bit {i}"
        syms.append((byte, is_k))
    return off, syms


def parse(syms):
    """-> list of ('idle_pairs', n) / ('frame', seq, type, payload); asserts structure."""
    items = []
    i = 0
    idle = 0
    while i < len(syms):
        if syms[i] == (m.K28_5, True):
            if i + 1 >= len(syms):
                break
            assert syms[i + 1] == (m.D16_2, False), f"K28.5 not followed by D16.2 at symbol {i}"
            idle += 1
            i += 2
        elif syms[i] == (m.K27_7, True):
            if idle:
                items.append(("idle", idle))
                idle = 0
            j = i
            while j < len(syms) and syms[j] != (m.K29_7, True):
                j += 1
            if j >= len(syms):
                break  # incomplete last frame
            items.append(("frame",) + m.unpack_frame(syms[i:j + 1]))
            i = j + 1
        else:
            raise AssertionError(f"unexpected symbol {syms[i]} at {i}")
    if idle:
        items.append(("idle", idle))
    return items


def nbits_for(frames):
    per_frame = (1 + 4 + TX_LEN + 2 + 1 + 2 * TX_GAP) * 10
    return (frames * per_frame + 60) * 1


@cocotb.test()
async def idle_before_enable(dut):
    """With enable low the stream is idle pairs only, run length <= 5, strobe spacing = DIV."""
    await setup(dut, 0)
    spacing = []
    bits = await capture(dut, 600, spacing)
    off, syms = to_symbols(bits)
    items = parse(syms)
    assert len(items) == 1 and items[0][0] == "idle", items
    assert runlen(bits) <= 5
    assert off == 0, f"first symbol is not the first K28.5 (offset {off})"
    assert all(s == DIV for s in spacing), set(spacing)
    exp = m.symbols_to_bits(m.encode_stream(m.idle_pair() * 30))
    assert bits == exp[:len(bits)]
    await FallingEdge(dut.clk)


@cocotb.test()
async def frames_match_model(dut):
    """Frames with seq 0,1,2..; PRBS continued; CRC (unpack_frame); exactly TX_GAP idle pairs."""
    await setup(dut, 0)
    pre = await capture(dut, 300)
    dut.enable.value = 1
    n_frames = 4 if TX_LEN >= 128 else 12
    bits = pre + await capture(dut, nbits_for(n_frames) + 200)
    off, syms = to_symbols(bits)
    assert runlen(bits) <= 5
    items = parse(syms)
    frames = [it for it in items if it[0] == "frame"]
    assert len(frames) >= n_frames, len(frames)
    stream = m.prbs15_bytes(0, TX_LEN * len(frames))
    for k, (_, seq, ftype, payload) in enumerate(frames):
        assert seq == k, (seq, k)
        assert ftype == 0
        assert list(payload) == stream[k * TX_LEN:(k + 1) * TX_LEN], f"payload mismatch in frame {k}"
        assert len(payload) == TX_LEN
    # idle counts: idle runs between frames are exactly TX_GAP pairs
    for a, b, c in zip(items, items[1:], items[2:]):
        if a[0] == "frame" and b[0] == "idle" and c[0] == "frame":
            assert b[1] == TX_GAP, f"gap {b[1]} != {TX_GAP}"
    if TX_GAP == 0:
        # frames follow each other directly: no idle item between two frames
        kinds = [it[0] for it in items]
        first = kinds.index("frame")
        assert all(k == "frame" for k in kinds[first:-1]), kinds
    # counters (the transmitter is at most 1-2 symbols ahead of the line)
    done = len(frames)
    assert done <= int(dut.frames_sent.value) <= done + 2
    assert int(dut.seq.value) == int(dut.frames_sent.value)
    await FallingEdge(dut.clk)


@cocotb.test()
async def enable_low_finishes_frame_then_idles(dut):
    """Dropping enable while the scheduler is in the payload state lets that frame finish."""
    await setup(dut, 0)
    bits = []

    async def collect():
        while True:
            await FallingEdge(dut.clk)
            if int(dut.tx_strobe.value):
                bits.append(int(dut.tx_bit.value))

    cocotb.start_soon(collect())
    for _ in range(100):
        await FallingEdge(dut.clk)
    dut.enable.value = 1
    for _ in range(100000):
        await FallingEdge(dut.clk)
        if int(dut.st.value) == 7:     # S_PAY (internal state, rtl/frame_tx.v)
            break
    else:
        raise AssertionError("never reached the payload state")
    dut.enable.value = 0
    n0 = len(bits)
    while len(bits) < n0 + nbits_for(1) + 20 * 10 + 400:
        await FallingEdge(dut.clk)
    off, syms = to_symbols(list(bits))
    assert runlen(bits) <= 5
    items = parse(syms)
    frames = [it for it in items if it[0] == "frame"]
    assert len(frames) == 1 and frames[0][1] == 0, items
    assert items[-1][0] == "idle" and items[-1][1] >= 3
    await FallingEdge(dut.clk)


@cocotb.test()
async def reset_restarts(dut):
    """A reset restarts seq at 0, the PRBS from its seed, and the disparity."""
    await setup(dut, 0)
    dut.enable.value = 1
    await capture(dut, nbits_for(2))
    dut.enable.value = 0
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    bits = []

    async def collect():
        while True:
            await FallingEdge(dut.clk)
            if int(dut.tx_strobe.value):
                bits.append(int(dut.tx_bit.value))

    cocotb.start_soon(collect())
    dut.rst.value = 0
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.enable.value = 1
    while len(bits) < nbits_for(2) + 200:
        await FallingEdge(dut.clk)
    off, syms = to_symbols(bits)
    assert off == 0, off
    items = parse(syms)
    frames = [it for it in items if it[0] == "frame"]
    assert frames and frames[0][1] == 0
    assert list(frames[0][3]) == m.prbs15_bytes(0, TX_LEN)
    await FallingEdge(dut.clk)
