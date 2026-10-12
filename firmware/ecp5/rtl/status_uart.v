// status_uart: link-status reporting (README section 7).
//
// Label: PROPOSED (README section 7); behaviour checked by tb/status_uart (Python bit-banged UART
// receivers and a Python reference for the message and the CRC-8). Nothing here has run on an FPGA.
//
// esp_txd (1 Mbaud 8N1), one 10-byte message per STATUS_PERIOD_CYCLES (default 5,000,000 = 50 ms
// at 100 MHz, 20 Hz):  0xA5, seq u8, nibble bytes 0..6, crc8.
//   seq counts messages, first message 0, wraps at 256.
//   nibble byte j: low nibble = lane 2j (node 2j+1), high nibble = lane 2j+1 (node 2j+2);
//   a lane >= N_LANES reports 0x7 (LOS, valid = 0). Seven bytes cover up to 14 lanes.
//   crc8 (rtl/crc8.v, poly 0x07, init 0) over seq and the seven nibble bytes (not over 0xA5).
//   The nibble vector is latched at the start of the message.
//
// ftdi_txd (115200 8N1), one report per ASCII_PERIOD_CYCLES (default 100,000,000 = 1 s):
//   LINK seq=<n> L0=<x> ... L<N-1>=<x> ok=<merged_ok> lost=<frames_lost> dup=<dups> hdrop=<host_drops> sent=<frames_sent>\r\n
//   LANE<i> lock=<0|1> err=<n> fe=<n> ok=<n>\r\n            (one line per lane, i = 0..N_LANES-1)
//   decimal numbers (no leading zeros), <x> = one hex digit (the LINK_ALL nibble, upper case).
//   seq counts reports, first 0, 16 bits. All inputs are latched at the start of a report.
//   ascii_enable = 0 resets the ASCII path (report in progress aborted, pending one dropped, its
//   period counter restarted) and holds ftdi_txd high, so the top level can share the FTDI pin
//   with host_sink_uart. An abort mid-character truncates that character (a framing error at the
//   host), so the top should switch the pin mux only while ftdi_txd is high.
//   Differences from README section 7 (the interface contract of this task overrides it): the
//   README LINK line ends "fe=<sum> err=<sum>"; this module sends "sent=<frames_sent>" instead and
//   the per-lane counters appear only on the LANE lines.
//
// Parameters
//   N_LANES (1..14), CLK_HZ (UART baud generators), STATUS_PERIOD_CYCLES, ASCII_PERIOD_CYCLES
//   (a message still in progress when its period expires is skipped, not queued, for the binary
//   path; the ASCII path keeps one pending report).
//
// Inputs: nibble[4i+:4] = {valid, class[2:0]} of lane i; lock[i]; err_count/frame_err/frames_ok
//   [16i+:16] per lane; merged_ok, frames_lost, dups, host_drops, frames_sent global 16-bit.
//
// ASCII formatter: byte-at-a-time FSM over a 29-step program (pc); literal strings are small
// constants selected by pc; numbers are converted by repeated subtraction of 10000..1; the lane
// vectors shift right per lane so no wide muxes are needed. About 4 cycles per output char plus
// the UART time; a full 7-lane report takes about 40 ms at 115200 baud.
`default_nettype none

module status_uart #(
  parameter N_LANES              = 7,
  parameter CLK_HZ               = 100_000_000,
  parameter STATUS_PERIOD_CYCLES = 5_000_000,
  parameter ASCII_PERIOD_CYCLES  = 100_000_000
) (
  input  wire                  clk,
  input  wire                  rst,
  input  wire [4*N_LANES-1:0]  nibble,
  input  wire [N_LANES-1:0]    lock,
  input  wire [16*N_LANES-1:0] err_count,
  input  wire [16*N_LANES-1:0] frame_err,
  input  wire [16*N_LANES-1:0] frames_ok,
  input  wire [15:0]           merged_ok,
  input  wire [15:0]           frames_lost,
  input  wire [15:0]           dups,
  input  wire [15:0]           host_drops,
  input  wire [15:0]           frames_sent,
  input  wire                  ascii_enable,
  output wire                  esp_txd,
  output wire                  ftdi_txd
);

  // ------------------------------------------------------------------ binary path
  reg [31:0] bcnt;
  reg [7:0]  bseq;
  reg [7:0]  bseq_l;
  reg [55:0] bpad;      // latched, padded nibble bytes, shifted right by 8 per byte sent
  reg [3:0]  bidx;      // 0..9 byte index; 10 = idle
  wire       b_ready;
  wire       b_start = (bcnt == STATUS_PERIOD_CYCLES - 1);
  wire       b_go    = b_start && (bidx == 4'd10);
  wire       b_fire;
  wire [7:0] b_crc;
  reg  [7:0] b_byte;

  reg [55:0] npad;      // nibble input padded to 14 lanes
  integer    li;
  always @* begin
    npad = {14{4'h7}};
    for (li = 0; li < N_LANES && li < 14; li = li + 1)
      npad[4*li +: 4] = nibble[4*li +: 4];
  end

  always @* begin
    case (bidx)
      4'd0:    b_byte = 8'hA5;
      4'd1:    b_byte = bseq_l;
      4'd9:    b_byte = b_crc;
      default: b_byte = bpad[7:0];
    endcase
  end

  wire b_busy = (bidx != 4'd10);
  assign b_fire = b_busy && b_ready;

  always @(posedge clk) begin
    if (rst) begin
      bcnt   <= 32'd0;
      bseq   <= 8'd0;
      bseq_l <= 8'd0;
      bpad   <= 56'd0;
      bidx   <= 4'd10;
    end else begin
      bcnt <= b_start ? 32'd0 : bcnt + 32'd1;
      if (b_go) begin
        bidx   <= 4'd0;
        bseq_l <= bseq;
        bseq   <= bseq + 8'd1;
        bpad   <= npad;
      end else if (b_fire) begin
        if (bidx == 4'd9) bidx <= 4'd10;
        else              bidx <= bidx + 4'd1;
        if (bidx >= 4'd2) bpad <= {8'h00, bpad[55:8]};
      end
    end
  end

  crc8 u_crc8 (.clk(clk), .rst(rst), .init(b_go), .data(b_byte),
               .data_valid(b_fire && bidx >= 4'd1 && bidx <= 4'd8), .crc(b_crc));

  uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(1_000_000)) u_esp (
    .clk(clk), .rst(rst), .data(b_byte), .valid(b_busy), .ready(b_ready), .txd(esp_txd));

  // ------------------------------------------------------------------ ASCII path
  localparam [2:0] A_IDLE = 3'd0, A_DISP = 3'd1, A_LIT = 3'd2, A_NUM = 3'd3, A_SEND = 3'd4,
                   A_ADV = 3'd5;
  localparam [1:0] OP_LIT = 2'd0, OP_NUM = 2'd1, OP_HEX = 2'd2, OP_END = 2'd3;

  reg [31:0] acnt;
  reg        apend;
  reg [2:0]  as;
  reg [2:0]  aret;        // state after the character has been accepted
  reg [4:0]  pc;
  reg [3:0]  lane;
  reg [3:0]  pos;         // literal character position
  reg [15:0] aseq;

  reg [15:0] val;
  reg [2:0]  pidx;
  reg [3:0]  dig;
  reg        started;
  reg [7:0]  adata;

  // latched report data: loaded before every use, so no reset
  reg [4*N_LANES-1:0]  l_nib;
  reg [N_LANES-1:0]    l_lock;
  reg [16*N_LANES-1:0] l_err, l_fe, l_ok;
  reg [15:0]           l_mok, l_lost, l_dup, l_hdrop, l_sent;

  wire a_ready;
  wire a_valid = (as == A_SEND) && a_ready && ascii_enable;
  wire a_start = (acnt == ASCII_PERIOD_CYCLES - 1);

  // program ROM: op and literal for each step
  reg [1:0]  op;
  reg [79:0] lit;
  always @* begin
    op  = OP_NUM;
    lit = 80'd0;
    case (pc)
      5'd0:  begin op = OP_LIT; lit = "LINK seq="; end
      5'd2:  begin op = OP_LIT; lit = " L"; end
      5'd4:  begin op = OP_LIT; lit = "="; end
      5'd5:  op = OP_HEX;
      5'd6:  begin op = OP_LIT; lit = " ok="; end
      5'd8:  begin op = OP_LIT; lit = " lost="; end
      5'd10: begin op = OP_LIT; lit = " dup="; end
      5'd12: begin op = OP_LIT; lit = " hdrop="; end
      5'd14: begin op = OP_LIT; lit = " sent="; end
      5'd16: begin op = OP_LIT; lit = {64'd0, 16'h0D0A}; end
      5'd17: begin op = OP_LIT; lit = "LANE"; end
      5'd19: begin op = OP_LIT; lit = " lock="; end
      5'd21: begin op = OP_LIT; lit = " err="; end
      5'd23: begin op = OP_LIT; lit = " fe="; end
      5'd25: begin op = OP_LIT; lit = " ok="; end
      5'd27: begin op = OP_LIT; lit = {64'd0, 16'h0D0A}; end
      5'd28: op = OP_END;
      default: op = OP_NUM;
    endcase
  end

  // numeric source for the current NUM step
  reg [15:0] nsrc;
  always @* begin
    case (pc)
      5'd1:  nsrc = aseq;
      5'd3, 5'd18: nsrc = {12'd0, lane};
      5'd7:  nsrc = l_mok;
      5'd9:  nsrc = l_lost;
      5'd11: nsrc = l_dup;
      5'd13: nsrc = l_hdrop;
      5'd15: nsrc = l_sent;
      5'd20: nsrc = {15'd0, l_lock[0]};
      5'd22: nsrc = l_err[15:0];
      5'd24: nsrc = l_fe[15:0];
      default: nsrc = l_ok[15:0];
    endcase
  end

  reg [15:0] pw;
  always @* begin
    case (pidx)
      3'd0: pw = 16'd10000;
      3'd1: pw = 16'd1000;
      3'd2: pw = 16'd100;
      3'd3: pw = 16'd10;
      default: pw = 16'd1;
    endcase
  end

  wire [7:0]  lit_c   = lit[8*(9-pos) +: 8];
  wire [3:0]  nib_cur = l_nib[3:0];
  wire [7:0]  hex_c   = (nib_cur < 4'd10) ? (8'h30 + {4'd0, nib_cur}) : (8'h37 + {4'd0, nib_cur});
  wire [3:0]  lane_n  = lane + 4'd1;
  wire        more    = ({28'd0, lane_n} < N_LANES);

  always @(posedge clk) begin
    if (rst || !ascii_enable) begin
      acnt  <= 32'd0;
      apend <= 1'b0;
      as    <= A_IDLE;
      aret  <= A_IDLE;
      pc    <= 5'd0;
      lane  <= 4'd0;
      pos   <= 4'd0;
      val   <= 16'd0;
      pidx  <= 3'd0;
      dig   <= 4'd0;
      started <= 1'b0;
      adata <= 8'd0;
      if (rst) aseq <= 16'd0;
    end else begin
      acnt <= a_start ? 32'd0 : acnt + 32'd1;
      if (a_start) apend <= 1'b1;
      case (as)
        A_IDLE: begin
          if (apend) begin
            apend  <= 1'b0;
            l_nib  <= nibble;
            l_lock <= lock;
            l_err  <= err_count;
            l_fe   <= frame_err;
            l_ok   <= frames_ok;
            l_mok  <= merged_ok;
            l_lost <= frames_lost;
            l_dup  <= dups;
            l_hdrop <= host_drops;
            l_sent <= frames_sent;
            pc     <= 5'd0;
            lane   <= 4'd0;
            as     <= A_DISP;
          end
        end
        A_DISP: begin
          case (op)
            OP_LIT: begin pos <= 4'd0; as <= A_LIT; end
            OP_NUM: begin
              val <= nsrc; pidx <= 3'd0; dig <= 4'd0; started <= 1'b0; as <= A_NUM;
            end
            OP_HEX: begin adata <= hex_c; aret <= A_ADV; as <= A_SEND; end
            default: begin aseq <= aseq + 16'd1; as <= A_IDLE; end
          endcase
        end
        A_LIT: begin
          if (pos == 4'd10) begin
            as <= A_ADV;
          end else begin
            pos <= pos + 4'd1;
            if (lit_c != 8'd0) begin
              adata <= lit_c; aret <= A_LIT; as <= A_SEND;
            end
          end
        end
        A_NUM: begin
          if (val >= pw) begin
            val <= val - pw;
            dig <= dig + 4'd1;
          end else begin
            dig  <= 4'd0;
            pidx <= pidx + 3'd1;
            if (dig != 4'd0 || started || pidx == 3'd4) begin
              started <= 1'b1;
              adata   <= 8'h30 + {4'd0, dig};
              aret    <= (pidx == 3'd4) ? A_ADV : A_NUM;
              as      <= A_SEND;
            end
          end
        end
        A_SEND: begin
          if (a_valid) as <= aret;
        end
        default: begin   // A_ADV
          as <= A_DISP;
          case (pc)
            5'd5: begin
              lane  <= lane_n;
              l_nib <= l_nib >> 4;
              pc    <= more ? 5'd2 : 5'd6;
            end
            5'd16: begin lane <= 4'd0; pc <= 5'd17; end
            5'd27: begin
              lane   <= lane_n;
              l_lock <= l_lock >> 1;
              l_err  <= l_err >> 16;
              l_fe <= l_fe >> 16;
              l_ok <= l_ok >> 16;
              pc     <= more ? 5'd17 : 5'd28;
            end
            default: pc <= pc + 5'd1;
          endcase
        end
      endcase
    end
  end

  wire a_txd;
  uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(115_200)) u_ftdi (
    .clk(clk), .rst(rst || !ascii_enable), .data(adata), .valid(a_valid), .ready(a_ready),
    .txd(a_txd));
  assign ftdi_txd = a_txd;

endmodule
`default_nettype wire
