# app_range

Status: PROPOSED; compiled (ESP-IDF v5.5.5, 2026-10-12). `range_fsm` and `range_m_est` are pure C and host-tested (`test_host`); `app_range.c` (task, DAC trim) is not host-tested and not run on hardware.

- `range_fsm.h/.c`: README s.6.3 state machine and TIA overload guard. Each constant is a `RFSM_*` macro with a `README s.6.3, PROPOSED` comment.
- `range_m_est.h/.c`: README s.6.4 estimator `M = 100 exp(0.069 (V25 - V100))`; unknown (-1) until `V100` (or VBR) is set.
- `app_range.c`: task prio 8, 100 ms. Closed-loop DAC_HV trim on HV_MON with a 134-code (20 V/s) step cap, only while `app_safety_hv_state() == HV_ON` (app_safety owns the ramps). MANUAL holds the DAC code; a changed `hv_set` triggers one closed-loop trim (README s.6.5).
- Interpretations to confirm (UNRESOLVED): V_lock is the pre-margin clean bias; the SEARCH raise pauses while a clean run is in progress; the class-2 average is a rolling 2 s window with a 1 s wait after each bump; the guard in MANUAL with `tia auto` only switches the TIA (no bias lowering); `FAULT_LOOP_LIMIT` is set only for the hv_max pin; V_lock is not persisted (no parameter exists).
