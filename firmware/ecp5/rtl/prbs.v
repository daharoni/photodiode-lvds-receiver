// prbs: PRBS-15 generator, x^15 + x^14 + 1, byte-wise (README section 3 type 0x00
// test pattern, section 8 frame_tx).
//
// Label: PROPOSED; sequence VERIFIED by tb/prbs against model/link8b10b.py
// prbs15_bytes (first 64 bytes, and a full-period check).
//
// Fibonacci LFSR, state s[14:0]. One step: fb = s[14] ^ s[13]; s <= {s[13:0], fb};
// the emitted bit is fb. `data` is the NEXT 8 bits as a combinational function of the
// state, data[0] = first bit generated (LSB-first). `advance` moves the state by 8
// steps (consumes the byte on `data`). `load` loads `seed` (priority over advance);
// an all-zero seed (lock-up state) loads 15'h7FFF instead. Reset loads 15'h7FFF.
//
// Parameters: none. (Checker mode is not implemented; the testbench uses the model.)
`default_nettype none

module prbs (
  input  wire        clk,
  input  wire        rst,
  input  wire [14:0] seed,
  input  wire        load,
  input  wire        advance,
  output reg  [7:0]  data
);

  reg [14:0] s;

  // 8 steps of the LFSR, unrolled combinationally: nxt_s = state after 8 steps.
  reg [14:0] nxt_s;
  reg [7:0]  nxt_b;
  reg        fb;
  integer    i;
  always @* begin
    nxt_s = s;
    nxt_b = 8'd0;
    fb    = 1'b0;
    for (i = 0; i < 8; i = i + 1) begin
      fb       = nxt_s[14] ^ nxt_s[13];
      nxt_s    = {nxt_s[13:0], fb};
      nxt_b[i] = fb;
    end
  end

  always @* data = nxt_b;

  always @(posedge clk) begin
    if (rst)
      s <= 15'h7FFF;
    else if (load)
      s <= (seed == 15'd0) ? 15'h7FFF : seed;
    else if (advance)
      s <= nxt_s;
  end

endmodule
`default_nettype wire
