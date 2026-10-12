/* range_m_est.c - see range_m_est.h. README s.6.4, PROPOSED. */
#include "range_m_est.h"
#include <math.h>

void range_m_est_init(range_m_est_cfg_t *c)
{
    c->have_v100 = false;
    c->v100 = 0.0f;
    c->have_code_cal = false;
    c->code_ref = 0;
    c->v_ref = 0.0f;
}

void range_m_est_set_v100(range_m_est_cfg_t *c, float v100)
{
    c->have_v100 = true;
    c->v100 = v100;
}

void range_m_est_set_vbr(range_m_est_cfg_t *c, float vbr)
{
    if (vbr > 0.0f) {
        range_m_est_set_v100(c, vbr - RANGE_V100_BELOW_VBR);
    }
}

void range_m_est_set_code_cal(range_m_est_cfg_t *c, uint16_t code, float v_measured)
{
    c->have_code_cal = true;
    c->code_ref = code;
    c->v_ref = v_measured;
}

float range_v25_from_code(const range_m_est_cfg_t *c, uint16_t code, float bias_v_measured)
{
    if (!c->have_code_cal) {
        /* No code calibration: fall back to the measured bias (drifts with
         * temperature at about 0.64 V/C of the NTC residual, README s.6.4). */
        return bias_v_measured;
    }
    /* Higher code = lower bias (README s.1 DAC_HV row). */
    return c->v_ref - ((float)code - (float)c->code_ref) * RANGE_V_PER_CODE;
}

float range_m_from_v25(float v25, float v100)
{
    return RANGE_M_AT_V100 * expf(RANGE_M_K_PER_V * (v25 - v100));
}

int32_t range_m_est_x10(const range_m_est_cfg_t *c, uint16_t code, float bias_v_measured)
{
    if (!c->have_v100) {
        return RANGE_M_UNKNOWN_X10;
    }
    float m = range_m_from_v25(range_v25_from_code(c, code, bias_v_measured), c->v100);
    if (!(m >= RANGE_M_MIN_VALID) || m > RANGE_M_MAX_VALID) {
        return RANGE_M_UNKNOWN_X10;
    }
    return (int32_t)(m * 10.0f + 0.5f);
}
