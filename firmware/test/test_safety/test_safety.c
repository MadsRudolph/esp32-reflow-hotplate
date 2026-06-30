#include <unity.h>
#include <math.h>
#include "safety.h"

void setUp(void) {}
void tearDown(void) {}

/* -----------------------------------------------------------------------
 * Accumulation/ordering semantics this suite pins down (must match safety.c):
 *
 *   STALL: each call FIRST does since_reading_s += dt_s, THEN checks
 *          since_reading_s >= stall_timeout_s, THEN resets to 0 when
 *          fresh_reading is nonzero.  Consequence: a fresh reading on the
 *          SAME tick that would otherwise stall STILL trips SAFE_STALL,
 *          because the >= check happens before the reset.  A fresh reading
 *          only prevents the NEXT tick's stall.
 *
 *   RUNAWAY: only evaluated while duty_pct > 50.  On the first heating tick
 *          after a (re)set, win_start_temp is captured; win_elapsed_s += dt_s
 *          on every heating tick (including the first).  When
 *          win_elapsed_s >= runaway_window_s, compare temp_c - win_start_temp
 *          against runaway_min_rise_c; if the rise is too small -> SAFE_RUNAWAY.
 *          The window then resets (win_start_temp = temp_c, win_elapsed_s = 0).
 *          While duty_pct <= 50 the window is held reset, so idle/cooldown
 *          never trips runaway.
 * ----------------------------------------------------------------------- */

/* -----------------------------------------------------------------------
 * Defaults applied by safety_init.
 * ----------------------------------------------------------------------- */
static void test_init_defaults(void)
{
    safety_t s;
    safety_init(&s);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 2.0f, s.runaway_min_rise_c);
    TEST_ASSERT_EQUAL_INT(20, s.runaway_window_s);
    TEST_ASSERT_EQUAL_INT(5, s.stall_timeout_s);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, s.win_start_temp);
    TEST_ASSERT_EQUAL_INT(0, s.win_elapsed_s);
    TEST_ASSERT_EQUAL_INT(0, s.since_reading_s);
}

/* -----------------------------------------------------------------------
 * Over-temp: at exactly the ceiling -> SAFE_OVERTEMP.
 * ----------------------------------------------------------------------- */
static void test_overtemp_at_ceiling(void)
{
    safety_t s;
    safety_init(&s);
    /* duty 0 to avoid runaway; fresh reading to avoid stall */
    TEST_ASSERT_EQUAL_INT(SAFE_OVERTEMP,
        safety_check(&s, SAFETY_CEILING_C, 1, 0.0f, 1, 1));
}

/* -----------------------------------------------------------------------
 * Just below ceiling with everything else healthy -> SAFE_OK.
 * ----------------------------------------------------------------------- */
static void test_just_below_ceiling_ok(void)
{
    safety_t s;
    safety_init(&s);
    TEST_ASSERT_EQUAL_INT(SAFE_OK,
        safety_check(&s, 259.9f, 1, 0.0f, 1, 1));
}

/* -----------------------------------------------------------------------
 * TC fault: tc_ok=0 beats over-temp (priority 1 > priority 2).
 * ----------------------------------------------------------------------- */
static void test_tc_fault_beats_overtemp(void)
{
    safety_t s;
    safety_init(&s);
    TEST_ASSERT_EQUAL_INT(SAFE_TC_FAULT,
        safety_check(&s, 300.0f, 0, 0.0f, 1, 1));
}

/* -----------------------------------------------------------------------
 * NaN temperature with tc_ok=1 -> SAFE_TC_FAULT.
 * ----------------------------------------------------------------------- */
static void test_nan_temp_is_tc_fault(void)
{
    safety_t s;
    safety_init(&s);
    TEST_ASSERT_EQUAL_INT(SAFE_TC_FAULT,
        safety_check(&s, NAN, 1, 0.0f, 1, 1));
}

/* -----------------------------------------------------------------------
 * Stall: with no fresh readings, accumulate dt_s until >= stall_timeout_s.
 * stall_timeout_s = 5.  After 5s of accumulation -> SAFE_STALL.
 * ----------------------------------------------------------------------- */
static void test_stall_after_timeout(void)
{
    safety_t s;
    safety_init(&s);
    /* 4 ticks of 1s each: since_reading goes 1,2,3,4 -> all OK */
    for (int i = 0; i < 4; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 80.0f, 1, 0.0f, 0, 1));
    /* 5th tick: since_reading reaches 5 >= 5 -> SAFE_STALL */
    TEST_ASSERT_EQUAL_INT(SAFE_STALL,
        safety_check(&s, 80.0f, 1, 0.0f, 0, 1));
}

/* -----------------------------------------------------------------------
 * A fresh_reading resets the stall timer: right after a fresh reading the
 * accumulator restarts, so we do not immediately stall.
 * ----------------------------------------------------------------------- */
static void test_fresh_reading_resets_stall(void)
{
    safety_t s;
    safety_init(&s);
    /* Build up 4s of staleness */
    for (int i = 0; i < 4; i++)
        safety_check(&s, 80.0f, 1, 0.0f, 0, 1);
    /* A fresh reading resets to 0 (after add+check on this same tick:
     * since_reading=5 would trip... but fresh is checked: per our ordering,
     * fresh resets AFTER the >= check.  To prove the RESET behaviour cleanly
     * we keep accumulation below the threshold here: 4s then fresh.
     * since_reading: 1,2,3,4 (4 stale ticks). Now a fresh tick: add ->5,
     * check 5>=5 -> STALL fires on the same tick per our documented ordering. */
    /* Therefore use only 3 stale ticks before the fresh reset to stay safe: */
    safety_init(&s);
    for (int i = 0; i < 3; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 80.0f, 1, 0.0f, 0, 1)); /* since_reading 1,2,3 */
    /* fresh reading: add->4 (4>=5 false, OK), then reset to 0 */
    TEST_ASSERT_EQUAL_INT(SAFE_OK,
        safety_check(&s, 80.0f, 1, 0.0f, 1, 1));
    /* Next stale tick: since_reading 1 -> OK (timer was reset) */
    TEST_ASSERT_EQUAL_INT(SAFE_OK,
        safety_check(&s, 80.0f, 1, 0.0f, 0, 1));
}

/* -----------------------------------------------------------------------
 * Runaway: heating hard (duty 100) but temp flat across the window -> trip.
 * runaway_window_s = 20.  Feed fresh readings each tick to avoid stall.
 * ----------------------------------------------------------------------- */
static void test_runaway_flat_temp_trips(void)
{
    safety_t s;
    safety_init(&s);
    /* 20 ticks of 1s, temp constant 80. win_elapsed: 1..20.
     * On the 20th tick win_elapsed=20>=20, rise=0 < 2.0 -> SAFE_RUNAWAY. */
    safety_fault_t f = SAFE_OK;
    for (int i = 0; i < 20; i++)
        f = safety_check(&s, 80.0f, 1, 100.0f, 1, 1);
    TEST_ASSERT_EQUAL_INT(SAFE_RUNAWAY, f);
}

/* -----------------------------------------------------------------------
 * Runaway: heating hard with temp rising well above min rise -> SAFE_OK.
 * ----------------------------------------------------------------------- */
static void test_runaway_rising_temp_ok(void)
{
    safety_t s;
    safety_init(&s);
    float temp = 80.0f;
    safety_fault_t f = SAFE_OK;
    for (int i = 0; i < 25; i++) {
        temp += 1.0f;  /* +1C/s -> +20C over the window, well above 2.0C */
        f = safety_check(&s, temp, 1, 100.0f, 1, 1);
        TEST_ASSERT_EQUAL_INT(SAFE_OK, f);
    }
}

/* -----------------------------------------------------------------------
 * Not heating (duty 0) with flat temp across more than a window -> SAFE_OK.
 * Proves the not-heating guard holds the window reset.
 * ----------------------------------------------------------------------- */
static void test_no_runaway_when_not_heating(void)
{
    safety_t s;
    safety_init(&s);
    for (int i = 0; i < 30; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 80.0f, 1, 0.0f, 1, 1));
}

/* -----------------------------------------------------------------------
 * A normal healthy heating tick -> SAFE_OK.
 * ----------------------------------------------------------------------- */
static void test_healthy_tick_ok(void)
{
    safety_t s;
    safety_init(&s);
    TEST_ASSERT_EQUAL_INT(SAFE_OK,
        safety_check(&s, 120.0f, 1, 100.0f, 1, 1));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_init_defaults);
    RUN_TEST(test_overtemp_at_ceiling);
    RUN_TEST(test_just_below_ceiling_ok);
    RUN_TEST(test_tc_fault_beats_overtemp);
    RUN_TEST(test_nan_temp_is_tc_fault);
    RUN_TEST(test_stall_after_timeout);
    RUN_TEST(test_fresh_reading_resets_stall);
    RUN_TEST(test_runaway_flat_temp_trips);
    RUN_TEST(test_runaway_rising_temp_ok);
    RUN_TEST(test_no_runaway_when_not_heating);
    RUN_TEST(test_healthy_tick_ok);
    return UNITY_END();
}
