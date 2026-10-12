# ECP5 gateware (ULX3S first)

Labels: VERIFIED (checked against a cited document or a passing test in this repo), PROPOSED (design intent), UNRESOLVED (open). Written 2026-10-12. Status: **complete v0 design in simulation; nothing has run on an FPGA.** All blocks exist, are integrated in `receiver_core.v`/`ulx3s_top.v`, and pass 239 cocotb tests in 17 directories including an end-to-end system test (transmitter -> jittered line model with +/-300 ppm and 2000 UI lane skew -> 3 lanes -> merge -> host sink and status messages, with a dead-lane LOS event). `make bit` passes timing on 85k and 12k (clk_s 200 MHz required, clk_c 50 MHz required; see section 0 for the numbers) and nextpnr writes `PIOA.BASE_TYPE INPUT_LVDS` and `PIOA.DIFFRESISTOR 100` for all 7 lane pads (whether the silicon terminates is unverified). The 8b/10b tables match the orchestrator's independently recalled clause 36 entries for all 256 data codes and K28.5 in both disparities (spot check, not a reading of the clause 36 text). The first design ran the core at 100 MHz and missed timing (38 MHz); the core now runs at 50 MHz, one 4-sample word per cycle, with the CDR and the merge pipelined (2026-10-12).

Authority: `docs/architecture.md` (signal-chain item 10, state table), `docs/decision-log.md` (decision 3, standing corrections 11 and 12), `docs/requirements.md` (rows 1, 4, 5), `docs/firmware/can-and-console-protocol.md` (s.1.5 LINK_ALL), `docs/research/ulx3s-lvds-input.md`, `firmware/esp32/README.md` s.10 (CAN master on the ULX3S ESP32).

## 0. What the FPGA does, and does not do

Does (PROPOSED): for each receiver module lane, recover the bit clock from the 50 Mbps LVDS stream by oversampling (no clock is sent), align to the 8b/10b comma, decode 8b/10b, parse frames, check the CRC, count invalid codes; merge the lanes into one frame stream by sequence number; report per-lane link status to the CAN master (the ULX3S's own ESP32, over a UART) in exactly the nibble format of LINK_ALL; supervise every lane with a watchdog on the independent 25 MHz oscillator clock (standing correction 12); provide a test-pattern transmitter so a lane can be looped back or an LED driven for the G1 optical tests.

Does not: any analog slicing (hard rule 1), the CAN protocol itself (the ESP32 on the ULX3S is the master, README s.10), the host link to a computer (UNRESOLVED, decision 14; a generic frame-stream port is provided, v0 sinks it to the FTDI UART).

Build results (2026-10-12, nextpnr-ecp5 0.11.1, Yosys 0.69, speed grade 6, N_LANES = 7, rerun by the orchestrator; VERIFIED as tool output, nothing measured on silicon):

| | LFE5U-85F | LFE5U-12F |
|---|---|---|
| clk_c 50 MHz core, achieved | 73.5 MHz | 74.1 MHz |
| clk_s 200 MHz sampling, achieved | 776 MHz | 682 MHz |
| clk25 watchdog, achieved | 167 MHz | 198 MHz |
| LUT4 | 9,813 (11 %) | 9,813 (40 %) |
| flip-flops | 5,195 | 5,195 (21 %) |
| DP16KD block RAM | 8 (7 lane frame buffers + host FIFO) | 8 of 56 |
| MULT18X18D | 0 | 0 |
| bitstream | 448,564 B | 265,826 B |

The clk_c critical path is now comma_align's history counter into the decoder's symbol register (about 13.6 of 20 ns).

## 1. Toolchain and layout

Open-source flow only: Yosys, nextpnr-ecp5, prjtrellis, openFPGALoader (or fujprog), Icarus Verilog + cocotb for simulation, Verilator for lint. All come from the YosysHQ OSS CAD Suite: `source tools/fpga-env.sh` from the repo root (installed in `~/opt/oss-cad-suite`, release 2026-10-12; CI installs the same suite). Versions seen 2026-10-12: Yosys 0.69, nextpnr 0.11.1, Verilator 5.053, Icarus 14.0, cocotb 2.1.

```
firmware/ecp5/
  README.md            this file (spec)
  Makefile             lint / test / synth / pnr / pack / prog / timing
  rtl/                 synthesisable Verilog-2005 (no SystemVerilog, so Icarus and Yosys agree)
    ulx3s_top.v        board top level
    clocks.v           EHXPLLL wrapper: 25 MHz -> 200 MHz sample (CLKOP), 50 MHz core (CLKOS, CLKOS_DIV 12, VCO 600 MHz)
    lane_phy.v         ECP5-specific LVDS capture: differential input, 200 MHz sampling, one non-overlapping 4-sample word per 50 MHz cycle
    cdr_oversample.v   4x blind-oversampling CDR, pure logic, 4-bit sample word in, 0-2 bits out per cycle
    comma_align.v      10-bit symbol alignment on K28.5
    dec_8b10b.v        8b/10b decoder with running disparity and error flags
    enc_8b10b.v        8b/10b encoder (test pattern transmitter and headstage reference)
    lane_rx.v          cdr + align + decode + lock/error counters for one lane (phy-agnostic)
    lane_monitor.v     100 ms error-class window, LOS, LINK_ALL nibble
    watchdog.v         per-lane activity watchdog on the 25 MHz clock
    frame_rx.v         frame parser + CRC-16 check, per-lane frame buffer
    lane_merge.v       sequence-number merge of N lanes into one frame stream
    frame_tx.v         test-pattern frame generator + serialiser (50 Mbps)
    crc16.v            CRC-16/CCITT-FALSE, byte-wise
    prbs.v             PRBS-15 generator (the testbenches check against the model)
    crc8.v             CRC-8 poly 0x07 for the status message
    uart_tx.v, uart_rx.v
    status_uart.v      20 Hz binary link-status frames to the ESP32; 1 Hz ASCII status to the FTDI UART
    host_sink_uart.v   v0 host port: frame stream to the FTDI UART with a drop counter
  constraints/ulx3s.lpf   only the pins used, each cited to ulx3s_v20.lpf (emard/ulx3s) and the v3.1.7 schematic
  model/               Python golden model (8b/10b tables, CRC, frame pack/unpack, line serialiser with jitter and ppm offset)
  tb/                  cocotb tests, one directory per block, plus tb/system (end-to-end)
  tools/               helper scripts (status monitor over the FTDI UART, bitstream info)
```

Verilog rules for subagents: one module per file, file name = module name; `default_nettype none`; synchronous active-high resets; no latches; no `initial` for synthesised state except memories; every parameter documented at the top of the file; no vendor primitives outside `clocks.v` and `lane_phy.v`; all other RTL must simulate in Icarus with no ECP5 library.

## 2. Board facts (ULX3S v3.1.x, LFE5U-xxF-6BG381C)

| Item | Value | Label / source |
|---|---|---|
| Oscillator | 25 MHz on ball G2 | VERIFIED: ulx3s_v20.lpf line 6 |
| LVDS-capable header pairs | gp/gn[8..13] bank 7 (A4/A5, A2/B1, C4/B4, F4/E3, G3/F3, H4/G5); gp/gn[14..21] banks 2/3 (U18/U17, N17/P16, N16/M17, L16/L17, H18/H17, F17/G18, D18/E17, C18/D17) | VERIFIED: ulx3s_v20.lpf lines 384-440; docs/research/ulx3s-lvds-input.md |
| Pairs shared with other loads | gp/gn[11] = ESP32 IO26/IO25; gp/gn[12] = ESP32 IO33/IO32 (reserved for the CAN transceiver, firmware/esp32/README.md s.10); gp/gn[13] = ESP32 IO35/IO34; gp/gn[14..17] = on-board ADC AIN0..7 | VERIFIED: ulx3s_v20.lpf comments on those lines |
| Pairs free of other loads | gp/gn 8, 9, 10, 18, 19, 20, 21: **7 lanes** | VERIFIED (same source). UNRESOLVED: 14 modules on one ULX3S need pairs 11, 13 and 14-17 too, i.e. the ESP32 pins tristated and the ADC inputs tolerated as loads, or a second ULX3S. Lane count is the build parameter `N_LANES` (default 7 clean pairs; lane order in constraints/ulx3s.lpf) |
| LVDS input | VINP/VINM 0 to 2.4 V; VCM 0.05 to 2.35 V; VTHD ±100 mV; on-chip 100 ohm ±20 % (DIFFRESISTOR) on left/right banks only; LVDS25 input up to 400 MHz | VERIFIED: ECP5 DS FPGA-DS-02012-3.4 Table 3.13 p.58, Table 2.12 p.44, Table 3.21 p.65 |
| Driver | TLV3605: VOCM 1.125-1.375 V, VOD 250-450 mV into 100 ohm | VERIFIED: TLV3605 DS p.7. Fit: common mode inside the ECP5 range; VOD min 250 mV = ±125 mV against the ±100 mV threshold, 25 mV margin at the minimum swing (PROPOSED reading; G1 eye measurement decides) |
| PLL | VCO 400-800 MHz, CLKOP/CLKOS 3.125-400 MHz, fIN 8-400 MHz | VERIFIED: DS Table 3.23 p.72 |
| Fabric speed, -6 | primary clock tree 257 MHz, edge clock 312 MHz, I/O and PFU register 312 MHz | VERIFIED: DS Table 3.22 p.66 |
| Polarity | On the cable SSTXp is high for a logic one (fan-out output inverted at J50, 2026-10-09). Which ULX3S pin the breakout routes SSTXp to is not designed yet. | PROPOSED: per-lane parameter `LANE_INVERT` (bit vector, default all 1 meaning gp carries SSTXp); docs/schematic/connector.md |
| ESP32 (CAN master) UART | FPGA TX -> ESP32 Serial1 RX on wifi_gpio16 (ball L1); ESP32 Serial1 TX -> FPGA RX on wifi_gpio17 (ball N3). Conflict: a WROVER module uses IO16/IO17 for PSRAM. Alternative: wifi_rxd/wifi_txd (K3/K4, the ESP32 UART0, shared with its programming console). | PROPOSED, UNRESOLVED which module is fitted: ulx3s_v20.lpf lines 179-184 |
| FTDI UART | FPGA TX on ftdi_rxd (ball L4), FPGA RX on ftdi_txd (ball M1); FT231X on the ULX3S, 3 Mbaud maximum | VERIFIED pins: ulx3s_v20.lpf lines 17-18. Baud limit PROPOSED (FT231X datasheet not read) |
| LEDs, buttons | led[7:0] H3,E1,E2,D1,D2,C1,C2,B2; btn[0] D6 is the power button (inverted), btn[1] R1 FIRE1, btn[2] T1 FIRE2 | VERIFIED: ulx3s_v20.lpf lines 29-53 |
| Device | 12F / 25F / 45F / 85F all share the package and pinout; `DEVICE` Makefile variable, default `85k`; the v0 build fits the 12k too (timing passed) | UNRESOLVED: which variant the lab's board is |

## 3. Line protocol (PROPOSED; the headstage transmitter must match)

Requirements row 1: 50 Mbps line rate, 8b/10b, continuous stream with regular commas, framed packets with sequence numbers. Row 5: redundant lanes merged by validated copies. The details below are this document's proposal; `model/` is the executable definition and `enc_8b10b.v`/`frame_tx.v` the reference transmitter.

- **Coding**: 8b/10b per IEEE 802.3 clause 36 tables (the encoder tables in `model/link8b10b.py` are the normative copy; `tb/enc_8b10b` checks them against the clause 36 properties: every code word has run length <= 5, disparity +2/0/-2, decode(encode(x)) = x for all 256 data and the 12 control symbols). Running disparity starts negative.
- **Bit order**: the 10-bit symbol is sent `abcdei fghj` with `a` first, as clause 36 does.
- **Idle**: the ordered set K28.5 D16.2 repeated (the clause 36 /I2/ pair). The pair preserves the running disparity (K28.5 flips it, D16.2 flips it back), so after a frame that ends at positive disparity the idle K28.5 is sent in its positive-disparity form; the receiver aligns on either form (both comma patterns), so this costs nothing. (The first draft claimed the pair leaves the disparity negative; wrong, corrected 2026-10-12 from the transmitter capture.) At least one idle pair between frames; the transmitter sends idle whenever it has nothing to send.
- **Frame**: `K27.7 (/S/)`, `seq u16 LE`, `type u8`, `len u8`, `payload[len+1]` (1 to 256 bytes), `crc u16 LE`, `K29.7 (/T/)`. The CRC is CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no xorout) over seq, type, len and payload, in transmit order. Maximum frame 262 bytes = 2620 UI = 52.4 us at 50 Mbps.
- **Sequence**: u16, incremented per frame by the transmitter, wraps; every lane carries the same frame stream (the redundancy contract, requirements row 5).
- **Types**: 0x00 test pattern (payload = PRBS-15, continued across frames), 0x01 counter pattern, 0x10-0xFF application (headstage-defined, not interpreted here).
- **Receiver tolerance**: a frame is accepted only if every symbol between /S/ and /T/ is a valid data symbol with correct running disparity, `len` matches the byte count received before /T/, and the CRC matches. Anything else discards the frame and counts a `frame_err`.

UNRESOLVED (requirements row 5 and open item 4): maximum lane-to-lane skew and the merge policy under conflicting copies. v0 policy in section 6.

## 4. Clocking and the LVDS front end

- `clk25` (G2, 25 MHz): the independent clock. Only `watchdog.v`, the PLL and the reset synchroniser run on it. PROPOSED.
- `clk_s` 200 MHz (PLL CLKOP) and `clk_c` 50 MHz (PLL CLKOS, same VCO, phase 0): 4 samples per 20 ns UI = 4 new samples per `clk_c` cycle, so the whole core runs at the bit rate with one word per cycle. `clocks.v` wraps EHXPLLL with the parameters ecppll reports (pasted in its header): VCO 600 MHz, inside the 400-800 MHz range (DS Table 3.23). History: the first draft used a 100 MHz core, which only carried two new samples per cycle and failed timing at 38 MHz; 50 MHz was chosen on 2026-10-12. PROPOSED until measured.
- `lane_phy.v` (ECP5-specific): `IO_TYPE=LVDS DIFFRESISTOR=100` on the gp pad (constraints; the gn pad is not a port, nextpnr claims it), a capture flop and three more flops at 200 MHz (c0..c3), then the 50 MHz register takes `{c0,c1,c2,c3}` as one word (`samples[0]` oldest). Because clk_c = clk_s/4 from the same PLL with phase 0, each clk_c edge coincides with a clk_s edge and the four flops hold exactly the four samples of the previous 20 ns: no overlap, no gap (derivation in the file header; checked by `tb/lane_phy` against the behavioural PLL model). UNRESOLVED: hold margin against global-clock skew on the real part is not analysed by nextpnr; if the real phase relation is off by one clk_s period the word is still a valid contiguous window, shifted by one sample, which the CDR absorbs. Only flops live in the 200 MHz domain. Alternative for later: IDDRX2F with ECLK 200 / SCLK 100 (DS p.65 note), not in v0.
- Rate change (architecture item 10 wants it): the PLL and `OVERSAMPLE` set the rate; v0 fixes OVERSAMPLE = 4 and 50 Mbps.

## 5. Per-lane receive chain (`lane_rx.v`)

Interfaces are the contract between agents; keep the names.

```verilog
module cdr_oversample #(parameter OVERSAMPLE = 4) (
  input  wire clk, input wire rst,
  input  wire [3:0] samples,   // one 4-sample word (one UI), [0] oldest
  input  wire       samples_valid, // tied high in the top (one word per cycle); 0 holds all state (tested)
  output reg  [1:0] bits,      // recovered bits, bits[0] first
  output reg  [1:0] nbits,     // 0, 1 or 2 bits valid this cycle
  output reg        transition // at least one edge seen this cycle (for the watchdog/LOS)
);
```
Algorithm as built (PROPOSED, host-tested): every edge between consecutive samples increments a 4-bin histogram of its position in the word; after 32 edges (8 right after silence) the bin vector's direction is quantised to 16 sectors, giving the measured phase; a second-order digital PLL (phase gain 1/8, frequency gain 1/2048 per word) tracks it, so a ppm offset is absorbed by the frequency register instead of lagging the phase; the sample index is round(phase + 1.5) mod 4, and a wrap of the index yields 0 or 2 bits in one word so the bit count is preserved; 16 edge-free words clear the histogram and re-arm a fast first estimate while the frequency register is kept across the silence. The first draft proposed a majority-hysteresis tracker; in a Python trial it lagged at +500 ppm with 0.3 UI jitter and made bit errors, so it was replaced. The block is a 4-stage pipeline (histogram and evaluation; magnitude and ratio comparators by shift-and-add, no DSP blocks; sector and phase error; phase/frequency update) and the sample data is delayed by the same 3 words so the sample-index decision applies to the word it was computed for; `bits`/`nbits` therefore lag `samples` by 4 cycles. Lock-in from reset at +/-500 ppm is about 1000 bits (20 us); the tests require zero errors after the first 2000 bits. Test: `tb/cdr_oversample` drives the line model at ppm offset in {-500, 0, +500}, uniform jitter in {0, 0.15, 0.3} UI and all four start phases, 1e5 bits each with zero bit errors, reacquisition within 100 bits after a 10 us gap, and `samples_valid` on alternate cycles giving the same bits as every cycle (46 tests).

```verilog
module comma_align (
  input wire clk, input wire rst, input wire realign,   // realign: drop alignment and search again
  input wire [1:0] bits, input wire [1:0] nbits,
  output reg [9:0] symbol, output reg symbol_valid,     // one 10-bit symbol, abcdeifghj order, a = bit 0
  output reg aligned
);
```
Aligns on either disparity of K28.5 (`0011111010` / `1100000101` in transmit order); `aligned` after one comma; realigns when `realign` or when the decoder reports 4 invalid symbols within the last 16 (an `invalid_pulse` input, fed from the decoder's code_err|disp_err).

```verilog
module dec_8b10b (
  input wire clk, input wire rst,
  input wire [9:0] symbol, input wire symbol_valid,
  output reg [7:0] data, output reg is_k, output reg data_valid,
  output reg code_err,    // not a valid 10-bit code
  output reg disp_err     // valid code, wrong running disparity
);
```

`lane_rx.v` wires the three, exposes `lock` (aligned and `LOCK_SYMBOLS` = 128 consecutive valid symbols, because the CDR frequency loop needs about 100 symbols to converge and with a 16-symbol rule errors appeared 42-64 symbols after lock in 8 of 24 runs; lost after 4 invalid in 16; first lock after reset at symbol 128-193, relock after a 10 us gap about 129-131 symbols after the gap ends), `err_pulse` (code_err or disp_err), `transition`, and the decoded byte stream (`data, is_k, data_valid`) to `frame_rx`.

`lane_monitor.v`: 100 ms windows on `clk_c` (10 Hz, WINDOW_CYCLES 5,000,000 at 50 MHz): counts `err_pulse` per window, maps the count of the last closed window to the LINK_ALL error class (0 none; 1 = 1-2; 2 = 3-8; 3 = 9-32; 4 = 33-128; 5 = more than 128; 7 = LOS). `valid` = lock held for the whole window. Class 7 when the watchdog's `los` was high at any time in the window or lock was lost at any time in it (as built, `valid` follows lock only, so a watchdog LOS with lock held reports {1, 7}; the nibble after reset is 0x7). Output `nibble[3:0] = {valid, class[2:0]}` exactly as protocol s.1.5 (thresholds PROPOSED there; this is the gateware side of that sentence).

`watchdog.v` (25 MHz domain): per lane, a counter cleared by a synchronised `transition` pulse; `los` asserted when no transition for 1 ms (PROPOSED; the idle pattern has a transition every <= 5 UI, so 1 ms is 50,000 UI of silence) or when both LVDS states are constant (standing correction 11: a stuck comparator output is invalid). `los` forces `realign` in the lane, so CDR and framing are reacquired after release (standing correction 12). Window and thresholds are parameters. Clock crossing as built: a toggle on every 50 MHz transition would alias to a constant at 25 MHz when edges come on consecutive cycles, so the lane side runs an 8-cycle prescaler and toggles at most every 160 ns; the 25 MHz side detects toggles through a 2-flop synchroniser. `los` is 1 in reset.

## 6. Framing and merge

`frame_rx.v`: per lane, a parser on the decoded byte stream: /S/ starts a frame, collects header + payload into a 512-byte frame buffer (one BRAM per lane), /T/ ends it; checks `len`, the CRC and that no error symbol occurred inside; on success commits the frame (seq, type, len, buffer) to `lane_merge`, otherwise discards and counts `frame_err`. Counters: `frames_ok`, `frame_err`, 16-bit each, readable in the status.

`lane_merge.v` (PROPOSED v0 policy): keeps `seq_next`. A committed frame with `seq == seq_next` is output and `seq_next++`. A frame with `seq` ahead of `seq_next` by 1..32767 (u16 difference) is output too, and the gap is added to `frames_lost`. A frame with `seq` behind (u16 difference >= 32768) is a duplicate from a slower lane: dropped, `dups++`. The first lane whose frame commits wins; there is no per-byte vote (UNRESOLVED merge policy under conflicting copies; both copies passed a CRC-16, so disagreement is detected only as a sequence anomaly). Output: `AXI-stream`-like `out_data[7:0], out_valid, out_ready, out_last` plus `out_seq, out_type, out_len` presented with the first byte. Per-lane round-robin arbitration when several lanes commit in the same cycle; the arbiter pick, the header copy and the sequence difference are registered in three pipeline states (frames are at least 10 UI apart on the line, so the extra cycles are free). On reset `seq_next` is unknown: the first committed frame sets it. Port names as built: the buffer release is `rel` (`release` is a Verilog keyword); the sink's inputs are `in_*`; `c_len`/`out_len` carry the raw `len` field (payload bytes = len + 1); a lock drop or an error on /T/ inside a frame counts one `frame_err`; a frame arriving while both lane buffers are held is dropped as `overrun` even if a buffer frees during it (PROPOSED v0 simplification).

`host_sink_uart.v` (v0 host port): writes each output frame to the FTDI UART at 3 Mbaud (16.67 clocks per bit at 50 MHz: the UARTs use a phase accumulator, so bits are 16 or 17 clocks with an exact mean rate and at most 6 % placement error per bit) as `0x5A, seq u16, type, len, payload, crc u16` and drops whole frames when the UART is busy (`host_drops` counter). At 3 Mbaud the sink carries about 300 kB/s against 5 MB/s of line payload, so it is a bring-up window, not the host link (UNRESOLVED, decision 14 host-link item).

## 7. Status reporting

`status_uart.v`, two outputs:
- To the ESP32 (CAN master), 1 Mbaud 8N1, every 50 ms (20 Hz, matching LINK_ALL): `0xA5, seq u8, nib[0..6] (7 bytes, node n in byte (n-1)/2, low nibble odd n, high nibble even n, lanes above N_LANES report LOS), crc8 (poly 0x07, over seq and the 7 bytes)`. 10 bytes = 100 us at 1 Mbaud. Lane index i reports as node i+1 (the lane-to-node map is a fixed bench assumption until the AUX-line association in protocol s.1.2 exists; UNRESOLVED).
- To the FTDI UART, 1 Hz ASCII report: `LINK seq=<n> L0=<nibble hex> L1=... ok=<merged_ok> lost=<frames_lost> dup=<dups> hdrop=<host_drops> sent=<frames_sent>` then `LANE<i> lock=<0/1> err=<invalid symbols in the last 100 ms window> fe=<frame_err> ok=<frames_ok>` per lane; all values latched at the start of the report. The host sink shares that UART, so the report is sent only while `ascii_enable` is high (top level: btn[2] toggles host mode; default off = status mode; the mux switches only while the line is idle high).

LEDs: led[7] blinks at 1 Hz from `clk25` (the watchdog clock is alive), led[6] = PLL locked, led[5:0] = lane lock for lanes 0-5 (in the v0 build before `lane_rx` exists: stretched activity, a transition on the lane within the last 100 ms). btn[1] (FIRE1, active high: PULLMODE=DOWN in ulx3s_v20.lpf line 55) = synchronous reset of everything but the PLL.

## 8. Test-pattern transmitter (`frame_tx.v`)

Generates the section 3 stream at 50 Mbps from `clk_c` (50 MHz, DIV = 1): type 0x00 frames with PRBS-15 payload of `TX_LEN` bytes (parameter, default 64), `TX_GAP` idle pairs between frames (default 4), seq incrementing. Outputs `tx_bit` (single-ended) on gp[0] (ball B11; bank 0, no LVDS needed) and its complement on gn[0] (ball C11) so a 100 ohm resistor and two wires make a loopback into an LVDS pair, or an LED driver takes gp[0] for the G1 optical tests. Also the normative reference for the headstage encoder, together with `model/`. Pin choice VERIFIED (ulx3s_v20.lpf), loopback levels PROPOSED (3.3 V single-ended into an LVDS pair is outside the LVDS input swing; use a resistive divider, documented in `constraints/ulx3s.lpf` comments, or loop back inside the FPGA with `LOOPBACK_INTERNAL=1`, the default for the first bench test).

## 9. Verification (cocotb + Icarus; `make test`)

Golden model `model/link8b10b.py`: encoder/decoder tables, running disparity, CRC-16, `pack_frame`, `unpack_frame`, `serialise(symbols, oversample, ppm, jitter_ui, invert)` returning the 4-samples-per-cycle word stream the RTL sees. Every test derives expected values from the model, never from the RTL.

| Test | Proves |
|---|---|
| tb/enc_8b10b, tb/dec_8b10b | all 256 data + 12 K codes round-trip; disparity rules; every invalid 10-bit word flagged |
| tb/crc16 | matches the model on 1000 random frames, including the CCITT-FALSE check value `0x29B1` for "123456789" |
| tb/cdr_oversample | zero errors at ±500 ppm with 0.3 UI jitter; reacquires after gaps |
| tb/comma_align, tb/lane_rx | aligns from any bit phase; lock/unlock thresholds; realign on `realign` |
| tb/lane_monitor, tb/watchdog | class thresholds at each boundary; LOS after 1 ms silence and on stuck-high/stuck-low; reacquire after release |
| tb/frame_rx | good frames commit; bad CRC, bad len, error symbol inside, missing /T/ all discard |
| tb/lane_merge | 3 lanes with skew 0..2000 UI, one lane with 1 % frame loss, one lane dead: output is every frame exactly once, in order, `dups`/`lost` counts match the model |
| tb/lane_rx | 24 decode runs (ppm -500/0/+500, four start phases, with and without inversion, 0.3 UI jitter): zero errors from the first lock; realign_in; single bit flip raises err_pulse; 8 flipped symbols drop lock and the lane relocks; relock after a 10 us gap |
| tb/lane_phy | the real 200 -> 50 MHz handoff with the behavioural PLL model: 400 words equal the recorded pad levels, INVERT, no overlap or gap |
| tb/system | frame_tx (300 frames, TX_LEN 32) -> model line model (ppm -300/0/+300, 0.2 UI jitter, skew 0/500/2000 UI) -> 3 x lane_rx -> frame_rx -> lane_merge -> host_sink (3 Mbaud, decoded in Python) and status_uart (0xA5 messages decoded): every frame exactly once in order, payload = PRBS continuation, 0 lost, duplicates counted, lane 1 held constant mid-run reports class 7 and relocks, host_sent + host_drops = merged_ok |
| tb/system/Makefile.top | ulx3s_top with the sim PLL and LOOPBACK_INTERNAL=1: lane 0 locks, frames merge, FIRE2 switches the FTDI pin to host frames (smoke test, not in `make test`) |

`make lint` runs Verilator `--lint-only -Wall` on all RTL except the two primitive wrappers. `make synth pnr pack` builds `build/<DEVICE>/ulx3s.bit` (outputs are per device so switching DEVICE cannot repack a stale config) and `make timing` fails if the 200 MHz or 50 MHz constraint is not met (nextpnr `--failed-timing` is not a flag; the Makefile greps the max-frequency report).

## 10. CI (`.github/workflows/ecp5-gateware.yml`)

Triggers on `firmware/ecp5/**`. Installs the OSS CAD Suite with `YosysHQ/setup-oss-cad-suite@v3`, runs `make lint`, `make test`, `make bit DEVICE=85k` and uploads the bitstream and the nextpnr timing report. HIL later: openFPGALoader on the Pi bench (not in v0).

## 11. Open items (UNRESOLVED)

1. Lane count: 7 clean pairs on one ULX3S versus 14 modules (section 2).
2. ESP32 UART pins (WROOM IO16/IO17 versus WROVER PSRAM); which ULX3S variant.
3. Breakout board polarity (`LANE_INVERT`) and the lane-to-node map.
4. Merge policy with conflicting valid copies; maximum skew (requirements open item 4).
5. DIFFRESISTOR: nextpnr accepts it and writes it into the config (section 0); the termination itself and the 200 MHz sampling are unverified until the ULX3S runs.
6. Host link (decision 14 open item): v0 UART sink only.
7. 25 mV differential margin at the TLV3605 minimum swing (section 2): G1 eye measurement.
