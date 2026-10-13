// lane_monitor.v : per-lane error-class window (LINK_ALL nibble).
// README section 5 (lane_monitor), section 7 (LINK_ALL, protocol s.1.5);
// section 9 row 5.  Status: PROPOSED (thresholds PROPOSED in protocol s.1.5);
// simulated only (tb/lane_monitor).
//
// Ports (clk_c domain, 50 MHz, synchronous active-high reset):
//   lock             lane lock from lane_rx (aligned and LOCK_SYMBOLS valid symbols)
//   err_pulse        1 clk per invalid symbol (code_err or disp_err) or idle_mismatch (lane_rx err_pulse2)
//   frame_err_pulse  1 clk per failed frame (frame_rx frame_err_p: CRC/length/abort).  A frame
//                    failure is an error even if every symbol was valid (an inverted or otherwise
//                    mis-decoded lane has valid 8b/10b symbols, review finding F1).  If it coincides
//                    with err_pulse both count (the window count is the sum).
//   los              loss of signal from the watchdog (los_sync of watchdog.v)
//   nibble[3:0]      {valid, class[2:0]} of the LAST CLOSED window
//   window_tick      1 clk pulse when a window closes and nibble updates
//   err_count_last   error count of the last closed window, saturating at 65535
//
// Rules (a window is WINDOW_CYCLES clocks; the closing clock belongs to it):
//   count = err_pulse clocks + frame_err_pulse clocks in the window
//   class: 0 none; 1 = 1-2; 2 = 3-8; 3 = 9-32; 4 = 33-128; 5 = >128;
//          7 = LOS: los high on ANY clock of the window, or lock low on ANY
//          clock of the window
//   valid = lock high on EVERY clock of the window (los does not change it)
// Before the first window closes nibble = 4'b0111 (not valid, class 7) so a
// fresh module never reports a good link.  Class 6 is unused.
//
// Parameters:
//   WINDOW_CYCLES  5_000_000  PROPOSED  100 ms at 50 MHz, README s.5; >= 2
`default_nettype none
module lane_monitor #(
  parameter WINDOW_CYCLES = 5_000_000
) (
  input  wire        clk,
  input  wire        rst,
  input  wire        lock,
  input  wire        err_pulse,
  input  wire        frame_err_pulse,
  input  wire        los,
  output reg  [3:0]  nibble,
  output reg         window_tick,
  output reg  [15:0] err_count_last
);
  localparam CW = (WINDOW_CYCLES <= 2) ? 1 : $clog2(WINDOW_CYCLES);

  reg [CW-1:0] cnt;
  reg [15:0]   errs;
  reg          los_seen, nolock_seen;

  wire         last   = (cnt == WINDOW_CYCLES - 1);
  wire [16:0]  errs_s = {1'b0, errs} + {16'd0, err_pulse} + {16'd0, frame_err_pulse};
  wire [15:0]  total  = errs_s[16] ? 16'hFFFF : errs_s[15:0];
  wire         los_w  = los_seen | los;
  wire         nolk_w = nolock_seen | ~lock;

  reg [2:0] cls;
  always @* begin
    if (los_w || nolk_w)     cls = 3'd7;
    else if (total == 16'd0) cls = 3'd0;
    else if (total <= 16'd2) cls = 3'd1;
    else if (total <= 16'd8) cls = 3'd2;
    else if (total <= 16'd32) cls = 3'd3;
    else if (total <= 16'd128) cls = 3'd4;
    else                     cls = 3'd5;
  end

  always @(posedge clk) begin
    if (rst) begin
      cnt <= {CW{1'b0}}; errs <= 16'd0; los_seen <= 1'b0; nolock_seen <= 1'b0;
      nibble <= 4'b0111; window_tick <= 1'b0; err_count_last <= 16'd0;
    end else begin
      window_tick <= last;
      if (last) begin
        nibble         <= {~nolk_w, cls};
        err_count_last <= total;
        cnt <= {CW{1'b0}}; errs <= 16'd0; los_seen <= 1'b0; nolock_seen <= 1'b0;
      end else begin
        cnt         <= cnt + {{(CW-1){1'b0}}, 1'b1};
        errs        <= total;
        los_seen    <= los_w;
        nolock_seen <= nolk_w;
      end
    end
  end
endmodule
`default_nettype wire
