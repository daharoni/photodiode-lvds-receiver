SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/crc16.v $(PWD)/../../rtl/uart_tx.v $(PWD)/../../rtl/host_sink_uart.v
TOPLEVEL = host_sink_uart
COCOTB_TEST_MODULES = test_host_sink_uart
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: check
check: results.xml
	@python3 -c "import sys,xml.etree.ElementTree as E; r=E.parse('results.xml').getroot(); bad=[c.get('name') for c in r.iter('testcase') if c.find('failure') is not None or c.find('error') is not None]; print('FAILED:',bad) if bad else print('all tests passed'); sys.exit(1 if bad else 0)"
