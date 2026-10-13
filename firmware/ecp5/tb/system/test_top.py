"""ulx3s_top smoke tests (rtl/ulx3s_top.v with the clocks.v simulation PLL model, LOOPBACK_INTERNAL=1,
FTDI_DEBOUNCE=100 and ASCII_PERIOD=20000 from Makefile.top).  Run by `make test` (entry
"system top smoke", top-level Makefile) and by `make -f Makefile.top` in this directory.
  button_held_at_reset_is_not_a_press : FIRE2 held while FIRE1 resets, then FIRE1 released: host mode stays off (F4).
  fire2_mid_report_stays_byte_aligned : FIRE2 pressed in the middle of an ASCII character: the mux waits for
                                        the UART to be between characters; the byte stream on ftdi_rxd has no
                                        framing error and no character straddles the switch; the same for the
                                        switch back from host mode (3 Mbaud bytes) (F4).
  top_loopback                        : lane 0 locks from the internal loopback, frames merge without loss,
                                        FIRE2 moves the FTDI pin to host mode where CRC-valid host_sink_uart
                                        frames appear at 3 Mbaud.
The end-to-end data-path test is tb/system's test_system.py.  The 0x5A scan skips the frame the sink was
part-way through at the switch.
"""
import bisect

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Edge, RisingEdge, Timer
from cocotb.utils import get_sim_time

_clock_started = False


async def boot(dut, btn_after_reset=0, btn_during_reset=2):
    """Start the 25 MHz clock once, hold FIRE1 (btn[1]) to reset everything but the PLL, release it."""
    global _clock_started
    if not _clock_started:
        cocotb.start_soon(Clock(dut.clk_25mhz, 40, unit="ns").start())
        _clock_started = True
    dut.lane_p.value = 0
    dut.ftdi_txd.value = 1
    dut.wifi_gpio17.value = 1
    dut.btn.value = btn_during_reset
    await Timer(3, unit="us")
    dut.btn.value = btn_after_reset
    await Timer(1, unit="us")


class Edges:
    """Records ftdi_rxd edges (time ns, level) and decodes 8N1 bytes from them."""
    def __init__(self, dut):
        self.t = [0.0]
        self.v = [1]
        self.dut = dut
        cocotb.start_soon(self._run())

    async def _run(self):
        while True:
            await Edge(self.dut.ftdi_rxd)
            self.t.append(get_sim_time("ns"))
            self.v.append(int(self.dut.ftdi_rxd.value))

    def level(self, t):
        return self.v[bisect.bisect_right(self.t, t) - 1]

    def decode(self, t_from, t_to, bit_ns):
        """-> (bytes [(t_start, value)], framing_errors) for start bits in [t_from, t_to]."""
        out, ferr = [], 0
        k = bisect.bisect_right(self.t, t_from)
        while k < len(self.t):
            if self.v[k] == 0 and self.v[k - 1] == 1:
                t0 = self.t[k]
                if t0 > t_to:
                    break
                b = 0
                for j in range(1, 9):
                    b |= self.level(t0 + (j + 0.5) * bit_ns) << (j - 1)
                if self.level(t0 + 9.5 * bit_ns) != 1:
                    ferr += 1
                out.append((t0, b))
                k = bisect.bisect_right(self.t, t0 + 9.5 * bit_ns)
            else:
                k += 1
        return out, ferr


ASCII_BIT = 1e9 / 115200
HOST_BIT = 1e9 / 3e6


@cocotb.test()
async def button_held_at_reset_is_not_a_press(dut):
    """F4: FIRE2 held down through reset (FIRE1 pressed together, released first) does not toggle host mode."""
    await boot(dut, btn_after_reset=4, btn_during_reset=6)
    await Timer(100, unit="us")                     # debounce is 100 clk_c cycles = 2 us
    assert int(dut.host_mode.value) == 0 and int(dut.want_host.value) == 0, "button held at reset toggled host mode"
    dut.btn.value = 0                               # releasing is not a press either
    await Timer(50, unit="us")
    assert int(dut.host_mode.value) == 0 and int(dut.want_host.value) == 0
    # and a genuine press still works
    dut.btn.value = 4
    await Timer(10, unit="us")
    dut.btn.value = 0
    await Timer(300, unit="us")
    assert int(dut.host_mode.value) == 1, "a real FIRE2 press did not switch to host mode"
    await Timer(1, unit="us")


@cocotb.test()
async def fire2_mid_report_stays_byte_aligned(dut):
    """F4: press FIRE2 while an ASCII report is in flight; then press again while the host sink is sending."""
    await boot(dut)
    ed = Edges(dut)
    sw = []                                         # host_mode changes: (time ns, new value)

    async def watch():
        """Every clk_c edge: values read here are the ones before the edge.  When host_mode changed at
        edge N-1, the decision used the values read at N-1: the UART the pin showed then must have been
        between characters and the pin high."""
        prev = None
        while True:
            await RisingEdge(dut.clk_c)
            cur = (int(dut.host_mode.value), int(dut.ftdi_tx_busy.value), int(dut.host_tx_busy.value),
                   int(dut.ftdi_rxd.value))
            if prev is not None and cur[0] != prev[0]:
                sw.append((get_sim_time("ns"), cur[0]))
                busy_then = prev[2] if prev[0] else prev[1]       # the UART that was on the pin
                assert busy_then == 0 and prev[3] == 1, f"mux switched with the {'host' if prev[0] else 'ASCII'} UART busy (pin {prev[3]})"
            prev = cur
    cocotb.start_soon(watch())
    # wait for the first ASCII character, then let 10 more go by and press in the middle of the next one
    for _ in range(400):
        await Timer(10, unit="us")
        if 0 in ed.v:
            break
    assert 0 in ed.v, "no ASCII report started"
    t_first = ed.t[ed.v.index(0)]                  # first start bit
    t_press = t_first + 10 * 10 * ASCII_BIT + 4.3 * ASCII_BIT       # 4.3 bit times into the 11th character
    await Timer(int(t_press - get_sim_time("ns")), unit="ns")
    dut.btn.value = 4
    await Timer(6, unit="us")
    dut.btn.value = 0
    for _ in range(100):                            # the switch waits for the UART to be between characters
        await Timer(10, unit="us")
        if sw:
            break
    await Timer(50, unit="us")
    assert sw and sw[0][1] == 1, f"host mode not entered: {sw}"
    t_sw1 = sw[0][0]
    chars, ferr = ed.decode(0, t_sw1 - 50, ASCII_BIT)
    text = bytes(b for _, b in chars)
    dut._log.info("ASCII before the switch: %d chars, framing errors %d, text %r", len(chars), ferr, text[:60])
    assert ferr == 0, f"{ferr} framing errors before the switch"
    assert text.startswith(b"LINK seq=0 "), text[:20]
    assert all(0x20 <= b < 0x7F or b in (0x0D, 0x0A) for b in text), f"junk byte in {text!r}"
    for t0, _ in chars:                             # no character straddles the switch
        assert not (t0 < t_sw1 < t0 + 10 * ASCII_BIT), "FTDI mux switched inside a character"
    assert t_sw1 > t_press, "host mode entered before the press"
    dut._log.info("press at %.0f ns, switch at %.0f ns (%.1f bit times later)", t_press, t_sw1, (t_sw1 - t_press) / ASCII_BIT)
    # host frames flowing; press again in the middle of a host byte
    await Timer(200, unit="us")
    dut.btn.value = 4
    await Timer(6, unit="us")
    dut.btn.value = 0
    for _ in range(100):
        await Timer(10, unit="us")
        if len(sw) >= 2:
            break
    await Timer(50, unit="us")
    assert len(sw) >= 2 and sw[1][1] == 0, f"host mode not left: {sw}"
    t_sw2 = sw[1][0]
    # The sink was mid-frame when the pin was switched to it (only the departing UART is waited for), so
    # decode from the first inter-frame idle (line high for >= 3 bit times) after the first switch.
    gaps = [ed.t[k + 1] for k in range(len(ed.t) - 1)
            if ed.v[k] == 1 and ed.t[k] > t_sw1 and ed.t[k + 1] - ed.t[k] >= 3 * HOST_BIT]
    assert gaps, "no inter-frame idle on the host stream"
    hb, hferr = ed.decode(gaps[0] - 1, t_sw2 - 4 * HOST_BIT, HOST_BIT)
    dut._log.info("host bytes decoded from the first idle gap: %d, framing errors %d", len(hb), hferr)
    assert len(hb) > 20 and hferr == 0, f"host bytes {len(hb)}, framing errors {hferr}"
    for t0, _ in hb:
        assert not (t0 < t_sw2 < t0 + 10 * HOST_BIT), "FTDI mux switched inside a host byte"
    # ASCII resumes cleanly after the switch back
    await Timer(4000, unit="us")
    chars, ferr = ed.decode(t_sw2, get_sim_time("ns") - 200000, ASCII_BIT)
    text = bytes(b for _, b in chars)
    dut._log.info("ASCII after the switch back: %d chars, framing errors %d, text %r", len(chars), ferr, text[:40])
    assert len(chars) >= 30 and ferr == 0 and text.startswith(b"LINK seq="), (len(chars), ferr, text[:20])
    await Timer(1, unit="us")


@cocotb.test()
async def top_loopback(dut):
    await boot(dut)
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
