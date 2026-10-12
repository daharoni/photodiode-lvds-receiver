# sense

Status: PROPOSED; compiled (ESP-IDF v5.5.5, 2026-10-12); not host-tested; not run on hardware.

Task `sense` (prio 10): reads AIN0 HV_MON, AIN1 RSSI, AIN2 VTH_MON every round and AIN3 GND every 10th round, publishes a mutex-protected snapshot, checks in with app_safety. Registers the live parameter `rssi_drop`.

RSSI idle level: default 1950 mV (README s.1, PROPOSED), learned as a low-pass while the bias is below 10 V (HV off). Per-TIA-gain values; if only one gain was learned it is reused for the other (UNRESOLVED: the two gains may have different dark levels). `cal rssi-idle` is not wired; `sense_rssi_idle_set()` is the hook.

If a read fails, the snapshot keeps the stale values with `valid = false` (app_safety treats that as "no measurement").
