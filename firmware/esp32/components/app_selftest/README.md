# app_selftest

Status: PROPOSED; compiled (ESP-IDF v5.5.5, 2026-10-12); not host-tested; not run on hardware. Every pass window is a first guess from README s.8 (PROPOSED).

Runs README s.8 steps 1-9 synchronously (`app_selftest_run(full)`), builds the protocol s.6 JSON (extra per-step key `d`), sets/clears FAULT_SELFTEST and sends SELFTEST_RESULT in bus mode. Step 9 goes through `app_safety_hv_request()`, temporarily sets `hv_set` to the 100 V test bias (never above the 110 V cap; `app_safety_hv_off_now()` on any reading over it), forces the range loop to manual and restores both. It never writes HV_DIS.

LED: a small `st_led` task drives the LED during the run (5 Hz) and for a short result display after it (pass: 3 x 1 s; fail: N flashes then 2 s pause, once). `app_selftest_running()` stays true during that display (up to about 8 s) because the telemetry LED task defers to it; this also blocks `hv on` for that time (trade-off, UNRESOLVED).
