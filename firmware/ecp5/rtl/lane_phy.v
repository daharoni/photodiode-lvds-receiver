// lane_phy.v : ECP5 LVDS capture for one lane (README section 4). PROPOSED, not run on hardware.
//
// Parameters
//   INVERT : 1 inverts the lane (the gp pad carries SSTXp, high for a logic one,
//            README s.2 Polarity); 0 passes the pad level through.
//
// Ports
//   lvds_p   : the gp pad. The differential pair is declared in the LPF with IO_TYPE=LVDS
//              on this pin only; the gn pin is NOT a port of the design (see constraints/
//              ulx3s.lpf and the findings in the build report: nextpnr-ecp5 claims the
//              partner pad itself).
//   clk_s    : 200 MHz sample clock.     clk_c : 50 MHz core clock, same PLL, phase 0.
//   samples  : [3:0], samples[0] OLDEST, samples[3] newest, registered on clk_c. One
//              NON-OVERLAPPING word per clk_c cycle: 4 samples = 20 ns = 1 UI, every
//              sample appears in exactly one word, none is skipped or repeated.
//              (This replaces the earlier 100 MHz sliding window and its word_ph enable.)
//
// 200 -> 50 MHz handoff (PROPOSED; simulated in tb/lane_phy, not measured):
//   clk_s and clk_c come from the same EHXPLLL VCO with clk_c = clk_s / 4 at phase 0 (clocks.v),
//   so every clk_c rising edge coincides with every 4th clk_s rising edge.  Let the clk_s edges
//   be E(n) and p(n) the pad level at E(n).  The chain c0..c3 shifts on every clk_s edge:
//     after E(n):  c0 = p(n), c1 = p(n-1), c2 = p(n-2), c3 = p(n-3).
//   A flop that samples on the coincident edge E(m) sees the values from BEFORE that edge (the
//   same-edge flop-to-flop transfer, one clk_s period of setup = 5 ns), i.e. the state after
//   E(m-1):  c3 = p(m-4) (oldest), c2 = p(m-3), c1 = p(m-2), c0 = p(m-1) (newest).  The next clk_c
//   edge is E(m+4) and registers p(m)..p(m+3): the words are p(m-4..m-1), p(m..m+3), ... back to
//   back, no overlap, no gap.  Hence samples = {c0, c1, c2, c3} (samples[0] = c3 = oldest).
//   The word grid is fixed by the clock phase (m = 0 mod 4), so there is no word_ph and no
//   phase ambiguity: lane skew relative to the grid is absorbed by the CDR.
//   Risk (UNRESOLVED until a bitstream runs): the transfer relies on the clk_c edge landing on
//   the clk_s edge; the 5 ns path is analysed by nextpnr, a hold check against global-clock
//   skew is not (documented in README s.4 as a bench item).  If the PLL phase were off by one
//   clk_s period the words would still be consecutive and non-overlapping, only the grid moves.
//
// Only flops live in the 200 MHz domain (the INVERT xor is applied in the 50 MHz register).
// Sampling: c0 is the capture flop (could be absorbed in the IO register; not forced),
// c1/c2 the metastability stages, c3 the oldest sample of the word.
`default_nettype none

module lane_phy #(
    parameter INVERT = 1
) (
    input  wire       lvds_p,
    input  wire       clk_s,
    input  wire       clk_c,
    output reg  [3:0] samples
);
    reg c0, c1, c2, c3;   // 200 MHz domain: flops only

    always @(posedge clk_s) begin
        c0 <= lvds_p;
        c1 <= c0;
        c2 <= c1;
        c3 <= c2;
    end

    // 50 MHz: c3 is oldest ... c0 newest
    always @(posedge clk_c) begin
        samples <= {c0, c1, c2, c3} ^ {4{(INVERT != 0)}};
    end
endmodule
`default_nettype wire
