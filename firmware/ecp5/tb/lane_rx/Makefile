# lane_rx testbench (cocotb 2.1, Icarus). Sources: lane_rx and the blocks it wires.
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/lane_rx.v $(PWD)/../../rtl/cdr_oversample.v \
  $(PWD)/../../rtl/comma_align.v $(PWD)/../../rtl/dec_8b10b.v
TOPLEVEL = lane_rx
COCOTB_TEST_MODULES = test_lane_rx
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: check
check:
	@! grep -q -E '<(failure|error)' results.xml || { echo "lane_rx: FAILED"; exit 1; }
	@grep -q '<testcase' results.xml || { echo "lane_rx: no tests ran"; exit 1; }
