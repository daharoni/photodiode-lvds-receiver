"""lane_monitor (README section 5/7, section 9 row 5), WINDOW_CYCLES = 400
(overridden in the Makefile).  Class thresholds are taken from the README
text, not from the RTL: 0 none; 1 = 1-2; 2 = 3-8; 3 = 9-32; 4 = 33-128;
5 = >128; 7 = LOS or no lock at any time in the window.
Not covered here: the 16-bit saturation (needs a >65535-cycle window).
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

W = 400


def class_of(n):
    if n == 0:
        return 0
    if n <= 2:
        return 1
    if n <= 8:
        return 2
    if n <= 32:
        return 3
    if n <= 128:
        return 4
    return 5


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.lock.value = 1
    dut.err_pulse.value = 0
    dut.los.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    # rst deasserts now; the next edge is cycle 0 of window 0
    dut.rst.value = 0


async def run_windows(dut, windows):
    """windows: list of dicts(errs=set of cycle idx, nolock=set, los=set).
    Returns (per-window (tick, nibble, count), tick cycle indices)."""
    reads = []
    cycles = []
    for wd in windows:
        for c in range(W):
            cycles.append((int(c in wd.get("errs", ())), int(c not in wd.get("nolock", ())),
                           int(c in wd.get("los", ()))))
    cycles.append((0, 1, 0))                       # one more clock to read the last window
    for e, lk, ls in cycles:
        dut.err_pulse.value = e
        dut.lock.value = lk
        dut.los.value = ls
        await RisingEdge(dut.clk)                  # reads lag the inputs by one edge
        reads.append((int(dut.window_tick.value), int(dut.nibble.value),
                      int(dut.err_count_last.value)))
    ticks = [i for i, r in enumerate(reads) if r[0]]
    res = [reads[(i + 1) * W] for i in range(len(windows))]
    return res, ticks


@cocotb.test()
async def reset_state_not_valid(dut):
    await reset(dut)
    await RisingEdge(dut.clk)
    assert int(dut.nibble.value) == 0b0111, "fresh module must not report a good link"


@cocotb.test()
async def class_boundaries(dut):
    """0,1,2,3,8,9,32,33,128,129 (and 300) errors: class from the README thresholds."""
    await reset(dut)
    counts = [0, 1, 2, 3, 8, 9, 32, 33, 128, 129, 300, 1, 0]
    wins = [dict(errs=set(range(0, 2 * n, 2)) if n <= 200 else set(range(n))) for n in counts]
    res, ticks = await run_windows(dut, wins)
    assert [t for t in ticks] == [W * (i + 1) for i in range(len(wins))], f"tick cadence {ticks[:5]}"
    for n, (tick, nib, cnt) in zip(counts, res):
        assert tick == 1
        assert nib == (1 << 3) | class_of(n), f"{n} errors: nibble {nib:04b}, expected valid + class {class_of(n)}"
        assert cnt == n, f"err_count_last {cnt} != {n}"


@cocotb.test()
async def err_on_window_edges(dut):
    """An error on the last clock of a window belongs to it; one on the first clock to the next."""
    await reset(dut)
    wins = [dict(errs={W - 1}), dict(errs={0, 1, 2}), dict(), dict(errs={0})]
    res, _ = await run_windows(dut, wins)
    # window 0 has 1 error (cycle W-1) -> class 1; window 1 has 3 -> class 2;
    # window 2 none -> 0; window 3 one error -> class 1
    assert [r[2] for r in res] == [1, 3, 0, 1]
    assert [r[1] for r in res] == [0b1001, 0b1010, 0b1000, 0b1001]


@cocotb.test()
async def lock_loss_any_cycle_is_class7_invalid(dut):
    """lock low for one clock at the first / middle / last clock: valid = 0, class 7;
    the next clean window is valid again."""
    await reset(dut)
    wins = []
    for c in (0, 17, W // 2, W - 2, W - 1):
        wins.append(dict(nolock={c}, errs={5}))
        wins.append(dict())
    res, _ = await run_windows(dut, wins)
    for i, r in enumerate(res):
        if i % 2 == 0:
            assert r[1] == 0b0111, f"window {i}: nibble {r[1]:04b} (lock lost once)"
        else:
            assert r[1] == 0b1000, f"window {i}: nibble {r[1]:04b} (clean after lock loss)"


@cocotb.test()
async def los_any_cycle_is_class7_but_valid_follows_lock(dut):
    """los high at one clock anywhere in the window: class 7; valid stays 1 when lock held."""
    await reset(dut)
    wins = []
    for c in (0, 100, W - 1):
        wins.append(dict(los={c}))
        wins.append(dict(errs={1}))
    res, _ = await run_windows(dut, wins)
    for i, r in enumerate(res):
        if i % 2 == 0:
            assert r[1] == 0b1111, f"window {i}: nibble {r[1]:04b} (LOS, lock held)"
        else:
            assert r[1] == 0b1001, f"window {i}: nibble {r[1]:04b} (recovered)"


@cocotb.test()
async def no_lock_whole_window(dut):
    """Lock low for the whole window with errors: class 7, invalid, count still reported."""
    await reset(dut)
    res, _ = await run_windows(dut, [dict(nolock=set(range(W)), errs=set(range(10))), dict()])
    assert res[0][1] == 0b0111
    assert res[0][2] == 10
    assert res[1][1] == 0b1000
