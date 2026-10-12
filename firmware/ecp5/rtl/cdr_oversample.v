// cdr_oversample.v : 4x blind-oversampling clock/data recovery, pure logic.
//
// README section 5 (interface), section 4 (clocking: one 4-bit word per
// valid cycle (every 2nd 100 MHz cycle in the lane, see samples_valid), 4 samples
// per 20 ns UI).  Status: PROPOSED; simulated only
// (tb/cdr_oversample against model/linesim.py), never run on hardware.
//
// Interface (exactly README section 5):
//   samples_valid 1 when samples[3:0] carries a NEW word (spec correction by the
//                 coordinator: at 200 MS/s a non-overlapping word arrives every
//                 other 100 MHz cycle, so the real condition is a valid every
//                 2nd clk; constant 1 also works).  0: all state holds,
//                 nbits = 0, transition = 0.
//   samples[3:0]  4 line samples per valid word, [0] oldest
//   bits[1:0]     recovered bits, bits[0] first in time; nbits says how many
//   nbits[1:0]    0, 1 or 2 bits valid this cycle (registered, 1 cycle latency)
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
// first few bits after reset are not meaningful.  Latency: 1 cycle.
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

  // direction of the bin vector, 16 sectors of 22.5 degrees (11.25-degree
  // boundaries approximated by the ratios 1/5, 2/3, 3/2, 5)
  wire signed [8:0] vx = $signed({2'b00, nb0}) - $signed({2'b00, nb2});
  wire signed [8:0] vy = $signed({2'b00, nb1}) - $signed({2'b00, nb3});
  wire [7:0] ax = vx[8] ? (~vx[7:0] + 8'd1) : vx[7:0];
  wire [7:0] ay = vy[8] ? (~vy[7:0] + 8'd1) : vy[7:0];
  wire [10:0] ax2 = {3'b000, ax};
  wire [10:0] ay2 = {3'b000, ay};
  reg  [2:0] k;
  always @* begin
    if      (ay2 * 5 < ax2)         k = 3'd0;
    else if (ay2 * 3 < ax2 * 2)     k = 3'd1;
    else if (ay2 * 2 < ax2 * 3)     k = 3'd2;
    else if (ay2 < ax2 * 5)         k = 3'd3;
    else                            k = 3'd4;
  end
  reg [3:0] m;
  always @* begin
    if (!vx[8] && !vy[8])      m = {1'b0, k};
    else if (vx[8] && !vy[8])  m = 4'd8 - {1'b0, k};
    else if (vx[8] && vy[8])   m = 4'd8 + {1'b0, k};
    else                       m = 4'd0 - {1'b0, k};
  end
  wire m_ok = (vx != 9'sd0) || (vy != 9'sd0);

  wire [23:0] pe_u = {m, 20'd0} - phi;
  wire signed [23:0] pe = pe_u;
  wire signed [23:0] pe_kp = pe >>> KP_SHIFT;
  wire signed [23:0] pe_ki = pe >>> KI_SHIFT;

  // floor((q + 8) / 4) mod 4 with q = phi[23:20] (quarter samples)
  wire [1:0] ph  = phi[23:22] + 2'd2;
  wire [1:0] dph = ph - ph_last;
  wire       silent = (ne == 3'd0) && (quiet >= QUIET_CYCLES - 1);
  wire       eval   = !silent && (en >= thr);

  always @(posedge clk) begin
    if (rst) begin
      prev3 <= 1'b0; bin0 <= 7'd0; bin1 <= 7'd0; bin2 <= 7'd0; bin3 <= 7'd0;
      ecnt <= 8'd0; quiet <= 6'd0; acq <= 1'b1;
      phi <= 24'd0; freq <= 24'd0; ph_last <= 2'd2;
      bits <= 2'b00; nbits <= 2'd0; transition <= 1'b0;
    end else if (!samples_valid) begin
      // no new word: hold all state, report nothing
      nbits      <= 2'd0;
      transition <= 1'b0;
    end else begin
      prev3      <= samples[3];
      ph_last    <= ph;
      transition <= (ne != 3'd0);
      // sample selection
      if (dph == 2'd1 && ph_last == 2'd3) begin
        nbits <= 2'd0; bits <= 2'b00;
      end else if (dph == 2'd3 && ph_last == 2'd0) begin
        nbits <= 2'd2; bits <= {samples[3], prev3};
      end else begin
        nbits <= 2'd1; bits <= {1'b0, samples[ph]};
      end
      // quiet detector
      if (ne != 3'd0) quiet <= 6'd0;
      else if (quiet < QUIET_CYCLES) quiet <= quiet + 6'd1;
      // histogram, phase loop
      phi <= phi + freq;
      if (silent) begin
        bin0 <= 7'd0; bin1 <= 7'd0; bin2 <= 7'd0; bin3 <= 7'd0;
        ecnt <= 8'd0; acq <= 1'b1;
      end else if (eval) begin
        bin0 <= 7'd0; bin1 <= 7'd0; bin2 <= 7'd0; bin3 <= 7'd0;
        ecnt <= 8'd0; acq <= 1'b0;
        if (m_ok) begin
          if (acq) phi <= {m, 20'd0};
          else begin
            phi  <= phi + freq + pe_kp;
            freq <= freq + pe_ki;
          end
        end
      end else begin
        bin0 <= nb0; bin1 <= nb1; bin2 <= nb2; bin3 <= nb3;
        ecnt <= en;
      end
    end
  end
endmodule
// verilator lint_on UNUSEDPARAM
`default_nettype wire
