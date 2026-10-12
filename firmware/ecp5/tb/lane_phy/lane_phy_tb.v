// lane_phy_tb.v : testbench wrapper (NOT synthesised). The clocks.v simulation PLL model (clk_s
// 200 MHz, clk_c 50 MHz, coincident rising edges) drives two lane_phy instances on one pad,
// INVERT = 0 and 1, so test_lane_phy.py can check the 200 -> 50 MHz word handoff.
`default_nettype none
module lane_phy_tb (
  input  wire       clk25,
  input  wire       pad,
  output wire       clk_s,
  output wire       clk_c,
  output wire [3:0] s_plain,
  output wire [3:0] s_inv
);
  wire locked, rst25, rst_c, rst_s;
  clocks u_clk (.clk25(clk25), .btn_rst(1'b0), .clk_s(clk_s), .clk_c(clk_c), .locked(locked),
                .rst25(rst25), .rst_c(rst_c), .rst_s(rst_s));
  lane_phy #(.INVERT(0)) u_p0 (.lvds_p(pad), .clk_s(clk_s), .clk_c(clk_c), .samples(s_plain));
  lane_phy #(.INVERT(1)) u_p1 (.lvds_p(pad), .clk_s(clk_s), .clk_c(clk_c), .samples(s_inv));
  wire unused = &{1'b0, locked, rst25, rst_c, rst_s};
endmodule
`default_nettype wire
