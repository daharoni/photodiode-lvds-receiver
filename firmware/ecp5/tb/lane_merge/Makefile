# lane_merge is run at N_LANES = 1, 3, 7 and 14 (separate build directories); `make N=<n>` runs one.
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/lane_merge.v
TOPLEVEL = lane_merge
COCOTB_TEST_MODULES = test_lane_merge
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)

ifdef N
SIM_BUILD = sim_build_$(N)
COMPILE_ARGS += -Plane_merge.N_LANES=$(N)
COCOTB_RESULTS_FILE = results_$(N).xml
export TB_N = $(N)
include $(shell cocotb-config --makefiles)/Makefile.sim
else
.PHONY: all
all:
	@for n in 1 3 7 14; do \
	  $(MAKE) --no-print-directory N=$$n || exit 1; \
	  if grep -q -E '<(failure|error)' results_$$n.xml; then echo "lane_merge test FAILED at N_LANES=$$n"; exit 1; fi; \
	done; echo "lane_merge: all N_LANES passed"
.PHONY: clean
clean:
	rm -rf sim_build_* results*.xml __pycache__
endif
