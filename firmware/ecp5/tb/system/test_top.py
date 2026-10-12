"""ulx3s_top smoke test (rtl/ulx3s_top.v with the clocks.v simulation PLL model, LOOPBACK_INTERNAL=1):
lane 0 locks from the internal tx_bit loopback, frames merge without loss, and a FIRE2 press moves the
FTDI pin to host mode where CRC-valid host_sink_uart frames appear at 3 Mbaud.  Run with
`make -f Makefile.top` in this directory (not part of `make test`; the end-to-end data-path test is
tb/system's test_system.py).  The 0x5A scan skips the frame the sink was part-way through at the switch.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, FallingEdge, RisingEdge

@cocotb.test()
async def top_loopback(dut):
    cocotb.start_soon(Clock(dut.clk_25mhz, 40, unit="ns").start())
    dut.btn.value = 0
    dut.lane_p.value = 0
    dut.ftdi_txd.value = 1
    dut.wifi_gpio17.value = 1
    await Timer(200, unit="us")
    dut._log.info("led=%s locked=%s", dut.led.value, (int(dut.led.value) >> 6) & 1)
    dut._log.info("lock lane0 (led0)=%s merged_ok=%d lost=%d dups=%d", (int(dut.led.value) & 1), int(dut.u_core.merged_ok.value), int(dut.u_core.frames_lost.value), int(dut.u_core.dups.value))
    assert int(dut.led.value) & 1
    assert int(dut.u_core.merged_ok.value) > 5
    assert int(dut.u_core.frames_lost.value) == 0
    # host mode: press FIRE2
    dut.btn.value = 4
    await Timer(5, unit="us")
    dut.btn.value = 0
    # watch ftdi_rxd for a falling edge (start bit) and decode first bytes at 3 Mbaud
    got = []
    for _ in range(40000):
        await Timer(10, unit="ns")
        pass
    dut._log.info("host_mode=%s", dut.host_mode.value)
    assert int(dut.host_mode.value) == 1
    # sample ftdi_rxd every 10 ns for 300 us, decode bytes
    samples = []
    for _ in range(70000):
        await Timer(10, unit="ns")
        samples.append(int(dut.ftdi_rxd.value))
    bc = 100/3.0
    i = 1; bytes_ = []
    while i < len(samples) - 400:
        if samples[i] == 0 and samples[i-1] == 1:
            t0 = i; b = 0
            for k in range(1, 9):
                b |= samples[int(t0 + (k+0.5)*bc)] << (k-1)
            bytes_.append(b); i = int(t0 + 9.5*bc)
        else:
            i += 1
    dut._log.info("first host bytes: %s", [hex(b) for b in bytes_[:12]])
    def crc16(data, crc=0xFFFF):
        for b in data:
            crc ^= b << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
        return crc
    ok = 0
    for j, b in enumerate(bytes_):
        if b == 0x5A and j + 7 < len(bytes_):
            ln = bytes_[j+4]
            e = j + 5 + ln + 1
            if e + 2 <= len(bytes_) and (bytes_[e] | bytes_[e+1] << 8) == crc16(bytes(bytes_[j+1:e])):
                ok += 1
    dut._log.info("valid host frames decoded on ftdi_rxd: %d of %d bytes", ok, len(bytes_))
    assert ok >= 1
    await Timer(1, unit="us")
