/*
 * sense.h - ADS1115 sensing task (HV_MON, RSSI, VTH_MON, occasional GND).
 *
 * README s.3 task table: priority 10, one round of AIN0-AIN2 per cycle
 * (about 100 ms with the 4-sample average at 128 SPS: the README's "about
 * 30 ms per round" does not follow from "8 ms each x 4 x 3"; UNRESOLVED,
 * see component README). Status: PROPOSED; not run on hardware.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int32_t hv_mon_mv;   /* AIN0, bias = hv_mon_mv x 101 / 1000 */
    int32_t rssi_mv;     /* AIN1, falls with light */
    int32_t vth_mv;      /* AIN2 */
    int32_t gnd_mv;      /* AIN3, refreshed about every 10th round, last value kept */
    int64_t t_us;        /* esp_timer time of the end of the round */
    bool valid;          /* a complete round has been read and the last round had no error */
} sense_snapshot_t;

/** Create the sensing task (prio 10). Needs ads1115_init() done. Registers the
 *  live getter for param rssi_drop. Checks in with app_safety every round. */
void sense_start(void);

/** Copy the latest snapshot (mutex-protected). Returns false if no round has
 *  ever completed. Check out->valid for freshness after an error. */
bool sense_get(sense_snapshot_t *out);

/** APD bias in volts: hv_mon_mv x 101 / 1000 (BOARD_HV_MON_DIVIDER). */
float sense_bias_v(const sense_snapshot_t *s);

/** RSSI idle level (mV) for the present TIA setting. Default 1950 mV (README
 *  s.1: idle about 1.9-2.0 V, PROPOSED). Learned as a low-pass of RSSI while
 *  the APD bias is below 10 V (HV off, so no avalanche gain), UNRESOLVED
 *  whether this equals the idle level with light-free HV on. */
int32_t sense_rssi_idle_mv(void);

/** idle minus present RSSI (positive with light), mV; 0 before the first round. */
int32_t sense_rssi_drop_mv(void);

/** Set the idle level explicitly for one TIA gain (e.g. `cal rssi-idle`). */
void sense_rssi_idle_set(bool tia_20k, int32_t mv);

/** Pure helper used by the learner (exposed for tests): one step of the
 *  low-pass idle <- idle + (x - idle) / 8. */
int32_t sense_lowpass8(int32_t idle, int32_t x);

#ifdef __cplusplus
}
#endif
