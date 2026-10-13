// lane_rx.v : per-lane receive chain, PHY-agnostic (README section 5, section 9 row 4).
// Status: PROPOSED; simulated only (tb/lane_rx against model/linesim.py), never run on hardware.
//
// Chain: [polarity XOR] -> cdr_oversample -> comma_align -> dec_8b10b.  The decoder's
// code_err | disp_err goes back to comma_align's invalid_pulse (its "4 invalid in 16" realign rule,
// README s.5) and out as err_pulse.  realign_in (the watchdog LOS, already synchronised to clk)
// drives comma_align's realign; the "4 invalid in 16" rule inside comma_align and the polarity
// flip below are the only other realign sources.
//
// Ports (all clk domain, synchronous active-high rst)
//   samples[3:0], samples_valid  one 4-sample word per valid cycle, [0] oldest, as cdr_oversample
//                                (the top ties samples_valid high: lane_phy gives one word per clk_c)
//   realign_in      1 = drop alignment and search again (held high during LOS: the lane stays
//                   unaligned and unlocked until it is released)
//   data, is_k, data_valid   decoded stream, 1 symbol per data_valid pulse (dec_8b10b output;
//                   data_valid also pulses for invalid symbols with data=0)
//   err_pulse       code_err | disp_err, aligned with data_valid (same cycle)
//   err_pulse2      idle_mismatch, aligned with data_valid: a K28.5 whose successor is a valid symbol that
//                   is none of D16.2 (idle), K27.7 (frame start) or K28.5.  It counts as an error in
//                   lane_monitor (receiver_core ORs it with err_pulse).  It is what makes a lane that is
//                   polarity-inverted but not corrected (AUTO_INVERT = 0, or during the AUTO_INVERT
//                   detection) visible: 8b/10b is complement-symmetric (every code word inverted is
//                   another valid word, K28.5 turns into K28.5 of the other disparity, D16.2 (0x50)
//                   into D16.5 (0xB0)), so an inverted lane locks, shows zero code/disparity errors and
//                   every frame fails CRC/length silently (review finding F1).
//   pol_inv         current polarity flop `inv`: 1 = the incoming samples are inverted before the CDR
//   lock            aligned and LOCK_SYMBOLS consecutive valid symbols have been decoded since
//                   alignment was gained (any error while unlocked restarts the count); once set
//                   it is kept until alignment is lost (the
//                   comma_align rule INV_THRESH invalid in INV_WINDOW, or realign_in).  A single
//                   error therefore does not clear lock, it is counted in err_pulse.
//   transition      from the CDR (an edge in the word; for the watchdog)
//   aligned         comma_align aligned
//
// Polarity (F1, PROPOSED; simulated in tb/lane_rx and tb/system, not measured).  `inv` XORs every
// incoming sample, so the CDR, aligner and decoder see the corrected stream.  Its initial value is
// INIT_INVERT (the static LANE_INVERT of the top: 1 = the pad is LOW for a logic one, the same
// meaning as lane_phy INVERT).  Detection (AUTO_INVERT = 1): while aligned, idle is K28.5 D16.2.
// Every K28.5 followed by D16.2 clears the counter; every K28.5 followed by D16.5 (0xB0, the
// inverted D16.2) increments it; a K28.5 followed by a symbol with err_pulse set, K27.7 or K28.5
// leaves it unchanged.  When FLIP_COMMAS (8) consecutive commas were followed by D16.5 with none by
// D16.2, `inv` toggles, a realign pulse is sent to comma_align, dec_8b10b gets rd_reset and the
// counter clears.  A genuine correct-polarity stream never has a comma followed by D16.5, so a
// false flip needs 8 consecutive such corruptions with no good idle pair between them.
// Detection latency (documented, checked in tb/lane_rx and tb/system): the flip comes with the
// 8th idle pair after alignment, i.e. 8 pairs = 160 UI = 160 clk_c cycles = 3.2 us at 50 MHz after
// the first K28.5 is seen aligned (the first pair already counts); then the aligner needs at most
// one comma period (20 UI) plus the CDR/aligner pipeline (about 6 clocks) to realign, and lock needs
// LOCK_SYMBOLS further valid symbols.  While the wrong polarity is applied, each idle pair raises
// err_pulse2 (8 pulses in total before the flip).
//
// Parameters
//   LOCK_SYMBOLS  128 PROPOSED  consecutive valid symbols for lock (README s.5 said 16; the CDR
//                             frequency loop needs about 100 symbols to converge from reset, with 16
//                             errors appeared 42-64 symbols after lock in 8 of 24 runs of tb/lane_rx;
//                             1 to 255)
//   INV_THRESH    4   PROPOSED  README s.5 (passed to comma_align)
//   INV_WINDOW    16  PROPOSED  README s.5 (passed to comma_align)
//   AUTO_INVERT   1   PROPOSED  1 = automatic polarity detection as above; 0 = `inv` stays INIT_INVERT
//   INIT_INVERT   0   PROPOSED  initial value of `inv` after reset
//   FLIP_COMMAS   8   PROPOSED  consecutive inverted idle pairs that flip `inv` (1..15)
//   CDR parameters are the cdr_oversample defaults (tuned in tb/cdr_oversample).
// Latency from a word to data_valid: CDR 4 (cdr_oversample PIPE) + align 1 + decoder 1 clock.
`default_nettype none
module lane_rx #(
  parameter LOCK_SYMBOLS = 128,
  parameter INV_THRESH   = 4,
  parameter INV_WINDOW   = 16,
  parameter AUTO_INVERT  = 1,
  parameter INIT_INVERT  = 0,
  parameter FLIP_COMMAS  = 8
) (
  input  wire       clk,
  input  wire       rst,
  input  wire [3:0] samples,
  input  wire       samples_valid,
  input  wire       realign_in,
  output wire [7:0] data,
  output wire       is_k,
  output wire       data_valid,
  output wire       err_pulse,
  output wire       err_pulse2,
  output reg        pol_inv,
  output reg        lock,
  output wire       transition,
  output wire       aligned
);
  wire [1:0] bits, nbits;
  wire [9:0] symbol;
  wire       symbol_valid;
  wire       code_err, disp_err;
  reg        flip;          // 1 clk pulse: polarity just toggled
  reg        aligned_q;

  wire [3:0] samples_x = samples ^ {4{pol_inv}};

  cdr_oversample u_cdr (
    .clk(clk), .rst(rst), .samples_valid(samples_valid), .samples(samples_x),
    .bits(bits), .nbits(nbits), .transition(transition));

  comma_align #(.INV_THRESH(INV_THRESH), .INV_WINDOW(INV_WINDOW)) u_align (
    .clk(clk), .rst(rst), .realign(realign_in | flip), .invalid_pulse(err_pulse),
    .bits(bits), .nbits(nbits), .symbol(symbol), .symbol_valid(symbol_valid),
    .aligned(aligned));

  // disparity is meaningless across a realignment (F6)
  wire rd_reset = realign_in | flip | (aligned_q & ~aligned);

  dec_8b10b u_dec (
    .clk(clk), .rst(rst), .symbol(symbol), .symbol_valid(symbol_valid), .rd_reset(rd_reset),
    .data(data), .is_k(is_k), .data_valid(data_valid),
    .code_err(code_err), .disp_err(disp_err));

  assign err_pulse = code_err | disp_err;

  // ---- idle polarity check (F1) ----
  wire is_comma = is_k && (data == 8'hBC);          // K28.5
  wire is_d162  = !is_k && (data == 8'h50);         // D16.2 (idle second symbol)
  wire is_d165  = !is_k && (data == 8'hB0);         // D16.5 (D16.2 inverted)
  wire is_s     = is_k && (data == 8'hFB);          // K27.7 (frame start)
  reg        after_comma;                           // the previous valid symbol was a K28.5
  reg  [3:0] inv_cnt;
  wire       judge = data_valid && after_comma && !err_pulse;   // the symbol after a comma, valid
  assign err_pulse2 = judge && !is_d162 && !is_s && !is_comma;
  wire       do_flip = (AUTO_INVERT != 0) && judge && is_d165 && (inv_cnt == FLIP_COMMAS[3:0] - 4'd1);

  always @(posedge clk) begin
    flip      <= 1'b0;
    aligned_q <= aligned & ~rst;
    if (rst) begin
      pol_inv     <= (INIT_INVERT != 0);
      after_comma <= 1'b0;
      inv_cnt     <= 4'd0;
    end else if (!aligned) begin
      after_comma <= 1'b0;
      inv_cnt     <= 4'd0;
    end else begin
      if (data_valid) begin
        after_comma <= is_comma && !err_pulse;
        if (judge) begin
          if (is_d162) inv_cnt <= 4'd0;
          else if (is_d165 && inv_cnt != 4'hF) inv_cnt <= inv_cnt + 4'd1;
        end
      end
      if (do_flip) begin
        pol_inv     <= ~pol_inv;
        flip        <= 1'b1;
        inv_cnt     <= 4'd0;
        after_comma <= 1'b0;
      end
    end
  end

  // consecutive valid symbols since alignment was gained (saturates at LOCK_SYMBOLS)
  localparam CW = 8;
  reg [CW-1:0] run;
  always @(posedge clk) begin
    if (rst || !aligned) begin
      run  <= {CW{1'b0}};
      lock <= 1'b0;
    end else if (data_valid) begin
      if (err_pulse) run <= {CW{1'b0}};
      else if (run != LOCK_SYMBOLS[CW-1:0]) run <= run + {{(CW-1){1'b0}}, 1'b1};
      if (!err_pulse && run == LOCK_SYMBOLS[CW-1:0] - {{(CW-1){1'b0}}, 1'b1}) lock <= 1'b1;
    end
  end
endmodule
`default_nettype wire
