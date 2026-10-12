// comma_align.v : 10-bit symbol alignment on K28.5, plus the invalid-symbol
// realign rule.  README section 5 (interface and rule), section 3 (idle =
// K28.5 D16.2, bit order a first); section 9 row 4.  Status: PROPOSED,
// simulated only (tb/comma_align).
//
// Interface = README section 5 plus ONE extra input, invalid_pulse:
//   realign        1 clk pulse: drop alignment and search again
//   invalid_pulse  1 clk pulse from the decoder per invalid symbol (code_err or
//                  disp_err).  It may arrive a few clocks after the symbol_valid
//                  of the symbol it belongs to; it is attributed to the slot
//                  opened by the most recent symbol_valid (see below).
//   bits/nbits     0, 1 or 2 new bits per clk; bits[0] is the earlier bit
//   symbol         10 bits in transmit order, symbol[0] = first bit received
//                  (abcdei fghj with a = bit 0, clause 36)
//   symbol_valid   1 clk pulse per symbol (the comma itself included)
//   aligned        set by a K28.5 of either disparity
//                    transmit order 0011111010 (RD-) or 1100000101 (RD+),
//                  cleared by realign or by the invalid rule
//
// Search: after every received bit the last 10 bits are compared with the two
// comma patterns; the first hit sets aligned, emits that symbol and starts
// the 10-bit symbol counter.  Aligned: one symbol every 10 bits, also when the
// 10th bit is the first of two bits in the same clock (the second bit then
// starts the next symbol).
//
// Invalid rule: a INV_WINDOW-deep shift register advances at every symbol_valid
// and collects invalid_pulse in its newest slot; when at least INV_THRESH of
// the INV_WINDOW slots hold an invalid symbol, alignment is dropped
// (README: 4 invalid within the last 16).  The history is cleared on every
// loss of alignment.
//
// Parameters:
//   INV_THRESH  4   PROPOSED  README s.5 (realign on 4 invalid in 16)
//   INV_WINDOW  16  PROPOSED  README s.5; 2..32
`default_nettype none
module comma_align #(
  parameter INV_THRESH = 4,
  parameter INV_WINDOW = 16
) (
  input  wire       clk,
  input  wire       rst,
  input  wire       realign,
  input  wire       invalid_pulse,
  input  wire [1:0] bits,
  input  wire [1:0] nbits,
  output reg  [9:0] symbol,
  output reg        symbol_valid,
  output reg        aligned
);
  localparam [9:0] COMMA_RDN = 10'b0101111100; // 0011111010 sent first-bit-first = bit0 first
  localparam [9:0] COMMA_RDP = 10'b1010000011; // 1100000101 likewise

  reg [8:0]  sh;                         // 9 newest bits, newest at [8], oldest at [0]
  reg [3:0]  cnt;                        // bits since the last symbol boundary, 0..9
  reg [INV_WINDOW-1:0] hist;

  // 10-bit window after one / after two new bits; symbol[0] = oldest bit
  wire [9:0]  s1  = {bits[0], sh};
  wire [9:0]  s2  = {bits[1], bits[0], sh[8:1]};
  wire        m1  = (s1 == COMMA_RDN) || (s1 == COMMA_RDP);
  wire        m2  = (s2 == COMMA_RDN) || (s2 == COMMA_RDP);
  wire        two = (nbits >= 2'd2);
  wire        one = (nbits == 2'd1);
  wire [3:0]  n   = two ? 4'd2 : {3'd0, one};
  wire [4:0]  tot = {1'b0, cnt} + {1'b0, n};

  function [5:0] popc;
    input [INV_WINDOW-1:0] v;
    integer i;
    begin
      popc = 6'd0;
      for (i = 0; i < INV_WINDOW; i = i + 1) popc = popc + {5'd0, v[i]};
    end
  endfunction

  wire drop = realign || (aligned && (popc(hist) >= INV_THRESH));

  // next-state decode
  reg        emit, al_n;
  reg [9:0]  sym_n;
  reg [3:0]  cnt_n;
  always @* begin
    emit = 1'b0; al_n = aligned; sym_n = symbol; cnt_n = cnt;
    if (drop) begin
      al_n = 1'b0; cnt_n = 4'd0;
    end else if (!aligned) begin
      if (two && m1)      begin emit = 1'b1; sym_n = s1; al_n = 1'b1; cnt_n = 4'd1; end
      else if (one && m1) begin emit = 1'b1; sym_n = s1; al_n = 1'b1; cnt_n = 4'd0; end
      else if (two && m2) begin emit = 1'b1; sym_n = s2; al_n = 1'b1; cnt_n = 4'd0; end
    end else begin
      if (tot < 5'd10)       cnt_n = tot[3:0];
      else if (tot == 5'd10) begin emit = 1'b1; sym_n = two ? s2 : s1; cnt_n = 4'd0; end
      else                   begin emit = 1'b1; sym_n = s1; cnt_n = 4'd1; end  // cnt 9 + two bits
    end
  end

  // invalid history: advance on every emitted symbol while aligned, collect
  // invalid_pulse in the newest slot; cleared on any loss/gain of alignment
  wire [INV_WINDOW-1:0] hist_adv = emit ? {hist[INV_WINDOW-2:0], 1'b0} : hist;
  wire [INV_WINDOW-1:0] hist_new = {hist_adv[INV_WINDOW-1:1], hist_adv[0] | invalid_pulse};

  always @(posedge clk) begin
    if (rst) begin
      sh <= 9'd0; cnt <= 4'd0; hist <= {INV_WINDOW{1'b0}};
      symbol <= 10'd0; symbol_valid <= 1'b0; aligned <= 1'b0;
    end else begin
      if (two)      sh <= s2[9:1];
      else if (one) sh <= s1[9:1];
      symbol_valid <= emit;
      symbol       <= sym_n;
      aligned      <= al_n;
      cnt          <= cnt_n;
      if (drop || !aligned) hist <= {INV_WINDOW{1'b0}};
      else                  hist <= hist_new;
    end
  end
endmodule
`default_nettype wire
