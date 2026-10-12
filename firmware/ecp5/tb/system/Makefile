# End-to-end system test (cocotb 2.1, Icarus): frame_tx -> line model -> 3 x lane_rx -> frame_rx
# -> lane_merge -> host_sink_uart / status_uart, through tb/system/system_top.v (the wrapper that
# mirrors ulx3s_top).  Parameters of system_top are set in the Verilog defaults.
SIM ?= icarus
TOPLEVEL_LANG = verilog
R = $(PWD)/../../rtl
VERILOG_SOURCES = $(PWD)/system_top.v $(R)/receiver_core.v $(R)/lane_rx.v $(R)/cdr_oversample.v \
  $(R)/comma_align.v $(R)/dec_8b10b.v $(R)/enc_8b10b.v $(R)/watchdog.v $(R)/lane_monitor.v \
  $(R)/frame_rx.v $(R)/frame_tx.v $(R)/crc16.v $(R)/crc8.v $(R)/prbs.v $(R)/lane_merge.v \
  $(R)/host_sink_uart.v $(R)/status_uart.v $(R)/uart_tx.v
TOPLEVEL = system_top
COCOTB_TEST_MODULES = test_system
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: check
check:
	@! grep -q -E '<(failure|error)' results.xml || { echo "system: FAILED"; exit 1; }
	@grep -q '<testcase' results.xml || { echo "system: no tests ran"; exit 1; }
