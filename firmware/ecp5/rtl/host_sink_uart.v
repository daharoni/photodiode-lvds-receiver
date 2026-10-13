// host_sink_uart: v0 host port, merged frame stream to a UART (README section 6).
//
// Label: PROPOSED (v0 bring-up window, host link is UNRESOLVED, decision 14). Behaviour
// VERIFIED only by the passing tb/host_sink_uart run recorded in the report that added it.
//
// Parameters: CLK_HZ (core clock), BAUD (UART rate, 8N1).
//
// Input: the lane_merge output stream, with lane_merge's out_* connected to in_*
// (in_valid<-out_valid, in_data<-out_data, in_first<-out_first, in_last<-out_last,
// in_seq<-out_seq, in_type<-out_type, in_len<-out_len). in_ready is tied high: the sink never
// stalls the merge.
//
// Policy: when in_first arrives and the sink is idle (the previous frame completely handed to
// the UART, no frame being received) the frame is accepted: the UART sends
//   0x5A, seq lo, seq hi, type, len, payload[len+1], crc lo, crc hi
// where crc = CRC-16/CCITT-FALSE over seq, type, len and payload (recomputed here with crc16;
// equals the CRC the frame carried on the line). Otherwise the whole frame is dropped
// and host_drops++. The 512-byte FIFO holds payload only (<= 256 bytes per accepted frame; the
// header is sent from registers), so it cannot overflow while the sink only accepts when idle.
// Counters (16 bit, wrap): host_sent (frames fully handed to the UART), host_drops.
// busy: a frame is being received or sent.
// tx_busy: the UART is sending a byte, or a byte has been handed over and is about to start (start bit
// to the end of the stop bit; low between bytes).  The top uses it so the FTDI pin mux never cuts a
// byte (F4); busy (frame level) is not the right signal for that. Throughput at 3 Mbaud, 50 MHz (16.67 clocks per bit, 16 or 17 per bit from the uart_tx phase accumulator): about 300 kB/s.
`default_nettype none

module host_sink_uart #(
  parameter CLK_HZ = 50_000_000,
  parameter BAUD   = 3_000_000
) (
  input  wire        clk,
  input  wire        rst,
  input  wire        in_valid,
  input  wire [7:0]  in_data,
  input  wire        in_first,
  input  wire        in_last,
  input  wire [15:0] in_seq,
  input  wire [7:0]  in_type,
  input  wire [7:0]  in_len,
  output wire        in_ready,
  output wire        txd,
  output reg  [15:0] host_sent,
  output reg  [15:0] host_drops,
  output wire        busy,
  output wire        tx_busy
);

  localparam [2:0] T_IDLE = 3'd0, T_HDR = 3'd1, T_PAY = 3'd2, T_CRC = 3'd3;

  assign in_ready = 1'b1;

  reg [2:0]  tst;
  reg        rx_active;
  reg [15:0] h_seq;
  reg [7:0]  h_type;
  reg [7:0]  h_len;
  reg [2:0]  hidx;
  reg [8:0]  pcnt;       // payload bytes sent
  reg        cidx;

  // payload FIFO
  reg [7:0]  mem [0:511];
  reg [9:0]  wp, rp;
  reg [7:0]  rdata;
  wire       empty = (wp == rp);
  reg        rd_issued;
  reg        have_b;
  reg [7:0]  txb;

  wire [15:0] crc;

  // UART interface
  reg        u_valid;
  reg [7:0]  u_data;
  wire       u_ready;
  uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) u_tx (
    .clk(clk), .rst(rst), .data(u_data), .valid(u_valid), .ready(u_ready), .txd(txd));

  wire idle   = (tst == T_IDLE) && !rx_active;
  wire accept = in_valid && in_first && idle;
  wire push   = in_valid && (accept || rx_active);
  assign busy = !idle;
  assign tx_busy = !u_ready || u_valid;

  always @(posedge clk) begin
    if (push) mem[wp[8:0]] <= in_data;
    rdata <= mem[rp[8:0]];
  end

  // send: a byte may be handed over when the UART is ready and no byte is pending
  wire can_send = !u_valid && u_ready;
  reg        send;
  reg [7:0]  send_b;
  reg        send_crc;      // byte participates in the CRC
  always @* begin
    send = 1'b0; send_b = 8'd0; send_crc = 1'b0;
    case (tst)
      T_HDR: if (can_send) begin
        send = 1'b1;
        send_crc = (hidx != 3'd0);
        case (hidx)
          3'd0: send_b = 8'h5A;
          3'd1: send_b = h_seq[7:0];
          3'd2: send_b = h_seq[15:8];
          3'd3: send_b = h_type;
          default: send_b = h_len;
        endcase
      end
      T_PAY: if (can_send && have_b) begin
        send = 1'b1; send_b = txb; send_crc = 1'b1;
      end
      T_CRC: if (can_send) begin
        send = 1'b1; send_b = cidx ? crc[15:8] : crc[7:0];
      end
      default: begin end
    endcase
  end

  crc16 u_crc (.clk(clk), .rst(rst), .init(accept), .data(send_b), .data_valid(send && send_crc), .crc(crc));

  always @(posedge clk) begin
    if (rst) begin
      tst <= T_IDLE; rx_active <= 1'b0; h_seq <= 16'd0; h_type <= 8'd0; h_len <= 8'd0;
      hidx <= 3'd0; pcnt <= 9'd0; cidx <= 1'b0;
      wp <= 10'd0; rp <= 10'd0; rd_issued <= 1'b0; have_b <= 1'b0; txb <= 8'd0;
      u_valid <= 1'b0; u_data <= 8'd0; host_sent <= 16'd0; host_drops <= 16'd0;
    end else begin
      // receive side
      if (push) wp <= wp + 10'd1;
      if (in_valid && in_first && !idle) host_drops <= host_drops + 16'd1;
      if (accept) begin
        h_seq <= in_seq; h_type <= in_type; h_len <= in_len;
        tst <= T_HDR; hidx <= 3'd0; pcnt <= 9'd0;
      end
      if (accept && !in_last) rx_active <= 1'b1;
      else if (in_valid && in_last) rx_active <= 1'b0;

      // transmit side
      if (u_valid) u_valid <= 1'b0;
      if (send) begin
        u_valid <= 1'b1;
        u_data  <= send_b;
      end
      if (rd_issued) begin
        txb <= rdata; have_b <= 1'b1; rd_issued <= 1'b0;
      end
      case (tst)
        T_HDR: if (send) begin
          if (hidx == 3'd4) tst <= T_PAY; else hidx <= hidx + 3'd1;
        end
        T_PAY: begin
          if (send) begin
            have_b <= 1'b0;
            if (pcnt == {1'b0, h_len}) begin
              tst <= T_CRC; cidx <= 1'b0;
            end
            pcnt <= pcnt + 9'd1;
          end else if (!rd_issued && !have_b && !empty) begin
            rd_issued <= 1'b1; rp <= rp + 10'd1;
          end
        end
        T_CRC: if (send) begin
          cidx <= 1'b1;
          if (cidx) begin tst <= T_IDLE; host_sent <= host_sent + 16'd1; end
        end
        default: begin end
      endcase
    end
  end

endmodule
`default_nettype wire
