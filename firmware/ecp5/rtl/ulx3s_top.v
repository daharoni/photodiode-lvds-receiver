// ulx3s_top.v : ULX3S board top (README sections 1, 2, 4, 5-8). PROPOSED; builds with the open
// flow and is simulated through tb/system/system_top.v (same receiver_core, same frame_tx wiring);
// never run on hardware.  The v0 banner top is gone: status_uart replaces it.
//
// Structure: clocks -> N_LANES x lane_phy (pad -> one 4-sample word per clk_c cycle) -> receiver_core
// (lane_rx, watchdog, lane_monitor, frame_rx, lane_merge, host_sink_uart, status_uart);
// frame_tx test-pattern generator; FTDI UART mux; LEDs.
//
// Parameters
//   N_LANES           LVDS lane inputs (default 7: gp/gn 8,9,10,18,19,20,21, README s.2;
//                     constraints/ulx3s.lpf only defines 7 lanes)
//   LANE_INVERT       per-lane INITIAL polarity (bit i = lane i), default all ones.  1 means the pad is LOW
//                     for a logic one (the same meaning as lane_phy INVERT: the samples are inverted).  It
//                     is the initial value of lane_rx's `inv` flop; lane_phy itself is built with INVERT = 0.
//                     On the cable SSTXp is HIGH for a logic one (README s.2), but which pin of the pair
//                     the breakout routes to the gp pad is not designed yet, so the polarity is not
//                     known and lane_rx detects it (AUTO_INVERT, F1: 8 idle pairs, then a flip and a
//                     realign); a wrong initial value only costs that detection time.
//   AUTO_INVERT       1 (default): lane_rx automatic polarity detection (rtl/lane_rx.v header)
//   ASCII_PERIOD      status_uart ASCII report period in clk_c cycles (default 50_000_000 = 1 s; the
//                     smoke test shortens it)
//   LOOPBACK_INTERNAL 1 (default): lane 0's samples come from frame_tx's tx_bit (replicated as a
//                     4-sample word {4{tx_bit}} every clk_c cycle) instead of the pad, so the
//                     first bench test needs no wiring (the loopback samples are XORed with LANE_INVERT[0],
//                     i.e. they are presented in the polarity lane_rx initially expects);
//                     0: all lanes from the pads.  The lane 0
//                     pad stays instantiated either way (and still drives lane_phy).
//   FTDI_DEBOUNCE     clk_c cycles btn[2] must be stable (default 500_000 = 10 ms at 50 MHz)
//
// Ports (names match constraints/ulx3s.lpf)
//   clk_25mhz        independent 25 MHz oscillator (G2)
//   btn[6:0]         btn[1] (FIRE1, active high) resets everything but the PLL; btn[2] (FIRE2)
//                    toggles host mode; others unused
//   led[7:0]         led[7] 1 Hz blink from clk25; led[6] PLL locked; led[5:0] = lock of lanes 0..5
//                    (lanes >= N_LANES read 0); README s.7
//   lane_p[]         LVDS lane inputs, positive pad only (the LPF claims the partner pad)
//   tp_p, tp_n       frame_tx tx_bit and its complement on gp[0]/gn[0] (README s.8)
//   ftdi_rxd         FPGA TX to the FT231X: ASCII status (115200, status_uart) when host mode is
//                    off, the host_sink_uart frame stream (3 Mbaud) when host mode is on
//   ftdi_txd         FPGA RX from the FT231X (unused)
//   wifi_gpio16      FPGA TX to ESP32 Serial1 RX: binary 0xA5 status messages, 1 Mbaud
//   wifi_gpio17      FPGA RX from ESP32 Serial1 TX (unused)
//
// FTDI mux (README s.7): a debounced rising edge of btn[2] requests the other mode; the mode flop
// changes only on a clk_c cycle in which the UART the pin shows NOW is between characters
// (ftdi_tx_busy low in status mode, host_tx_busy low in host mode), so the departing character or
// byte is never cut on the pin (F4: the earlier level test "both txd high" is true inside every '1'
// data bit).  Waiting for BOTH uart_tx instances to be idle at once was tried first and starves:
// the host sink runs back-to-back at 3 Mbaud and its gaps never coincided with the ASCII gaps in a
// 30 ms simulation (switch never happened).  Consequence, by design: when the pin is switched TO
// host mode the sink is usually mid-frame, so the host receiver sees a partial first byte/frame
// and resynchronises on the next frame (CRC-protected); switching to status mode is clean (the ASCII
// path is held in reset while host mode is on, so its pin is idle high).  The debounced button state
// is initialised from the synchronised pin during reset, so a button held at reset does not toggle
// host mode at boot (F4).  The ASCII status path is held in reset while host mode is
// on (status_uart ascii_enable = ~host_mode); a host frame in progress when the mode is switched
// away is abandoned on the pin at a byte boundary, the sink itself keeps running.  Reset: host mode off.
// wifi_en is not driven (ESP32 left to its own default).
`default_nettype none
module ulx3s_top #(
    parameter N_LANES           = 7,
    parameter LANE_INVERT       = {N_LANES{1'b1}},
    parameter AUTO_INVERT       = 1,
    parameter LOOPBACK_INTERNAL = 1,
    parameter FTDI_DEBOUNCE     = 500_000,
    parameter ASCII_PERIOD      = 50_000_000
) (
    input  wire               clk_25mhz,
    input  wire [6:0]         btn,
    output wire [7:0]         led,
    input  wire [N_LANES-1:0] lane_p,
    output wire               tp_p,
    output wire               tp_n,
    output wire               ftdi_rxd,
    input  wire               ftdi_txd,
    output wire               wifi_gpio16,
    input  wire               wifi_gpio17
);
    wire clk_s, clk_c, locked, rst25, rst_c, rst_s;

    clocks u_clocks (
        .clk25(clk_25mhz), .btn_rst(btn[1]),
        .clk_s(clk_s), .clk_c(clk_c), .locked(locked),
        .rst25(rst25), .rst_c(rst_c), .rst_s(rst_s)
    );

    // ---- test pattern transmitter ------------------------------------------
    wire        tx_bit, tx_strobe;
    wire [15:0] tx_seq, frames_sent;
    frame_tx #(.TX_LEN(64), .TX_GAP(4), .DIV(1)) u_tx (     // 1 clock per bit: 50 Mbps at 50 MHz
        .clk(clk_c), .rst(rst_c), .enable(1'b1), .tx_bit(tx_bit), .tx_strobe(tx_strobe),
        .seq(tx_seq), .frames_sent(frames_sent));
    assign tp_p = tx_bit;
    assign tp_n = ~tx_bit;

    // ---- lanes: pad -> lane_phy, lane 0 optionally from the internal loopback ----
    wire [4*N_LANES-1:0] samples;
    wire [N_LANES-1:0]   samples_valid = {N_LANES{1'b1}};   // lane_phy gives one word per clk_c cycle

    genvar i;
    generate
        for (i = 0; i < N_LANES; i = i + 1) begin : g_lane
            wire [3:0] ps;
            lane_phy #(.INVERT(0)) u_phy (
                .lvds_p(lane_p[i]), .clk_s(clk_s), .clk_c(clk_c), .samples(ps));
            if (i == 0 && LOOPBACK_INTERNAL != 0) begin : g_lb
                assign samples[3:0] = {4{tx_bit ^ LANE_INVERT[0]}};
                wire unused_lb = &{1'b0, ps};
            end else begin : g_pad
                assign samples[4*i +: 4] = ps;
            end
        end
    endgenerate

    // ---- receiver core -------------------------------------------------------
    wire [N_LANES-1:0]   lock, lane_los, pol_inv;
    wire [15:0]          resyncs;
    wire                 ftdi_tx_busy, host_tx_busy;
    wire [4*N_LANES-1:0] nibble;
    wire                 esp_txd, status_txd, host_txd;
    wire                 ascii_enable;
    wire                 mrg_valid, mrg_first, mrg_last;
    wire [7:0]           mrg_data, mrg_type, mrg_len;
    wire [15:0]          mrg_seq, merged_ok, frames_lost, dups, host_sent, host_drops;

    receiver_core #(.N_LANES(N_LANES), .AUTO_INVERT(AUTO_INVERT), .INIT_INVERT(LANE_INVERT),
                    .ASCII_PERIOD_CYCLES(ASCII_PERIOD)) u_core (
        .clk_c(clk_c), .rst_c(rst_c), .clk25(clk_25mhz), .rst25(rst25),
        .samples(samples), .samples_valid(samples_valid), .frames_sent(frames_sent),
        .ascii_enable(ascii_enable), .esp_txd(esp_txd), .ftdi_status_txd(status_txd),
        .host_txd(host_txd), .lock(lock), .lane_los(lane_los), .pol_inv(pol_inv), .resyncs(resyncs),
        .ftdi_tx_busy(ftdi_tx_busy), .host_tx_busy(host_tx_busy), .nibble(nibble),
        .mrg_valid(mrg_valid), .mrg_data(mrg_data), .mrg_first(mrg_first), .mrg_last(mrg_last),
        .mrg_seq(mrg_seq), .mrg_type(mrg_type), .mrg_len(mrg_len),
        .merged_ok(merged_ok), .frames_lost(frames_lost), .dups(dups),
        .host_sent(host_sent), .host_drops(host_drops));

    assign wifi_gpio16 = esp_txd;

    // ---- FTDI mux: btn[2] toggles host mode, debounced, switches only while idle ----
    reg  [1:0]  b2s;
    reg  [19:0] db_cnt;
    reg         b2_clean, b2_prev, want_host, host_mode;
    wire        press = b2_clean & ~b2_prev;
    wire        idle_cur  = host_mode ? ~host_tx_busy : ~ftdi_tx_busy;   // the UART the pin shows now
    always @(posedge clk_c) begin
        b2s <= {b2s[0], btn[2]};                  // synchroniser runs during reset too
        if (rst_c) begin
            db_cnt <= 20'd0; b2_clean <= b2s[1]; b2_prev <= b2s[1];   // a button held at reset is not a press
            want_host <= 1'b0; host_mode <= 1'b0;
        end else begin
            b2_prev <= b2_clean;
            if (b2s[1] == b2_clean) db_cnt <= 20'd0;
            else if (db_cnt == FTDI_DEBOUNCE[19:0] - 20'd1) begin
                db_cnt <= 20'd0; b2_clean <= b2s[1];
            end else db_cnt <= db_cnt + 20'd1;
            if (press) want_host <= ~want_host;
            if (want_host != host_mode && idle_cur) host_mode <= want_host;
        end
    end
    assign ascii_enable = ~host_mode;
    assign ftdi_rxd     = host_mode ? host_txd : status_txd;

    // ---- LEDs ---------------------------------------------------------------
    reg [23:0] half_cnt;
    reg        blink1;
    always @(posedge clk_25mhz) begin
        if (rst25) begin
            half_cnt <= 24'd0;
            blink1   <= 1'b0;
        end else if (half_cnt == 24'd12_499_999) begin
            half_cnt <= 24'd0;
            blink1   <= ~blink1;
        end else begin
            half_cnt <= half_cnt + 24'd1;
        end
    end
    wire [31:0] lock32 = {{(32-N_LANES){1'b0}}, lock};
    assign led[7]   = blink1;
    assign led[6]   = locked;
    assign led[5:0] = lock32[5:0];

    // Unused inputs and observation outputs, kept so the LPF/board map is stable.
    wire unused = &{1'b0, btn[6:3], btn[0], ftdi_txd, wifi_gpio17, rst_s, tx_strobe, tx_seq,
                    lane_los, pol_inv, resyncs, nibble, mrg_valid, mrg_first, mrg_last, mrg_data, mrg_type, mrg_len,
                    mrg_seq, merged_ok, frames_lost, dups, host_sent, host_drops, lock32[31:6]};
endmodule
`default_nettype wire
