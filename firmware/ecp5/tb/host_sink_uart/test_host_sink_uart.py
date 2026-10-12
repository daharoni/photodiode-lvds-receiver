"""host_sink_uart vs model/link8b10b (README section 6 host sink, section 9).

Input stream is driven like lane_merge's output; the UART line is decoded by a Python bit-banged
receiver sampling at the middle of each bit (50 MHz clock, 3 Mbaud, 16.67 clocks per bit).
Expected bytes come from the model: 0x5A followed by the non-K symbols of pack_frame
(seq LE, type, len, payload, crc LE). Every test ends on an await (tb/README.md).
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as m

CLK_HZ = 50_000_000
BAUD = 3_000_000
CPB = CLK_HZ / BAUD          # clocks per bit


def wire_bytes(seq, ftype, payload):
    body = bytes(b for b, k in m.pack_frame(seq, ftype, payload) if not k)
    return bytes([0x5A]) + body


class Env:
    def __init__(self, dut):
        self.dut = dut
        self.t = 0
        self.rx = bytearray()
        self.rx_times = []
        self.framing_errors = 0
        self.busy_seen = []

    async def uart_rx(self):
        d = self.dut
        prev = 1
        state = "idle"
        t0 = 0
        bits = []
        k = 0
        while True:
            await FallingEdge(d.clk)
            self.t += 1
            level = int(d.txd.value)
            if state == "idle":
                if prev == 1 and level == 0:
                    state, t0, bits, k = "bits", self.t, [], 1
            else:
                if self.t >= t0 + (k + 0.5) * CPB:
                    bits.append(level)
                    k += 1
                    if k == 10:
                        if bits[-1] != 1:
                            self.framing_errors += 1
                        self.rx.append(sum(b << i for i, b in enumerate(bits[:8])))
                        self.rx_times.append(t0)
                        state = "idle"
                        # next start bit can only begin after the stop bit's mid point; re-arm on the edge
                        prev = 1
                        continue
            prev = level

    async def idle(self, n):
        for _ in range(n):
            await FallingEdge(self.dut.clk)

    async def feed(self, seq, ftype, payload, gap=2):
        """Drive one frame like lane_merge: byte every `gap` cycles (gap=1: every cycle). Returns cycles used."""
        d = self.dut
        n = len(payload)
        used = 0
        rng = random.Random(seq)
        for i, b in enumerate(payload):
            d.in_valid.value = 1
            d.in_data.value = b
            d.in_first.value = 1 if i == 0 else 0
            d.in_last.value = 1 if i == n - 1 else 0
            d.in_seq.value = seq
            d.in_type.value = ftype
            d.in_len.value = n - 1
            await FallingEdge(d.clk)
            used += 1
            for _ in range(gap - 1):
                d.in_valid.value = 0
                d.in_first.value = rng.randrange(2)     # garbage while not valid
                d.in_last.value = rng.randrange(2)
                d.in_data.value = rng.randrange(256)
                await FallingEdge(d.clk)
                used += 1
        d.in_valid.value = 0
        d.in_first.value = 0
        d.in_last.value = 0
        d.in_seq.value = rng.randrange(65536)           # merge may change these after the frame
        d.in_type.value = rng.randrange(256)
        d.in_len.value = rng.randrange(256)
        await FallingEdge(d.clk)
        return used + 1


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in (dut.in_valid, dut.in_data, dut.in_first, dut.in_last, dut.in_seq, dut.in_type, dut.in_len):
        s.value = 0
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)
    env = Env(dut)
    cocotb.start_soon(env.uart_rx())
    return env


def counters(dut):
    return int(dut.host_sent.value), int(dut.host_drops.value)


@cocotb.test()
async def single_frames(dut):
    env = await start(dut)
    rng = random.Random(4)
    exp = bytearray()
    sent = 0
    for n, gap in ((1, 2), (2, 1), (3, 2), (64, 2), (64, 1), (255, 1), (256, 2), (256, 1), (17, 3)):
        p = bytes(rng.randrange(256) for _ in range(n))
        seq, t = rng.randrange(65536), rng.randrange(256)
        assert int(dut.in_ready.value) == 1
        await env.feed(seq, t, p, gap)
        exp += wire_bytes(seq, t, p)
        sent += 1
        # wait for the whole frame on the wire
        await env.idle(int((len(p) + 8) * 10 * CPB) + 300)
        assert bytes(env.rx) == bytes(exp), (n, len(env.rx), len(exp))
        assert counters(dut) == (sent, 0), counters(dut)
        assert int(dut.busy.value) == 0
    assert env.framing_errors == 0
    await env.idle(5)


@cocotb.test()
async def busy_flag(dut):
    env = await start(dut)
    assert int(dut.busy.value) == 0
    await env.feed(0x1234, 5, bytes(range(20)), 2)
    saw = 0
    for _ in range(int(30 * 10 * CPB) + 300):
        await FallingEdge(dut.clk)
        saw |= int(dut.busy.value)
    assert saw == 1 and int(dut.busy.value) == 0
    await env.idle(5)


@cocotb.test()
async def burst_drops(dut):
    """Frames arrive faster than the UART drains: exactly the frames arriving while busy are dropped."""
    env = await start(dut)
    rng = random.Random(12)
    accepted = bytearray()
    n_acc = n_drop = 0
    busy_until = -1.0          # clock at which the last byte of the accepted frame starts to be sent
    t = 0
    for i in range(40):
        n = rng.randint(1, 24)
        p = bytes(rng.randrange(256) for _ in range(n))
        seq = rng.randrange(65536)
        # arrival: advance by a random spacing, avoiding the ambiguous zone around busy_until
        t += rng.choice([300, 700, 1500])
        if abs(t - busy_until) < 250:
            t += 500
        # bring the testbench clock to absolute time t (cycles since start of this test)
        while env.t < t:
            await FallingEdge(dut.clk)
        t0 = env.t
        used = await env.feed(seq, 7, p, gap=2)
        if t0 >= busy_until:
            accepted += wire_bytes(seq, 7, p)
            n_acc += 1
            busy_until = t0 + (n + 7 - 1) * 10 * CPB       # frame = n + 7 bytes on the wire
        else:
            n_drop += 1
        t = max(t, env.t)
        # a frame fed while its arrival time was inside the feed window may collide: avoid
        assert used < 400
    await env.idle(int(35 * 10 * CPB) + 500)
    assert n_drop >= 10 and n_acc >= 5, (n_acc, n_drop)
    assert counters(dut) == (n_acc, n_drop), (counters(dut), n_acc, n_drop)
    assert bytes(env.rx) == bytes(accepted)
    assert env.framing_errors == 0
    await env.idle(5)


@cocotb.test()
async def back_to_back_after_idle(dut):
    """A frame arriving right after the previous one has fully left is accepted again."""
    env = await start(dut)
    exp = bytearray()
    for i in range(4):
        p = bytes([i] * 5)
        await env.feed(i, 1, p, 2)
        exp += wire_bytes(i, 1, p)
        await env.idle(int(12 * 10 * CPB) + 60)      # 5 + 7 bytes on the wire + margin
    assert bytes(env.rx) == bytes(exp) and counters(dut) == (4, 0)
    await env.idle(5)
