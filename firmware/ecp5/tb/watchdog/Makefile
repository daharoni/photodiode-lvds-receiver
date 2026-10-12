# watchdog testbench (cocotb 2.1, Icarus).  cocotb 2.1 exits nonzero when a test fails;
# the results.xml grep is a second guard so a silent skip also fails the build.
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/watchdog.v
TOPLEVEL = watchdog
COMPILE_ARGS += -Pwatchdog.TIMEOUT_CYCLES=100
COCOTB_TEST_MODULES = test_watchdog
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

# Guard: fail if results.xml has a failure/error or no testcase at all.
.PHONY: check
check:
	@! grep -q -E '<(failure|error)' results.xml || { echo "watchdog: FAILED"; exit 1; }
	@grep -q '<testcase' results.xml || { echo "watchdog: no tests ran"; exit 1; }
