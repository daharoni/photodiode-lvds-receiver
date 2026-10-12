// system_top.v : testbench wrapper for the end-to-end test (tb/system). NOT synthesised.
// It is the reference for how rtl/ulx3s_top.v is wired: the same receiver_core and the same
// frame_tx, with no clocks.v, no lane_phy and no ECP5 primitive: the testbench supplies clk_c,
// clk25 and the resets, and the lane sample words and samples_valid.  The FTDI UART mux and the
// LED/debounce logic of ulx3s_top are not here (they have no function in the data path).
//
// clk_c is 50 MHz in the design (the testbench uses a 20 ns clock; CLK_HZ = 50_000_000 inside
// receiver_core), frame_tx DIV = 1 (default), samples_valid driven high by the testbench.
// Parameters: N_LANES, TX_LEN, TX_GAP (frame_tx), the receiver_core timing parameters
// (small values so that LOS, windows and status messages fit in a short simulation).
// Ports: see receiver_core.  tx_enable gates frame_tx; tx_bit/tx_strobe are for the Python
// capture; obs packs the per-cycle observations so the testbench makes one read per clock:
//   obs = {mrg_data[7:0], mrg_last, mrg_first, mrg_valid, tx_strobe, tx_bit, host_txd, esp_txd}
//   bit 0 esp_txd, 1 host_txd, 2 tx_bit, 3 tx_strobe, 4 mrg_valid, 5 mrg_first, 6 mrg_last,
//   7+ unused, [15:8] mrg_data (obs[7] = 0).
`default_nettype none
module system_top #(
  parameter N_LANES              = 3,
  parameter TX_LEN               = 32,
  parameter TX_GAP               = 4,
  parameter WD_TIMEOUT           = 1000,
  parameter MON_WINDOW           = 10000,
  parameter STATUS_PERIOD_CYCLES = 15000,
  parameter ASCII_PERIOD_CYCLES  = 50_000_000
) (
  input  wire                 clk_c,
  input  wire                 rst_c,
  input  wire                 clk25,
  input  wire                 rst25,
  input  wire                 tx_enable,
  input  wire [4*N_LANES-1:0] samples,
  input  wire [N_LANES-1:0]   samples_valid,
  input  wire                 ascii_enable,
  output wire                 tx_bit,
  output wire                 tx_strobe,
  output wire                 esp_txd,
  output wire                 ftdi_status_txd,
  output wire                 host_txd,
  output wire [N_LANES-1:0]   lock,
  output wire [N_LANES-1:0]   lane_los,
  output wire [4*N_LANES-1:0] nibble,
  output wire [15:0]          obs,
  output wire [15:0]          mrg_seq,
  output wire [7:0]           mrg_type,
  output wire [7:0]           mrg_len,
  output wire [15:0]          merged_ok,
  output wire [15:0]          frames_lost,
  output wire [15:0]          dups,
  output wire [15:0]          host_sent,
  output wire [15:0]          host_drops,
  output wire [15:0]          frames_sent
);
  wire [15:0] seq;
  frame_tx #(.TX_LEN(TX_LEN), .TX_GAP(TX_GAP)) u_tx (
    .clk(clk_c), .rst(rst_c), .enable(tx_enable), .tx_bit(tx_bit), .tx_strobe(tx_strobe),
    .seq(seq), .frames_sent(frames_sent));

  wire        mrg_valid, mrg_first, mrg_last;
  wire [7:0]  mrg_data;

  receiver_core #(.N_LANES(N_LANES), .WD_TIMEOUT(WD_TIMEOUT), .MON_WINDOW(MON_WINDOW),
                  .STATUS_PERIOD_CYCLES(STATUS_PERIOD_CYCLES),
                  .ASCII_PERIOD_CYCLES(ASCII_PERIOD_CYCLES)) u_core (
    .clk_c(clk_c), .rst_c(rst_c), .clk25(clk25), .rst25(rst25),
    .samples(samples), .samples_valid(samples_valid), .frames_sent(frames_sent),
    .ascii_enable(ascii_enable), .esp_txd(esp_txd), .ftdi_status_txd(ftdi_status_txd),
    .host_txd(host_txd), .lock(lock), .lane_los(lane_los), .nibble(nibble),
    .mrg_valid(mrg_valid), .mrg_data(mrg_data), .mrg_first(mrg_first), .mrg_last(mrg_last),
    .mrg_seq(mrg_seq), .mrg_type(mrg_type), .mrg_len(mrg_len),
    .merged_ok(merged_ok), .frames_lost(frames_lost), .dups(dups),
    .host_sent(host_sent), .host_drops(host_drops));

  // mrg_seq/type/len are held from the first to the last payload byte: read when mrg_first is seen.
  assign obs = {mrg_data, 1'b0, mrg_last, mrg_first, mrg_valid, tx_strobe, tx_bit, host_txd, esp_txd};
  wire unused = &{1'b0, seq};
endmodule
`default_nettype wire
