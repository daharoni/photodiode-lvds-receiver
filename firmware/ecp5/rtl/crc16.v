// crc16: CRC-16/CCITT-FALSE, byte-wise (README section 3 frame CRC, section 9).
//
// Label: PROPOSED (line protocol); function VERIFIED by tb/crc16 against
// model/link8b10b.py (check value 0x29B1 for "123456789", 1000 random frames).
//
// poly 0x1021, init 0xFFFF, no reflection, no xorout, bytes fed in transmit order
// (MSB-first within the CRC register, as the model).
//
// Interface
//   init       : load 0xFFFF (takes priority over data_valid in the same cycle)
//   data_valid : fold `data` into the CRC in one cycle
//   crc        : valid the cycle after the last byte; holds when idle
//
// Parameters: none. Reset loads 0xFFFF.
`default_nettype none

module crc16 (
  input  wire        clk,
  input  wire        rst,
  input  wire        init,
  input  wire [7:0]  data,
  input  wire        data_valid,
  output reg  [15:0] crc
);

  function [15:0] step;
    input [15:0] c;
    input [7:0]  d;
    reg   [15:0] r;
    integer i;
    begin
      r = c ^ {d, 8'h00};
      for (i = 0; i < 8; i = i + 1)
        r = r[15] ? ((r << 1) ^ 16'h1021) : (r << 1);
      step = r;
    end
  endfunction

  always @(posedge clk) begin
    if (rst || init)
      crc <= 16'hFFFF;
    else if (data_valid)
      crc <= step(crc, data);
  end

endmodule
`default_nettype wire
