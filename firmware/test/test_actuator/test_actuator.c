#include <unity.h>
#include "actuator.h"
void setUp(void){} void tearDown(void){}
static void test_positive_effort_heats_only(void){ drive_t d=actuator_split(60.0f,5.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f,60.0f,d.heater_pct); TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,d.fan_pct); }
static void test_negative_effort_cools_only(void){ drive_t d=actuator_split(-40.0f,5.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,d.heater_pct); TEST_ASSERT_FLOAT_WITHIN(0.01f,40.0f,d.fan_pct); }
static void test_deadband_both_off(void){ drive_t d=actuator_split(3.0f,5.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,d.heater_pct); TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,d.fan_pct); }
static void test_never_both_on(void){ for(float e=-100;e<=100;e+=1.0f){ drive_t d=actuator_split(e,5.0f);
    TEST_ASSERT_FALSE(d.heater_pct>0.0f && d.fan_pct>0.0f);
    TEST_ASSERT_TRUE(d.heater_pct>=0.0f && d.heater_pct<=100.0f);
    TEST_ASSERT_TRUE(d.fan_pct>=0.0f && d.fan_pct<=100.0f); } }
static void test_clamps_over_range(void){ drive_t d=actuator_split(150.0f,5.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f,100.0f,d.heater_pct);
    drive_t c=actuator_split(-150.0f,5.0f); TEST_ASSERT_FLOAT_WITHIN(0.01f,100.0f,c.fan_pct); }
/* Deadband boundary inclusivity: effort == +deadband -> both off (inclusive). */
static void test_deadband_boundary_inclusive_both_off(void){ drive_t d=actuator_split(5.0f,5.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,d.heater_pct); TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,d.fan_pct);
    drive_t c=actuator_split(-5.0f,5.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,c.heater_pct); TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,c.fan_pct); }
/* Just above deadband -> heater turns on (strict inequality past boundary). */
static void test_just_above_deadband_heats(void){ drive_t d=actuator_split(5.5f,5.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f,5.5f,d.heater_pct); TEST_ASSERT_FLOAT_WITHIN(0.01f,0.0f,d.fan_pct); }
int main(void){ UNITY_BEGIN(); RUN_TEST(test_positive_effort_heats_only);
    RUN_TEST(test_negative_effort_cools_only); RUN_TEST(test_deadband_both_off);
    RUN_TEST(test_never_both_on); RUN_TEST(test_clamps_over_range);
    RUN_TEST(test_deadband_boundary_inclusive_both_off);
    RUN_TEST(test_just_above_deadband_heats); return UNITY_END(); }
