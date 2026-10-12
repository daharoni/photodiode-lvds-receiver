// cdr_oversample.v : 4x blind-oversampling clock/data recovery, pure logic.
//
// README section 5 (interface), section 4 (clocking: one 4-bit word per 50 MHz clk_c
// cycle, 4 samples per 20 ns UI, so 1 word = 1 UI nominally).  Status: PROPOSED; simulated only
// (tb/cdr_oversample against model/linesim.py), never run on hardware.
//
// Interface (exactly README section 5):
//   samples_valid 1 when samples[3:0] carries a NEW word.  The top ties it high (lane_phy
//                 delivers one non-overlapping word per clk_c cycle); kept as an input
//                 for the tests and for slower word rates.  0: all state holds,
//                 nbits = 0, transition = 0.
//   samples[3:0]  4 line samples per valid word, [0] oldest
//   bits[1:0]     recovered bits, bits[0] first in time; nbits says how many
//   nbits[1:0]    0, 1 or 2 bits valid this cycle (registered, 4 cycles latency, see Pipelining)
//   transition    at least one line edge inside this word (or at its boundary
//                 with the previous word); registered, for the watchdog
//
// Algorithm (PROPOSED):
//   1. Every edge (sample differs from the sample before it) increments the
//      histogram bin of its position 0..3 in the word.  Bit boundaries sit at
//      one fixed position (the bit period is exactly 4 samples).
//   2. After BLK_EDGES edges (ACQ_EDGES right after reset/silence) the
//      circular mean of the 4 bins is taken as a vector (x = b0-b2, y = b1-b3)
//      and quantised to one of 16 directions m (quarter-sample units).
//   3. A second-order digital PLL tracks m: phi (24 bit, 4.20 fixed point in
//      quarter samples, wraps at one word) advances by the frequency
//      register f every clock; at each block phi += pe>>>KP_SHIFT and
//      f += pe>>>KI_SHIFT, pe = m - phi.  The integral path removes the
//      lag caused by a ppm offset (plain hysteresis/majority trackers lag by
//      half a window, which does not fit the 0.3 UI jitter eye at 500 ppm).
//   4. The bit is sampled at the eye centre, sample index
//      round(circular-mean + 1.5) = floor((phi_int + 8)/4) mod 4.  When that
//      index moves from 3 to 0 the word has no sample (nbits = 0); when it
//      moves from 0 to 3 the word has two (previous word's sample 3, then this
//      word's sample 3).  Otherwise one bit per word.
//   5. QUIET_CYCLES words without an edge clear the histogram and re-arm the
//      fast first estimate (phi jumps to m after ACQ_EDGES edges; f is kept
//      because the transmitter clock is unchanged across a silence).
//
// Parameters (all PROPOSED, tuned in tb/cdr_oversample at +-500 ppm, 0.3 UI):
//   OVERSAMPLE   4 only (the word width and the bin count are fixed to 4)
//   BLK_EDGES    32   edges per tracking block
//   ACQ_EDGES    8    edges for the first estimate after silence
//   QUIET_CYCLES 16   edge-free words that count as silence (idle/data runs
//                     are <= 5 bits, so <= 6 edge-free words in a valid stream)
//   KP_SHIFT     3    proportional gain 1/8 per block
//   KI_SHIFT     11   integral gain 1/2048 per block
// Lock-in from reset at +-500 ppm takes about 1000 bits (f converges); the
// first few bits after reset are not meaningful.  Latency: bits/nbits 4 cycles (1 + PIPE 3), transition 1 cycle.
//
// Pipelining (2026-10-12, for the 50 MHz core clock; PROPOSED, simulated only):
//   The block estimate used to be one combinational chain: histogram -> vector -> ratio
//   comparators -> direction m -> phase error -> phi/f update (about 18 ns in nextpnr, and the
//   `*5 *3 *2` comparisons became MULT18X18D blocks).  It is now four register stages that
//   advance only on valid words (samples_valid = 0 freezes them too):
//     S0 (word cycle)   histogram, edge counter, quiet detector, eval decision; on eval the
//                       bin vector is registered as vx1, vy1 (9 bit signed) with acq1 = acq
//     S1                |vx|, |vy|, five-way ratio comparison by shift-and-add (no multiplier)
//                       -> k2 (0..4), sign bits, m_ok2
//     S2                direction m (0..15) from k and the signs, pe3 = {m,20'd0} - phi
//     S3                phi/f update: phi <= phi + freq + (pe3 >>> KP_SHIFT), f += pe3 >>> KI_SHIFT
//                       (or phi <= {m,20'd0} in the first estimate after silence)
//   Added latency and how it is hidden: the estimate of a block reaches phi PIPE = 3 words
//   after the block closes (in the single-cycle version it reached phi one word after).  The
//   data path is therefore delayed by the same 3 words (sd1..sd3, 12 flops) before the sample
//   is selected, so every data word sees the same phi it saw before pipelining (up to the
//   pe staleness below); tb/cdr_oversample passes with its original bounds, all 46 tests,
//   zero errors (bit-for-bit equality with the unpipelined RTL was not checked); only bits/nbits come 3 cycles later (latency 4 cycles, was 1).
//   `transition` is taken from the undelayed word (latency 1) for the watchdog.  The phase
//   error is measured against phi as it is two words before it is applied (a drift of two
//   freq steps, < 0.005 sample at 500 ppm; kick change < 0.001 sample), and the first estimate
//   {m,0} is applied 3 words late, which the data delay again absorbs.
//   (First attempt without the data delay: lock-in unchanged, but one bit error at the sample
//   index rounding boundary in the -500 ppm / 0.3 UI / phase 3 case, because the index flip
//   moved by 3 words; the margin there is 0.3 sample, so the delay was moved to the data.)
//   A block needs at least 8 words (4 edges per word at most, 32 edges), so stages never overlap.
//   Cost: 12 flops for the data delay, no multipliers, three small register stages.
`default_nettype none
// OVERSAMPLE is documentation only: the 4-bit word and the 4 bins fix it to 4.
// verilator lint_off UNUSEDPARAM
module cdr_oversample #(
  parameter OVERSAMPLE   = 4,
  parameter BLK_EDGES    = 32,
  parameter ACQ_EDGES    = 8,
  parameter QUIET_CYCLES = 16,
  parameter KP_SHIFT     = 3,
  parameter KI_SHIFT     = 11
) (
  input  wire       clk,
  input  wire       rst,
  input  wire       samples_valid,  // 1: samples[3:0] is one new non-overlapping word
  input  wire [3:0] samples,
  output reg  [1:0] bits,
  output reg  [1:0] nbits,
  output reg        transition
);
  reg        prev3;                 // sample 3 of the previous word
  reg [6:0]  bin0, bin1, bin2, bin3;
  reg [7:0]  ecnt;
  reg [5:0]  quiet;
  reg        acq;
  reg [23:0] phi;                   // 4.20 fixed point, quarter samples
  reg [23:0] freq;                  // per-clock increment, same scaling
  reg [1:0]  ph_last;
  reg [3:0]  sd1, sd2, sd3;         // data path delayed by PIPE = 3 words (see header)
  reg        sd3_prev3;             // sample 3 of the word before sd3

  // pipeline registers (see header)
  reg               v1, acq1;       // S0 -> S1: a block closed
  reg signed [8:0]  vx1, vy1;
  reg               v2, acq2, m_ok2, sx2, sy2;   // S1 -> S2
  reg [2:0]         k2;
  reg               v3, acq3, m_ok3;             // S2 -> S3
  reg [3:0]         m3;
  reg [23:0]        pe3;

  // edges between consecutive samples, e[0] spans the word boundary
  wire [3:0] e = {samples[3] ^ samples[2], samples[2] ^ samples[1],
                  samples[1] ^ samples[0], samples[0] ^ prev3};
  wire [2:0] ne = {2'b00, e[0]} + {2'b00, e[1]} + {2'b00, e[2]} + {2'b00, e[3]};

  wire [6:0] nb0 = bin0 + {6'd0, e[0]};
  wire [6:0] nb1 = bin1 + {6'd0, e[1]};
  wire [6:0] nb2 = bin2 + {6'd0, e[2]};
  wire [6:0] nb3 = bin3 + {6'd0, e[3]};
  wire [7:0] en  = ecnt + {5'd0, ne};
  wire [7:0] thr = acq ? ACQ_EDGES[7:0] : BLK_EDGES[7:0];

  // S0 -> S1 vector of the closing block: x = b0-b2, y = b1-b3
  wire signed [8:0] vx0 = $signed({2'b00, nb0}) - $signed({2'b00, nb2});
  wire signed [8:0] vy0 = $signed({2'b00, nb1}) - $signed({2'b00, nb3});

  // S1: direction of the bin vector, 16 sectors of 22.5 degrees (11.25-degree
  // boundaries approximated by the ratios 1/5, 2/3, 3/2, 5), multiplications by shift-and-add
  wire [7:0] ax = vx1[8] ? (~vx1[7:0] + 8'd1) : vx1[7:0];
  wire [7:0] ay = vy1[8] ? (~vy1[7:0] + 8'd1) : vy1[7:0];
  wire [10:0] ax1 = {3'b000, ax};
  wire [10:0] ay1 = {3'b000, ay};
  wire [10:0] ax2 = ax1 << 1;
  wire [10:0] ay2 = ay1 << 1;
  wire [10:0] ax3 = ax2 + ax1;
  wire [10:0] ay3 = ay2 + ay1;
  wire [10:0] ax5 = (ax1 << 2) + ax1;
  wire [10:0] ay5 = (ay1 << 2) + ay1;
  reg  [2:0] k;
  always @* begin
    if      (ay5 < ax1)  k = 3'd0;     // ay*5 < ax
    else if (ay3 < ax2)  k = 3'd1;     // ay*3 < ax*2
    else if (ay2 < ax3)  k = 3'd2;     // ay*2 < ax*3
    else if (ay1 < ax5)  k = 3'd3;     // ay   < ax*5
    else                 k = 3'd4;
  end

  // S2: direction index from k and the quadrant
  reg [3:0] m;
  always @* begin
    if (!sx2 && !sy2)      m = {1'b0, k2};
    else if (sx2 && !sy2)  m = 4'd8 - {1'b0, k2};
    else if (sx2 && sy2)   m = 4'd8 + {1'b0, k2};
    else                   m = 4'd0 - {1'b0, k2};
  end
  wire [23:0] pe_u = {m, 20'd0} - phi;

  // S3: loop update from the registered phase error
  wire signed [23:0] pe3s   = pe3;
  wire signed [23:0] pe_kp = pe3s >>> KP_SHIFT;
  wire signed [23:0] pe_ki = pe3s >>> KI_SHIFT;

  // floor((q + 8) / 4) mod 4 with q = phi[23:20] (quarter samples)
  wire [1:0] ph  = phi[23:22] + 2'd2;
  wire [1:0] dph = ph - ph_last;
  wire       silent = (ne == 3'd0) && (quiet >= QUIET_CYCLES - 1);
  wire       eval   = !silent && (en >= thr);

  always @(posedge clk) begin
    if (rst) begin
      prev3 <= 1'b0; sd1 <= 4'd0; sd2 <= 4'd0; sd3 <= 4'd0; sd3_prev3 <= 1'b0; bin0 <= 7'd0; bin1 <= 7'd0; bin2 <= 7'd0; bin3 <= 7'd0;
      ecnt <= 8'd0; quiet <= 6'd0; acq <= 1'b1;
      phi <= 24'd0; freq <= 24'd0; ph_last <= 2'd2;
      bits <= 2'b00; nbits <= 2'd0; transition <= 1'b0;
      v1 <= 1'b0; acq1 <= 1'b0; vx1 <= 9'sd0; vy1 <= 9'sd0;
      v2 <= 1'b0; acq2 <= 1'b0; m_ok2 <= 1'b0; sx2 <= 1'b0; sy2 <= 1'b0; k2 <= 3'd0;
      v3 <= 1'b0; acq3 <= 1'b0; m_ok3 <= 1'b0; m3 <= 4'd0; pe3 <= 24'd0;
    end else if (!samples_valid) begin
      // no new word: hold all state, report nothing
      nbits      <= 2'd0;
      transition <= 1'b0;
    end else begin
      prev3      <= samples[3];
      sd1 <= samples; sd2 <= sd1; sd3 <= sd2; sd3_prev3 <= sd3[3];
      ph_last    <= ph;
      transition <= (ne != 3'd0);
      // sample selection on the word delayed by PIPE (= the S0..S3 latency of the loop)
      if (dph == 2'd1 && ph_last == 2'd3) begin
        nbits <= 2'd0; bits <= 2'b00;
      end else if (dph == 2'd3 && ph_last == 2'd0) begin
        nbits <= 2'd2; bits <= {sd3[3], sd3_prev3};
      end else begin
        nbits <= 2'd1; bits <= {1'b0, sd3[ph]};
      end
      // quiet detector
      if (ne != 3'd0) quiet <= 6'd0;
      else if (quiet < QUIET_CYCLES) quiet <= quiet + 6'd1;
      // S0: histogram, block close
      phi <= phi + freq;
      v1  <= 1'b0;
      if (silent) begin
        bin0 <= 7'd0; bin1 <= 7'd0; bin2 <= 7'd0; bin3 <= 7'd0;
        ecnt <= 8'd0; acq <= 1'b1;
      end else if (eval) begin
        bin0 <= 7'd0; bin1 <= 7'd0; bin2 <= 7'd0; bin3 <= 7'd0;
        ecnt <= 8'd0; acq <= 1'b0;
        v1 <= 1'b1; acq1 <= acq; vx1 <= vx0; vy1 <= vy0;
      end else begin
        bin0 <= nb0; bin1 <= nb1; bin2 <= nb2; bin3 <= nb3;
        ecnt <= en;
      end
      // S1: ratio comparison
      v2 <= v1; acq2 <= acq1; k2 <= k; sx2 <= vx1[8]; sy2 <= vy1[8];
      m_ok2 <= (vx1 != 9'sd0) || (vy1 != 9'sd0);
      // S2: direction and phase error
      v3 <= v2; acq3 <= acq2; m_ok3 <= m_ok2; m3 <= m; pe3 <= pe_u;
      // S3: loop update (overrides the free-running phi advance of this word)
      if (v3 && m_ok3) begin
        if (acq3) phi <= {m3, 20'd0};
        else begin
          phi  <= phi + freq + pe_kp;
          freq <= freq + pe_ki;
        end
      end
    end
  end
endmodule
// verilator lint_on UNUSEDPARAM
`default_nettype wire
