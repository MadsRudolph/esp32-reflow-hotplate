#include <unity.h>
#include <math.h>
#include <stdio.h>
#include "profile.h"

void setUp(void) {}
void tearDown(void) {}

/* -----------------------------------------------------------------------
 * Helper: build a minimal 1-stage profile for setpoint tests.
 * Stage 0: target=200 °C, duration=100 s
 * Ramps from 25 °C (ambient) to 200 °C over 100 s.
 * ----------------------------------------------------------------------- */
static profile_t make_single_stage(void)
{
    profile_t p;
    p.n_stages = 1;
    snprintf(p.name, PROFILE_NAME_LEN, "Test");
    p.stages[0].target_c  = 200.0f;
    p.stages[0].duration_s = 100;
    snprintf(p.stages[0].name, PROFILE_NAME_LEN, "ramp");
    return p;
}

/* -----------------------------------------------------------------------
 * Setpoint at t=0 should be approximately ambient (25 °C).
 * ----------------------------------------------------------------------- */
static void test_setpoint_at_t0_is_ambient(void)
{
    profile_t p = make_single_stage();
    float sp = profile_setpoint(&p, 0);
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 25.0f, sp);
}

/* -----------------------------------------------------------------------
 * Mid-ramp: at t=50 (halfway through 100 s stage), setpoint should be
 * halfway between 25 and 200 = 112.5 °C.
 * ----------------------------------------------------------------------- */
static void test_setpoint_mid_ramp(void)
{
    profile_t p = make_single_stage();
    float sp = profile_setpoint(&p, 50);
    /* Linear interp: 25 + (200-25)*50/100 = 25 + 87.5 = 112.5 */
    TEST_ASSERT_FLOAT_WITHIN(0.5f, 112.5f, sp);
}

/* -----------------------------------------------------------------------
 * At exactly total time (end of last stage), setpoint == last target.
 * ----------------------------------------------------------------------- */
static void test_setpoint_at_total_time_equals_last_target(void)
{
    profile_t p = make_single_stage();
    int total = profile_total_s(&p);
    float sp = profile_setpoint(&p, total);
    TEST_ASSERT_FLOAT_WITHIN(0.5f, 200.0f, sp);
}

/* -----------------------------------------------------------------------
 * Past the end, setpoint clamps to last target.
 * ----------------------------------------------------------------------- */
static void test_setpoint_past_end_clamps(void)
{
    profile_t p = make_single_stage();
    float sp = profile_setpoint(&p, 9999);
    TEST_ASSERT_FLOAT_WITHIN(0.5f, 200.0f, sp);
}

/* -----------------------------------------------------------------------
 * Validate: both defaults must pass.
 * ----------------------------------------------------------------------- */
static void test_validate_leaded_default(void)
{
    profile_t p;
    profile_default_leaded(&p);
    TEST_ASSERT_EQUAL_INT(1, profile_validate(&p));
}

static void test_validate_lead_free_default(void)
{
    profile_t p;
    profile_default_lead_free(&p);
    TEST_ASSERT_EQUAL_INT(1, profile_validate(&p));
}

/* -----------------------------------------------------------------------
 * Validate: reject a stage whose target exceeds PROFILE_MAX_TEMP_C.
 * ----------------------------------------------------------------------- */
static void test_validate_rejects_over_max_temp(void)
{
    profile_t p;
    profile_default_leaded(&p);
    /* Force one stage above ceiling */
    p.stages[0].target_c = (float)(PROFILE_MAX_TEMP_C + 1);
    TEST_ASSERT_EQUAL_INT(0, profile_validate(&p));
}

/* -----------------------------------------------------------------------
 * Validate: reject a profile with a zero-duration stage.
 * ----------------------------------------------------------------------- */
static void test_validate_rejects_zero_duration(void)
{
    profile_t p;
    profile_default_leaded(&p);
    p.stages[0].duration_s = 0;
    TEST_ASSERT_EQUAL_INT(0, profile_validate(&p));
}

/* -----------------------------------------------------------------------
 * Validate: reject a profile with zero stages.
 * ----------------------------------------------------------------------- */
static void test_validate_rejects_zero_stages(void)
{
    profile_t p;
    profile_default_leaded(&p);
    p.n_stages = 0;
    TEST_ASSERT_EQUAL_INT(0, profile_validate(&p));
}

/* -----------------------------------------------------------------------
 * Default peak checks: leaded reflow peak should be 210–225 °C.
 * ----------------------------------------------------------------------- */
static void test_leaded_peak_in_range(void)
{
    profile_t p;
    profile_default_leaded(&p);
    /* Find the maximum target across all stages */
    float peak = 0.0f;
    for (int i = 0; i < p.n_stages; i++) {
        if (p.stages[i].target_c > peak)
            peak = p.stages[i].target_c;
    }
    TEST_ASSERT_GREATER_OR_EQUAL_FLOAT(210.0f, peak);
    TEST_ASSERT_LESS_OR_EQUAL_FLOAT(225.0f, peak);
}

/* -----------------------------------------------------------------------
 * Default peak checks: lead-free reflow peak should be 240–250 °C.
 * ----------------------------------------------------------------------- */
static void test_lead_free_peak_in_range(void)
{
    profile_t p;
    profile_default_lead_free(&p);
    float peak = 0.0f;
    for (int i = 0; i < p.n_stages; i++) {
        if (p.stages[i].target_c > peak)
            peak = p.stages[i].target_c;
    }
    TEST_ASSERT_GREATER_OR_EQUAL_FLOAT(240.0f, peak);
    TEST_ASSERT_LESS_OR_EQUAL_FLOAT(250.0f, peak);
}

/* -----------------------------------------------------------------------
 * Multi-stage interpolation: verify stage boundary and interior of
 * a 2-stage profile.
 * Stage 0: 100°C / 60s  (ramps from 25 → 100)
 * Stage 1: 200°C / 60s  (ramps from 100 → 200)
 * At t=60 (start of stage 1 / end of stage 0) → 100 °C
 * At t=90 (halfway through stage 1) → 150 °C
 * ----------------------------------------------------------------------- */
static void test_setpoint_multi_stage_boundary(void)
{
    profile_t p;
    p.n_stages = 2;
    snprintf(p.name, PROFILE_NAME_LEN, "Multi");
    p.stages[0].target_c  = 100.0f;
    p.stages[0].duration_s = 60;
    snprintf(p.stages[0].name, PROFILE_NAME_LEN, "s0");
    p.stages[1].target_c  = 200.0f;
    p.stages[1].duration_s = 60;
    snprintf(p.stages[1].name, PROFILE_NAME_LEN, "s1");

    /* At t=60 (end of stage 0) → 100 °C */
    TEST_ASSERT_FLOAT_WITHIN(0.5f, 100.0f, profile_setpoint(&p, 60));
    /* At t=90 (halfway through stage 1: 100 + (200-100)*30/60 = 150) */
    TEST_ASSERT_FLOAT_WITHIN(0.5f, 150.0f, profile_setpoint(&p, 90));
}

/* -----------------------------------------------------------------------
 * profile_total_s must equal sum of all stage durations.
 * ----------------------------------------------------------------------- */
static void test_total_s_equals_sum_of_durations(void)
{
    profile_t p;
    profile_default_leaded(&p);
    int expected = 0;
    for (int i = 0; i < p.n_stages; i++)
        expected += p.stages[i].duration_s;
    TEST_ASSERT_EQUAL_INT(expected, profile_total_s(&p));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_setpoint_at_t0_is_ambient);
    RUN_TEST(test_setpoint_mid_ramp);
    RUN_TEST(test_setpoint_at_total_time_equals_last_target);
    RUN_TEST(test_setpoint_past_end_clamps);
    RUN_TEST(test_validate_leaded_default);
    RUN_TEST(test_validate_lead_free_default);
    RUN_TEST(test_validate_rejects_over_max_temp);
    RUN_TEST(test_validate_rejects_zero_duration);
    RUN_TEST(test_validate_rejects_zero_stages);
    RUN_TEST(test_leaded_peak_in_range);
    RUN_TEST(test_lead_free_peak_in_range);
    RUN_TEST(test_setpoint_multi_stage_boundary);
    RUN_TEST(test_total_s_equals_sum_of_durations);
    return UNITY_END();
}
