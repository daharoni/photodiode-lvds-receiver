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
//   clk_s    : 200 MHz sample clock.     clk_c : 100 MHz core clock, same PLL, phase 0.
//   rst_c    : synchronous reset, clk_c domain (only the word-phase flop uses it).
//   samples  : [3:0], samples[0] OLDEST, samples[3] newest, registered on clk_c. It is a
//              SLIDING window of the last four 200 MS/s samples, refreshed every clk_c cycle,
//              so consecutive words overlap by two samples. 4 samples = 20 ns = 1 UI.
//   word_ph  : toggles every clk_c cycle (free running after reset). A word taken when
//              word_ph has a fixed value is non-overlapping (new word every 20 ns = one UI,
//              50 MHz word rate); consumers that want one word per UI use that enable.
//              Which phase is arbitrary but constant until reset.
//
// Clock-domain assumption (documented, not constrained further): clk_s and clk_c come
// from the same EHXPLLL VCO, clk_c = clk_s / 2 with phase 0, so every clk_c rising edge
// coincides with a clk_s rising edge. The only 200 MHz -> 100 MHz crossing is the
// direct read of flops c0..c3 by the clk_c register; timing analysis treats it as a
// 5 ns (one clk_s period) path and nextpnr reports it as such. Only flops live in the
// 200 MHz domain (the INVERT xor is applied in the 100 MHz register).
//
// Sampling: c0 is the capture flop (could be absorbed in the IO register; not forced),
// c1/c2 the metastability stages, c3 the oldest sample of the window.
`default_nettype none

module lane_phy #(
    parameter INVERT = 1
) (
    input  wire       lvds_p,
    input  wire       clk_s,
    input  wire       clk_c,
    input  wire       rst_c,
    output reg  [3:0] samples,
    output reg        word_ph
);
    reg c0, c1, c2, c3;   // 200 MHz domain: flops only

    always @(posedge clk_s) begin
        c0 <= lvds_p;
        c1 <= c0;
        c2 <= c1;
        c3 <= c2;
    end

    // 100 MHz: c3 is oldest ... c0 newest
    always @(posedge clk_c) begin
        samples <= {c0, c1, c2, c3} ^ {4{(INVERT != 0)}};
        if (rst_c) word_ph <= 1'b0;
        else       word_ph <= ~word_ph;
    end
endmodule
`default_nettype wire
