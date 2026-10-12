# lane_phy testbench (cocotb 2.1, Icarus): the 200 -> 50 MHz word handoff with the clocks.v
# simulation PLL model (coincident clk_s / clk_c rising edges).
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/lane_phy_tb.v $(PWD)/../../rtl/lane_phy.v $(PWD)/../../rtl/clocks.v
TOPLEVEL = lane_phy_tb
COCOTB_TEST_MODULES = test_lane_phy
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: check
check:
	@! grep -q -E '<(failure|error)' results.xml || { echo "lane_phy: FAILED"; exit 1; }
	@grep -q '<testcase' results.xml || { echo "lane_phy: no tests ran"; exit 1; }
