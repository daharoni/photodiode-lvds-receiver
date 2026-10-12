"""Loopback of uart_tx into uart_rx at BAUD (env var) with a 50 MHz clock (20 ns, the core clock; 3 Mbaud is 16.67 clocks per bit) (cocotb 2.1)."""
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, FallingEdge

BAUD = int(os.environ.get("BAUD", "1000000"))
BIT_NS = 1e9 / BAUD


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.rst.value = 1
    dut.tx_valid.value = 0
    dut.tx_data.value = 0
    dut.force_low.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def send(dut, byte):
    await Timer(1, unit="ns")   # let registered outputs settle after the previous edge
    while int(dut.tx_ready.value) == 0:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
    dut.tx_data.value = byte
    dut.tx_valid.value = 1
    await RisingEdge(dut.clk)
    dut.tx_valid.value = 0


async def collect(dut, out, errs):
    while True:
        await RisingEdge(dut.clk)
        if int(dut.rx_valid.value):
            out.append(int(dut.rx_data.value))
            errs.append(int(dut.rx_frame_err.value))


@cocotb.test()
async def all_bytes_back_to_back(dut):
    """All 256 byte values back to back; every byte received once, in order, no frame errors."""
    await setup(dut)
    got, errs = [], []
    cocotb.start_soon(collect(dut, got, errs))
    for b in range(256):
        await send(dut, b)
    await Timer(int(12 * BIT_NS), unit="ns")
    assert got == list(range(256)), f"mismatch, first diffs: {[(i, g) for i, g in enumerate(got) if i != g][:5]}, n={len(got)}"
    assert not any(errs)


@cocotb.test()
async def random_with_gaps(dut):
    """Random bytes with random idle gaps."""
    await setup(dut)
    got, errs = [], []
    cocotb.start_soon(collect(dut, got, errs))
    rng = random.Random(1)
    sent = []
    for _ in range(100):
        b = rng.randrange(256)
        sent.append(b)
        await send(dut, b)
        await Timer(int(rng.uniform(0, 30) * BIT_NS), unit="ns")
    await Timer(int(12 * BIT_NS), unit="ns")
    assert got == sent


@cocotb.test()
async def bit_period(dut):
    """The start-to-stop frame lasts 10 bit periods within 1 clock (20 ns) of ideal."""
    await setup(dut)
    await send(dut, 0x00)
    await FallingEdge(dut.txd)
    t0 = cocotb.utils.get_sim_time("ns")
    await RisingEdge(dut.txd)   # stop bit begins after 9 bit times (all zeros)
    t1 = cocotb.utils.get_sim_time("ns")
    assert abs((t1 - t0) - 9 * BIT_NS) <= 20.0, f"9 bits took {t1 - t0} ns, ideal {9 * BIT_NS}"


@cocotb.test()
async def framing_error(dut):
    """A line held low through the stop bit flags frame_err."""
    await setup(dut)
    got, errs = [], []
    cocotb.start_soon(collect(dut, got, errs))
    dut.force_low.value = 1
    await Timer(int(12 * BIT_NS), unit="ns")
    dut.force_low.value = 0
    await Timer(int(4 * BIT_NS), unit="ns")
    assert got == [0] and errs == [1], (got, errs)
