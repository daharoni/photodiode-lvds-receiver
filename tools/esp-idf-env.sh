# Source this file (zsh or bash) to get the ESP-IDF v5.5.x toolchain for the
# ESP32-C6 firmware in firmware/esp32/:
#
#   source tools/esp-idf-env.sh
#   cd firmware/esp32 && idf.py set-target esp32c6 && idf.py build
#
# ESP-IDF is installed in ~/esp/esp-idf (git tag v5.5.5, installed 2026-10-12
# with `install.sh esp32c6`; tools live in ~/.espressif). ESP-IDF's export.sh
# picks the first `python3` on PATH and the installed Python environment was
# built with Homebrew python@3.12, so the Homebrew interpreter has to come
# first (the macOS system python3 is 3.9 and has no matching environment).
export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH"
export IDF_PATH="${IDF_PATH:-$HOME/esp/esp-idf}"
. "$IDF_PATH/export.sh"
