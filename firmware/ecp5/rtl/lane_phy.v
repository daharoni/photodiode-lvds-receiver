// lane_phy.v : ECP5 LVDS capture for one lane (README section 4). PROPOSED, not run on hardware.
//
// Parameters
//   INVERT : polarity of the pad.  INVERT = 1 means the pad is LOW for a logic one: every sample is
//            inverted so that samples carry the logic level (1 = logic one).  INVERT = 0 passes the
//            pad level through (pad HIGH = logic one).  On the cable SSTXp is HIGH for a logic one
//            (README s.2, docs/schematic/connector.md); which pin of the pair the breakout routes
//            to the gp pad is not designed yet, so the polarity of a lane is not known: ulx3s_top
//            leaves this at 0 and lane_rx corrects the polarity automatically (AUTO_INVERT, review
//            finding F1; the static LANE_INVERT of the top is only the initial value there).
//            INVERT stays here for tb/lane_phy and for a fixed-polarity build.
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
//   so every clk_c rising edge coincides with every 4th clk_s rising edge.  Let the clk_s rising
//   edges be E(n) and p(n) the pad level at E(n).  The chain c0..c3 shifts on every clk_s rising edge:
//     after E(n):  c0 = p(n), c1 = p(n-1), c2 = p(n-2), c3 = p(n-3).
//   Review finding F3: capturing c0..c3 directly on the clk_c edge E(m) is a same-edge transfer
//   between two clock trees whose skew nextpnr does not analyse (hold depends on it).  So a
//   second stage n0..n3 captures c0..c3 on the clk_s FALLING edge F(m-1) = E(m-1) + 2.5 ns; the
//   clk_c word register then reads n0..n3 on E(m).  Both transfers have half a clk_s period
//   (2.5 ns) of setup AND of hold margin (c changes only at rising edges, n only at falling
//   edges, clk_c rises with a rising edge), independent of the PLL phase setting and of clock skew
//   up to that margin.  Only a gross error (clk_c phase moved by more than a quarter of clk_s period)
//   would break it.
//   Words: F(m-1) lies after E(m-1) and before E(m); at F(m-1) the chain holds the state after E(m-1):
//     c0 = p(m-1) (newest), c1 = p(m-2), c2 = p(m-3), c3 = p(m-4) (oldest),
//   so n0..n3 = p(m-1), p(m-2), p(m-3), p(m-4) and the word registered at E(m) is p(m-4..m-1).  The
//   next clk_c edge is E(m+4) and registers p(m)..p(m+3): back to back, no overlap, no gap, the same
//   words as the direct capture would give.  Hence samples = {n0, n1, n2, n3} (samples[0] = n3 =
//   oldest).  The word grid is fixed by the clock phase (m = 0 mod 4), so there is no word_ph and no
//   phase ambiguity: lane skew relative to the grid is absorbed by the CDR.
//   Risk (UNRESOLVED until a bitstream runs): that clk_c really is phase-aligned to clk_s (clocks.v
//   documents the PLL settings; the +-2.5 ns margin is what this stage buys), and that nextpnr/the
//   ECP5 map the negedge flops onto slice flops with the clock inversion (it reported timing for
//   the build recorded in the report that added this stage, see README s.0).  If the PLL phase
//   were off by one clk_s period the words would still be consecutive and non-overlapping, only the
//   grid moves.
//
// Only flops live in the 200 MHz domain (posedge c0..c3, negedge n0..n3; the INVERT xor is applied in
// the 50 MHz register).  Sampling: c0 is the capture flop (could be absorbed in the IO register; not
// forced), c1/c2 the metastability stages, c3 the oldest sample of the word.
`default_nettype none

module lane_phy #(
    parameter INVERT = 1
) (
    input  wire       lvds_p,
    input  wire       clk_s,
    input  wire       clk_c,
    output reg  [3:0] samples
);
    reg c0, c1, c2, c3;   // 200 MHz domain, rising edge: flops only
    reg n0, n1, n2, n3;   // 200 MHz domain, falling edge: half-period retiming stage (F3)

    always @(posedge clk_s) begin
        c0 <= lvds_p;
        c1 <= c0;
        c2 <= c1;
        c3 <= c2;
    end

    always @(negedge clk_s) begin
        n0 <= c0;
        n1 <= c1;
        n2 <= c2;
        n3 <= c3;
    end

    // 50 MHz: n3 is oldest ... n0 newest
    always @(posedge clk_c) begin
        samples <= {n0, n1, n2, n3} ^ {4{(INVERT != 0)}};
    end
endmodule
`default_nettype wire
