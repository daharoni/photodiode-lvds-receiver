// dec_8b10b: 8b/10b decoder with running disparity, IEEE 802.3 clause 36
// (README section 5 interface; section 3 coding).
//
// Label: PROPOSED (line protocol); behaviour VERIFIED against model/link8b10b.py
// by tb/dec_8b10b (all 1024 ten-bit words in both disparities). Not run on an FPGA.
//
// Interface (README section 5), latency 1 cycle, all outputs registered:
//   symbol[9:0], symbol_valid : 'a' = symbol[0]
//   data, is_k, data_valid    : data_valid pulses with every symbol_valid
//   code_err : word is not one the encoder can emit. data_valid=1, data=0,
//              is_k=0 in the same cycle so downstream counters stay aligned.
//   disp_err : valid word whose legal start disparity differs from the tracked
//              disparity; the byte is still decoded.
//
// Parameters: none.
//
// Running disparity: register rd (0 = negative) reset to negative. After a
// valid symbol: if the word is unbalanced rd = sign of its disparity; if it is
// balanced and legal for only one start disparity, rd = that one (this makes
// disp_err symbols resynchronise too); otherwise rd is unchanged.
// Resynchronisation: a code_err sets rd_unk. While rd_unk is set no disp_err is
// reported; the first valid symbol that fixes a disparity (unbalanced, or
// balanced with a single legal start disparity) loads rd from it and clears rd_unk.
// Balanced symbols legal for both disparities leave rd_unk set.
//
// Method: guess (byte, k) from simple 6b/4b lookups, then re-encode the guess for
// both start disparities and compare with the received word. The word is valid
// iff it equals one of the two encodings, so invalid words can never pass.
`default_nettype none

module dec_8b10b (
  input  wire       clk,
  input  wire       rst,
  input  wire [9:0] symbol,
  input  wire       symbol_valid,
  output reg  [7:0] data,
  output reg        is_k,
  output reg        data_valid,
  output reg        code_err,
  output reg        disp_err
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

  // 6b -> x (EDCBA). Every code in either column of Table 36-1 plus K28; others give 0.
  function [4:0] dec6;
    input [5:0] w;
    begin
      case (w)
        6'b101000: dec6 = 5'd23; // 000101
        6'b011000: dec6 = 5'd8; // 000110
        6'b111000: dec6 = 5'd7; // 000111
        6'b100100: dec6 = 5'd27; // 001001
        6'b010100: dec6 = 5'd4; // 001010
        6'b110100: dec6 = 5'd20; // 001011
        6'b001100: dec6 = 5'd24; // 001100
        6'b101100: dec6 = 5'd12; // 001101
        6'b011100: dec6 = 5'd28; // 001110
        6'b111100: dec6 = 5'd28; // 001111
        6'b100010: dec6 = 5'd29; // 010001
        6'b010010: dec6 = 5'd2; // 010010
        6'b110010: dec6 = 5'd18; // 010011
        6'b001010: dec6 = 5'd31; // 010100
        6'b101010: dec6 = 5'd10; // 010101
        6'b011010: dec6 = 5'd26; // 010110
        6'b111010: dec6 = 5'd15; // 010111
        6'b000110: dec6 = 5'd0; // 011000
        6'b100110: dec6 = 5'd6; // 011001
        6'b010110: dec6 = 5'd22; // 011010
        6'b110110: dec6 = 5'd16; // 011011
        6'b001110: dec6 = 5'd14; // 011100
        6'b101110: dec6 = 5'd1; // 011101
        6'b011110: dec6 = 5'd30; // 011110
        6'b100001: dec6 = 5'd30; // 100001
        6'b010001: dec6 = 5'd1; // 100010
        6'b110001: dec6 = 5'd17; // 100011
        6'b001001: dec6 = 5'd16; // 100100
        6'b101001: dec6 = 5'd9; // 100101
        6'b011001: dec6 = 5'd25; // 100110
        6'b111001: dec6 = 5'd0; // 100111
        6'b000101: dec6 = 5'd15; // 101000
        6'b100101: dec6 = 5'd5; // 101001
        6'b010101: dec6 = 5'd21; // 101010
        6'b110101: dec6 = 5'd31; // 101011
        6'b001101: dec6 = 5'd13; // 101100
        6'b101101: dec6 = 5'd2; // 101101
        6'b011101: dec6 = 5'd29; // 101110
        6'b000011: dec6 = 5'd28; // 110000
        6'b100011: dec6 = 5'd3; // 110001
        6'b010011: dec6 = 5'd19; // 110010
        6'b110011: dec6 = 5'd24; // 110011
        6'b001011: dec6 = 5'd11; // 110100
        6'b101011: dec6 = 5'd4; // 110101
        6'b011011: dec6 = 5'd27; // 110110
        6'b000111: dec6 = 5'd7; // 111000
        6'b100111: dec6 = 5'd8; // 111001
        6'b010111: dec6 = 5'd23; // 111010
        default: dec6 = 5'd0;
      endcase
    end
  endfunction

  // 4b -> y. kpos: the 6b block was K28 positive form (110000), where the balanced
  // codes are swapped (K28.1 = 110000 0110 etc).
  function [2:0] dec4;
    input [3:0] w;
    input       kpos;
    begin
      case (w)
        4'b1101: dec4 = 3'd0; // 1011
        4'b0010: dec4 = 3'd0; // 0100
        4'b1001: dec4 = kpos ? 3'd6 : 3'd1; // 1001
        4'b1010: dec4 = kpos ? 3'd5 : 3'd2; // 0101
        4'b0011: dec4 = 3'd3; // 1100
        4'b1100: dec4 = 3'd3; // 0011
        4'b1011: dec4 = 3'd4; // 1101
        4'b0100: dec4 = 3'd4; // 0010
        4'b0101: dec4 = kpos ? 3'd2 : 3'd5; // 1010
        4'b0110: dec4 = kpos ? 3'd1 : 3'd6; // 0110
        4'b0111: dec4 = 3'd7; // 1110
        4'b1000: dec4 = 3'd7; // 0001
        4'b1110: dec4 = 3'd7; // 0111
        4'b0001: dec4 = 3'd7; // 1000
        default: dec4 = 3'd0;
      endcase
    end
  endfunction


  function [3:0] ones10;
    input [9:0] w;
    integer i;
    begin
      ones10 = 4'd0;
      for (i = 0; i < 10; i = i + 1)
        ones10 = ones10 + {3'd0, w[i]};
    end
  endfunction

  reg rd;      // running disparity, 0 = negative
  reg rd_unk;  // disparity unknown after a code_err

  wire [4:0] x_g    = dec6(symbol[5:0]);
  wire       k28    = (symbol[5:0] == 6'b111100) || (symbol[5:0] == 6'b000011);  // transmit 001111 / 110000
  wire       k28pos = (symbol[5:0] == 6'b000011);                                 // 110000
  wire [2:0] y_g    = dec4(symbol[9:6], k28pos);
  wire       k_g    = k28 || (y_g == 3'd7 && (symbol[9:6] == 4'b1110 || symbol[9:6] == 4'b0001) &&  // A7 (transmit 0111 / 1000)
                             
                              (x_g == 5'd23 || x_g == 5'd27 || x_g == 5'd29 || x_g == 5'd30));
  wire [7:0] d_g    = {y_g, x_g};

  // The rd_out bit (bit 10) of enc_comb is not needed here.
  /* verilator lint_off UNUSEDSIGNAL */
  wire [10:0] en = enc_comb(d_g, k_g, 1'b0);
  wire [10:0] ep = enc_comb(d_g, k_g, 1'b1);
  /* verilator lint_on UNUSEDSIGNAL */
  wire v_neg = (en[9:0] == symbol);
  wire v_pos = (ep[9:0] == symbol);
  wire valid = v_neg || v_pos;

  wire [3:0] ones = ones10(symbol);
  // Disparity known after this symbol, and its value.
  wire fix_known = (ones != 4'd5) || (v_neg != v_pos);
  wire fix_val   = (ones > 4'd5) ? 1'b1 : (ones < 4'd5) ? 1'b0 : v_pos;

  always @(posedge clk) begin
    if (rst) begin
      rd         <= 1'b0;
      rd_unk     <= 1'b0;
      data       <= 8'd0;
      is_k       <= 1'b0;
      data_valid <= 1'b0;
      code_err   <= 1'b0;
      disp_err   <= 1'b0;
    end else begin
      data_valid <= symbol_valid;
      code_err   <= 1'b0;
      disp_err   <= 1'b0;
      if (symbol_valid) begin
        if (!valid) begin
          data     <= 8'd0;
          is_k     <= 1'b0;
          code_err <= 1'b1;
          rd_unk   <= 1'b1;
        end else begin
          data     <= d_g;
          is_k     <= k_g;
          disp_err <= !rd_unk && !(rd ? v_pos : v_neg);
          if (fix_known) begin
            rd     <= fix_val;
            rd_unk <= 1'b0;
          end
        end
      end
    end
  end

endmodule
`default_nettype wire
