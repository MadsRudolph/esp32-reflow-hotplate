#include <unity.h>
#include <math.h>
#include "pid.h"

void setUp(void) {}
void tearDown(void) {}

static void test_p_only(void) {
    pid_t p;
    pid_init(&p, 2, 0, 0, 0, 100);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 20.0f, pid_step(&p, 110, 100, 1.0f)); /* 2*(110-100)=20 */
}

static void test_clamp_and_antiwindup(void) {
    pid_t p;
    pid_init(&p, 0, 10, 0, 0, 100);
    for (int i = 0; i < 100; i++) pid_step(&p, 200, 0, 1.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 100.0f, pid_step(&p, 200, 0, 1.0f)); /* clamped */
    float integ_sat = p.integ;
    pid_step(&p, 200, 0, 1.0f);
    TEST_ASSERT_TRUE(p.integ <= integ_sat + 0.001f); /* no windup */
}

static void test_deriv_on_measurement_no_setpoint_kick(void) {
    pid_t a, b;
    pid_init(&a, 0, 0, 5, -1000, 1000);
    pid_init(&b, 0, 0, 5, -1000, 1000);
    pid_step(&a, 100, 100, 1.0f);
    float kick = pid_step(&a, 140, 100, 1.0f); /* setpoint jumps, meas steady */
    pid_step(&b, 100, 100, 1.0f);
    float steady = pid_step(&b, 100, 100, 1.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, steady, kick); /* identical: no kick */
}

/* After a normal step, a dt_s=0 call must return a finite value within
   [out_min, out_max] even with non-zero kd and a measurement change. */
static void test_dt_zero_is_finite_and_safe(void) {
    pid_t p;
    pid_init(&p, 1, 0, 10, 0, 100); /* kd=10, out range [0,100] */
    /* Prime the controller so prev_meas is set and started=1 */
    pid_step(&p, 100, 50, 1.0f);
    /* Now call with dt_s=0 and a measurement change — would divide by zero
       in the old code, producing ±Inf or NaN. */
    float out = pid_step(&p, 100, 80, 0.0f);
    TEST_ASSERT_FALSE(isnan(out));
    TEST_ASSERT_FALSE(isinf(out));
    TEST_ASSERT_GREATER_OR_EQUAL_FLOAT(0.0f, out);
    TEST_ASSERT_LESS_OR_EQUAL_FLOAT(100.0f, out);
}

/* Feed an adversarial sequence (including dt=0 and extreme values) and
   assert every returned output is finite and within [out_min, out_max]. */
static void test_output_never_nan(void) {
    pid_t p;
    pid_init(&p, 2, 1, 5, -100, 100);

    float dt_seq[]   = {1.0f, 0.0f, 0.0f, 1.0f, 0.5f, 0.0f, 2.0f};
    float meas_seq[] = {0.0f, 1e30f, -1e30f, 50.0f, 50.0f, 50.0f, 100.0f};
    int n = (int)(sizeof(dt_seq) / sizeof(dt_seq[0]));

    for (int i = 0; i < n; i++) {
        float out = pid_step(&p, 100.0f, meas_seq[i], dt_seq[i]);
        TEST_ASSERT_FALSE_MESSAGE(isnan(out), "pid_step returned NaN");
        TEST_ASSERT_FALSE_MESSAGE(isinf(out), "pid_step returned Inf");
        TEST_ASSERT_GREATER_OR_EQUAL_FLOAT(-100.0f, out);
        TEST_ASSERT_LESS_OR_EQUAL_FLOAT(100.0f, out);
    }
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_p_only);
    RUN_TEST(test_clamp_and_antiwindup);
    RUN_TEST(test_deriv_on_measurement_no_setpoint_kick);
    RUN_TEST(test_dt_zero_is_finite_and_safe);
    RUN_TEST(test_output_never_nan);
    return UNITY_END();
}
