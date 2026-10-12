# cdr_oversample testbench (cocotb 2.1, Icarus).  cocotb 2.1 exits nonzero when a test fails;
# the results.xml grep is a second guard so a silent skip also fails the build.
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/cdr_oversample.v
TOPLEVEL = cdr_oversample
COCOTB_TEST_MODULES = test_cdr_oversample
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

# Guard: fail if results.xml has a failure/error or no testcase at all.
.PHONY: check
check:
	@! grep -q -E '<(failure|error)' results.xml || { echo "cdr_oversample: FAILED"; exit 1; }
	@grep -q '<testcase' results.xml || { echo "cdr_oversample: no tests ran"; exit 1; }
