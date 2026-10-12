# status_uart testbench. `make` runs N_LANES = 1, 7 and 14 as separate builds; fails if any fails.
# CLK_HZ is set to 10 MHz (the sim clock is still 10 ns) so the 115200 baud ASCII report is 10x
# shorter in simulated cycles; the UART divider ratios stay valid (10 and 86.8 clk per bit).
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/crc8.v $(PWD)/../../rtl/uart_tx.v $(PWD)/../../rtl/status_uart.v
TOPLEVEL = status_uart
COCOTB_TEST_MODULES = test_status_uart
CASES = 1 7 14
CLK_HZ_TB = 10000000
STATUS_PERIOD_TB = 3000

ifdef N
ASCII_PERIOD_TB = $(shell echo $$((1200 * (100 + 45 * $(N)))))
SIM_BUILD = sim_build_$(N)
COMPILE_ARGS += -Pstatus_uart.N_LANES=$(N) -Pstatus_uart.CLK_HZ=$(CLK_HZ_TB) \
  -Pstatus_uart.STATUS_PERIOD_CYCLES=$(STATUS_PERIOD_TB) -Pstatus_uart.ASCII_PERIOD_CYCLES=$(ASCII_PERIOD_TB)
COCOTB_RESULTS_FILE = results_$(N).xml
export N CLK_HZ_TB STATUS_PERIOD_TB ASCII_PERIOD_TB
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim
else
.PHONY: all
all:
	@for n in $(CASES); do \
	  $(MAKE) --no-print-directory N=$$n || exit 1; \
	  if grep -q -E '<(failure|error)' results_$$n.xml; then echo "status_uart FAILED for N_LANES=$$n"; exit 1; fi; \
	done; echo "status_uart: all cases passed"
.PHONY: clean
clean:
	rm -rf sim_build_* results*.xml __pycache__
endif
