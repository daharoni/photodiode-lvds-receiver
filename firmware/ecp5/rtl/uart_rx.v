// uart_rx.v : 8N1 UART receiver, mid-bit sampling (one sample per bit at the bit centre,
// no 16x majority vote; a glitch shorter than half a bit on the start bit is rejected
// by re-checking the line at the centre of the start bit).
// Parameters: CLK_HZ, BAUD. Bit timing uses the same phase accumulator as uart_tx
// (acc += BAUD per clock, tick at acc >= CLK_HZ). On the falling edge of the
// (2-flop synchronised) rxd the accumulator is loaded with CLK_HZ/2 so the first tick
// lands at the middle of the start bit and later ticks at the middle of each bit.
// Outputs: valid = 1-clock pulse with data when the stop bit has been sampled; frame_err
// is a 1-clock pulse (together with valid) if the stop bit was low. Synchronous active-high rst.
`default_nettype none

module uart_rx #(
    parameter CLK_HZ = 100_000_000,
    parameter BAUD   = 115_200
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       rxd,
    output reg  [7:0] data,
    output reg        valid,
    output reg        frame_err
);
    reg        s1, s2;
    reg        busy;
    reg [3:0]  cnt;     // sampled so far: 0 = start bit check, 1..8 = data, 9 = stop
    reg [7:0]  sh;
    reg [31:0] acc;

    wire [31:0] acc_n = acc + BAUD;
    wire        tick  = (acc_n >= CLK_HZ);

    always @(posedge clk) begin
        s1 <= rxd;
        s2 <= s1;
        valid     <= 1'b0;
        frame_err <= 1'b0;
        if (rst) begin
            busy <= 1'b0;
            cnt  <= 4'd0;
            sh   <= 8'd0;
            acc  <= 32'd0;
            data <= 8'd0;
            s1   <= 1'b1;
            s2   <= 1'b1;
        end else if (!busy) begin
            if (!s2) begin
                busy <= 1'b1;
                cnt  <= 4'd0;
                acc  <= CLK_HZ / 2;
            end
        end else begin
            acc <= tick ? (acc_n - CLK_HZ) : acc_n;
            if (tick) begin
                if (cnt == 4'd0) begin
                    if (s2) busy <= 1'b0;       // start bit not low at its centre: glitch
                    else    cnt  <= 4'd1;
                end else if (cnt <= 4'd8) begin
                    sh  <= {s2, sh[7:1]};       // LSB first
                    cnt <= cnt + 4'd1;
                end else begin
                    data      <= sh;
                    valid     <= 1'b1;
                    frame_err <= ~s2;
                    busy      <= 1'b0;
                end
            end
        end
    end
endmodule
`default_nettype wire
