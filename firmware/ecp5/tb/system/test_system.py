"""End-to-end system test, N_LANES = 3 (tb/system/system_top.v wraps receiver_core + frame_tx).

Flow (README section 9, row tb/system):
  1. capture: frame_tx runs after reset; its tx_bit is captured in Python on every tx_strobe.
     The captured stream is decoded with the model and checked against the PRBS-15 continuation.
  2. reset, replay: frame_tx restarts and produces the same stream (checked bit for bit); the
     captured bits go through model/linesim per lane (ppm -300/0/+300, jitter 0.2 UI, different
     start phases, lane skew 0/500/2000 UI by prepending the periodic idle pattern) into the
     lanes as 4-sample words, one per clk_c cycle (50 MHz core clock, 20 ns, samples_valid held high).  Lane 1 is forced to a
     constant level for a stretch in the middle, then restored.
     F1: lane INV_LANE is fed polarity-inverted (every word XOR 0xF) and must auto-correct (lane_rx
     AUTO_INVERT): its pol_inv rises, it contributes frames (frames_ok within 10 % of the frames sent,
     its error count small) and the other lanes stay uninverted.
  3. Python UART receivers decode host_txd (3 Mbaud frames, 16.67 clocks per bit) and esp_txd (1 Mbaud, 0xA5 messages).
All expectations come from the captured/modelled stream, never from the RTL.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer

from model import link8b10b as M
from model import linesim as L

N = 3
TX_LEN = 32
FRAMES_TARGET = 300              # frames sent by frame_tx while enabled (sim length / 2 min budget)
FRAME_CYC = 480                  # clk_c cycles per frame period (48 symbols = 480 bits, 1 bit per cycle at 50 Mbps)
ENABLE_AT = 4000                 # cycles after reset: 4000 UI of idle so every lane locks first (needs ~1500 UI)
ENABLE_END = ENABLE_AT + FRAMES_TARGET * FRAME_CYC
TOTAL = ENABLE_END + 12000       # tail: lane 2 skew (2000 cycles) + sink drain (>= 7000 cycles)
SKEW = [0, 500, 2000]            # UI
PPM = [-300, 0, 300]
PHASE = [0.3, 1.45, 2.6]
JIT = 0.2
KILL_LANE = 1
INV_LANE = 0                     # fed inverted, auto-corrected by lane_rx (F1)
KILL_A = ENABLE_AT + 100 * FRAME_CYC
KILL_B = KILL_A + 40000          # 800 us at 20 ns: > WD timeout (40 us) + 2 monitor windows (400 us)
MON_WINDOW = 10000
STATUS_PERIOD = 15000


# ---------------------------------------------------------------- Python UART receiver
class UartRx:
    def __init__(self, cycles_per_bit):
        self.bc = cycles_per_bit
        self.prev = 1
        self.state = 0           # 0 idle, 1 receiving
        self.t0 = 0
        self.k = 0
        self.byte = 0
        self.bytes = []          # (cycle, value)
        self.frame_errors = 0

    def feed(self, t, level):
        if self.state == 0:
            if level == 0 and self.prev == 1:
                self.state = 1
                self.t0 = t
                self.k = 1
                self.byte = 0
        else:
            while self.state == 1 and t >= self.t0 + (self.k + 0.5) * self.bc:
                if self.k <= 8:
                    self.byte |= level << (self.k - 1)
                    self.k += 1
                else:
                    if level != 1:
                        self.frame_errors += 1
                    self.bytes.append((self.t0, self.byte))
                    self.state = 0
        self.prev = level


def crc8(data, crc=0):
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


# ---------------------------------------------------------------- model-side helpers
def decode_frames(bits):
    """Decode a tx bit stream (starts on a symbol boundary at disparity -) -> frames list of
    (seq, type, payload); asserts clean decoding."""
    rd = -1
    syms = []
    for i in range(0, len(bits) - 9, 10):
        code = sum(b << j for j, b in enumerate(bits[i:i + 10]))
        byte, is_k, rd, cerr, derr = M.decode(code, rd)
        assert not cerr and not derr, f"model decode error at symbol {i // 10}"
        syms.append((byte, is_k))
    frames, cur = [], None
    for s in syms:
        if s == (M.K27_7, True):
            cur = [s]
        elif cur is not None:
            cur.append(s)
            if s == (M.K29_7, True):
                frames.append(M.unpack_frame(cur))
                cur = None
    return frames


def lane_bits(cap, skew):
    """The captured stream delayed by `skew` UI: the periodic idle pattern (continued backwards
    from the stream start) is prepended; an idle continuation is appended so no lane runs dry."""
    prefix = [L.IDLE_PAIR[(-skew + k) % 20] for k in range(skew)]
    tail = [cap[-20 + (k % 20)] for k in range(600)]
    return prefix + list(cap) + tail


# ---------------------------------------------------------------- test
async def reset(dut, cycles=12):
    dut.rst_c.value = 1
    dut.rst25.value = 1
    dut.tx_enable.value = 0
    dut.samples.value = 0
    dut.samples_valid.value = 0
    dut.ascii_enable.value = 0
    for _ in range(cycles):
        await FallingEdge(dut.clk_c)
    dut.rst_c.value = 0
    dut.rst25.value = 0


@cocotb.test()
async def end_to_end(dut):
    cocotb.start_soon(Clock(dut.clk_c, 20, unit="ns").start())
    await Timer(3, unit="ns")                       # clk25 edges not aligned to clk_c
    cocotb.start_soon(Clock(dut.clk25, 40, unit="ns").start())
    await reset(dut)

    # ---------------- phase 1: capture the transmitter stream
    cap = []
    for c in range(TOTAL):
        dut.tx_enable.value = 1 if ENABLE_AT <= c < ENABLE_END else 0
        await FallingEdge(dut.clk_c)
        o = int(dut.obs.value)
        if o & 8:
            cap.append((o >> 2) & 1)
    nsent_cap = int(dut.frames_sent.value)
    dut._log.info("capture: %d cycles, %d bits, frames_sent=%d", TOTAL, len(cap), nsent_cap)
    assert cap[:40] == L.IDLE_PAIR * 2, "stream does not start with idle pairs"
    frames = decode_frames(cap)
    assert len(frames) == nsent_cap == FRAMES_TARGET, f"decoded {len(frames)} frames, frame_tx says {nsent_cap}"
    nf = len(frames)
    prbs = M.prbs15_bytes(0x7FFF, nf * TX_LEN)
    for n, (seq, ftype, payload) in enumerate(frames):
        assert seq == n and ftype == 0 and list(payload) == prbs[n * TX_LEN:(n + 1) * TX_LEN], f"frame {n} is not the PRBS continuation"
    exp = {n: bytes(f[2]) for n, f in enumerate(frames)}
    dbg = [i for i in range(len(cap)-2000, len(cap)) if cap[i] != L.IDLE_PAIR[i % 20]]
    # after the last frame the idle pair (K28.5 D16.2, disparity preserving /I2/) repeats with period 20
    # bits; its disparity flavour is whatever the last frame left (README s.3 says "negative": it is not
    # forced, see the report).
    assert cap[-400:] == [cap[-20 + (k % 20)] for k in range(400)], "capture does not end in periodic idle"

    # ---------------- lane streams
    lanes = []
    for l in range(N):
        bits = lane_bits(cap, SKEW[l])
        w = L.line_samples(bits, ppm=PPM[l], jitter_ui=JIT, start_phase=PHASE[l], seed=100 + l)
        assert len(w) >= TOTAL + 50, f"lane {l}: only {len(w)} words"
        lanes.append(list(w))
    for l in range(N):
        a, b = (KILL_A, KILL_B) if l == KILL_LANE else (0, 0)
        for w in range(a, b):
            lanes[l][w] = 0x0                        # constant low level, no transitions
    lanes[INV_LANE] = [w ^ 0xF for w in lanes[INV_LANE]]    # polarity-inverted lane (8b/10b is complement symmetric)
    dut._log.info("lane streams ready (%d words each)", len(lanes[0]))

    # ---------------- phase 2: reset and replay
    await reset(dut)
    esp = UartRx(50)                                 # 1 Mbaud at 50 MHz
    host = UartRx(50 / 3.0)                          # 3 Mbaud at 50 MHz
    cap2, merged, cur = [], [], None
    lock_log, los_log = [], []
    for c in range(TOTAL):
        v = 0
        for l in range(N):
            v |= lanes[l][c] << (4 * l)
        dut.samples.value = v
        dut.samples_valid.value = (1 << N) - 1
        dut.tx_enable.value = 1 if ENABLE_AT <= c < ENABLE_END else 0
        await FallingEdge(dut.clk_c)
        o = int(dut.obs.value)
        esp.feed(c, o & 1)
        host.feed(c, (o >> 1) & 1)
        if o & 8:
            cap2.append((o >> 2) & 1)
        if o & 0x10:                                  # merged stream byte
            if o & 0x20:
                cur = {"seq": int(dut.mrg_seq.value), "type": int(dut.mrg_type.value),
                       "len": int(dut.mrg_len.value), "data": []}
            cur["data"].append((o >> 8) & 0xFF)
            if o & 0x40:
                merged.append(cur)
                cur = None
        if c % 200 == 0:
            lock_log.append((c, int(dut.lock.value), int(dut.lane_los.value)))
    dut.samples_valid.value = 0
    await FallingEdge(dut.clk_c)

    assert cap2 == cap[:len(cap2)] and len(cap2) >= len(cap) - 2, "frame_tx stream differs after reset"
    host_sent = int(dut.host_sent.value)
    host_drops = int(dut.host_drops.value)
    merged_ok = int(dut.merged_ok.value)
    lost = int(dut.frames_lost.value)
    dups = int(dut.dups.value)
    # F1: the inverted lane was corrected by lane_rx and delivered frames on its own
    lane_scope = dut.u_core.g_lane[INV_LANE]
    inv_ok = int(lane_scope.u_frx.frames_ok.value)
    inv_fe = int(lane_scope.u_frx.frame_err.value)
    pol = int(dut.u_core.pol_inv.value)
    dut._log.info("inverted lane %d: pol_inv vector %s, frames_ok=%d (of %d), frame_err=%d", INV_LANE, bin(pol), inv_ok, nf, inv_fe)
    assert pol == 1 << INV_LANE, f"pol_inv {pol:0{N}b}: only lane {INV_LANE} should be inverted"
    assert inv_ok >= 0.9 * nf, f"inverted lane delivered only {inv_ok} of {nf} frames"
    assert inv_fe <= 3, f"inverted lane frame_err={inv_fe}"
    dut._log.info("counters: frames=%d merged_ok=%d lost=%d dups=%d host_sent=%d host_drops=%d",
                  nf, merged_ok, lost, dups, host_sent, host_drops)

    # ---------------- merged stream: every frame exactly once, in order, payload == PRBS
    seqs = [m["seq"] for m in merged]
    assert seqs == list(range(nf)), f"merged seqs not each frame exactly once in order (got {len(seqs)}; first mismatch " \
        f"{next((i for i, (a, b) in enumerate(zip(seqs, range(nf))) if a != b), None)})"
    for m in merged:
        assert m["len"] == TX_LEN - 1 and bytes(m["data"]) == exp[m["seq"]], f"merged frame {m['seq']} payload differs"
    assert merged_ok == nf and lost == 0, f"merged_ok={merged_ok} lost={lost}"
    assert dups >= nf - 10, f"dups={dups}: lane 2 (2000 UI skew) should have produced about one dup per frame"

    # ---------------- host stream (3 Mbaud): frames equal the PRBS continuation; drops accounted
    assert host.frame_errors == 0, f"{host.frame_errors} UART framing errors on host_txd"
    hb = [b for _, b in host.bytes]
    hframes, i = [], 0
    while i < len(hb):
        assert hb[i] == 0x5A, f"host byte {i} is 0x{hb[i]:02X}, not the 0x5A start"
        seq = hb[i + 1] | (hb[i + 2] << 8)
        ftype, ln = hb[i + 3], hb[i + 4]
        pl = bytes(hb[i + 5:i + 5 + ln + 1])
        crc = hb[i + 5 + ln + 1] | (hb[i + 6 + ln + 1] << 8)
        assert len(pl) == ln + 1 and i + 7 + ln + 1 <= len(hb), "truncated host frame"
        assert crc == M.crc16_ccitt_false(bytes(hb[i + 1:i + 5 + ln + 1])), f"host frame seq {seq} CRC mismatch"
        hframes.append((seq, ftype, pl))
        i += 7 + ln + 1
    for seq, ftype, pl in hframes:
        assert pl == exp[seq], f"host frame {seq} payload is not the PRBS continuation"
    hs = [h[0] for h in hframes]
    assert hs == sorted(set(hs)), "host frames not strictly increasing"
    assert len(hframes) == host_sent, f"python saw {len(hframes)} host frames, host_sent={host_sent}"
    assert host_sent + host_drops == merged_ok, f"host_sent {host_sent} + host_drops {host_drops} != merged_ok {merged_ok}"
    assert host_sent >= 5, "too few host frames to check"
    dut._log.info("host: %d frames received, %d dropped while the UART was busy (sink is 3 Mbaud vs 50 Mbps line)", host_sent, host_drops)

    # ---------------- status messages
    assert esp.frame_errors == 0
    eb = esp.bytes
    msgs, j = [], 0
    while j + 10 <= len(eb):
        assert eb[j][1] == 0xA5, f"status byte {j} is 0x{eb[j][1]:02X}"
        body = [b for _, b in eb[j + 1:j + 9]]
        assert eb[j + 9][1] == crc8(body), f"status crc8 mismatch in message at cycle {eb[j][0]}"
        msgs.append({"t": eb[j][0], "seq": body[0], "nib": body[1:]})
        j += 10
    assert j == len(eb) or len(eb) - j < 10
    assert len(msgs) >= TOTAL // STATUS_PERIOD - 2, f"only {len(msgs)} status messages"
    for a, b in zip(msgs, msgs[1:]):
        assert b["seq"] == (a["seq"] + 1) & 0xFF, "status seq not consecutive"
    def lane_nib(m, l):
        v = m["nib"][l // 2]
        return (v >> 4) & 0xF if l & 1 else v & 0xF
    for m in msgs:
        for l in range(N, 14):
            assert lane_nib(m, l) == 0x7, f"lane {l} (absent) should report LOS 7"
    series = {l: [(m["t"], lane_nib(m, l)) for m in msgs] for l in range(N)}
    for l in range(N):
        dut._log.info("lane %d nibbles: %s", l, " ".join("%X" % n for _, n in series[l]))
    assert all(lane_nib(msgs[0], l) == 0x7 for l in range(N)), "first message before any window closed must be 0x7"
    pre = [m for m in msgs if ENABLE_AT + 12000 <= m["t"] < KILL_A]
    assert pre, "no status message between lock and the kill"
    for m in pre:
        for l in range(N):
            assert lane_nib(m, l) & 0x8, f"lane {l} not valid before the kill at cycle {m['t']}"
    during = [m for m in msgs if KILL_A + MON_WINDOW * 2 + 1000 <= m["t"] < KILL_B]
    assert during, "no status message inside the kill window"
    for m in during:
        assert lane_nib(m, KILL_LANE) == 0x7, f"killed lane nibble {lane_nib(m, KILL_LANE):X} at cycle {m['t']}"
        for l in range(N):
            if l != KILL_LANE:
                assert lane_nib(m, l) & 0x8, f"healthy lane {l} not valid during the kill"
    post = [m for m in msgs if m["t"] >= KILL_B + 3 * MON_WINDOW and m["t"] < ENABLE_END]
    assert post, "no status message after the restore"
    assert lane_nib(post[-1], KILL_LANE) & 0x8, "killed lane did not relock after restore"
    dut._log.info("kill lane %d: nibble 7 inside the kill window, valid again at cycle %d (restored at %d)",
                  KILL_LANE, next(m["t"] for m in post if lane_nib(m, KILL_LANE) & 8), KILL_B)
    # LOS/lock observed directly
    k_los = [(c, lk, ls) for c, lk, ls in lock_log if KILL_A + 12000 < c < KILL_B]
    assert all((ls >> KILL_LANE) & 1 and not (lk >> KILL_LANE) & 1 for _, lk, ls in k_los), "lane 1 LOS/lock wrong during the kill"
    c_end = [(c, lk, ls) for c, lk, ls in lock_log if c > KILL_B + 20000 and c < ENABLE_END]
    assert all((lk >> KILL_LANE) & 1 and not (ls >> KILL_LANE) & 1 for _, lk, ls in c_end), "lane 1 not locked after restore"
    await FallingEdge(dut.clk_c)
