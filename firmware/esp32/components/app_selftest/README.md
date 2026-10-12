# app_selftest

Status: PROPOSED; compiled (ESP-IDF v5.5.5, 2026-10-12); not host-tested; not run on hardware. Every pass window is a first guess from README s.8 (PROPOSED).

Runs README s.8 steps 1-9 synchronously (`app_selftest_run(full)`), builds the protocol s.6 JSON (extra per-step key `d`), sets/clears FAULT_SELFTEST and sends SELFTEST_RESULT in bus mode. Step 9 (changed 2026-10-12) uses `app_safety_hv_request_ex(true, 120 V cap, hv_min target)`: enable at 0xFFF, 2 s settle within 1 V, `hv_floor_v` required in 95-115 V (PROPOSED, UNRESOLVED), then a 60-code slope step through `app_range_manual_set_code()`; the cap is enforced by the hv_gate machine, `hv_set` is no longer touched. The run start is an atomic exchange and `hv_auto` is inhibited during the run. It never writes HV_DIS. Host tests: none for this file.

LED: a small `st_led` task drives the LED during the run (5 Hz) and for a short result display after it (pass: 3 x 1 s; fail: N flashes then 2 s pause, once). `app_selftest_running()` stays true during that display (up to about 8 s) because the telemetry LED task defers to it; this also blocks `hv on` for that time (trade-off, UNRESOLVED).
