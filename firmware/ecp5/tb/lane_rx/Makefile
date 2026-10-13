# lane_rx testbench (cocotb 2.1, Icarus). Sources: lane_rx and the blocks it wires.
# `make` runs two builds, AUTO_INVERT = 1 (all tests) and 0 (the no-auto-invert test); `make AUTO=<0|1>` runs one.
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/lane_rx.v $(PWD)/../../rtl/cdr_oversample.v \
  $(PWD)/../../rtl/comma_align.v $(PWD)/../../rtl/dec_8b10b.v
TOPLEVEL = lane_rx
COCOTB_TEST_MODULES = test_lane_rx
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)

ifdef AUTO
SIM_BUILD = sim_build_$(AUTO)
COMPILE_ARGS += -Plane_rx.AUTO_INVERT=$(AUTO)
COCOTB_RESULTS_FILE = results_$(AUTO).xml
export TB_AUTO = $(AUTO)
include $(shell cocotb-config --makefiles)/Makefile.sim
else
.PHONY: all check clean
all:
	@for a in 1 0; do \
	  $(MAKE) --no-print-directory AUTO=$$a || exit 1; \
	  if grep -q -E '<(failure|error)' results_$$a.xml; then echo "lane_rx test FAILED at AUTO_INVERT=$$a"; exit 1; fi; \
	done; echo "lane_rx: AUTO_INVERT 1 and 0 passed"
check:
	@for a in 1 0; do \
	  ! grep -q -E '<(failure|error)' results_$$a.xml || { echo "lane_rx: FAILED"; exit 1; }; \
	  grep -q '<testcase' results_$$a.xml || { echo "lane_rx: no tests ran"; exit 1; }; \
	done
clean:
	rm -rf sim_build_* sim_build results*.xml __pycache__
endif
