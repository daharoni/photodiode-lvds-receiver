// watchdog.v : per-lane activity watchdog on the independent 25 MHz clock.
// README section 5 (watchdog.v), section 4 (clk25 independent of the PLL),
// section 9 row 5, standing correction 12 (independent watchdog clock).
// Status: PROPOSED; simulated only (tb/watchdog).
//
// Ports
//   clk_c, rst_c       50 MHz lane clock and its synchronous active-high reset
//   transition_async   1-clk pulse(s) in the clk_c domain: "an edge was seen in
//                      this word" (cdr_oversample.transition; may be high on
//                      consecutive clocks)
//   clk25, rst25       25 MHz watchdog clock and its own synchronous reset
//   los                clk25 domain: 1 when no transition for TIMEOUT_CYCLES clk25
//                      clocks; falls on the next transition.  Also 1 in reset.
//   los_sync           los resynchronised to clk_c with 2 flops (for the lane,
//                      which forces realign on it, standing correction 12)
//
// Stuck-high and stuck-low line states produce NO transitions, so both give
// LOS after the timeout (standing correction 11: a stuck comparator output
// is invalid; the idle pattern has an edge at least every 5 UI so a healthy
// link never times out).
//
// Clock crossing (the toggle-flop handshake lives HERE, in clk_c, so the
// caller only passes the raw pulse):
//   clk_c: `seen` latches transition_async; a free-running STRETCH_BITS-bit
//          prescaler samples it every 2**STRETCH_BITS clk_c and toggles `tog`
//          if it is set.  Without the prescaler a transition on consecutive
//          50 MHz clocks (the normal case: an edge in consecutive words) would
//          toggle `tog` at 25 MHz, which a 25 MHz sampler aliases to a constant
//          and misses.  `tog` toggles at most every 8 clk_c = 160 ns (>= 2 clk25
//          periods), so the 2-flop synchroniser + XOR edge detector in clk25
//          sees every toggle.
//   clk25: tog -> 2 flops -> XOR with a third flop = event.
// Event-to-LOS: LOS rises exactly TIMEOUT_CYCLES clk25 edges after the clk25
// edge at which the event was detected; transition-to-event latency is at most
// 2**STRETCH_BITS clk_c plus 3 clk25 (a few hundred ns, nothing against 1 ms).
//
// Parameters
//   TIMEOUT_CYCLES 25_000  PROPOSED  1 ms at 25 MHz, README s.5; >= 2
//   STRETCH_BITS   3       PROPOSED  prescaler 8 clk_c; 2..6
`default_nettype none
module watchdog #(
  parameter TIMEOUT_CYCLES = 25_000,
  parameter STRETCH_BITS   = 3
) (
  input  wire clk_c,
  input  wire rst_c,
  input  wire transition_async,
  input  wire clk25,
  input  wire rst25,
  output reg  los,
  output reg  los_sync
);
  // ---------------- clk_c domain: stretch + toggle ----------------
  reg [STRETCH_BITS-1:0] pre;
  reg                    seen;
  reg                    tog;
  wire                   pre_last = &pre;
  always @(posedge clk_c) begin
    if (rst_c) begin
      pre <= {STRETCH_BITS{1'b0}}; seen <= 1'b0; tog <= 1'b0;
    end else begin
      pre <= pre + {{(STRETCH_BITS-1){1'b0}}, 1'b1};
      if (pre_last) begin
        seen <= 1'b0;                       // a pulse in this very clock is
        if (seen | transition_async) tog <= ~tog;   // folded in, not lost
      end else if (transition_async) begin
        seen <= 1'b1;
      end
    end
  end

  // ---------------- clk25 domain: synchroniser, edge detect, timeout ----------------
  localparam CW = (TIMEOUT_CYCLES <= 2) ? 1 : $clog2(TIMEOUT_CYCLES);
  reg          s1, s2, s3;
  reg [CW-1:0] cnt;
  wire         event_w = s2 ^ s3;
  always @(posedge clk25) begin
    if (rst25) begin
      s1 <= 1'b0; s2 <= 1'b0; s3 <= 1'b0;
      cnt <= {CW{1'b0}}; los <= 1'b1;
    end else begin
      s1 <= tog; s2 <= s1; s3 <= s2;
      if (event_w) begin
        cnt <= {CW{1'b0}}; los <= 1'b0;
      end else if (!los) begin
        if (cnt == TIMEOUT_CYCLES - 1) los <= 1'b1;
        else cnt <= cnt + {{(CW-1){1'b0}}, 1'b1};
      end
    end
  end

  // ---------------- back to clk_c ----------------
  reg l1;
  always @(posedge clk_c) begin
    if (rst_c) begin l1 <= 1'b1; los_sync <= 1'b1; end
    else       begin l1 <= los;  los_sync <= l1;  end
  end
endmodule
`default_nettype wire
