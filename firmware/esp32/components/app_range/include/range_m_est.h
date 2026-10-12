/*
 * range_m_est.h - APD gain (M) estimator, pure C (no ESP-IDF).
 * firmware/esp32/README.md s.6.4. PROPOSED; nothing measured, per-unit
 * values UNRESOLVED (need G1 bench calibration, README s.6.4 / s.12 item 1).
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* d ln M / dV = 0.069 per volt near M = 50-100: gain doubles per ~10 V.
 * README s.6.4, PROPOSED (docs/research/apd-selection.md, graph-read, not VERIFIED). */
#define RANGE_M_K_PER_V       0.069f
/* M at the V100 anchor. README s.6.4: M = 100 x exp(0.069 x (V25 - V100)). */
#define RANGE_M_AT_V100       100.0f
/* Nominal DAC_HV slope, README s.4 step 9c: 14.95 mV of bias per code (calculated). */
#define RANGE_V_PER_CODE      0.01495f
/* When only VBR is known: V100 = VBR - 17.5 V. Derived from README s.6.4
 * "M = 100 sits near 130-135 V for a typical part [VBR 150 V]"; the offset
 * (15..20 V) is a guess, UNRESOLVED until `cal vop`. */
#define RANGE_V100_BELOW_VBR  17.5f
/* Estimates above/below this are reported as unknown (sanity window, PROPOSED). */
#define RANGE_M_MIN_VALID     1.0f
#define RANGE_M_MAX_VALID     1000.0f
#define RANGE_M_UNKNOWN_X10   (-1)     /* returned when not calibrated */
#define RANGE_M_CAN_UNKNOWN   0xFFFF   /* protocol s.1.4 TLM_ANALOG m_x10 wire value */

typedef struct {
    bool have_v100;       /* V100 known (cal vop or cal vbr) */
    float v100;           /* bias for M = 100 at 25 C-equivalent */
    bool have_code_cal;   /* (code_ref, v_ref) pair measured at room temperature */
    uint16_t code_ref;
    float v_ref;
} range_m_est_cfg_t;

/** Clear the configuration (estimate unknown). */
void range_m_est_init(range_m_est_cfg_t *c);
/** Set V100 directly (`cal vop 100 <V>`). */
void range_m_est_set_v100(range_m_est_cfg_t *c, float v100);
/** Derive V100 from a per-unit VBR (see RANGE_V100_BELOW_VBR). Ignored if vbr <= 0. */
void range_m_est_set_vbr(range_m_est_cfg_t *c, float vbr);
/** Record the bias measured at a DAC code during room-temperature calibration. */
void range_m_est_set_code_cal(range_m_est_cfg_t *c, uint16_t code, float v_measured);
/** V25-equivalent bias of a DAC code (nominal slope; code 0xFFF = minimum bias). */
float range_v25_from_code(const range_m_est_cfg_t *c, uint16_t code, float bias_v_measured);
/** M for a V25-equivalent bias given V100: 100 x exp(0.069 (v25 - v100)). */
float range_m_from_v25(float v25, float v100);
/** M estimate in x10 units; RANGE_M_UNKNOWN_X10 (-1) if not calibrated or out of window. */
int32_t range_m_est_x10(const range_m_est_cfg_t *c, uint16_t code, float bias_v_measured);

#ifdef __cplusplus
}
#endif
