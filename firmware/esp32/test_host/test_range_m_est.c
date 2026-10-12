#include "test_harness.h"
#include "range_m_est.h"

TEST(m_unknown_until_calibrated)
{
    range_m_est_cfg_t c;
    range_m_est_init(&c);
    ASSERT_EQ(range_m_est_x10(&c, 2000, 130.0f), RANGE_M_UNKNOWN_X10);
}

TEST(m_at_v100_is_100)
{
    range_m_est_cfg_t c;
    range_m_est_init(&c);
    range_m_est_set_v100(&c, 132.0f);
    ASSERT_EQ(range_m_est_x10(&c, 0, 132.0f), 1000);
}

TEST(m_doubles_per_ten_volts)
{
    range_m_est_cfg_t c;
    range_m_est_init(&c);
    range_m_est_set_v100(&c, 132.0f);
    int32_t m = range_m_est_x10(&c, 0, 142.0f);
    ASSERT_NEAR(m / 10.0, 199.4, 0.2);   /* 100*exp(0.69) = 199.4 */
    ASSERT_NEAR((double)m / range_m_est_x10(&c, 0, 132.0f), 2.0, 0.02);
}

TEST(m_from_code_calibration)
{
    range_m_est_cfg_t c;
    range_m_est_init(&c);
    range_m_est_set_v100(&c, 132.0f);
    range_m_est_set_code_cal(&c, 2000, 140.0f);
    /* 100 codes lower = +1.495 V; measured bias argument is ignored */
    ASSERT_NEAR(range_v25_from_code(&c, 1900, 0.0f), 141.495, 1e-3);
    ASSERT_NEAR(range_v25_from_code(&c, 2000, 0.0f), 140.0, 1e-3);
}

TEST(m_vbr_fallback_and_window)
{
    range_m_est_cfg_t c;
    range_m_est_init(&c);
    range_m_est_set_vbr(&c, 150.0f);
    ASSERT_NEAR(c.v100, 132.5, 1e-3);
    ASSERT_EQ(range_m_est_x10(&c, 0, 60.0f), RANGE_M_UNKNOWN_X10);  /* M < 1: out of window */
}

TH_MAIN
