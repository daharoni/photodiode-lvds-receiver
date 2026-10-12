// crc8: CRC-8, poly 0x07, init 0x00, no reflection, no xorout, byte-wise
// (README section 7: status message to the ESP32).
//
// Label: PROPOSED; function checked by tb/status_uart against a Python reference
// (the binary status message CRC). Same style as crc16.v.
//
// Interface
//   init       : load 0x00 (priority over data_valid)
//   data_valid : fold `data` into the CRC in one cycle
//   crc        : valid the cycle after the last byte; holds when idle
//
// Parameters: none. Reset loads 0x00.
`default_nettype none

module crc8 (
  input  wire       clk,
  input  wire       rst,
  input  wire       init,
  input  wire [7:0] data,
  input  wire       data_valid,
  output reg  [7:0] crc
);

  function [7:0] step;
    input [7:0] c;
    input [7:0] d;
    reg   [7:0] r;
    integer i;
    begin
      r = c ^ d;
      for (i = 0; i < 8; i = i + 1)
        r = r[7] ? ((r << 1) ^ 8'h07) : (r << 1);
      step = r;
    end
  endfunction

  always @(posedge clk) begin
    if (rst || init)
      crc <= 8'h00;
    else if (data_valid)
      crc <= step(crc, data);
  end

endmodule
`default_nettype wire
