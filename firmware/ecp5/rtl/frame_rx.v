// frame_rx: per-lane frame parser, CRC-16 check and ping-pong frame buffer
// (README section 3 frame format, section 6 framing, section 9 tb/frame_rx).
//
// Label: PROPOSED (line protocol and v0 commit interface). Behaviour VERIFIED only by
// the passing tb/frame_rx run recorded in the report that added it; not run on an FPGA.
//
// Frame (README s.3): /S/=K27.7 (0xFB), seq u16 LE, type u8, len u8, payload[len+1],
// crc u16 LE (CRC-16/CCITT-FALSE over seq,type,len,payload), /T/=K29.7 (0xFD).
//
// Parameters
//   BUF_AW : address bits of one frame buffer (2**BUF_AW bytes per bank). Must be >= 8
//            (a payload is up to 256 bytes). Two banks, 2*2**BUF_AW bytes, one inferred
//            block RAM (one write port, one synchronous read port).
//
// Inputs (from dec_8b10b / lane_rx): data, is_k, data_valid, err_pulse, lock.
//   err_pulse: code or disparity error, aligned with data_valid (it is also honoured
//   without data_valid). lock low: all input ignored; a frame in progress is discarded.
// A frame is discarded, and frame_err_p pulses (counter frame_err +1), when between /S/ and
// /T/ inclusive: a K symbol other than a restarting /S/ appears before the expected /T/ slot,
// a data byte or other K symbol occupies the /T/ slot, err_pulse is seen (also on the /T/ cycle),
// the byte count does not match len (shorter -> /T/ inside the body, longer -> data in the /T/
// slot), the CRC mismatches, or lock drops. A /S/ inside a frame counts one frame_err for the
// aborted frame and restarts parsing. Symbols after a discard are ignored until the next /S/.
// An error on the /S/ symbol itself (disp_err) is ignored (the frame starts).
//
// Commit interface to lane_merge:
//   commit        1-cycle pulse: a frame passed all checks and sits in bank c_bank.
//   c_seq,c_type,c_len,c_bank valid with commit and held until `rel`.
//   c_len is the wire len field (payload bytes = c_len + 1).
//   rel           1-cycle pulse from lane_merge: finished reading the presented bank.
//                 (Port is named rel, not "release": release is a Verilog keyword.)
//                 If a second frame is already committed in the other bank, commit pulses
//                 again the cycle after rel with that frame's c_* (frames are presented in
//                 arrival order, one at a time).
//   rd_addr[BUF_AW:0] = {bank, addr}; rd_data one cycle later.
// Overrun: the bank is chosen at /S/. If both banks are committed-and-unreleased then, the frame
// is parsed but not stored; if it passes all checks, overrun_p pulses and it is dropped
// (counted in overrun, not frames_ok, not frame_err).
// Counters (16 bit, wrap): frames_ok, frame_err, overrun.
// Throughput: one symbol per cycle.
`default_nettype none

module frame_rx #(
  parameter BUF_AW = 9
) (
  input  wire              clk,
  input  wire              rst,
  input  wire [7:0]        data,
  input  wire              is_k,
  input  wire              data_valid,
  input  wire              err_pulse,
  input  wire              lock,
  output reg               commit,
  output reg  [15:0]       c_seq,
  output reg  [7:0]        c_type,
  output reg  [7:0]        c_len,
  output reg               c_bank,
  input  wire              rel,
  input  wire [BUF_AW:0]   rd_addr,
  output reg  [7:0]        rd_data,
  output reg               frame_err_p,
  output reg               overrun_p,
  output reg  [15:0]       frames_ok,
  output reg  [15:0]       frame_err,
  output reg  [15:0]       overrun
);

  localparam [3:0] S_IDLE = 4'd0, S_SEQ0 = 4'd1, S_SEQ1 = 4'd2, S_TYPE = 4'd3, S_LEN = 4'd4,
                   S_PAY = 4'd5, S_CRC0 = 4'd6, S_CRC1 = 4'd7, S_END = 4'd8;

  reg [3:0]  st;
  reg [15:0] p_seq;
  reg [7:0]  p_type;
  reg [7:0]  p_len;
  reg [8:0]  cnt;
  reg [7:0]  crc_lo;
  reg        crc_ok;
  reg        wr_bank;
  reg        has_bank;
  reg        head;           // presented (oldest committed) bank
  reg [1:0]  ncommit;        // committed-and-unreleased frames
  reg [31:0] m_seq;          // stored meta per bank: bank b at [16*b +: 16]
  reg [15:0] m_type;
  reg [15:0] m_len;

  wire [15:0] crc;
  wire in_frame = (st != S_IDLE);
  wire is_s     = data_valid && is_k && (data == 8'hFB);
  wire is_t     = data_valid && is_k && (data == 8'hFD);
  wire body_st  = (st == S_SEQ0) || (st == S_SEQ1) || (st == S_TYPE) || (st == S_LEN) || (st == S_PAY);
  wire crc_init = lock && is_s;
  wire crc_dv   = lock && data_valid && !is_k && !err_pulse && body_st;

  crc16 u_crc (.clk(clk), .rst(rst), .init(crc_init), .data(data), .data_valid(crc_dv), .crc(crc));

  // ---- frame buffer: plain inferred RAM, one write port, one registered read port ----
  reg [7:0] mem [0:2*(2**BUF_AW)-1];
  wire              we = lock && st == S_PAY && data_valid && !is_k && !err_pulse && has_bank;
  wire [BUF_AW:0]   wa = {wr_bank, cnt[BUF_AW-1:0]};
  always @(posedge clk) begin
    if (we) mem[wa] <= data;
    rd_data <= mem[rd_addr];
  end

  // ---- parser and commit queue ----
  wire       rel_v = rel && (ncommit != 2'd0);
  reg        fail;
  reg        restart;
  reg        done;
  wire       start_bank = (ncommit == 2'd2 && rel_v) ? head : ~head;
  wire       adv = lock && in_frame && data_valid && !is_k && !err_pulse;

  always @* begin
    fail = 1'b0; restart = 1'b0; done = 1'b0;
    if (!lock) begin
      fail = in_frame;
    end else if (in_frame) begin
      if (is_s) begin
        fail = 1'b1; restart = 1'b1;
      end else if (err_pulse) begin
        fail = 1'b1;
      end else if (data_valid) begin
        case (st)
          S_SEQ0, S_SEQ1, S_TYPE, S_LEN, S_PAY, S_CRC0, S_CRC1: fail = is_k;
          S_END: begin
            if (is_t && crc_ok) done = 1'b1; else fail = 1'b1;
          end
          default: fail = 1'b1;
        endcase
      end
    end
  end

  wire [15:0] hd_seq  = m_seq[(head ? 0 : 16) +: 16];
  wire [7:0]  hd_type = m_type[(head ? 0 : 8) +: 8];
  wire [7:0]  hd_len  = m_len[(head ? 0 : 8) +: 8];

  always @(posedge clk) begin
    commit      <= 1'b0;
    frame_err_p <= 1'b0;
    overrun_p   <= 1'b0;
    if (rst) begin
      st <= S_IDLE; p_seq <= 16'd0; p_type <= 8'd0; p_len <= 8'd0; cnt <= 9'd0;
      crc_lo <= 8'd0; crc_ok <= 1'b0; wr_bank <= 1'b0; has_bank <= 1'b0; head <= 1'b0;
      ncommit <= 2'd0; m_seq <= 32'd0; m_type <= 16'd0; m_len <= 16'd0;
      c_seq <= 16'd0; c_type <= 8'd0; c_len <= 8'd0; c_bank <= 1'b0;
      frames_ok <= 16'd0; frame_err <= 16'd0; overrun <= 16'd0;
    end else begin
      if (adv) begin
        case (st)
          S_SEQ0: begin p_seq[7:0]  <= data; st <= S_SEQ1; end
          S_SEQ1: begin p_seq[15:8] <= data; st <= S_TYPE; end
          S_TYPE: begin p_type <= data; st <= S_LEN; end
          S_LEN:  begin p_len <= data; cnt <= 9'd0; st <= S_PAY; end
          S_PAY: begin
            if (cnt == {1'b0, p_len}) st <= S_CRC0;
            else cnt <= cnt + 9'd1;
          end
          S_CRC0: begin crc_lo <= data; st <= S_CRC1; end
          S_CRC1: begin crc_ok <= (crc == {data, crc_lo}); st <= S_END; end
          default: begin end
        endcase
      end

      // start of a frame (from idle or by restart)
      if ((lock && is_s && !in_frame) || restart) begin
        st       <= S_SEQ0;
        cnt      <= 9'd0;
        has_bank <= !(ncommit == 2'd2 && !rel_v);
        wr_bank  <= start_bank;
      end else if (fail || done) begin
        st <= S_IDLE;
      end
      if (fail) begin
        frame_err_p <= 1'b1;
        frame_err   <= frame_err + 16'd1;
      end

      // completion
      if (done && !has_bank) begin
        overrun_p <= 1'b1;
        overrun   <= overrun + 16'd1;
      end
      if (done && has_bank) begin
        frames_ok <= frames_ok + 16'd1;
        m_seq[(wr_bank ? 16 : 0) +: 16] <= p_seq;
        m_type[(wr_bank ? 8 : 0) +: 8]  <= p_type;
        m_len[(wr_bank ? 8 : 0) +: 8]   <= p_len;
      end

      // commit queue
      ncommit <= ncommit - {1'b0, rel_v} + {1'b0, (done && has_bank)};
      if (rel_v && ncommit == 2'd2) begin
        head   <= ~head;
        c_seq  <= hd_seq;  c_type <= hd_type;  c_len <= hd_len;  c_bank <= ~head;
        commit <= 1'b1;
      end else if ((ncommit == 2'd0 || (ncommit == 2'd1 && rel_v)) && done && has_bank) begin
        head   <= wr_bank;
        c_seq  <= p_seq;   c_type <= p_type;  c_len <= p_len;   c_bank <= wr_bank;
        commit <= 1'b1;
      end
    end
  end

endmodule
`default_nettype wire
