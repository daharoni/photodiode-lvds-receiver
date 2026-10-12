// clocks.v : EHXPLLL wrapper plus reset synchronisers (README section 4).
//
// 25 MHz in -> clk_s 200 MHz (CLKOP) and clk_c 100 MHz (CLKOS, phase 0), same VCO.
// Labels: PROPOSED (nothing measured on hardware). The PLL parameters below are the
// output of `ecppll -i 25 -o 200 --clkout1 100 -f /dev/stdout` (prjtrellis, oss-cad-suite
// 2026-10-12), pasted verbatim here:
//
//   sdiv 6
//   Pll parameters:
//   Refclk divisor: 1
//   Feedback divisor: 8
//   clkout0 divisor: 3
//   clkout0 frequency: 200 MHz
//   clkout1 divisor: 6
//   clkout1 frequency: 100 MHz
//   clkout1 phase shift: 0 degrees
//   VCO frequency: 600
//   (generated module "pll": EHXPLLL with CLKI_DIV=1, CLKOP_DIV=3, CLKOS_DIV=6,
//    CLKFB_DIV=8, FEEDBK_PATH="CLKOP", CLKOP_CPHASE=1, CLKOS_CPHASE=1, FPHASE=0,
//    ICP_CURRENT=12, LPF_RESISTOR=8, MFG_ENABLE_FILTEROPAMP=1, MFG_GMCREF_SEL=2)
//
// NOTE: the VCO is 600 MHz (25 MHz x 8 x ... = 200 MHz x CLKOP_DIV 3), not 800 MHz as
// README section 4 says; 600 MHz is inside the 400-800 MHz VCO range (DS Table 3.23).
//
// Reset polarity: btn[1] is FIRE1, active HIGH (ulx3s_v20.lpf line 55: PULLMODE=DOWN, a
// pressed button pulls the pin up). Each reset output (rst25, rst_c, rst_s) asserts
// asynchronously when locked=0 or btn_rst=1 and deasserts synchronously to its own clock
// through a 2-flop chain. All three include ~locked (so rst25 also holds while the PLL is
// not locked). btn_rst is not debounced.
//
// Simulation: under `ifdef SYNTHESIS the EHXPLLL is instantiated; otherwise a behavioural
// model makes clk_s = 8x and clk_c = 4x of clk25 (Icarus), locked after 16 clk25 cycles.
// Only this file and lane_phy.v may hold vendor primitives (README s.1).
`default_nettype none

module clocks (
    input  wire clk25,
    input  wire btn_rst,   // active high (FIRE1)
    output wire clk_s,     // 200 MHz
    output wire clk_c,     // 100 MHz
    output wire locked,
    output wire rst25,     // synchronous to clk25, high while reset
    output wire rst_c,     // synchronous to clk_c
    output wire rst_s      // synchronous to clk_s
);

`ifdef SYNTHESIS
    (* FREQUENCY_PIN_CLKI="25" *)
    (* FREQUENCY_PIN_CLKOP="200" *)
    (* FREQUENCY_PIN_CLKOS="100" *)
    (* ICP_CURRENT="12" *) (* LPF_RESISTOR="8" *) (* MFG_ENABLE_FILTEROPAMP="1" *) (* MFG_GMCREF_SEL="2" *)
    EHXPLLL #(
        .PLLRST_ENA("DISABLED"),
        .INTFB_WAKE("DISABLED"),
        .STDBY_ENABLE("DISABLED"),
        .DPHASE_SOURCE("DISABLED"),
        .OUTDIVIDER_MUXA("DIVA"),
        .OUTDIVIDER_MUXB("DIVB"),
        .OUTDIVIDER_MUXC("DIVC"),
        .OUTDIVIDER_MUXD("DIVD"),
        .CLKI_DIV(1),
        .CLKOP_ENABLE("ENABLED"),
        .CLKOP_DIV(3),
        .CLKOP_CPHASE(1),
        .CLKOP_FPHASE(0),
        .CLKOS_ENABLE("ENABLED"),
        .CLKOS_DIV(6),
        .CLKOS_CPHASE(1),
        .CLKOS_FPHASE(0),
        .FEEDBK_PATH("CLKOP"),
        .CLKFB_DIV(8)
    ) pll_i (
        .RST(1'b0),
        .STDBY(1'b0),
        .CLKI(clk25),
        .CLKOP(clk_s),
        .CLKOS(clk_c),
        .CLKOS2(),
        .CLKOS3(),
        .CLKFB(clk_s),
        .CLKINTFB(),
        .PHASESEL0(1'b0),
        .PHASESEL1(1'b0),
        .PHASEDIR(1'b1),
        .PHASESTEP(1'b1),
        .PHASELOADREG(1'b1),
        .PLLWAKESYNC(1'b0),
        .ENCLKOP(1'b0),
        .LOCK(locked),
        .ENCLKOS(),
        .ENCLKOS2(),
        .ENCLKOS3(),
        .INTLOCK(),
        .REFCLK()
    );
`else
    // Behavioural model (simulation only; `initial` is allowed here, not synthesised).
    // Half periods assume the 25 MHz input has a 40 ns period.
    /* verilator lint_off PROCASSINIT */
    reg clk_s_r = 1'b0;
    reg clk_c_r = 1'b0;
    reg lock_r  = 1'b0;
    reg [4:0] lock_cnt = 5'd0;
    always #2.5 clk_s_r = ~clk_s_r;
    always #5.0 clk_c_r = ~clk_c_r;
    always @(posedge clk25) begin
        if (lock_cnt != 5'd16) lock_cnt <= lock_cnt + 5'd1;
        else lock_r <= 1'b1;
    end
    /* verilator lint_on PROCASSINIT */
    assign clk_s  = clk_s_r;
    assign clk_c  = clk_c_r;
    assign locked = lock_r;
`endif

    // Reset request: PLL not locked or button pressed.
    wire rst_req = ~locked | btn_rst;

    // 2-flop reset synchronisers: asynchronous assert, synchronous release.
    reg [1:0] r25, rc, rs;  // no initial values: rst_req is high at power-up (locked=0)
    always @(posedge clk25 or posedge rst_req) begin
        if (rst_req) r25 <= 2'b11; else r25 <= {r25[0], 1'b0};
    end
    always @(posedge clk_c or posedge rst_req) begin
        if (rst_req) rc <= 2'b11; else rc <= {rc[0], 1'b0};
    end
    always @(posedge clk_s or posedge rst_req) begin
        if (rst_req) rs <= 2'b11; else rs <= {rs[0], 1'b0};
    end
    assign rst25 = r25[1];
    assign rst_c = rc[1];
    assign rst_s = rs[1];
endmodule
`default_nettype wire
