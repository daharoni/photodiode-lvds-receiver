"""frame_rx vs model/link8b10b (README sections 3, 6, 9).

Expectations come from the model (pack_frame, crc16_ccitt_false, idle_pair); the RTL is only read
through its ports. Inputs are driven on the falling edge, outputs sampled on the next falling edge.
Every test ends on an await (Icarus/vvp shutdown rule, tb/README.md).
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from model import link8b10b as m

IDLE = [(b, k, 0) for b, k in m.idle_pair()]


def tri(syms):
    return [(b, 1 if k else 0, 0) for b, k in syms]


def frame(seq, ftype, payload):
    return tri(m.pack_frame(seq, ftype, payload))


def body_frame(seq, ftype, len_field, payload, crc=None):
    """Hand-built frame so len/crc can be wrong independently."""
    body = bytes([seq & 255, seq >> 8, ftype, len_field]) + bytes(payload)
    c = m.crc16_ccitt_false(body) if crc is None else crc
    body += bytes([c & 255, c >> 8])
    return [(m.K27_7, 1, 0)] + [(b, 0, 0) for b in body] + [(m.K29_7, 1, 0)]


class Env:
    def __init__(self, dut):
        self.dut = dut
        self.commits = []      # dict(seq,type,len,bank)
        self.payloads = []     # bytes read back, same order as commits (auto reader)
        self.ferr = 0
        self.ovr = 0
        self.auto = True
        self.rel_delay = (0, 0)
        self.rng = random.Random(5)
        self.reader_busy = False
        self.nread = 0

    async def sampler(self):
        d = self.dut
        while True:
            await FallingEdge(d.clk)
            if int(d.commit.value):
                self.commits.append(dict(seq=int(d.c_seq.value), type=int(d.c_type.value),
                                         len=int(d.c_len.value), bank=int(d.c_bank.value)))
            self.ferr += int(d.frame_err_p.value)
            self.ovr += int(d.overrun_p.value)

    async def read_bank(self, c):
        d = self.dut
        out = bytearray()
        for i in range(c["len"] + 1):
            d.rd_addr.value = (c["bank"] << 9) | i
            await FallingEdge(d.clk)
            out.append(int(d.rd_data.value))
        return bytes(out)

    async def release(self):
        self.dut.rel.value = 1
        await FallingEdge(self.dut.clk)
        self.dut.rel.value = 0

    async def reader(self):
        d = self.dut
        while True:
            await FallingEdge(d.clk)
            if self.auto and self.nread < len(self.commits):
                self.reader_busy = True
                c = self.commits[self.nread]
                self.payloads.append(await self.read_bank(c))
                self.nread += 1
                lo, hi = self.rel_delay
                for _ in range(self.rng.randint(lo, hi)):
                    await FallingEdge(d.clk)
                await self.release()
                self.reader_busy = False


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in (dut.data, dut.is_k, dut.data_valid, dut.err_pulse, dut.rel, dut.rd_addr):
        s.value = 0
    dut.lock.value = 1
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)
    env = Env(dut)
    cocotb.start_soon(env.sampler())
    cocotb.start_soon(env.reader())
    return env


async def send(dut, syms, gap=1, lock_low=None, rng=None):
    """One symbol per `gap` cycles (data_valid high one cycle, garbage otherwise).
    lock_low = (i0, i1): lock is low for symbol indices i0 <= i < i1."""
    rng = rng or random.Random(1)
    for i, (b, k, e) in enumerate(syms):
        dut.lock.value = 0 if (lock_low and lock_low[0] <= i < lock_low[1]) else 1
        dut.data.value = b
        dut.is_k.value = k
        dut.err_pulse.value = e
        dut.data_valid.value = 1
        await FallingEdge(dut.clk)
        for _ in range(gap - 1):
            dut.data_valid.value = 0
            dut.err_pulse.value = 0
            dut.data.value = rng.randrange(256)
            dut.is_k.value = rng.randrange(2)
            await FallingEdge(dut.clk)
    dut.lock.value = 1
    dut.data_valid.value = 0
    dut.err_pulse.value = 0
    dut.is_k.value = 0
    await FallingEdge(dut.clk)


async def drain(dut, env, n=8):
    for _ in range(3000):
        await FallingEdge(dut.clk)
        if not env.reader_busy and env.nread == len(env.commits):
            break
    for _ in range(n):
        await FallingEdge(dut.clk)
    assert env.nread == len(env.commits)


def counters(dut):
    return int(dut.frames_ok.value), int(dut.frame_err.value), int(dut.overrun.value)


def check_commit(env, i, seq, ftype, payload):
    c = env.commits[i]
    assert c["seq"] == seq and c["type"] == ftype and c["len"] == len(payload) - 1, (i, c)
    assert env.payloads[i] == bytes(payload), (i, env.payloads[i][:8], bytes(payload)[:8])


@cocotb.test()
async def good_lengths(dut):
    rng = random.Random(11)
    for gap in (1, 20):
        env = await start(dut)
        exp = []
        for n in (1, 2, 64, 255, 256):
            p = bytes(rng.randrange(256) for _ in range(n))
            seq, t = rng.randrange(65536), rng.randrange(256)
            exp.append((seq, t, p))
            await send(dut, IDLE + frame(seq, t, p) + IDLE, gap)
            await drain(dut, env)
        assert len(env.commits) == 5, env.commits
        for i, (seq, t, p) in enumerate(exp):
            check_commit(env, i, seq, t, p)
        assert counters(dut) == (5, 0, 0)
        assert env.ferr == 0 and env.ovr == 0
        assert {c["bank"] for c in env.commits} == {0, 1}      # ping-pong used both banks
    await FallingEdge(dut.clk)


def bad_cases(rng):
    """(name, symbols, expected frame_err delta, expected commits delta)."""
    p = bytes(rng.randrange(256) for _ in range(40))
    good = m.pack_frame(0x1234, 0x10, p)
    out = []
    # bad CRC
    c = m.crc16_ccitt_false(bytes([0x34, 0x12, 0x10, 39]) + p) ^ 0x0100
    out.append(("bad_crc", body_frame(0x1234, 0x10, 39, p, crc=c), 1, 0))
    out.append(("len_field_shorter", body_frame(0x1234, 0x10, 30, p), 1, 0))
    out.append(("len_field_longer", body_frame(0x1234, 0x10, 41, p), 1, 0))
    out.append(("len_field_longer_by_many", body_frame(0x1234, 0x10, 255, p), 1, 0))
    g = tri(good)
    for pos, name in ((1, "err_seq"), (4, "err_len"), (20, "err_payload"), (len(g) - 3, "err_crc")):
        s = list(g)
        s[pos] = (0, 0, 1)             # decoder output on a code error: data 0, err_pulse
        out.append((name, s, 1, 0))
    s = list(g)
    b, k, _ = s[20]
    s[20] = (b, k, 1)                  # disparity error: byte intact, err_pulse
    out.append(("disp_err_payload", s, 1, 0))
    s = list(g)
    s[-1] = (m.K29_7, 1, 1)            # error on the /T/ symbol itself
    out.append(("err_on_T", s, 1, 0))
    for pos, name in ((2, "K_seq"), (4, "K_len"), (20, "K_payload"), (len(g) - 2, "K_crc")):
        s = list(g)
        s[pos] = (m.K28_5, 1, 0)
        out.append((name, s, 1, 0))
    s = list(g)
    s[20] = (m.K29_7, 1, 0)            # /T/ early (looks like shorter frame)
    out.append(("T_early", s, 1, 0))
    out.append(("missing_T_idle", g[:-1] + IDLE, 1, 0))
    out.append(("missing_T_data", g[:-1] + [(0x00, 0, 0)] + IDLE, 1, 0))
    out.append(("other_K_for_T", g[:-1] + [(m.K30_7, 1, 0)], 1, 0))
    out.append(("missing_T_then_next_S", g[:-1] + frame(7, 1, b"\x55\xAA"), 1, 1))
    out.append(("restart_by_S", g[:12] + frame(8, 2, b"\x01"), 1, 1))
    out.append(("restart_by_S_twice", g[:3] + g[:9] + frame(9, 3, b"\x02\x03"), 2, 1))
    out.append(("S_alone_then_idle", g[:1] + IDLE, 1, 0))
    return out


@cocotb.test()
async def bad_frames(dut):
    rng = random.Random(3)
    for gap in (1, 20):
        env = await start(dut)
        tot_err = 0
        tot_ok = 0
        for name, syms, derr, dcom in bad_cases(rng):
            n0 = len(env.commits)
            await send(dut, IDLE + syms + IDLE, gap)
            await drain(dut, env)
            tot_err += derr
            tot_ok += dcom
            assert len(env.commits) - n0 == dcom, (name, gap, env.commits[n0:])
            assert env.ferr == tot_err, (name, gap, env.ferr, tot_err)
            assert counters(dut) == (tot_ok, tot_err, 0), (name, gap, counters(dut))
            # the parser has recovered: a good frame still commits
            p = bytes(rng.randrange(256) for _ in range(5))
            n1 = len(env.commits)
            await send(dut, IDLE + frame(0x4000 + n1, 0x20, p) + IDLE, gap)
            await drain(dut, env)
            tot_ok += 1
            assert len(env.commits) == n1 + 1, (name, gap)
            check_commit(env, n1, 0x4000 + n1, 0x20, p)
            assert counters(dut) == (tot_ok, tot_err, 0), (name, gap, counters(dut))
        assert env.ovr == 0
    await FallingEdge(dut.clk)


@cocotb.test()
async def lock_handling(dut):
    for gap in (1, 20):
        env = await start(dut)
        p = bytes(range(30))
        g = frame(0x0102, 0x33, p)
        # lock drops mid frame and returns before the frame ends: discarded, 1 frame_err
        await send(dut, IDLE + g + IDLE, gap, lock_low=(IDLE.__len__() + 10, IDLE.__len__() + 14))
        await drain(dut, env)
        assert counters(dut) == (0, 1, 0) and env.ferr == 1 and not env.commits, counters(dut)
        # lock low for the whole frame: ignored, no error
        await send(dut, IDLE + g + IDLE, gap, lock_low=(0, 200))
        await drain(dut, env)
        assert counters(dut) == (0, 1, 0) and not env.commits
        # lock low only around the /S/ (frame started while unlocked): ignored
        await send(dut, IDLE + g + IDLE, gap, lock_low=(0, IDLE.__len__() + 1))
        await drain(dut, env)
        assert counters(dut) == (0, 1, 0) and not env.commits
        # err_pulse in idle does not count
        await send(dut, IDLE + [(0, 0, 1), (0, 0, 1)] + IDLE, gap)
        await drain(dut, env)
        assert counters(dut) == (0, 1, 0)
        # good frame after all of it
        await send(dut, IDLE + g + IDLE, gap)
        await drain(dut, env)
        assert counters(dut) == (1, 1, 0)
        check_commit(env, 0, 0x0102, 0x33, p)
    await FallingEdge(dut.clk)


@cocotb.test()
async def overrun(dut):
    rng = random.Random(21)
    for gap in (1, 20):
        env = await start(dut)
        env.auto = False
        fr = [(rng.randrange(65536), rng.randrange(256), bytes(rng.randrange(256) for _ in range(rng.randint(1, 100))))
              for _ in range(3)]
        for seq, t, p in fr:
            await send(dut, IDLE + frame(seq, t, p) + IDLE, gap)
        for _ in range(5):
            await FallingEdge(dut.clk)
        assert counters(dut) == (2, 0, 1), counters(dut)
        assert env.ovr == 1 and len(env.commits) == 1
        c1 = env.commits[0]
        assert (c1["seq"], c1["type"], c1["len"]) == (fr[0][0], fr[0][1], len(fr[0][2]) - 1)
        assert await env.read_bank(c1) == fr[0][2]
        # release the first: the second frame is presented with a fresh commit pulse
        await env.release()
        for _ in range(4):
            await FallingEdge(dut.clk)
        assert len(env.commits) == 2
        c2 = env.commits[1]
        assert (c2["seq"], c2["type"], c2["len"]) == (fr[1][0], fr[1][1], len(fr[1][2]) - 1)
        assert c2["bank"] != c1["bank"]
        assert await env.read_bank(c2) == fr[1][2]
        # with the first bank free again a fourth frame is accepted and queued behind
        seq4, p4 = 0x7777, bytes(rng.randrange(256) for _ in range(256))
        await send(dut, IDLE + frame(seq4, 0x44, p4) + IDLE, gap)
        assert counters(dut) == (3, 0, 1) and len(env.commits) == 2
        await env.release()
        for _ in range(4):
            await FallingEdge(dut.clk)
        assert len(env.commits) == 3 and env.commits[2]["seq"] == seq4
        assert await env.read_bank(env.commits[2]) == p4
        await env.release()
        for _ in range(6):
            await FallingEdge(dut.clk)
        assert len(env.commits) == 3 and env.ovr == 1
        await env.release()            # spurious release with nothing presented: ignored
        for _ in range(6):
            await FallingEdge(dut.clk)
        assert len(env.commits) == 3
    await FallingEdge(dut.clk)


@cocotb.test()
async def back_to_back(dut):
    """Frames with exactly one idle pair between them, data_valid every cycle and every 20th."""
    rng = random.Random(8)
    for gap in (1, 20):
        env = await start(dut)
        env.rel_delay = (0, 0)
        exp = []
        syms = list(IDLE)
        for i in range(12):
            p = bytes(rng.randrange(256) for _ in range(rng.randint(1, 12)))
            exp.append((0xFFF0 + i, 0x10 + i, p))
            syms += frame(0xFFF0 + i, 0x10 + i, p) + IDLE
        await send(dut, syms, gap)
        await drain(dut, env)
        assert len(env.commits) == 12 and counters(dut) == (12, 0, 0)
        for i, (seq, t, p) in enumerate(exp):
            check_commit(env, i, seq & 0xFFFF, t, p)
        # no idle at all between /T/ and the next /S/
        syms = []
        for i in range(4):
            syms += frame(i, 9, bytes([i, i + 1]))
        await send(dut, IDLE + syms + IDLE, gap)
        await drain(dut, env)
        assert len(env.commits) == 16 and counters(dut) == (16, 0, 0)
    await FallingEdge(dut.clk)


@cocotb.test()
async def random_stress(dut):
    rng = random.Random(77)
    env = await start(dut)
    env.rel_delay = (0, 400)
    sent_good = []
    n_bad = 0
    for i in range(150):
        n = rng.choice([1, 2, 3, 17, 64, 200, 256]) if rng.random() < 0.8 else rng.randint(1, 256)
        p = bytes(rng.randrange(256) for _ in range(n))
        seq = i
        syms = frame(seq, i & 255, p)
        r = rng.random()
        if r < 0.2:
            pos = rng.randrange(1, len(syms) - 1)
            syms[pos] = (syms[pos][0], syms[pos][1], 1)
            n_bad += 1
        elif r < 0.3:
            syms[rng.randrange(5, len(syms) - 3)] = (m.K28_5, 1, 0)
            n_bad += 1
        else:
            sent_good.append((seq, i & 255, p))
        await send(dut, syms + IDLE * rng.randint(1, 3), rng.choice([1, 1, 2, 20]) if n < 100 else 1, rng=rng)
    await drain(dut, env, 40)
    ok, fe, ov = counters(dut)
    assert fe == n_bad == env.ferr, (fe, n_bad)
    assert ok + ov == len(sent_good), (ok, ov, len(sent_good))
    assert len(env.commits) == ok and env.ovr == ov
    by_seq = {s: (t, p) for s, t, p in sent_good}
    last = -1
    for i, c in enumerate(env.commits):
        assert c["seq"] > last          # arrival order kept
        last = c["seq"]
        t, p = by_seq[c["seq"]]
        check_commit(env, i, c["seq"], t, p)
    dut._log.info('random_stress: sent_good=%d ok=%d overrun=%d bad=%d', len(sent_good), ok, ov, n_bad)
    assert ov > 0, 'stress never reached overrun'
    await FallingEdge(dut.clk)
