// ulx3s_top.v : ULX3S board top, v0 bring-up (README sections 1, 2, 4, 7). PROPOSED; not run on hardware.
//
// Parameters
//   N_LANES     : number of LVDS lane inputs (default 7: gp/gn 8,9,10,18,19,20,21, README s.2).
//                 constraints/ulx3s.lpf only defines 7 lanes; more need more LPF lines.
//   LANE_INVERT : per-lane polarity bit vector (bit i for lane i), default all ones.
// Macro (command line / Makefile): GIT_SHA = quoted string of at most 8 characters
//   (default "dev"), printed in the banner.
//
// Ports (names match constraints/ulx3s.lpf)
//   clk_25mhz            independent 25 MHz oscillator (G2)
//   btn[6:0]             only btn[1] (FIRE1, active high) is used: reset of everything but the PLL
//   led[7:0]             led[7] 1 Hz blink from clk25; led[6] PLL locked;
//                        led[5:0] lanes 0-5: 100 ms stretched TRANSITION activity of samples
//                        (README says "samples[0] stretched"; a stretched level would sit on
//                        for any stuck-high line, so the stretched event is a change between
//                        samples[0] and samples[1]. Documented deviation.)
//   lane_p[N_LANES-1:0]  LVDS lane inputs. ONLY the positive pad is a port: the LPF gives it
//                        IO_TYPE=LVDS and nextpnr-ecp5 claims the partner pad itself.
//   tp_p, tp_n           test pattern outputs on ULX3S gp[0]/gn[0] (B11/C11): v0 placeholder,
//                        1 MHz square from clk_c (tp_n = complement). Real frame_tx later.
//   ftdi_rxd             FPGA TX to the FT231X, 115200 8N1: banner once per second
//   ftdi_txd             FPGA RX from the FT231X (unused in v0)
//   wifi_gpio16          FPGA TX to ESP32 Serial1 RX, 1 Mbaud: same banner (README s.2, UNRESOLVED
//                        which ESP32 module is fitted)
//   wifi_gpio17          FPGA RX from ESP32 Serial1 TX (unused in v0)
// wifi_en is not driven (ESP32 left to its own default).
//
// Banner: "ULX3S receiver v0 build <sha> lanes=<N>\r\n" (NUL padding of the sha and of the
// lane number is skipped, not sent). The UARTs run on clk25 so only rst25 is needed.
`default_nettype none
`ifndef GIT_SHA
 `define GIT_SHA "dev"
`endif

module ulx3s_top #(
    parameter N_LANES     = 7,
    parameter LANE_INVERT = {N_LANES{1'b1}}
) (
    input  wire               clk_25mhz,
    input  wire [6:0]         btn,
    output wire [7:0]         led,
    input  wire [N_LANES-1:0] lane_p,
    output wire               tp_p,
    output wire               tp_n,
    output wire               ftdi_rxd,
    input  wire               ftdi_txd,
    output wire               wifi_gpio16,
    input  wire               wifi_gpio17
);
    wire clk_s, clk_c, locked, rst25, rst_c, rst_s;

    clocks u_clocks (
        .clk25(clk_25mhz), .btn_rst(btn[1]),
        .clk_s(clk_s), .clk_c(clk_c), .locked(locked),
        .rst25(rst25), .rst_c(rst_c), .rst_s(rst_s)
    );

    // ---- lanes -------------------------------------------------------------
    wire [3:0] samples [0:N_LANES-1];
    wire       word_ph [0:N_LANES-1];
    genvar i;
    generate
        for (i = 0; i < N_LANES; i = i + 1) begin : g_lane
            lane_phy #(.INVERT(LANE_INVERT[i])) u_phy (
                .lvds_p(lane_p[i]), .clk_s(clk_s), .clk_c(clk_c), .rst_c(rst_c),
                .samples(samples[i]), .word_ph(word_ph[i])
            );
        end
    endgenerate

    // ---- activity stretchers (clk_c, 100 ms = 10,000,000 cycles) ----------
    localparam STRETCH = 10_000_000;
    reg [N_LANES-1:0] act;
    generate
        for (i = 0; i < N_LANES; i = i + 1) begin : g_act
            reg [23:0] cnt;
            wire edge_seen = samples[i][0] ^ samples[i][1];
            always @(posedge clk_c) begin
                if (rst_c) begin
                    cnt <= 24'd0;
                    act[i] <= 1'b0;
                end else begin
                    if (edge_seen) cnt <= STRETCH;
                    else if (cnt != 24'd0) cnt <= cnt - 24'd1;
                    act[i] <= (cnt != 24'd0);
                end
            end
        end
    endgenerate
    wire [31:0] act32 = {{(32-N_LANES){1'b0}}, act};

    // ---- 1 s tick and 1 Hz blink on the independent clock ------------------
    reg [24:0] sec_cnt;
    wire       sec_tick = (sec_cnt == 25'd24_999_999);
    always @(posedge clk_25mhz) begin
        if (rst25 || sec_tick) sec_cnt <= 25'd0;
        else                   sec_cnt <= sec_cnt + 25'd1;
    end
    // blink1 toggles every half second (true 1 Hz square)
    reg [23:0] half_cnt;
    reg        blink1;
    always @(posedge clk_25mhz) begin
        if (rst25) begin
            half_cnt <= 24'd0;
            blink1   <= 1'b0;
        end else if (half_cnt == 24'd12_499_999) begin
            half_cnt <= 24'd0;
            blink1   <= ~blink1;
        end else begin
            half_cnt <= half_cnt + 24'd1;
        end
    end

    assign led[7]   = blink1;
    assign led[6]   = locked;
    assign led[5:0] = act32[5:0];

    // ---- test pattern placeholder: 1 MHz square from clk_c -----------------
    reg [5:0] tp_cnt;
    reg       tp;
    always @(posedge clk_c) begin
        if (rst_c) begin
            tp_cnt <= 6'd0;
            tp     <= 1'b0;
        end else if (tp_cnt == 6'd49) begin
            tp_cnt <= 6'd0;
            tp     <= ~tp;
        end else begin
            tp_cnt <= tp_cnt + 6'd1;
        end
    end
    assign tp_p = tp;
    assign tp_n = ~tp;

    // ---- banner senders -----------------------------------------------------
    localparam [8*8-1:0]  SHA   = `GIT_SHA;
    localparam [7:0]      L_TEN = (N_LANES >= 10) ? (8'h30 + N_LANES / 10) : 8'h00;
    localparam [7:0]      L_ONE = 8'h30 + (N_LANES % 10);
    localparam MSG_LEN = 43;
    localparam [8*MSG_LEN-1:0] MSG = {"ULX3S receiver v0 build ", SHA, " lanes=", L_TEN, L_ONE, 8'h0D, 8'h0A};

    wire [1:0] txd_o;
    generate
        for (i = 0; i < 2; i = i + 1) begin : g_ban
            localparam BAUD = (i == 0) ? 115_200 : 1_000_000;
            reg [5:0] idx;
            wire [7:0] b = MSG[8*(MSG_LEN-1-idx) +: 8];
            wire       ready;
            wire       v = (idx < MSG_LEN) && (b != 8'h00);
            always @(posedge clk_25mhz) begin
                if (rst25) idx <= MSG_LEN;
                else if (sec_tick) idx <= 6'd0;
                else if (idx < MSG_LEN) begin
                    if (b == 8'h00 || ready) idx <= idx + 6'd1;
                end
            end
            uart_tx #(.CLK_HZ(25_000_000), .BAUD(BAUD)) u_tx (
                .clk(clk_25mhz), .rst(rst25), .data(b), .valid(v), .ready(ready), .txd(txd_o[i]));
        end
    endgenerate
    assign ftdi_rxd    = txd_o[0];
    assign wifi_gpio16 = txd_o[1];

    // Unused inputs (v0), kept as ports so the LPF/board map is stable.
    wire unused = &{1'b0, btn[6:2], btn[0], ftdi_txd, wifi_gpio17, rst_s, word_ph[0], samples[0][3:2], act32[31:6]};
endmodule
`default_nettype wire
