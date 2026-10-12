// enc_8b10b: 8b/10b encoder, IEEE 802.3 clause 36 (README section 3, line protocol).
//
// Label: PROPOSED (line protocol); table contents VERIFIED against the Python
// model model/link8b10b.py by tb/enc_8b10b (all 256 data + 12 control symbols,
// both disparities). Nothing here has run on an FPGA.
//
// Interface
//   data, is_k, data_valid : one symbol per cycle with data_valid=1
//   code[9:0]              : registered result, code[0] = 'a' (first transmitted)
//                            .. code[9] = 'j'. Latency 1 cycle.
//   code_valid             : data_valid delayed by one cycle
//   enc_err                : (registered with code) is_k was set for a byte that is
//                            not one of the 12 control codes; K28.5 is encoded instead.
//
// Parameters: none.
//
// Running disparity: one register (0 = negative, 1 = positive), reset to
// negative, updated only when data_valid=1. Explicit case-statement tables for
// 5b/6b and 3b/4b (no 1024-entry ROM); Yosys maps them to LUT4s.
`default_nettype none

module enc_8b10b (
  input  wire       clk,
  input  wire       rst,
  input  wire [7:0] data,
  input  wire       is_k,
  input  wire       data_valid,
  output reg  [9:0] code,
  output reg        code_valid,
  output reg        enc_err
);

  // 5b/6b table: {pos[5:0], neg[5:0]} codes, bit 0 = 'a' (first transmitted).
  // Selector {k28, x[4:0]}. Generated from model/link8b10b.py (clause 36 Table 36-1/36-2).
  function [11:0] t6;
    input [5:0] sel;
    begin
      case (sel)
        6'd0: t6 = {6'b000110, 6'b111001}; // D0  100111 / 011000
        6'd1: t6 = {6'b010001, 6'b101110}; // D1  011101 / 100010
        6'd2: t6 = {6'b010010, 6'b101101}; // D2  101101 / 010010
        6'd3: t6 = {6'b100011, 6'b100011}; // D3  110001 / 110001
        6'd4: t6 = {6'b010100, 6'b101011}; // D4  110101 / 001010
        6'd5: t6 = {6'b100101, 6'b100101}; // D5  101001 / 101001
        6'd6: t6 = {6'b100110, 6'b100110}; // D6  011001 / 011001
        6'd7: t6 = {6'b111000, 6'b000111}; // D7  111000 / 000111
        6'd8: t6 = {6'b011000, 6'b100111}; // D8  111001 / 000110
        6'd9: t6 = {6'b101001, 6'b101001}; // D9  100101 / 100101
        6'd10: t6 = {6'b101010, 6'b101010}; // D10  010101 / 010101
        6'd11: t6 = {6'b001011, 6'b001011}; // D11  110100 / 110100
        6'd12: t6 = {6'b101100, 6'b101100}; // D12  001101 / 001101
        6'd13: t6 = {6'b001101, 6'b001101}; // D13  101100 / 101100
        6'd14: t6 = {6'b001110, 6'b001110}; // D14  011100 / 011100
        6'd15: t6 = {6'b000101, 6'b111010}; // D15  010111 / 101000
        6'd16: t6 = {6'b001001, 6'b110110}; // D16  011011 / 100100
        6'd17: t6 = {6'b110001, 6'b110001}; // D17  100011 / 100011
        6'd18: t6 = {6'b110010, 6'b110010}; // D18  010011 / 010011
        6'd19: t6 = {6'b010011, 6'b010011}; // D19  110010 / 110010
        6'd20: t6 = {6'b110100, 6'b110100}; // D20  001011 / 001011
        6'd21: t6 = {6'b010101, 6'b010101}; // D21  101010 / 101010
        6'd22: t6 = {6'b010110, 6'b010110}; // D22  011010 / 011010
        6'd23: t6 = {6'b101000, 6'b010111}; // D23  111010 / 000101
        6'd24: t6 = {6'b001100, 6'b110011}; // D24  110011 / 001100
        6'd25: t6 = {6'b011001, 6'b011001}; // D25  100110 / 100110
        6'd26: t6 = {6'b011010, 6'b011010}; // D26  010110 / 010110
        6'd27: t6 = {6'b100100, 6'b011011}; // D27  110110 / 001001
        6'd28: t6 = {6'b011100, 6'b011100}; // D28  001110 / 001110
        6'd29: t6 = {6'b100010, 6'b011101}; // D29  101110 / 010001
        6'd30: t6 = {6'b100001, 6'b011110}; // D30  011110 / 100001
        6'd31: t6 = {6'b001010, 6'b110101}; // D31  101011 / 010100
        6'd60: t6 = {6'b000011, 6'b111100}; // K28  001111 / 110000
        default: t6 = 12'd0;
      endcase
    end
  endfunction

  // 3b/4b table: {pos[3:0], neg[3:0]}; y=7 is the primary P7.
  function [7:0] t4;
    input [2:0] y;
    begin
      case (y)
        3'd0: t4 = {4'b0010, 4'b1101}; // x.0  1011 / 0100
        3'd1: t4 = {4'b1001, 4'b1001}; // x.1  1001 / 1001
        3'd2: t4 = {4'b1010, 4'b1010}; // x.2  0101 / 0101
        3'd3: t4 = {4'b1100, 4'b0011}; // x.3  1100 / 0011
        3'd4: t4 = {4'b0100, 4'b1011}; // x.4  1101 / 0010
        3'd5: t4 = {4'b0101, 4'b0101}; // x.5  1010 / 1010
        3'd6: t4 = {4'b0110, 4'b0110}; // x.6  0110 / 0110
        3'd7: t4 = {4'b1000, 4'b0111}; // x.7  1110 / 0001
      endcase
    end
  endfunction

  // Combinational encoder for a VALID symbol. rd: 0 = negative, 1 = positive.
  // Returns {rd_out, code[9:0]}.
  function [10:0] enc_comb;
    input [7:0] d;
    input       k;
    input       rd;
    reg  [4:0]  x;
    reg  [2:0]  y;
    reg  [11:0] e6;
    reg  [5:0]  c6;
    reg         flip6;
    reg         rd6;
    reg  [7:0]  e4;
    reg  [3:0]  c4;
    reg         a7;
    reg         flip4;
    begin
      x     = d[4:0];
      y     = d[7:5];
      e6    = t6({k && (x == 5'd28), x});
      c6    = rd ? e6[11:6] : e6[5:0];
      // The pos and neg columns differ exactly when the code is unbalanced.
      flip6 = (e6[11:6] != e6[5:0]) && (x != 5'd7);
      rd6   = rd ^ flip6;
      e4    = t4(y);
      // A7 replaces P7 to avoid a run of five: x=17,18,20 after rd6-, x=11,13,14 after rd6+;
      // K.x.7 always uses A7.
      a7    = (y == 3'd7) && (k ||
                (!rd6 && (x == 5'd17 || x == 5'd18 || x == 5'd20)) ||
                ( rd6 && (x == 5'd11 || x == 5'd13 || x == 5'd14)));
      if (a7)
        c4 = rd6 ? 4'b0001 : 4'b1110;  // A7: neg 0111, pos 1000 (transmit order); bit0 = 'f'
      else
        c4 = rd6 ? e4[7:4] : e4[3:0];
      // K28.1/.2/.5/.6: the balanced 4b codes are complemented after rd6-.
      if (k && x == 5'd28 && (y == 3'd1 || y == 3'd2 || y == 3'd5 || y == 3'd6) && !rd6)
        c4 = ~c4;
      flip4 = (y == 3'd0) || (y == 3'd4) || (y == 3'd7);
      enc_comb = {rd6 ^ flip4, c4, c6};
    end
  endfunction

  // Valid control bytes: K28.0-7 (x=28) and K23.7, K27.7, K29.7, K30.7.
  wire k_ok = (data[4:0] == 5'd28) ||
              (data[7:5] == 3'd7 && (data[4:0] == 5'd23 || data[4:0] == 5'd27 ||
                                     data[4:0] == 5'd29 || data[4:0] == 5'd30));
  wire       bad_k = is_k && !k_ok;
  wire [7:0] d_use = bad_k ? 8'hBC : data;
  wire       k_use = is_k;  // bad_k encodes K28.5, still a control symbol

  reg  rd;  // running disparity, 0 = negative
  wire [10:0] e = enc_comb(d_use, k_use, rd);

  always @(posedge clk) begin
    if (rst) begin
      rd         <= 1'b0;
      code       <= 10'd0;
      code_valid <= 1'b0;
      enc_err    <= 1'b0;
    end else begin
      code_valid <= data_valid;
      enc_err    <= data_valid && bad_k;
      if (data_valid) begin
        code <= e[9:0];
        rd   <= e[10];
      end
    end
  end

endmodule
`default_nettype wire
