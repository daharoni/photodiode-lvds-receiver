// lane_merge: sequence-number merge of N lane frame buffers into one frame stream
// (README section 6 v0 policy, section 9 tb/lane_merge).
//
// Label: PROPOSED (merge policy is UNRESOLVED under conflicting copies, README s.11 item 4).
// Behaviour VERIFIED only by the passing tb/lane_merge run recorded in the report that added it.
//
// Parameters
//   N_LANES : number of frame_rx lanes, 1..14.
//   BUF_AW  : frame_rx BUF_AW (>= 8); the per-lane read address is {bank, BUF_AW-bit address}.
//   RESYNC_DUPS : 32 (PROPOSED), 1..255. Resynchronisation threshold, see below.
//
// Per-lane ports are flat vectors, lane i at bits [i*W +: W]. Connection to frame_rx i:
//   commit[i], c_seq, c_type, c_len, c_bank <- frame_rx; rel[i], rd_addr <- to frame_rx;
//   rd_data <- frame_rx (1 cycle after rd_addr). `rel` replaces the spec name "release"
//   (a Verilog keyword).
//
// Policy (v0): commit sets the lane's pending flag. A round-robin arbiter (starting after the
// lane served last) picks a pending lane (S_IDLE registers the decision in `sel`), S_MUX registers
// the lane's seq/type/len/bank, S_DIFF registers d = seq - seq_next (u16), S_DEC acts on it
// (three extra cycles per frame compared with the single-cycle decision, so the 50 MHz core
// clock closes timing; frames are far more than 3 cycles apart on the line: a frame is at
// least 10 UI = 10 cycles). d:
//   no frame yet since reset : output it, no loss counted (the first frame sets seq_next);
//   d >= 32768 (behind)      : duplicate; rel pulse, dups++, nothing output;
//   d == 0                   : output;
//   d in 1..32767 (ahead)    : output and frames_lost += d.
// After the last payload byte is accepted, seq_next = seq + 1, merged_ok++, rel pulses.
// The pending flag is cleared when rel is issued, so a lane re-commits only after its release.
//
// Resynchronisation (review finding F2; PROPOSED, simulated in tb/lane_merge only): the rule
// "d >= 32768 is a duplicate" has no recovery by itself.  After a transmitter restart at seq 0
// while seq_next is in 1..32768, every new frame has d = -seq_next mod 65536 + seq >= 32768 and would
// be dropped as a duplicate for up to 32768 frames (a restart at seq 0 while seq_next is in
// 32769..65535 gives d in 1..32767, "ahead": it is accepted at once and counted as a large
// frames_lost, no stall).  A global counter counts consecutive duplicate decisions with no accepted frame in
// between; at RESYNC_DUPS the merge clears have_next, so the next frame served is accepted without
// a loss count and re-seeds seq_next, and `resyncs` is incremented.  Recovery therefore takes
// RESYNC_DUPS dropped frames, the next one is delivered (RESYNC_DUPS + 1 frames).  Side effect,
// also on a false trigger: a genuine burst of RESYNC_DUPS consecutive duplicates from slow lanes
// also resyncs; the effect is one re-seed: the next frame served, possibly an old copy, is
// delivered once more and frames_lost can over-count by up to the depth of that burst (harmless
// for the data path, visible in the counters).  Default 32, raised from the first choice of 16
// because tb/lane_merge's 14-lane run with up to 2000 cycles of lane skew (700 cycle frame
// period) produces a longest run of 21 consecutive duplicates by itself (7 lanes: 10, 3 lanes: 3,
// measured in that test; a real 14-lane module with such skews is not expected, the margin over 21
// is about 1.5x).  tb/lane_merge checks that its 3-, 7- and 14-lane skew runs never resync.
//
// Output stream: out_valid/out_ready handshake. out_data is one payload byte; out_first with
// the first byte, out_last with the last (payload = out_len + 1 bytes); out_seq/out_type/out_len
// are held from the first byte to the last. out_ready low stalls the merge, nothing is dropped.
// Throughput: one byte per 2 cycles (address cycle, then data cycle, the RAM read latency is 1),
// plus 4 cycles of frame set-up (IDLE, MUX, DIFF, DEC; a dup costs the same 4 cycles).
// Counters (16 bit, wrap): merged_ok, frames_lost, dups, resyncs.
`default_nettype none

module lane_merge #(
  parameter N_LANES = 7,
  parameter BUF_AW  = 9,
  parameter RESYNC_DUPS = 32
) (
  input  wire                        clk,
  input  wire                        rst,
  input  wire [N_LANES-1:0]          commit,
  input  wire [16*N_LANES-1:0]       c_seq,
  input  wire [8*N_LANES-1:0]        c_type,
  input  wire [8*N_LANES-1:0]        c_len,
  input  wire [N_LANES-1:0]          c_bank,
  input  wire [8*N_LANES-1:0]        rd_data,
  output reg  [N_LANES-1:0]          rel,
  output wire [(BUF_AW+1)*N_LANES-1:0] rd_addr,
  output reg                         out_valid,
  output reg  [7:0]                  out_data,
  output reg                         out_first,
  output reg                         out_last,
  output reg  [15:0]                 out_seq,
  output reg  [7:0]                  out_type,
  output reg  [7:0]                  out_len,
  input  wire                        out_ready,
  output reg  [15:0]                 merged_ok,
  output reg  [15:0]                 frames_lost,
  output reg  [15:0]                 dups,
  output reg  [15:0]                 resyncs
);

  function integer clog2;
    input integer v;
    integer i;
    begin
      clog2 = 0;
      for (i = v - 1; i > 0; i = i >> 1) clog2 = clog2 + 1;
    end
  endfunction

  localparam IW = (N_LANES > 1) ? clog2(N_LANES) : 1;
  localparam [2:0] S_IDLE = 3'd0, S_ADDR = 3'd1, S_DATA = 3'd2, S_OUT = 3'd3,
                   S_MUX  = 3'd4, S_DIFF = 3'd5, S_DEC  = 3'd6;

  reg [2:0]          st;
  reg [N_LANES-1:0]  pend;
  reg [IW-1:0]       rr;        // first lane to try
  reg [IW-1:0]       sel;       // lane being served
  reg                bank;
  reg [8:0]          cnt;
  reg [15:0]         seq_next;
  reg                have_next;
  reg [15:0]         r_seq;     // registered fields of the picked lane (S_MUX)
  reg [7:0]          r_type;
  reg [7:0]          r_len;
  reg                r_bank;
  reg [15:0]         diff_r;    // r_seq - seq_next (S_DIFF)
  reg [7:0]          dup_run;   // consecutive duplicate decisions since the last accepted frame

  // ---- arbiter and lane muxes (combinational) ----
  wire [31:0]   rr32  = {{(32-IW){1'b0}}, rr};
  wire [31:0]   sel32 = {{(32-IW){1'b0}}, sel};
  reg           found;
  reg [IW-1:0]  pick;
  reg [15:0]    pk_seq;
  reg [7:0]     pk_type;
  reg [7:0]     pk_len;
  reg           pk_bank;
  reg [7:0]     sel_rd;
  integer       k, idx;
  always @* begin
    found = 1'b0; pick = {IW{1'b0}};
    for (k = 0; k < N_LANES; k = k + 1) begin
      idx = rr32 + k;
      if (idx >= N_LANES) idx = idx - N_LANES;
      if (!found && pend[idx]) begin
        found = 1'b1;
        pick  = idx[IW-1:0];
      end
    end
  end
  always @* begin
    pk_seq = 16'd0; pk_type = 8'd0; pk_len = 8'd0; pk_bank = 1'b0; sel_rd = 8'd0;
    for (k = 0; k < N_LANES; k = k + 1) begin
      if (sel32 == k) begin
        pk_seq  = c_seq[16*k +: 16];
        pk_type = c_type[8*k +: 8];
        pk_len  = c_len[8*k +: 8];
        pk_bank = c_bank[k];
      end
      if (sel32 == k) sel_rd = rd_data[8*k +: 8];
    end
  end

  wire        do_dup   = (st == S_DEC) && have_next && diff_r[15];
  wire        do_take  = (st == S_DEC) && !do_dup;
  wire        fin      = (st == S_OUT) && out_valid && out_ready && out_last;
  wire [IW-1:0] nxt_rr = (sel32 == N_LANES - 1) ? {IW{1'b0}} : sel + 1'b1;

  reg [N_LANES-1:0] clr;
  always @* begin
    clr = {N_LANES{1'b0}};
    for (k = 0; k < N_LANES; k = k + 1)
      if ((do_dup || fin) && sel32 == k) clr[k] = 1'b1;
  end

  genvar gi;
  generate
    for (gi = 0; gi < N_LANES; gi = gi + 1) begin : g_addr
      assign rd_addr[gi*(BUF_AW+1) +: (BUF_AW+1)] =
          ((st == S_ADDR || st == S_DATA || st == S_OUT) && sel == gi) ? {bank, cnt[BUF_AW-1:0]} : {(BUF_AW+1){1'b0}};
    end
  endgenerate

  always @(posedge clk) begin
    if (rst) begin
      st <= S_IDLE; pend <= {N_LANES{1'b0}}; rr <= {IW{1'b0}}; sel <= {IW{1'b0}};
      bank <= 1'b0; cnt <= 9'd0; seq_next <= 16'd0; have_next <= 1'b0;
      r_seq <= 16'd0; r_type <= 8'd0; r_len <= 8'd0; r_bank <= 1'b0; diff_r <= 16'd0;
      rel <= {N_LANES{1'b0}};
      out_valid <= 1'b0; out_data <= 8'd0; out_first <= 1'b0; out_last <= 1'b0;
      out_seq <= 16'd0; out_type <= 8'd0; out_len <= 8'd0;
      merged_ok <= 16'd0; frames_lost <= 16'd0; dups <= 16'd0; resyncs <= 16'd0;
      dup_run <= 8'd0;
    end else begin
      rel  <= clr;
      pend <= (pend & ~clr) | commit;
      if (do_dup) begin
        dups <= dups + 16'd1;
        rr   <= nxt_rr;
        st   <= S_IDLE;
        if (dup_run == RESYNC_DUPS[7:0] - 8'd1) begin
          dup_run   <= 8'd0;
          have_next <= 1'b0;
          resyncs   <= resyncs + 16'd1;
        end else begin
          dup_run <= dup_run + 8'd1;
        end
      end
      if (do_take) begin
        dup_run  <= 8'd0;
        bank     <= r_bank;
        cnt      <= 9'd0;
        out_seq  <= r_seq;
        out_type <= r_type;
        out_len  <= r_len;
        if (have_next) frames_lost <= frames_lost + diff_r;
        st <= S_ADDR;
      end
      case (st)
        S_IDLE: if (found) begin
          sel <= pick;
          st  <= S_MUX;
        end
        S_MUX: begin
          r_seq <= pk_seq; r_type <= pk_type; r_len <= pk_len; r_bank <= pk_bank;
          st    <= S_DIFF;
        end
        S_DIFF: begin
          diff_r <= r_seq - seq_next;
          st     <= S_DEC;
        end
        S_ADDR: st <= S_DATA;
        S_DATA: begin
          out_data  <= sel_rd;
          out_first <= (cnt == 9'd0);
          out_last  <= (cnt == {1'b0, out_len});
          out_valid <= 1'b1;
          st        <= S_OUT;
        end
        S_OUT: begin
          if (out_valid && out_ready) begin
            out_valid <= 1'b0;
            if (out_last) begin
              seq_next  <= out_seq + 16'd1;
              have_next <= 1'b1;
              merged_ok <= merged_ok + 16'd1;
              rr        <= nxt_rr;
              st        <= S_IDLE;
            end else begin
              cnt <= cnt + 9'd1;
              st  <= S_ADDR;
            end
          end
        end
        default: begin end
      endcase
    end
  end

endmodule
`default_nettype wire
