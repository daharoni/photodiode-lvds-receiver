# Source this from the repo root before any ECP5 gateware work:
#   source tools/fpga-env.sh && cd firmware/ecp5 && make test
#
# The YosysHQ OSS CAD Suite (yosys, nextpnr-ecp5, prjtrellis, verilator, iverilog,
# openFPGALoader, fujprog, cocotb with its own python "tabbypy3") is installed as a
# single tarball in ~/opt/oss-cad-suite (release 2026-10-12, darwin-arm64).
# The same suite is used in CI through YosysHQ/setup-oss-cad-suite.
OSS_CAD_SUITE="${OSS_CAD_SUITE:-$HOME/opt/oss-cad-suite}"
if [ ! -x "$OSS_CAD_SUITE/bin/yosys" ]; then
  echo "fpga-env: OSS CAD Suite not found at $OSS_CAD_SUITE (download from" \
       "https://github.com/YosysHQ/oss-cad-suite-build/releases and extract to ~/opt)" >&2
  return 1 2>/dev/null || exit 1
fi
# The suite's own environment script prepends its bin/ and py3bin/ to PATH.
source "$OSS_CAD_SUITE/environment"
export OSS_CAD_SUITE
