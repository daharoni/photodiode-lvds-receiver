"""lane_merge vs a Python reference of the README section 6 v0 policy (section 9 tb/lane_merge).

The DUT is the merge only. Each lane is emulated in Python with frame_rx's commit semantics
(two banks, one presented frame at a time, `commit` pulse, c_* held, next frame re-committed after
`rel`, one-cycle RAM read latency). Expectations are derived from frame contents generated here and
from the policy replayed in Python (class Ref); the RTL is only observed through its ports.
Inputs are driven on the falling edge and outputs sampled on the next falling edge.
Every test ends on an await (vvp shutdown rule, tb/README.md).
Run for N_LANES from the environment (TB_N): Makefile loops 1, 3, 7, 14.
"""
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

N = int(os.environ.get("TB_N", "3"))
AW = 9


class Ref:
    """Policy of README section 6, replayed on the order in which the DUT served the frames."""

    def __init__(self):
        self.seq_next = None
        self.out = []          # (seq, type, payload)
        self.dups = 0
        self.lost = 0

    def serve(self, seq, ftype, payload):
        if self.seq_next is None:
            d = 0
        else:
            d = (seq - self.seq_next) & 0xFFFF
            if d >= 0x8000:
                self.dups += 1
                return "dup"
        self.lost += d
        self.out.append((seq, ftype, bytes(payload)))
        self.seq_next = (seq + 1) & 0xFFFF
        return "out"


class Lane:
    def __init__(self, idx):
        self.idx = idx
        self.mem = [bytearray(b"\xEE" * 512) for _ in range(2)]
        self.q = []            # committed frames in arrival order: dict(bank, seq, type, payload)
        self.incoming = []     # (arrival cycle, seq, type, payload), ascending
        self.to_present = False
        self.c = (0, 0, 0, 0)  # seq, type, len, bank
        self.pend_rd = 0
        self.commits = 0
        self.lane_overruns = 0

    def arrive(self, seq, ftype, payload):
        used = {f["bank"] for f in self.q}
        free = [b for b in (0, 1) if b not in used]
        if not free:
            self.lane_overruns += 1
            return
        b = free[0]
        self.mem[b][:len(payload)] = payload
        self.q.append(dict(bank=b, seq=seq, type=ftype, payload=bytes(payload)))
        if len(self.q) == 1:
            self.to_present = True

    def head(self):
        return self.q[0]


class Env:
    def __init__(self, dut, ready_p=1.0, seed=1):
        self.dut = dut
        self.lanes = [Lane(i) for i in range(N)]
        self.rng = random.Random(seed)
        self.ready_p = ready_p
        self.ref = Ref()
        self.out_frames = []
        self.cur = None
        self.t = 0
        self.rel_log = []      # (lane, seq) in DUT service order
        self.err = []
        self.prev_hold = None

    def schedule(self, lane, t, seq, ftype, payload):
        self.lanes[lane].incoming.append((t, seq, ftype, payload))

    async def run(self, n_cycles, until_idle=True):
        d = self.dut
        mask_rd = (1 << (AW + 1)) - 1
        for _ in range(n_cycles):
            await FallingEdge(d.clk)
            self.t += 1
            rel = int(d.rel.value)
            addr = int(d.rd_addr.value)
            # --- release handling
            for ln in self.lanes:
                if rel >> ln.idx & 1:
                    f = ln.q.pop(0)
                    self.rel_log.append((ln.idx, f["seq"]))
                    r = self.ref.serve(f["seq"], f["type"], f["payload"])
                    if ln.q:
                        ln.to_present = True
                    f["res"] = r
            # --- output stream capture; ready decided now, transfer happens at the next rising edge
            ready = 1 if self.rng.random() < self.ready_p else 0
            d.out_ready.value = ready
            if int(d.out_valid.value):
                snap = (int(d.out_data.value), int(d.out_first.value), int(d.out_last.value),
                        int(d.out_seq.value), int(d.out_type.value), int(d.out_len.value))
                if self.prev_hold is not None and self.prev_hold != snap:
                    self.err.append("output changed while stalled at t=%d" % self.t)
                if ready:
                    self.prev_hold = None
                    self.take(snap)
                else:
                    self.prev_hold = snap
            else:
                if self.prev_hold is not None:
                    self.err.append("out_valid dropped while stalled at t=%d" % self.t)
                    self.prev_hold = None
            # --- memory pipeline (data for the address seen one falling edge ago)
            rd = 0
            for ln in self.lanes:
                rd |= ln.pend_rd << (8 * ln.idx)
            d.rd_data.value = rd
            for ln in self.lanes:
                a = (addr >> (ln.idx * (AW + 1))) & mask_rd
                ln.pend_rd = ln.mem[(a >> AW) & 1][a & 511]
            # --- arrivals and commit drive
            cmt = 0
            cs = ct = cl = cb = 0
            for ln in self.lanes:
                while ln.incoming and ln.incoming[0][0] <= self.t:
                    _, seq, ft, pl = ln.incoming.pop(0)
                    ln.arrive(seq, ft, pl)
                if ln.to_present and ln.q:
                    h = ln.head()
                    ln.c = (h["seq"], h["type"], len(h["payload"]) - 1, h["bank"])
                    ln.to_present = False
                    ln.commits += 1
                    cmt |= 1 << ln.idx
                cs |= ln.c[0] << (16 * ln.idx)
                ct |= ln.c[1] << (8 * ln.idx)
                cl |= ln.c[2] << (8 * ln.idx)
                cb |= ln.c[3] << ln.idx
            d.commit.value = cmt
            d.c_seq.value = cs
            d.c_type.value = ct
            d.c_len.value = cl
            d.c_bank.value = cb
            if until_idle and self.idle() and self.t > 50:
                break
        # one more await so no write is pending at test end
        await FallingEdge(d.clk)

    def idle(self):
        return (all(not ln.q and not ln.incoming for ln in self.lanes) and self.cur is None
                and not int(self.dut.out_valid.value))

    def take(self, snap):
        data, first, last, seq, ftype, ln_ = snap
        if first:
            if self.cur is not None:
                self.err.append("out_first inside a frame")
            self.cur = dict(seq=seq, type=ftype, len=ln_, data=bytearray())
        elif self.cur is None:
            self.err.append("byte outside a frame")
            return
        c = self.cur
        if (seq, ftype, ln_) != (c["seq"], c["type"], c["len"]):
            self.err.append("meta changed within frame")
        c["data"].append(data)
        if last:
            if len(c["data"]) != c["len"] + 1:
                self.err.append("out_last with %d bytes, len field %d" % (len(c["data"]), c["len"]))
            self.out_frames.append((c["seq"], c["type"], bytes(c["data"])))
            self.cur = None
        elif len(c["data"]) > c["len"] + 1:
            self.err.append("too many bytes")


async def start(dut, ready_p=1.0, seed=1):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.commit.value = 0
    for s in (dut.c_seq, dut.c_type, dut.c_len, dut.c_bank, dut.rd_data):
        s.value = 0
    dut.out_ready.value = 0
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)
    return Env(dut, ready_p, seed)


def mk_payload(rng, seq, n=None):
    n = n or rng.choice([1, 2, 5, 17, 40, 64])
    return bytes(rng.randrange(256) for _ in range(n))


def counters(dut):
    return int(dut.merged_ok.value), int(dut.frames_lost.value), int(dut.dups.value)


def check_against_ref(dut, env):
    assert not env.err, env.err[:5]
    assert env.out_frames == env.ref.out, (len(env.out_frames), len(env.ref.out))
    ok, lost, dups = counters(dut)
    assert (ok, lost, dups) == (len(env.ref.out), env.ref.lost & 0xFFFF, env.ref.dups), (
        (ok, lost, dups), (len(env.ref.out), env.ref.lost, env.ref.dups))
    # every commit was served exactly once
    assert len(env.rel_log) == sum(ln.commits for ln in env.lanes)
    assert all(not ln.q for ln in env.lanes)


def build_cfg(rng, skews):
    """Lane configuration: lane 0 lossy (1 %), lane 1 dead, lane 2 clean, others clean."""
    cfg = []
    for i in range(N):
        cfg.append(dict(skew=skews[i % len(skews)] if i < len(skews) else rng.randrange(0, 2001),
                        loss=0.01 if (i == 0 and N >= 2) else 0.0, dead=(i == 1 and N >= 3)))
    return cfg


async def run_stream(dut, env, cfg, n_frames, period, seq0=0, nmax=None):
    rng = random.Random(1234)
    frames = []
    # lossy lanes drop exactly 1 % of the frames (at least 2), at random positions
    drops = {i: set(rng.sample(range(n_frames), max(2, n_frames // 100)))
             for i, c in enumerate(cfg) if c["loss"] > 0}
    for k in range(n_frames):
        seq = (seq0 + k) & 0xFFFF
        p = mk_payload(rng, seq)
        ft = k & 255
        frames.append((seq, ft, p))
        for i, c in enumerate(cfg):
            if c["dead"]:
                continue
            if k in drops.get(i, ()):
                continue
            env.schedule(i, 100 + k * period + c["skew"], seq, ft, p)
    for ln in env.lanes:
        ln.incoming.sort(key=lambda x: x[0])
    await env.run(100 + n_frames * period + max(c["skew"] for c in cfg) + 3000)
    return frames


@cocotb.test()
async def skew_within_period(dut):
    """Skews below one frame period: every frame exactly once, in order, from a lossy + dead + clean set."""
    env = await start(dut, ready_p=0.6, seed=2)
    rng = random.Random(5)
    cfg = build_cfg(rng, [0, 100, 300])
    for c in cfg:
        c["skew"] = min(c["skew"], 400)
    n = 150 if N < 14 else 60
    frames = await run_stream(dut, env, cfg, n, period=700)
    check_against_ref(dut, env)
    assert [s for s, _, _ in env.ref.out] == [s for s, _, _ in frames]       # all, once, ordered
    assert env.out_frames == frames
    assert env.ref.lost == 0
    for ln in env.lanes:
        assert ln.lane_overruns == 0
    dut._log.info("N=%d skew_within_period: out=%d dups=%d lost=%d", N, len(env.out_frames), env.ref.dups, env.ref.lost)
    await FallingEdge(dut.clk)


@cocotb.test()
async def skew_large(dut):
    """Skews 0..2000 cycles (several frame periods): policy replay, ordering, loss accounting."""
    env = await start(dut, ready_p=0.5, seed=3)
    rng = random.Random(9)
    cfg = build_cfg(rng, [0, 700, 2000])
    n = 150 if N < 14 else 60
    frames = await run_stream(dut, env, cfg, n, period=700)
    check_against_ref(dut, env)
    seqs = [s for s, _, _ in env.out_frames]
    assert seqs == sorted(set(seqs)), "output not strictly increasing"
    byseq = {s: (t, p) for s, t, p in frames}
    for s, t, p in env.out_frames:
        assert byseq[s] == (t, p)
    missing = [s for s, _, _ in frames if s not in set(seqs) and seqs[0] < s < seqs[-1]]
    assert len(missing) == env.ref.lost == int(dut.frames_lost.value), (len(missing), env.ref.lost)
    if N == 3:
        assert env.ref.lost >= 1, "the lossy lane should have cost at least one frame"
    commits = sum(ln.commits for ln in env.lanes)
    assert commits == len(env.out_frames) + env.ref.dups
    dut._log.info("N=%d skew_large: out=%d dups=%d lost=%d", N, len(env.out_frames), env.ref.dups, env.ref.lost)
    await FallingEdge(dut.clk)


@cocotb.test()
async def seq_wrap(dut):
    env = await start(dut, ready_p=0.7, seed=4)
    rng = random.Random(6)
    cfg = build_cfg(rng, [0, 50, 200])
    for c in cfg:
        c["loss"] = 0.0
        c["skew"] = min(c["skew"], 300)
    frames = await run_stream(dut, env, cfg, 40, period=500, seq0=0xFFF0)
    check_against_ref(dut, env)
    assert [s for s, _, _ in env.out_frames] == [(0xFFF0 + k) & 0xFFFF for k in range(40)]
    assert env.out_frames == frames
    assert env.ref.lost == 0 and int(dut.frames_lost.value) == 0
    await FallingEdge(dut.clk)


@cocotb.test()
async def directed_policy(dut):
    """First frame sets seq_next without loss; gaps; duplicates; extremes of ahead/behind."""
    env = await start(dut, ready_p=1.0, seed=7)
    rng = random.Random(1)
    seqs = [0x1000, 0x1001, 0x1001, 0x1000, 0x1005, 0x1006, 0x1005, 0x9005, 0x9004, 0x9006, 0x9006,
            0xFFFF, 0x0000, 0x0000, 0x0003, 0x0002]
    t = 30
    for i, s in enumerate(seqs):
        env.schedule(i % N, t, s, i & 255, mk_payload(rng, s))
        t += 400
    await env.run(t + 2000)
    check_against_ref(dut, env)
    assert [s for s, _, _ in env.out_frames] == [0x1000, 0x1001, 0x1005, 0x1006, 0x9005, 0x9006, 0xFFFF, 0x0000, 0x0003]
    # lost = 3 (0x1002..0x1004) + 0x7FFF (0x1007..0x9004... gap to 0x9005) + gaps to 0xFFFF and 0x0003
    exp_lost = 3 + (0x9005 - 0x1007) + (0xFFFF - 0x9007) + 2
    assert env.ref.lost == exp_lost == int(dut.frames_lost.value), (env.ref.lost, exp_lost)
    assert int(dut.dups.value) == len(seqs) - 9
    await FallingEdge(dut.clk)


@cocotb.test()
async def round_robin(dut):
    """Simultaneous commits on all lanes: served in round-robin order starting after the lane served last."""
    env = await start(dut, ready_p=1.0, seed=8)
    if N < 2:
        await FallingEdge(dut.clk)
        return
    rng = random.Random(2)
    for rnd in range(N + 2):
        for i in range(N):
            env.schedule(i, 40 + rnd * 1500, rnd, rnd, mk_payload(rng, rnd, 10))
    await env.run(40 + (N + 2) * 1500 + 500)
    check_against_ref(dut, env)
    order = [l for l, _ in env.rel_log]
    # all lanes commit in the same cycle; round r is served starting at lane r mod N after the
    # lane served first in round r-1 is followed by the rest (rr = lane served last + 1)
    exp = []
    rr = 0
    for rnd in range(N + 2):
        exp.append(rr)
        # the first lane served (outputs, nothing else) is rr; the others are duplicates in rr+1..
        seq_ = [(rr + k) % N for k in range(N)]
        exp.extend(seq_[1:])
        rr = (seq_[-1] + 1) % N
    # rr after a dup is the lane after it, so the next round starts after the last served lane
    assert order == exp, (order[:12], exp[:12])
    assert len(env.out_frames) == N + 2 and env.ref.dups == (N + 2) * (N - 1)
    await FallingEdge(dut.clk)


@cocotb.test()
async def stall_never_drops(dut):
    """Long ready stalls (ready low for tens of cycles at a time) never lose or alter a frame."""
    env = await start(dut, ready_p=0.04, seed=10)
    rng = random.Random(3)
    for i in range(6):
        env.schedule(i % N, 20 + i * 1100, i, i, mk_payload(rng, i, 40))
    await env.run(30000)
    check_against_ref(dut, env)
    assert [s for s, _, _ in env.out_frames] == [0, 1, 2, 3, 4, 5]
    assert all(ln.lane_overruns == 0 for ln in env.lanes)
    await FallingEdge(dut.clk)
