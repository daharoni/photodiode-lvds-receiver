SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(PWD)/../../rtl/dec_8b10b.v
TOPLEVEL = dec_8b10b
COCOTB_TEST_MODULES = test_dec_8b10b
export PYTHONPATH := $(PWD)/../..:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim

# cocotb's own Makefile exits 0 even when a test fails in some versions; make it explicit.
.PHONY: check
check: results.xml
	@python3 -c "import sys,xml.etree.ElementTree as E; r=E.parse('results.xml').getroot(); bad=[c.get('name') for c in r.iter('testcase') if c.find('failure') is not None or c.find('error') is not None]; print('FAILED:',bad) if bad else print('all tests passed'); sys.exit(1 if bad else 0)"
