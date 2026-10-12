# frame_tx testbench. `make` runs several parameter cases (separate build dirs); fails if any
# case fails (cocotb 2.1 exits nonzero; the grep on results xml is a second guard).
# Case format: TX_LEN:TX_GAP:DIV
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/enc_8b10b.v $(PWD)/../../rtl/crc16.v $(PWD)/../../rtl/prbs.v $(PWD)/../../rtl/frame_tx.v
TOPLEVEL = frame_tx
COCOTB_TEST_MODULES = test_frame_tx
CASES = 64:4:2 1:4:2 256:4:2 7:0:1 5:3:3

ifdef CASE
TX_LEN := $(word 1,$(subst :, ,$(CASE)))
TX_GAP := $(word 2,$(subst :, ,$(CASE)))
DIV    := $(word 3,$(subst :, ,$(CASE)))
TAG    := $(TX_LEN)_$(TX_GAP)_$(DIV)
SIM_BUILD = sim_build_$(TAG)
COMPILE_ARGS += -Pframe_tx.TX_LEN=$(TX_LEN) -Pframe_tx.TX_GAP=$(TX_GAP) -Pframe_tx.DIV=$(DIV)
COCOTB_RESULTS_FILE = results_$(TAG).xml
export TX_LEN TX_GAP DIV
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim
else
.PHONY: all
all:
	@for c in $(CASES); do \
	  t=$$(echo $$c | tr : _); \
	  $(MAKE) --no-print-directory CASE=$$c || exit 1; \
	  if grep -q -E '<(failure|error)' results_$$t.xml; then echo "frame_tx FAILED for case $$c"; exit 1; fi; \
	done; echo "frame_tx: all cases passed"
.PHONY: clean
clean:
	rm -rf sim_build_* results*.xml __pycache__
endif
