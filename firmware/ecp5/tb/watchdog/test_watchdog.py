"""watchdog (README section 5/9 row 5, standing corrections 11 and 12).
TIMEOUT_CYCLES = 100 clk25 clocks (Makefile override).  clk_c = 100 MHz,
clk25 = 25 MHz with an arbitrary phase offset (a real asynchronous pair).
Stuck-high and stuck-low lines produce no transitions; the test derives
the transition pulses from the line model, never from the RTL.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb.utils import get_sim_time

from model import linesim as L

T = 100             # TIMEOUT_CYCLES (Makefile)
CLK25_NS = 40


async def start(dut, offset_ns=3, rst_ns=400):
    dut.rst_c.value = 1
    dut.rst25.value = 1
    dut.transition_async.value = 0
    cocotb.start_soon(Clock(dut.clk_c, 10, unit="ns").start())
    if offset_ns:
        await Timer(offset_ns, unit="ns")
    cocotb.start_soon(Clock(dut.clk25, CLK25_NS, unit="ns").start())
    await Timer(rst_ns, unit="ns")
    dut.rst_c.value = 0
    dut.rst25.value = 0
    await RisingEdge(dut.clk_c)


class Mon:
    """Records every clk25 edge: time and the los value seen right after it."""
    def __init__(self, dut):
        self.dut = dut
        self.rises = []
        self.falls = []
        self.last = None
        cocotb.start_soon(self.run())

    async def run(self):
        while True:
            await RisingEdge(self.dut.clk25)
            await Timer(1, unit="ns")
            v = int(self.dut.los.value)
            t = get_sim_time("ns")
            if self.last is not None and v != self.last:
                (self.rises if v else self.falls).append(t)
            self.last = v


async def pulse(dut, n=1):
    """n consecutive clk_c clocks of transition_async."""
    await RisingEdge(dut.clk_c)             # always drive just after a clk_c edge
    dut.transition_async.value = 1
    t = get_sim_time("ns")
    for _ in range(n):
        await RisingEdge(dut.clk_c)
    dut.transition_async.value = 0
    return t


async def idle_clk25(dut, n):
    for _ in range(n):
        await RisingEdge(dut.clk25)


@cocotb.test()
async def reset_state_is_los(dut):
    await start(dut)
    assert int(dut.los.value) == 1 and int(dut.los_sync.value) == 1


@cocotb.test()
@cocotb.parametrize(offset=[0, 3, 7, 11, 17, 23, 31, 37])
async def los_after_exactly_timeout_and_release(dut, offset):
    """A single transition clears LOS; with no further transition LOS rises
    TIMEOUT clk25 clocks after the (fixed-latency) detection; the next
    transition releases it again.  Repeated at 8 clock phase offsets."""
    await start(dut, offset_ns=offset)
    mon = Mon(dut)
    t_p = await pulse(dut)
    await idle_clk25(dut, 12)
    assert int(dut.los.value) == 0, "LOS not cleared by a transition"
    await idle_clk25(dut, 2 * T)
    assert len(mon.rises) == 1, mon.rises
    # distance from the transition pulse to the LOS rise, in clk25 clocks
    lat = (mon.rises[0] - t_p) / CLK25_NS
    # detection takes <= 8 clk_c (2 clk25) + 3 clk25 synchroniser/edge stages
    assert T + 1 <= lat <= T + 7, f"LOS rose {lat:.2f} clk25 after the transition (timeout {T})"
    dut._log.info("offset %d: LOS %.2f clk25 after the last transition", offset, lat)
    # los_sync follows within 3 clk_c
    await idle_clk25(dut, 2)
    assert int(dut.los_sync.value) == 1
    # release
    t_r = await pulse(dut)
    await idle_clk25(dut, 10)
    assert int(dut.los.value) == 0, "LOS not released by the next transition"
    assert len(mon.falls) >= 1
    assert (mon.falls[-1] - t_r) / CLK25_NS <= 7
    await idle_clk25(dut, 3)
    assert int(dut.los_sync.value) == 0


@cocotb.test()
async def spacing_just_below_and_above_timeout(dut):
    """Transitions every T-10 clk25 never produce LOS; every T+10 always do."""
    await start(dut)
    mon = Mon(dut)
    await pulse(dut)
    for _ in range(8):
        await idle_clk25(dut, T - 10)
        await pulse(dut)
    await idle_clk25(dut, 5)
    assert not mon.rises, f"false LOS with transitions every {T - 10} clk25"
    for _ in range(4):
        await idle_clk25(dut, T + 10)
        await pulse(dut)
    await idle_clk25(dut, 5)
    assert len(mon.rises) == 4, f"expected 4 LOS events, got {len(mon.rises)}"
    assert len(mon.falls) >= 4


@cocotb.test()
async def dense_transitions_keep_los_low(dut):
    """Edge-every-clock and idle-pattern-like activity at 100 MHz (50 MHz toggle
    aliasing trap): LOS stays low over 5 timeouts."""
    await start(dut)
    mon = Mon(dut)
    await pulse(dut, 3)
    await idle_clk25(dut, 12)
    assert int(dut.los.value) == 0
    # (a) a transition on every clk_c
    dut.transition_async.value = 1
    await idle_clk25(dut, 5 * T)
    dut.transition_async.value = 0
    assert not mon.rises, "LOS with a transition on every clock"
    # (b) the real idle pattern through the model: per-clock edge flags
    bits = L.idle_bits(400)
    words = L.line_samples(bits, start_phase=1)
    samples = L.words_to_samples(words)
    prev = samples[0]
    for i, w in enumerate(words[:3000]):
        s = samples[4 * i:4 * i + 4]
        edge = int(any(a != b for a, b in zip([prev] + s[:3], s)))
        prev = s[3]
        dut.transition_async.value = edge
        await RisingEdge(dut.clk_c)
    dut.transition_async.value = 0
    assert not mon.rises, "LOS during the idle pattern"


@cocotb.test()
@cocotb.parametrize(level=[0, 1])
async def stuck_line_gives_los(dut, level):
    """Standing correction 11: stuck-low and stuck-high comparator outputs make
    no transitions, so LOS asserts after the timeout.  Transition pulses come
    from the model's words (random run-limited data, then a constant level)."""
    await start(dut)
    mon = Mon(dut)
    tx = L.random_runlimited_bits(600, seed=4)
    words = L.line_samples(tx, start_phase=2, ppm=100, jitter_ui=0.1, seed=1)
    words += [0xF if level else 0x0] * 3000
    # make the stuck level continue the last driven level without an edge
    samples = L.words_to_samples(words)
    prev = samples[0]
    last_active = 0
    flags = []
    for i in range(len(words)):
        s = samples[4 * i:4 * i + 4]
        e = int(any(a != b for a, b in zip([prev] + s[:3], s)))
        prev = s[3]
        flags.append(e)
        if e:
            last_active = i
    assert last_active < len(words) - 2900
    for e in flags:
        dut.transition_async.value = e
        await RisingEdge(dut.clk_c)
    dut.transition_async.value = 0
    await idle_clk25(dut, 4)
    assert int(dut.los.value) == 1, "stuck-%s line did not produce LOS" % ("high" if level else "low")
    assert len(mon.rises) == 1
    await idle_clk25(dut, 3)
    assert int(dut.los_sync.value) == 1


@cocotb.test()
async def reset_clears_toggle_state(dut):
    """rst25 alone returns los to 1 and a transition afterwards clears it."""
    await start(dut)
    await pulse(dut)
    await idle_clk25(dut, 12)
    assert int(dut.los.value) == 0
    dut.rst25.value = 1
    await idle_clk25(dut, 3)
    dut.rst25.value = 0
    await idle_clk25(dut, 2)
    assert int(dut.los.value) == 1
    await pulse(dut)
    await idle_clk25(dut, 12)
    assert int(dut.los.value) == 0
