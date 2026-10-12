# ECP5 gateware (ULX3S first)

Labels: VERIFIED (checked against a cited document or a passing test in this repo), PROPOSED (design intent), UNRESOLVED (open). Written 2026-10-12. Status: **specification, skeleton and simulation tests; nothing has run on an FPGA.** Stage 1 (2026-10-12, VERIFIED by the orchestrator rerunning every command): 8b/10b codec, CRC, PRBS, UART, PLL wrapper, LVDS capture and the ULX3S top build with the open-source flow; `make bit DEVICE=85k` passes timing (clk_s 954 MHz against 200 required, clk_c 177 MHz against 100, nextpnr 0.11.1, 290,530-byte bitstream) and nextpnr writes `PIOA.BASE_TYPE INPUT_LVDS` and `PIOA.DIFFRESISTOR 100` for all 7 lane pads into the config (whether the silicon terminates is unverified). The 8b/10b tables match the orchestrator's independently recalled clause 36 entries for all 256 data codes and K28.5 in both disparities (spot check, not a reading of the clause 36 text). The headstage (transmitter) is co-designed with this receiver (decision 7), so the line protocol in section 3 is defined here, labelled PROPOSED, and the headstage must follow it.

Authority: `docs/architecture.md` (signal-chain item 10, state table), `docs/decision-log.md` (decision 3, standing corrections 11 and 12), `docs/requirements.md` (rows 1, 4, 5), `docs/firmware/can-and-console-protocol.md` (s.1.5 LINK_ALL), `docs/research/ulx3s-lvds-input.md`, `firmware/esp32/README.md` s.10 (CAN master on the ULX3S ESP32).

## 0. What the FPGA does, and does not do

Does (PROPOSED): for each receiver module lane, recover the bit clock from the 50 Mbps LVDS stream by oversampling (no clock is sent), align to the 8b/10b comma, decode 8b/10b, parse frames, check the CRC, count invalid codes; merge the lanes into one frame stream by sequence number; report per-lane link status to the CAN master (the ULX3S's own ESP32, over a UART) in exactly the nibble format of LINK_ALL; supervise every lane with a watchdog on the independent 25 MHz oscillator clock (standing correction 12); provide a test-pattern transmitter so a lane can be looped back or an LED driven for the G1 optical tests.

Does not: any analog slicing (hard rule 1), the CAN protocol itself (the ESP32 on the ULX3S is the master, README s.10), the host link to a computer (UNRESOLVED, decision 14; a generic frame-stream port is provided, v0 sinks it to the FTDI UART).

## 1. Toolchain and layout

Open-source flow only: Yosys, nextpnr-ecp5, prjtrellis, openFPGALoader (or fujprog), Icarus Verilog + cocotb for simulation, Verilator for lint. All come from the YosysHQ OSS CAD Suite: `source tools/fpga-env.sh` from the repo root (installed in `~/opt/oss-cad-suite`, release 2026-10-12; CI installs the same suite). Versions seen 2026-10-12: Yosys 0.69, nextpnr 0.11.1, Verilator 5.053, Icarus 14.0, cocotb 2.1.

```
firmware/ecp5/
  README.md            this file (spec)
  Makefile             lint / test / synth / pnr / pack / prog / timing
  rtl/                 synthesisable Verilog-2005 (no SystemVerilog, so Icarus and Yosys agree)
    ulx3s_top.v        board top level
    clocks.v           EHXPLLL wrapper: 25 MHz -> 200 MHz sample, 100 MHz core
    lane_phy.v         ECP5-specific LVDS capture: differential input, 200 MHz sampling, 4-sample sliding window at 100 MHz plus word_ph
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
- **Idle**: the ordered set K28.5 D16.2 repeated (the clause 36 /I2/ pair, which leaves the running disparity negative so every K28.5 is the same bit pattern and the comma is unambiguous). At least one idle pair between frames; the transmitter sends idle whenever it has nothing to send.
- **Frame**: `K27.7 (/S/)`, `seq u16 LE`, `type u8`, `len u8`, `payload[len+1]` (1 to 256 bytes), `crc u16 LE`, `K29.7 (/T/)`. The CRC is CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no xorout) over seq, type, len and payload, in transmit order. Maximum frame 262 bytes = 2620 UI = 52.4 us at 50 Mbps.
- **Sequence**: u16, incremented per frame by the transmitter, wraps; every lane carries the same frame stream (the redundancy contract, requirements row 5).
- **Types**: 0x00 test pattern (payload = PRBS-15, continued across frames), 0x01 counter pattern, 0x10-0xFF application (headstage-defined, not interpreted here).
- **Receiver tolerance**: a frame is accepted only if every symbol between /S/ and /T/ is a valid data symbol with correct running disparity, `len` matches the byte count received before /T/, and the CRC matches. Anything else discards the frame and counts a `frame_err`.

UNRESOLVED (requirements row 5 and open item 4): maximum lane-to-lane skew and the merge policy under conflicting copies. v0 policy in section 6.

## 4. Clocking and the LVDS front end

- `clk25` (G2, 25 MHz): the independent clock. Only `watchdog.v`, the PLL and the reset synchroniser run on it. PROPOSED.
- `clk_s` 200 MHz (PLL CLKOP) and `clk_c` 100 MHz (PLL CLKOS, same VCO, phase 0): 4 samples per 20 ns UI, which is 2 new samples per `clk_c` cycle. `clocks.v` wraps EHXPLLL with the parameters ecppll reports (pasted in its header): VCO 600 MHz, inside the 400-800 MHz range (DS Table 3.23). nextpnr timing on the 200 MHz domain passed (section 0). PROPOSED until measured.
- `lane_phy.v` (ECP5-specific): `IO_TYPE=LVDS DIFFRESISTOR=100` on the gp pad (constraints; the gn pad is not a port, nextpnr claims it), input register at 200 MHz, two more 200 MHz stages (metastability), then a 4-bit sliding window `samples[3:0]` registered at 100 MHz (`samples[0]` oldest; consecutive words overlap by two samples) plus `word_ph`, which toggles every `clk_c` cycle: taking the word on one phase of `word_ph` gives one non-overlapping 4-sample word per UI (50 MHz word rate), and that is the `samples_valid` enable of the CDR. Only flops live in the 200 MHz domain. The first draft of this section said four new samples per 100 MHz cycle, twice the real rate; corrected 2026-10-12. Alternative for later: IDDRX2F with ECLK 200 / SCLK 100 (DS p.65 note: DDR doubles the data rate), not in v0.
- Rate change (architecture item 10 wants it): the PLL and `OVERSAMPLE` set the rate; v0 fixes OVERSAMPLE = 4 and 50 Mbps.

## 5. Per-lane receive chain (`lane_rx.v`)

Interfaces are the contract between agents; keep the names.

```verilog
module cdr_oversample #(parameter OVERSAMPLE = 4) (
  input  wire clk, input wire rst,
  input  wire [3:0] samples,   // one 4-sample word (one UI), [0] oldest
  input  wire       samples_valid, // one pulse per UI (50 MHz): consume the word; otherwise hold state
  output reg  [1:0] bits,      // recovered bits, bits[0] first
  output reg  [1:0] nbits,     // 0, 1 or 2 bits valid this cycle
  output reg        transition // at least one edge seen this cycle (for the watchdog/LOS)
);
```
Algorithm (PROPOSED): track the phase of the last transition in the 4-sample window; sample the bit two positions after the transition phase (eye centre); move the phase pointer by one position when the majority of the last 8 transitions say early or late (hysteresis, so ±200 ppm frequency offset walks the pointer slowly and random jitter below 0.3 UI does not). Nominally 1 bit per valid word; 0 or 2 when the pointer wraps. Test: `tb/cdr_oversample` drives the model serialiser with ppm offset in {-500, 0, +500} and uniform jitter up to 0.3 UI and requires zero bit errors over 1e5 bits and reacquisition after a 10 us gap.

```verilog
module comma_align (
  input wire clk, input wire rst, input wire realign,   // realign: drop alignment and search again
  input wire [1:0] bits, input wire [1:0] nbits,
  output reg [9:0] symbol, output reg symbol_valid,     // one 10-bit symbol, abcdeifghj order, a = bit 0
  output reg aligned
);
```
Aligns on either disparity of K28.5 (`0011111010` / `1100000101` in transmit order); `aligned` after one comma; realigns when `realign` or when the decoder reports 4 invalid symbols within the last 16.

```verilog
module dec_8b10b (
  input wire clk, input wire rst,
  input wire [9:0] symbol, input wire symbol_valid,
  output reg [7:0] data, output reg is_k, output reg data_valid,
  output reg code_err,    // not a valid 10-bit code
  output reg disp_err     // valid code, wrong running disparity
);
```

`lane_rx.v` wires the three, exposes `lock` (aligned and 16 consecutive valid symbols; lost after 4 invalid in 16), `err_pulse` (code_err or disp_err), `transition`, and the decoded byte stream (`data, is_k, data_valid`) to `frame_rx`.

`lane_monitor.v`: 100 ms windows on `clk_c` (10 Hz): counts `err_pulse` per window, maps the count of the last closed window to the LINK_ALL error class (0 none; 1 = 1-2; 2 = 3-8; 3 = 9-32; 4 = 33-128; 5 = more than 128; 7 = LOS). `valid` = lock held for the whole window. LOS when the watchdog says so or no lock during the window. Output `nibble[3:0] = {valid, class[2:0]}` exactly as protocol s.1.5 (thresholds PROPOSED there; this is the gateware side of that sentence).

`watchdog.v` (25 MHz domain): per lane, a counter cleared by a synchronised `transition` pulse; `los` asserted when no transition for 1 ms (PROPOSED; the idle pattern has a transition every <= 5 UI, so 1 ms is 50,000 UI of silence) or when both LVDS states are constant (standing correction 11: a stuck comparator output is invalid). `los` forces `realign` in the lane, so CDR and framing are reacquired after release (standing correction 12). Window and thresholds are parameters.

## 6. Framing and merge

`frame_rx.v`: per lane, a parser on the decoded byte stream: /S/ starts a frame, collects header + payload into a 512-byte frame buffer (one BRAM per lane), /T/ ends it; checks `len`, the CRC and that no error symbol occurred inside; on success commits the frame (seq, type, len, buffer) to `lane_merge`, otherwise discards and counts `frame_err`. Counters: `frames_ok`, `frame_err`, 16-bit each, readable in the status.

`lane_merge.v` (PROPOSED v0 policy): keeps `seq_next`. A committed frame with `seq == seq_next` is output and `seq_next++`. A frame with `seq` ahead of `seq_next` by 1..255 is output too, and the gap is added to `frames_lost`. A frame with `seq` behind (within a 32768 window) is a duplicate from a slower lane: dropped, `dups++`. The first lane whose frame commits wins; there is no per-byte vote (UNRESOLVED merge policy under conflicting copies; both copies passed a CRC-16, so disagreement is detected only as a sequence anomaly). Output: `AXI-stream`-like `out_data[7:0], out_valid, out_ready, out_last` plus `out_seq, out_type, out_len` presented with the first byte. Per-lane round-robin arbitration when several lanes commit in the same cycle. On reset `seq_next` is unknown: the first committed frame sets it.

`host_sink_uart.v` (v0 host port): writes each output frame to the FTDI UART at 3 Mbaud as `0x5A, seq u16, type, len, payload, crc u16` and drops whole frames when the UART is busy (`host_drops` counter). At 3 Mbaud the sink carries about 300 kB/s against 5 MB/s of line payload, so it is a bring-up window, not the host link (UNRESOLVED, decision 14 host-link item).

## 7. Status reporting

`status_uart.v`, two outputs:
- To the ESP32 (CAN master), 1 Mbaud 8N1, every 50 ms (20 Hz, matching LINK_ALL): `0xA5, seq u8, nib[0..6] (7 bytes, node n in byte (n-1)/2, low nibble odd n, high nibble even n, lanes above N_LANES report LOS), crc8 (poly 0x07, over seq and the 7 bytes)`. 10 bytes = 100 us at 1 Mbaud. Lane index i reports as node i+1 (the lane-to-node map is a fixed bench assumption until the AUX-line association in protocol s.1.2 exists; UNRESOLVED).
- To the FTDI UART, 1 Hz ASCII line: `LINK seq=<n> L0=<nibble hex> L1=... ok=<frames_ok merged> lost=<frames_lost> dup=<dups> hdrop=<host_drops> fe=<sum frame_err> err=<sum err_pulse this second>` and `LANE<i> lock=<0/1> err=<n> fe=<n> ok=<n>` per lane. The host sink shares that UART, so in v0 the status line is sent only when `host_enable` is off (btn[2] toggles; default off = status mode).

LEDs: led[7] blinks at 1 Hz from `clk25` (the watchdog clock is alive), led[6] = PLL locked, led[5:0] = lane lock for lanes 0-5 (in the v0 build before `lane_rx` exists: stretched activity, a transition on the lane within the last 100 ms). btn[1] (FIRE1, active high: PULLMODE=DOWN in ulx3s_v20.lpf line 55) = synchronous reset of everything but the PLL.

## 8. Test-pattern transmitter (`frame_tx.v`)

Generates the section 3 stream at 50 Mbps from `clk_c` (100 MHz / 2): type 0x00 frames with PRBS-15 payload of `TX_LEN` bytes (parameter, default 64), `TX_GAP` idle pairs between frames (default 4), seq incrementing. Outputs `tx_bit` (single-ended) on gp[0] (ball B11; bank 0, no LVDS needed) and its complement on gn[0] (ball C11) so a 100 ohm resistor and two wires make a loopback into an LVDS pair, or an LED driver takes gp[0] for the G1 optical tests. Also the normative reference for the headstage encoder, together with `model/`. Pin choice VERIFIED (ulx3s_v20.lpf), loopback levels PROPOSED (3.3 V single-ended into an LVDS pair is outside the LVDS input swing; use a resistive divider, documented in `constraints/ulx3s.lpf` comments, or loop back inside the FPGA with `LOOPBACK_INTERNAL=1`, the default for the first bench test).

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
| tb/system | frame_tx -> model line model (ppm, jitter) -> N lanes of lane_rx -> frame_rx -> lane_merge -> host_sink: payload equals the PRBS; status frames carry the right nibbles |

`make lint` runs Verilator `--lint-only -Wall` on all RTL except the two primitive wrappers. `make synth pnr pack` builds `build/ulx3s.bit` for `DEVICE` and `make timing` fails if the 200 MHz or 100 MHz constraint is not met (nextpnr `--failed-timing` is not a flag; the Makefile greps the max-frequency report).

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
