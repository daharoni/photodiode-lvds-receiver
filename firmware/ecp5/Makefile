# ECP5 gateware build flow (ULX3S). `source ../../tools/fpga-env.sh` first.
#   make info | lint | test | synth | pnr | pack | bit | timing | prog | flash | clean
# DEVICE = 85k (default) | 45k | 25k | 12k ; all share package CABGA381 and the ULX3S pinout.
# GIT_SHA (max 8 chars) is printed in the UART banner; default is the short commit id, or "dev".

DEVICE   ?= 85k
PACKAGE  ?= CABGA381
SPEED    ?= 6
TOP      ?= ulx3s_top
BUILD    ?= build
GIT_SHA  ?= $(shell git rev-parse --short=7 HEAD 2>/dev/null || echo dev)
SEED     ?= 1

RTL_ALL  := $(sort $(wildcard rtl/*.v))
# Synthesis reads everything in rtl/ (the other agents' blocks are not instantiated by v0 and are dropped).
SYN_SRC  := $(RTL_ALL)
TBDIRS   := $(patsubst %/Makefile,%,$(wildcard tb/*/Makefile))

.PHONY: all info lint test synth pnr pack bit timing prog flash clean
all: bit

info:
	@echo "DEVICE=$(DEVICE) PACKAGE=$(PACKAGE) SPEED=$(SPEED) GIT_SHA=$(GIT_SHA)"
	@yosys -V
	@nextpnr-ecp5 --version 2>&1 | head -1
	@ecppack --help 2>&1 | head -1 || true
	@verilator --version
	@iverilog -V 2>&1 | head -1
	@openFPGALoader --Version 2>&1 | head -1 || true
	@cocotb-config --version

lint: | $(BUILD)
	@echo "verilator lint over: $(RTL_ALL)"
	verilator --lint-only -Wall --timing -Irtl $(RTL_ALL) --top-module $(TOP)

test:
	@pass=0; fail=0; for d in $(TBDIRS); do \
	  echo "=== $$d"; \
	  if $(MAKE) -C $$d; then pass=$$((pass+1)); else fail=$$((fail+1)); echo "FAILED: $$d"; echo "test summary: $$pass passed, $$fail failed (stopped at first failure)"; exit 1; fi; \
	done; echo "test summary: $$pass passed, $$fail failed"

$(BUILD):
	mkdir -p $(BUILD)

synth: $(BUILD)/ulx3s.json
$(BUILD)/ulx3s.json: $(SYN_SRC) | $(BUILD)
	yosys -q -l $(BUILD)/yosys.log -p "read_verilog -DSYNTHESIS -DGIT_SHA=\"$(GIT_SHA)\" $(SYN_SRC); synth_ecp5 -top $(TOP) -json $@"
	@grep -A60 "Printing statistics" $(BUILD)/yosys.log | tail -45

pnr: $(BUILD)/ulx3s.config
$(BUILD)/ulx3s.config: $(BUILD)/ulx3s.json constraints/ulx3s.lpf
	nextpnr-ecp5 --$(DEVICE) --package $(PACKAGE) --speed $(SPEED) --lpf constraints/ulx3s.lpf \
	  --json $(BUILD)/ulx3s.json --textcfg $@ --report $(BUILD)/timing.json --seed $(SEED) \
	  --log $(BUILD)/nextpnr.log
	@grep -E "Max frequency" $(BUILD)/nextpnr.log | tail -4

pack: $(BUILD)/ulx3s.bit
$(BUILD)/ulx3s.bit: $(BUILD)/ulx3s.config
	ecppack --compress --input $< --bit $@
	@ls -l $@

bit: synth pnr pack

# Fail if the last (post-route) Max frequency lines show clk_s < 200 MHz or clk_c < 100 MHz.
# Clock names in nextpnr's log contain the net name ("clk_s" / "clk_c").
timing:
	@test -f $(BUILD)/nextpnr.log || { echo "no $(BUILD)/nextpnr.log: run make pnr first"; exit 1; }
	@grep "Max frequency for clock" $(BUILD)/nextpnr.log | tail -3 | tee $(BUILD)/timing.txt
	@awk '/Max frequency for clock/ { n=$$0; f=$$0; sub(/.*: /,"",f); sub(/ MHz.*/,"",f); \
	  if (n ~ /clk_s/) { seen_s=1; if (f+0 < 200) { print "FAIL clk_s " f " MHz < 200"; bad=1 } } \
	  else if (n ~ /clk_c/) { seen_c=1; if (f+0 < 100) { print "FAIL clk_c " f " MHz < 100"; bad=1 } } } \
	  END { if (!seen_s || !seen_c) { print "FAIL: clk_s or clk_c not found in log"; bad=1 } \
	        if (bad) exit 1; print "timing OK: clk_s >= 200 MHz and clk_c >= 100 MHz" }' $(BUILD)/timing.txt

prog: $(BUILD)/ulx3s.bit
	openFPGALoader -b ulx3s $<

flash: $(BUILD)/ulx3s.bit
	openFPGALoader -b ulx3s -f $<

clean:
	rm -rf $(BUILD)
	@for d in $(TBDIRS); do $(MAKE) -C $$d clean 2>/dev/null || true; done
