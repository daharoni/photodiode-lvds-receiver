# comma_align testbench (cocotb 2.1, Icarus).  cocotb 2.1 exits nonzero when a test fails;
# the results.xml grep is a second guard so a silent skip also fails the build.
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/comma_align.v
TOPLEVEL = comma_align
COCOTB_TEST_MODULES = test_comma_align
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

# Guard: fail if results.xml has a failure/error or no testcase at all.
.PHONY: check
check:
	@! grep -q -E '<(failure|error)' results.xml || { echo "comma_align: FAILED"; exit 1; }
	@grep -q '<testcase' results.xml || { echo "comma_align: no tests ran"; exit 1; }
