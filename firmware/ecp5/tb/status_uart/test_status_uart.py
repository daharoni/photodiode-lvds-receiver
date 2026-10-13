"""status_uart testbench (cocotb 2.1). Parameters from env N, CLK_HZ_TB, STATUS_PERIOD_TB,
ASCII_PERIOD_TB (see Makefile). Bit-banged Python UART receivers; Python reference for the binary
message, CRC-8 and the ASCII report. Each test ends on an await."""
import os
import random
import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

N = int(os.environ["N"])
CLK_HZ = int(os.environ["CLK_HZ_TB"])
SPERIOD = int(os.environ["STATUS_PERIOD_TB"])
APERIOD = int(os.environ["ASCII_PERIOD_TB"])


def crc8(data, crc=0):
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def ref_message(seq, nibbles):
    """nibbles: list of N lane nibbles -> 10 bytes."""
    pad = list(nibbles) + [0x7] * (14 - len(nibbles))
    nb = [(pad[2 * j + 1] << 4) | pad[2 * j] for j in range(7)]
    body = [seq] + nb
    return [0xA5] + body + [crc8(body)]


class Uart:
    """Samples a line once per clk (falling edge), decodes 8N1 at CLK_HZ/baud clocks per bit."""

    def __init__(self, dut, sig, baud, name):
        self.dut, self.sig, self.name = dut, sig, name
        self.T = CLK_HZ / baud
        self.bytes = []          # (byte, cycle of start bit)
        self.errors = []
        self.low_cycles = 0
        self.cycle = 0
        self.task = cocotb.start_soon(self.run())

    async def run(self):
        while True:
            await FallingEdge(self.dut.clk)
            self.cycle += 1
            if int(self.sig.value) == 0:
                t0 = self.cycle
                nxt = [t0 + int((k + 0.5) * self.T + 0.5) for k in range(10)]
                samples = []
                for t in nxt:
                    while self.cycle < t:
                        await FallingEdge(self.dut.clk)
                        self.cycle += 1
                    samples.append(int(self.sig.value))
                if samples[0] != 0 or samples[9] != 1:
                    self.errors.append((self.name, t0, "framing"))
                self.bytes.append((sum(b << i for i, b in enumerate(samples[1:9])), t0))
                end = t0 + int(10 * self.T)
                while self.cycle < end:
                    await FallingEdge(self.dut.clk)
                    self.cycle += 1


async def setup(dut, asc_en=1):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.ascii_enable.value = asc_en
    drive(dut, [0] * N, [0] * N, [0] * N, [0] * N, [0] * 5)
    for _ in range(4):
        await FallingEdge(dut.clk)
    dut.rst.value = 0


def drive(dut, nib, lock, err, fe, ok_and_glob):
    """ok_and_glob = [merged_ok, lost, dup, hdrop, sent]; per-lane frames_ok passed in `fe2` below."""
    pass


def pack(vals, w):
    return sum((v & ((1 << w) - 1)) << (w * i) for i, v in enumerate(vals))


def drive(dut, nib, lock, err, fe, glob, okl=None, inv=None, rs=0):
    dut.nibble.value = pack(nib, 4)
    dut.lock.value = pack(lock, 1)
    dut.err_count.value = pack(err, 16)
    dut.frame_err.value = pack(fe, 16)
    dut.frames_ok.value = pack(okl if okl is not None else [0] * N, 16)
    dut.merged_ok.value = glob[0]
    dut.frames_lost.value = glob[1]
    dut.dups.value = glob[2]
    dut.host_drops.value = glob[3]
    dut.frames_sent.value = glob[4]
    dut.pol_inv.value = pack(inv if inv is not None else [0] * N, 1)
    dut.resyncs.value = rs


def rand_state(rng):
    return dict(
        nib=[rng.randrange(16) for _ in range(N)],
        lock=[rng.randrange(2) for _ in range(N)],
        err=[rng.choice([0, 1, 9, 99, 1000, 65535, rng.randrange(65536)]) for _ in range(N)],
        fe=[rng.randrange(65536) for _ in range(N)],
        okl=[rng.choice([0, 10, 100, 12345, 65535]) for _ in range(N)],
        glob=[rng.choice([0, 7, 65535, rng.randrange(65536)]) for _ in range(5)],
        inv=[rng.randrange(2) for _ in range(N)],
        rs=rng.choice([0, 1, 65535, rng.randrange(65536)]),
    )


def drive_state(dut, s):
    drive(dut, s["nib"], s["lock"], s["err"], s["fe"], s["glob"], s["okl"], s["inv"], s["rs"])


@cocotb.test()
async def binary_messages(dut):
    """Random nibble vectors: bytes 0xA5, seq, 7 nibble bytes (LOS padding), CRC-8 match the reference."""
    await setup(dut, asc_en=0)
    rng = random.Random(N)
    esp = Uart(dut, dut.esp_txd, 1_000_000, "esp")
    driven = []
    for _ in range(14):
        s = rand_state(rng)
        drive_state(dut, s)
        driven.append(s["nib"])
        for _ in range(SPERIOD * 2 + 17):
            await FallingEdge(dut.clk)
    msgs = [esp.bytes[i:i + 10] for i in range(0, len(esp.bytes) - 9, 10)]
    assert len(msgs) >= 20, len(msgs)
    assert not esp.errors
    for k, mb in enumerate(msgs):
        data = [b for b, _ in mb]
        t0 = [t for _, t in mb]
        assert t0[1] - t0[0] >= 9 * CLK_HZ // 1_000_000 and t0[9] - t0[0] < 11 * 10 * 10  # back to back
        assert data[0] == 0xA5
        assert data[1] == k & 0xFF, (data[1], k)
        assert any(data == ref_message(k & 0xFF, nib) for nib in driven), (k, data)
    # period: start of consecutive messages SPERIOD clocks apart
    starts = [mb[0][1] for mb in msgs]
    assert all(b - a == SPERIOD for a, b in zip(starts, starts[1:])), [b - a for a, b in zip(starts, starts[1:])]
    await FallingEdge(dut.clk)


@cocotb.test()
async def binary_node_map(dut):
    """Single known vector: lane i nibble = i+1 (mod 16); byte j low nibble = lane 2j."""
    await setup(dut, asc_en=0)
    nib = [(i + 1) & 0xF for i in range(N)]
    drive(dut, nib, [1] * N, [0] * N, [0] * N, [0] * 5)
    esp = Uart(dut, dut.esp_txd, 1_000_000, "esp")
    for _ in range(SPERIOD * 3):
        await FallingEdge(dut.clk)
    data = [b for b, _ in esp.bytes[:10]]
    assert data == ref_message(0, nib), data
    pad = nib + [7] * (14 - N)
    assert data[2] == (pad[1] << 4) | pad[0]
    if N < 14:
        assert data[2 + 6] == (pad[13] << 4) | pad[12]
    await FallingEdge(dut.clk)


def parse_report(text):
    lines = text.split("\r\n")
    assert lines[-1] == "", repr(lines[-1])
    lines = lines[:-1]
    m = re.fullmatch(r"LINK seq=(\d+)((?: L\d+=[0-9A-F])+) ok=(\d+) lost=(\d+) dup=(\d+) hdrop=(\d+) sent=(\d+) rs=(\d+)", lines[0])
    assert m, repr(lines[0])
    seq = int(m.group(1))
    lanes = re.findall(r" L(\d+)=([0-9A-F])", m.group(2))
    assert [int(a) for a, _ in lanes] == list(range(N))
    nibs = [int(b, 16) for _, b in lanes]
    glob = [int(m.group(i)) for i in range(3, 8)]
    rs = int(m.group(8))
    per = []
    assert len(lines) == 1 + N, len(lines)
    for i, ln in enumerate(lines[1:]):
        mm = re.fullmatch(r"LANE(\d+) lock=([01]) err=(\d+) fe=(\d+) ok=(\d+) inv=([01])", ln)
        assert mm, repr(ln)
        assert int(mm.group(1)) == i
        per.append(tuple(int(mm.group(j)) for j in range(2, 7)))
    return seq, nibs, glob, rs, per


@cocotb.test()
async def ascii_report(dut):
    """ASCII reports parse back to the inputs; all inputs latched at the start of the report."""
    await setup(dut, asc_en=1)
    rng = random.Random(100 + N)
    ftdi = Uart(dut, dut.ftdi_txd, 115_200, "ftdi")
    sa = rand_state(rng)
    sb = rand_state(rng)
    drive_state(dut, sa)
    # wait for the first start bit, then change every input: the report must still show sa
    while not ftdi.bytes:
        await FallingEdge(dut.clk)
    drive_state(dut, sb)
    # the second report starts one period after the first; collect through the second
    first_start = ftdi.bytes[0][1]
    while ftdi.cycle < first_start + APERIOD + 2000:
        await FallingEdge(dut.clk)
    # let the second report finish
    last = len(ftdi.bytes)
    for _ in range(3000):
        await FallingEdge(dut.clk)
    while len(ftdi.bytes) != last:
        last = len(ftdi.bytes)
        for _ in range(3000):
            await FallingEdge(dut.clk)
    assert not ftdi.errors
    text = "".join(chr(b) for b, _ in ftdi.bytes)
    # split into reports at "LINK"
    reports = [("LINK" + r) for r in text.split("LINK")[1:]]
    assert len(reports) >= 2, len(reports)
    for k, r in enumerate(reports[:2]):
        s = sa if k == 0 else sb
        seq, nibs, glob, rs, per = parse_report(r)
        assert seq == k
        assert nibs == s["nib"], (nibs, s["nib"])
        assert glob == s["glob"], (glob, s["glob"])
        assert rs == s["rs"], (rs, s["rs"])
        assert per == [(s["lock"][i], s["err"][i], s["fe"][i], s["okl"][i], s["inv"][i]) for i in range(N)]
    await FallingEdge(dut.clk)


@cocotb.test()
async def ascii_enable_low_idles_line(dut):
    """ascii_enable = 0: ftdi_txd stays high (and the report in progress is aborted); esp keeps going."""
    await setup(dut, asc_en=0)
    drive_state(dut, rand_state(random.Random(5)))
    esp = Uart(dut, dut.esp_txd, 1_000_000, "esp")
    for _ in range(int(APERIOD * 1.2)):
        await FallingEdge(dut.clk)
        assert int(dut.ftdi_txd.value) == 1
    assert len(esp.bytes) >= 10 * 10, len(esp.bytes)
    # enable, let a report start, then disable mid-report: line goes and stays high
    dut.ascii_enable.value = 1
    ftdi = Uart(dut, dut.ftdi_txd, 115_200, "ftdi")
    for _ in range(APERIOD + 30000):
        await FallingEdge(dut.clk)
    assert ftdi.bytes, "no report after enabling"
    dut.ascii_enable.value = 0
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    n_before = len(ftdi.bytes)
    for _ in range(APERIOD):
        await FallingEdge(dut.clk)
        assert int(dut.ftdi_txd.value) == 1
    assert len(ftdi.bytes) <= n_before + 1
    await FallingEdge(dut.clk)


@cocotb.test()
async def ftdi_busy_matches_character_framing(dut):
    """F4: ftdi_busy is high from the start bit to the end of the stop bit of every ASCII character
    and low between characters and while ascii_enable = 0 (the top switches the FTDI mux only when low)."""
    await setup(dut, asc_en=1)
    drive_state(dut, rand_state(random.Random(9)))
    bit = 10_000_000 / 115_200            # clocks per bit (CLK_HZ_TB = 10 MHz)
    prev_txd, start, n_chars, low_seen = 1, None, 0, 0
    t = 0
    while n_chars < 40 and t < APERIOD * 2:
        await FallingEdge(dut.clk)
        t += 1
        txd, busy = int(dut.ftdi_txd.value), int(dut.ftdi_busy.value)
        if txd == 0 and prev_txd == 1 and start is None:      # start bit
            start = t
        if start is not None:
            if t - start < 9 * bit - 1:
                assert busy == 1, f"ftdi_busy low {t - start} clocks into a character"
            if not busy:
                assert t - start >= 10 * bit - 2, f"character ended after {t - start} clocks"
                n_chars += 1
                start = None
        elif not busy:
            low_seen += 1
        prev_txd = txd
    assert n_chars >= 40 and low_seen > 0
    dut.ascii_enable.value = 0
    for _ in range(4):
        await FallingEdge(dut.clk)
    assert int(dut.ftdi_busy.value) == 0 and int(dut.ftdi_txd.value) == 1
    await FallingEdge(dut.clk)
