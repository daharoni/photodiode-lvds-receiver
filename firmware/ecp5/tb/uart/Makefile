# Loopback test of uart_tx -> uart_rx at 1 Mbaud and 3 Mbaud, 100 MHz clock.
# `make` runs both bauds (separate build dirs) and fails if either fails or if results.xml
# contains a failure/error (cocotb 2.1 already exits nonzero; the grep is a second guard).
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/uart_tx.v $(PWD)/../../rtl/uart_rx.v $(PWD)/uart_loop.v
TOPLEVEL = uart_loop
COCOTB_TEST_MODULES = test_uart

ifdef BAUD
SIM_BUILD = sim_build_$(BAUD)
COMPILE_ARGS += -DTB_BAUD=$(BAUD)
COCOTB_RESULTS_FILE = results_$(BAUD).xml
export BAUD
include $(shell cocotb-config --makefiles)/Makefile.sim
else
.PHONY: all
all:
	@for b in 1000000 3000000; do \
	  $(MAKE) --no-print-directory BAUD=$$b || exit 1; \
	  if grep -q -E '<(failure|error)' results_$$b.xml; then echo "uart test FAILED at $$b baud"; exit 1; fi; \
	done; echo "uart: all bauds passed"
.PHONY: clean
clean:
	rm -rf sim_build_* results*.xml __pycache__
endif
