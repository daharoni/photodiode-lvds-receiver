// lane_rx.v : per-lane receive chain, PHY-agnostic (README section 5, section 9 row 4).
// Status: PROPOSED; simulated only (tb/lane_rx against model/linesim.py), never run on hardware.
//
// Chain: cdr_oversample -> comma_align -> dec_8b10b.  The decoder's code_err | disp_err goes
// back to comma_align's invalid_pulse (its "4 invalid in 16" realign rule, README s.5) and out
// as err_pulse.  realign_in (the watchdog LOS, already synchronised to clk) drives comma_align's
// realign; the "4 invalid in 16" rule inside comma_align is the only other realign source.
//
// Ports (all clk domain, synchronous active-high rst)
//   samples[3:0], samples_valid  one 4-sample word per valid cycle, [0] oldest, as cdr_oversample
//                                (the top ties samples_valid high: lane_phy gives one word per clk_c)
//   realign_in      1 = drop alignment and search again (held high during LOS: the lane stays
//                   unaligned and unlocked until it is released)
//   data, is_k, data_valid   decoded stream, 1 symbol per data_valid pulse (dec_8b10b output;
//                   data_valid also pulses for invalid symbols with data=0)
//   err_pulse       code_err | disp_err, aligned with data_valid (same cycle)
//   lock            aligned and LOCK_SYMBOLS consecutive valid symbols have been decoded since
//                   alignment was gained (any error while unlocked restarts the count); once set
//                   it is kept until alignment is lost (the
//                   comma_align rule INV_THRESH invalid in INV_WINDOW, or realign_in).  A single
//                   error therefore does not clear lock, it is counted in err_pulse.
//   transition      from the CDR (an edge in the word; for the watchdog)
//   aligned         comma_align aligned
//
// Parameters
//   LOCK_SYMBOLS  128 PROPOSED  consecutive valid symbols for lock (README s.5 said 16; the CDR
//                             frequency loop needs about 100 symbols to converge from reset, with 16
//                             errors appeared 42-64 symbols after lock in 8 of 24 runs of tb/lane_rx;
//                             1 to 255)
//   INV_THRESH    4   PROPOSED  README s.5 (passed to comma_align)
//   INV_WINDOW    16  PROPOSED  README s.5 (passed to comma_align)
//   CDR parameters are the cdr_oversample defaults (tuned in tb/cdr_oversample).
// Latency from a word to data_valid: CDR 4 (cdr_oversample PIPE) + align 1 + decoder 1 clock.
`default_nettype none
module lane_rx #(
  parameter LOCK_SYMBOLS = 128,
  parameter INV_THRESH   = 4,
  parameter INV_WINDOW   = 16
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
  output reg        lock,
  output wire       transition,
  output wire       aligned
);
  wire [1:0] bits, nbits;
  wire [9:0] symbol;
  wire       symbol_valid;
  wire       code_err, disp_err;

  cdr_oversample u_cdr (
    .clk(clk), .rst(rst), .samples_valid(samples_valid), .samples(samples),
    .bits(bits), .nbits(nbits), .transition(transition));

  comma_align #(.INV_THRESH(INV_THRESH), .INV_WINDOW(INV_WINDOW)) u_align (
    .clk(clk), .rst(rst), .realign(realign_in), .invalid_pulse(err_pulse),
    .bits(bits), .nbits(nbits), .symbol(symbol), .symbol_valid(symbol_valid),
    .aligned(aligned));

  dec_8b10b u_dec (
    .clk(clk), .rst(rst), .symbol(symbol), .symbol_valid(symbol_valid),
    .data(data), .is_k(is_k), .data_valid(data_valid),
    .code_err(code_err), .disp_err(disp_err));

  assign err_pulse = code_err | disp_err;

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
