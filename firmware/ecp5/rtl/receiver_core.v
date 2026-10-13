// receiver_core.v : everything from the lane samples to the UART outputs (README sections 5-7).
// Status: PROPOSED; simulated only (tb/system via tb/system/system_top.v), and built as part of
// ulx3s_top (nextpnr); never run on hardware.  ulx3s_top and tb/system/system_top.v both
// instantiate this module, so the testbench exercises exactly the wiring that is synthesised.
//
// Per lane i (generate): lane_rx (cdr + comma_align + decoder) -> frame_rx -> lane_merge;
// watchdog (clk25, forces lane_rx realign through los_sync) and lane_monitor (clk_c).  Then one
// lane_merge, one host_sink_uart (merged frame stream -> host_txd) and one status_uart
// (esp_txd binary, ftdi_status_txd ASCII).  Nothing here uses an ECP5 primitive.
//
// Review fixes wired here (README s.5-7): lane_rx pol_inv/AUTO_INVERT polarity correction (F1) and
// its err_pulse2 (idle_mismatch) ORed into the monitor's error input; frame_rx frame_err_p into the
// monitor's frame_err_pulse (a failed frame is an error even if every symbol was valid); lane_merge
// resync (F2); ftdi_tx_busy / host_tx_busy for the top's FTDI mux (F4).
//
// Parameters
//   N_LANES               1..14 (README s.2: 7 clean ULX3S pairs)
//   CLK_HZ                clk_c frequency, for the UART baud generators (50 MHz)
//   WD_TIMEOUT            watchdog TIMEOUT_CYCLES on clk25 (25_000 = 1 ms, README s.5)
//   WD_STRETCH            watchdog STRETCH_BITS
//   MON_WINDOW            lane_monitor WINDOW_CYCLES on clk_c (5_000_000 = 100 ms at 50 MHz)
//   STATUS_PERIOD_CYCLES, ASCII_PERIOD_CYCLES   status_uart periods on clk_c (50 ms = 2_500_000, 1 s = 50_000_000)
//   HOST_BAUD             host_sink_uart baud (3 Mbaud, README s.6): 50 MHz / 3 Mbaud = 16.67 clocks
//                         per bit; uart_tx/uart_rx use a phase accumulator, so each bit is 16 or 17
//                         clocks (<= 1 clock of jitter, no cumulative error; the mean baud is exact)
//   BUF_AW                frame_rx buffer address bits (>= 8)
//   AUTO_INVERT           lane_rx automatic polarity detection (default 1); INIT_INVERT[i] initial polarity
//                         flop of lane i (default 0); RESYNC_DUPS lane_merge resync threshold (default 32)
//
// Ports
//   clk_c, rst_c          50 MHz core clock and its synchronous reset
//   clk25, rst25          independent 25 MHz clock and its reset (watchdogs only)
//   samples[4i+:4], samples_valid[i]   lane i word (samples[0] oldest) and its enable (the top ties it high:
//                         one word per clk_c cycle = one per UI)
//   frames_sent           frame_tx frames_sent, reported in the ASCII status
//   ascii_enable          1 = the ASCII status report runs (top level: host mode off)
//   esp_txd               binary 0xA5 status messages, 1 Mbaud (to the ESP32)
//   ftdi_status_txd       ASCII report, 115200 baud, high when ascii_enable = 0
//   host_txd              host_sink_uart output (HOST_BAUD)
//   lock[i], lane_los[i], nibble[4i+:4]   per-lane lock, watchdog LOS (clk_c domain), LINK_ALL nibble
//   pol_inv[i], resyncs, ftdi_tx_busy, host_tx_busy   lane polarity flops, lane_merge resync count, and
//                         "this UART is sending a character" for the top's FTDI mux
//   mrg_*, merged_ok, frames_lost, dups, host_sent, host_drops   merge output stream and counters
//     (debug/observation ports: the testbench checks the merged stream here; the top ignores them)
`default_nettype none
module receiver_core #(
  parameter N_LANES              = 7,
  parameter CLK_HZ               = 50_000_000,
  parameter WD_TIMEOUT           = 25_000,
  parameter WD_STRETCH           = 3,
  parameter MON_WINDOW           = 5_000_000,
  parameter STATUS_PERIOD_CYCLES = 2_500_000,
  parameter ASCII_PERIOD_CYCLES  = 50_000_000,
  parameter HOST_BAUD            = 3_000_000,
  parameter BUF_AW               = 9,
  parameter AUTO_INVERT          = 1,
  parameter [N_LANES-1:0] INIT_INVERT = {N_LANES{1'b0}},
  parameter RESYNC_DUPS          = 32
) (
  input  wire                 clk_c,
  input  wire                 rst_c,
  input  wire                 clk25,
  input  wire                 rst25,
  input  wire [4*N_LANES-1:0] samples,
  input  wire [N_LANES-1:0]   samples_valid,
  input  wire [15:0]          frames_sent,
  input  wire                 ascii_enable,
  output wire                 esp_txd,
  output wire                 ftdi_status_txd,
  output wire                 host_txd,
  output wire [N_LANES-1:0]   lock,
  output wire [N_LANES-1:0]   lane_los,
  output wire [N_LANES-1:0]   pol_inv,
  output wire [15:0]          resyncs,
  output wire                 ftdi_tx_busy,
  output wire                 host_tx_busy,
  output wire [4*N_LANES-1:0] nibble,
  output wire                 mrg_valid,
  output wire [7:0]           mrg_data,
  output wire                 mrg_first,
  output wire                 mrg_last,
  output wire [15:0]          mrg_seq,
  output wire [7:0]           mrg_type,
  output wire [7:0]           mrg_len,
  output wire [15:0]          merged_ok,
  output wire [15:0]          frames_lost,
  output wire [15:0]          dups,
  output wire [15:0]          host_sent,
  output wire [15:0]          host_drops
);
  wire [N_LANES-1:0]           commit, c_bank, rel, los25, los_c;
  wire [16*N_LANES-1:0]        c_seq;
  wire [8*N_LANES-1:0]         c_type, c_len, rd_data;
  wire [(BUF_AW+1)*N_LANES-1:0] rd_addr;
  wire [16*N_LANES-1:0]        err_count, frame_err, frames_ok;

  genvar i;
  generate
    for (i = 0; i < N_LANES; i = i + 1) begin : g_lane
      wire [7:0] data;
      wire       is_k, data_valid, err_pulse, err_pulse2, transition, aligned;
      wire       fe_p, ov_p, win_tick;
      wire [15:0] overrun;

      lane_rx #(.AUTO_INVERT(AUTO_INVERT), .INIT_INVERT(INIT_INVERT[i])) u_rx (
        .clk(clk_c), .rst(rst_c), .samples(samples[4*i +: 4]), .samples_valid(samples_valid[i]),
        .realign_in(los_c[i]), .data(data), .is_k(is_k), .data_valid(data_valid),
        .err_pulse(err_pulse), .err_pulse2(err_pulse2), .pol_inv(pol_inv[i]),
        .lock(lock[i]), .transition(transition), .aligned(aligned));

      watchdog #(.TIMEOUT_CYCLES(WD_TIMEOUT), .STRETCH_BITS(WD_STRETCH)) u_wd (
        .clk_c(clk_c), .rst_c(rst_c), .transition_async(transition),
        .clk25(clk25), .rst25(rst25), .los(los25[i]), .los_sync(los_c[i]));

      lane_monitor #(.WINDOW_CYCLES(MON_WINDOW)) u_mon (
        .clk(clk_c), .rst(rst_c), .lock(lock[i]), .err_pulse(err_pulse | err_pulse2), .frame_err_pulse(fe_p), .los(los_c[i]),
        .nibble(nibble[4*i +: 4]), .window_tick(win_tick), .err_count_last(err_count[16*i +: 16]));

      frame_rx #(.BUF_AW(BUF_AW)) u_frx (
        .clk(clk_c), .rst(rst_c), .data(data), .is_k(is_k), .data_valid(data_valid),
        .err_pulse(err_pulse), .lock(lock[i]),
        .commit(commit[i]), .c_seq(c_seq[16*i +: 16]), .c_type(c_type[8*i +: 8]),
        .c_len(c_len[8*i +: 8]), .c_bank(c_bank[i]), .rel(rel[i]),
        .rd_addr(rd_addr[(BUF_AW+1)*i +: BUF_AW+1]), .rd_data(rd_data[8*i +: 8]),
        .frame_err_p(fe_p), .overrun_p(ov_p),
        .frames_ok(frames_ok[16*i +: 16]), .frame_err(frame_err[16*i +: 16]), .overrun(overrun));

      assign lane_los[i] = los_c[i];
      wire unused_lane = &{1'b0, ov_p, win_tick, overrun, aligned, los25[i]};
    end
  endgenerate

  wire mg_ready = 1'b1;
  lane_merge #(.N_LANES(N_LANES), .BUF_AW(BUF_AW), .RESYNC_DUPS(RESYNC_DUPS)) u_merge (
    .clk(clk_c), .rst(rst_c), .commit(commit), .c_seq(c_seq), .c_type(c_type), .c_len(c_len),
    .c_bank(c_bank), .rd_data(rd_data), .rel(rel), .rd_addr(rd_addr),
    .out_valid(mrg_valid), .out_data(mrg_data), .out_first(mrg_first), .out_last(mrg_last),
    .out_seq(mrg_seq), .out_type(mrg_type), .out_len(mrg_len), .out_ready(mg_ready),
    .merged_ok(merged_ok), .frames_lost(frames_lost), .dups(dups), .resyncs(resyncs));

  wire sink_ready, sink_busy;
  host_sink_uart #(.CLK_HZ(CLK_HZ), .BAUD(HOST_BAUD)) u_sink (
    .clk(clk_c), .rst(rst_c), .in_valid(mrg_valid), .in_data(mrg_data), .in_first(mrg_first),
    .in_last(mrg_last), .in_seq(mrg_seq), .in_type(mrg_type), .in_len(mrg_len),
    .in_ready(sink_ready), .txd(host_txd), .host_sent(host_sent), .host_drops(host_drops),
    .busy(sink_busy), .tx_busy(host_tx_busy));

  status_uart #(.N_LANES(N_LANES), .CLK_HZ(CLK_HZ), .STATUS_PERIOD_CYCLES(STATUS_PERIOD_CYCLES),
                .ASCII_PERIOD_CYCLES(ASCII_PERIOD_CYCLES)) u_status (
    .clk(clk_c), .rst(rst_c), .nibble(nibble), .lock(lock), .err_count(err_count),
    .frame_err(frame_err), .frames_ok(frames_ok), .merged_ok(merged_ok),
    .frames_lost(frames_lost), .dups(dups), .host_drops(host_drops), .frames_sent(frames_sent),
    .pol_inv(pol_inv), .resyncs(resyncs),
    .ascii_enable(ascii_enable), .esp_txd(esp_txd), .ftdi_txd(ftdi_status_txd),
    .ftdi_busy(ftdi_tx_busy));

  wire unused_core = &{1'b0, sink_ready, sink_busy};
endmodule
`default_nettype wire
