cmake_minimum_required(VERSION 3.16)
project(receiver_esp32c6_host_tests C)
enable_testing()

set(CMAKE_C_STANDARD 11)
set(COMP ${CMAKE_CURRENT_SOURCE_DIR}/../components)
set(CORE
    ${COMP}/app_range/range_fsm.c
    ${COMP}/app_range/range_m_est.c
    ${COMP}/can_link/can_codec.c
    ${COMP}/app_safety/hv_gate.c)

# One executable per test file, one ctest entry each (TH_MAIN in each file).
foreach(t test_can_codec test_range_fsm test_range_m_est test_hv_gate)
    add_executable(${t} ${t}.c ${CORE})
    target_include_directories(${t} PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${COMP}/app_range/include
        ${COMP}/can_link/include
        ${COMP}/app_safety/include
        ${COMP}/board/include)
    target_compile_options(${t} PRIVATE -Wall -Wextra)
    target_link_libraries(${t} PRIVATE m)
    add_test(NAME ${t} COMMAND ${t})
endforeach()
