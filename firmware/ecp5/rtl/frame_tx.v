// frame_tx: test-pattern frame generator and 50 Mbps serialiser (README sections 3 and 8).
//
// Label: PROPOSED (line protocol, README section 3); behaviour checked by tb/frame_tx against
// model/link8b10b.py (see the run record in the report that added it). Nothing here has run on
// an FPGA.
//
// Stream: while `enable` is low, idle pairs K28.5 D16.2 forever. While high, at every idle-pair
// boundary after TX_GAP idle pairs have been sent since the last frame:
//   K27.7, seq u16 LE, type 0x00, len = TX_LEN-1, TX_LEN bytes of PRBS-15 (rtl/prbs.v, state
//   not reset between frames, so the pattern continues), crc u16 LE (CRC-16/CCITT-FALSE over
//   seq, type, len, payload; rtl/crc16.v), K29.7.
// Then TX_GAP idle pairs, then the next frame with seq+1. Dropping `enable` mid-frame lets that
// frame finish. The 10-bit code from rtl/enc_8b10b.v is sent code[0] ('a') first. Running
// disparity starts negative at reset (enc_8b10b).
//
// Parameters
//   TX_LEN : payload bytes per frame, 1..256 (default 64)
//   TX_GAP : idle pairs between frames (default 4)
//   DIV    : clk cycles per line bit (default 2: 100 MHz / 2 = 50 Mbps); >= 1
//
// Ports
//   clk, rst (synchronous, active high), enable
//   tx_bit    : line bit, changes only on a tx_strobe cycle
//   tx_strobe : 1-cycle pulse, coincident with the first clk cycle of every new tx_bit
//   seq       : sequence number of the next frame to be started (increments when /T/ is issued)
//   frames_sent : frames completed (increments when /T/ is issued), wraps
//
// Structure: byte scheduler FSM -> enc_8b10b (1-cycle latency) -> 10-bit shift register -> bit
// divider. The scheduler issues the next symbol at bit index 5 of the symbol being sent; the
// encoder output register holds it until the shift register loads it at the symbol boundary.
// The CRC register is updated by the cycle after a byte is issued, long before it is read back
// (>= 10 bit periods later).
`default_nettype none

module frame_tx #(
  parameter TX_LEN = 64,
  parameter TX_GAP = 4,
  parameter DIV    = 2
) (
  input  wire        clk,
  input  wire        rst,
  input  wire        enable,
  output reg         tx_bit,
  output reg         tx_strobe,
  output reg  [15:0] seq,
  output reg  [15:0] frames_sent
);

  localparam [3:0] S_IDLE_K = 4'd0, S_IDLE_D = 4'd1, S_SEQL = 4'd3,
                   S_SEQH = 4'd4, S_TYPE = 4'd5, S_LEN = 4'd6, S_PAY = 4'd7,
                   S_CRCL = 4'd8, S_CRCH = 4'd9, S_EOF = 4'd10;
  localparam [7:0] K28_5 = 8'hBC, D16_2 = 8'h50, K27_7 = 8'hFB, K29_7 = 8'hFD;
  localparam [7:0] LEN_M1 = TX_LEN - 1;
  localparam PCW = (DIV > 1) ? $clog2(DIV) : 1;
  localparam [31:0] DIV_M1 = DIV - 1;
  wire [PCW-1:0] PC_LAST = DIV_M1[PCW-1:0];

  reg  [3:0]  st;
  reg  [8:0]  pay_left;
  reg  [15:0] gap_left;
  reg         run;       // first symbol issued
  reg  [PCW-1:0] pc;     // clk within bit
  reg  [3:0]  bi;        // index of the bit on tx_bit within the symbol
  reg  [8:0]  sh;        // remaining bits of the symbol being sent

  wire [9:0]  code;
  wire        code_valid_unused;
  wire        enc_err_unused;
  wire [15:0] crc;
  wire [7:0]  pdata;

  wire issue = !run || (run && bi == 4'd5 && pc == {PCW{1'b0}});

  reg [7:0] sym;
  reg       sym_k;
  always @* begin
    sym   = D16_2;
    sym_k = 1'b0;
    case (st)
      S_IDLE_K: begin
        if (gap_left == 16'd0 && enable) begin sym = K27_7; sym_k = 1'b1; end
        else begin sym = K28_5; sym_k = 1'b1; end
      end
      S_IDLE_D: begin sym = D16_2; sym_k = 1'b0; end
      S_SEQL: sym = seq[7:0];
      S_SEQH: sym = seq[15:8];
      S_TYPE: sym = 8'h00;
      S_LEN:  sym = LEN_M1;
      S_PAY:  sym = pdata;
      S_CRCL: sym = crc[7:0];
      S_CRCH: sym = crc[15:8];
      default: begin sym = K29_7; sym_k = 1'b1; end   // S_EOF
    endcase
  end

  // The state S_IDLE_K emits /S/ itself when a frame starts (first symbol of the frame), so
  // the state to go to after it is S_SEQL; `start` flags that case.
  wire start = (st == S_IDLE_K) && (gap_left == 16'd0) && enable;

  wire is_body = (st == S_SEQL) || (st == S_SEQH) || (st == S_TYPE) || (st == S_LEN) || (st == S_PAY);

  prbs u_prbs (.clk(clk), .rst(rst), .seed(15'd0), .load(1'b0),
               .advance(issue && st == S_PAY), .data(pdata));

  crc16 u_crc (.clk(clk), .rst(rst), .init(issue && start), .data(sym),
               .data_valid(issue && is_body), .crc(crc));

  enc_8b10b u_enc (.clk(clk), .rst(rst), .data(sym), .is_k(sym_k), .data_valid(issue),
                   .code(code), .code_valid(code_valid_unused), .enc_err(enc_err_unused));

  always @(posedge clk) begin
    if (rst) begin
      st          <= S_IDLE_K;
      pay_left    <= 9'd0;
      gap_left    <= 16'd0;
      run         <= 1'b0;
      pc          <= {PCW{1'b0}};
      bi          <= 4'd9;
      sh          <= 9'd0;
      tx_bit      <= 1'b0;
      tx_strobe   <= 1'b0;
      seq         <= 16'd0;
      frames_sent <= 16'd0;
    end else begin
      tx_strobe <= 1'b0;

      // bit divider and shift register
      if (run) begin
        if (pc == PC_LAST) begin
          pc        <= {PCW{1'b0}};
          tx_strobe <= 1'b1;
          if (bi == 4'd9) begin
            bi     <= 4'd0;
            tx_bit <= code[0];
            sh     <= code[9:1];
          end else begin
            bi     <= bi + 4'd1;
            tx_bit <= sh[0];
            sh     <= {1'b0, sh[8:1]};
          end
        end else begin
          pc <= pc + {{(PCW-1){1'b0}}, 1'b1};
        end
      end

      // byte scheduler
      if (issue) begin
        run <= 1'b1;
        case (st)
          S_IDLE_K: begin
            if (start) st <= S_SEQL;
            else       st <= S_IDLE_D;
          end
          S_IDLE_D: begin
            st <= S_IDLE_K;
            if (gap_left != 16'd0) gap_left <= gap_left - 16'd1;
          end
          S_SEQL: st <= S_SEQH;
          S_SEQH: st <= S_TYPE;
          S_TYPE: st <= S_LEN;
          S_LEN: begin
            st       <= S_PAY;
            pay_left <= TX_LEN[8:0];
          end
          S_PAY: begin
            pay_left <= pay_left - 9'd1;
            if (pay_left == 9'd1) st <= S_CRCL;
          end
          S_CRCL: st <= S_CRCH;
          S_CRCH: st <= S_EOF;
          default: begin   // S_EOF
            st          <= S_IDLE_K;
            gap_left    <= TX_GAP;
            seq         <= seq + 16'd1;
            frames_sent <= frames_sent + 16'd1;
          end
        endcase
      end
    end
  end

  wire unused_ok = &{1'b0, code_valid_unused, enc_err_unused};

endmodule
`default_nettype wire
