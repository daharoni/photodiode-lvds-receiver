cmake_minimum_required(VERSION 3.16)

# Firmware version comes from version.txt (PROJECT_VER is read by ESP-IDF and
# exposed as esp_app_get_description()->version).
file(STRINGS "${CMAKE_CURRENT_LIST_DIR}/version.txt" PROJECT_VER LIMIT_COUNT 1)

# components/ is picked up by default; no EXTRA_COMPONENT_DIRS needed.
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(receiver_esp32c6)
