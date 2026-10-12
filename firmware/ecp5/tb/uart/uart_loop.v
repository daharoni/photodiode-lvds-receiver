// Test wrapper: uart_tx -> uart_rx. BAUD is set from the cocotb run through a macro (default 1 Mbaud).
`default_nettype none
`ifndef TB_BAUD
 `define TB_BAUD 1000000
`endif
module uart_loop (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] tx_data,
    input  wire       tx_valid,
    output wire       tx_ready,
    output wire       txd,
    input  wire       force_low,   // test hook: drive the line low (break) to provoke a framing error
    output wire [7:0] rx_data,
    output wire       rx_valid,
    output wire       rx_frame_err
);
    uart_tx #(.CLK_HZ(100_000_000), .BAUD(`TB_BAUD)) u_tx (
        .clk(clk), .rst(rst), .data(tx_data), .valid(tx_valid), .ready(tx_ready), .txd(txd));
    uart_rx #(.CLK_HZ(100_000_000), .BAUD(`TB_BAUD)) u_rx (
        .clk(clk), .rst(rst), .rxd(txd & ~force_low), .data(rx_data), .valid(rx_valid), .frame_err(rx_frame_err));
endmodule
`default_nettype wire
