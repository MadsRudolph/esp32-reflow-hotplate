#include <unity.h>
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

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_p_only);
    RUN_TEST(test_clamp_and_antiwindup);
    RUN_TEST(test_deriv_on_measurement_no_setpoint_kick);
    return UNITY_END();
}
