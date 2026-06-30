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
 *   RUNAWAY: only evaluated while duty_pct > 50.  The baseline-capture tick
 *          and the evaluation tick are ALWAYS different ticks.  On the first
 *          heating tick after a (re)set (win_elapsed_s == 0) win_start_temp is
 *          captured and win_elapsed_s += dt_s, but the window does NOT evaluate
 *          this tick — even if a single huge dt_s already exceeds the window.
 *          On subsequent heating ticks (win_elapsed_s > 0) win_elapsed_s += dt_s
 *          and, when win_elapsed_s >= runaway_window_s, temp_c - win_start_temp
 *          is compared against runaway_min_rise_c; too small -> SAFE_RUNAWAY.
 *          Either way the window then rolls over (win_start_temp = temp_c,
 *          win_elapsed_s = 0).  While duty_pct <= 50 the window is held reset,
 *          so idle/cooldown never trips runaway.
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
    /* 3 stale ticks: since_reading 1,2,3 (all < 5) -> OK. */
    for (int i = 0; i < 3; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 80.0f, 1, 0.0f, 0, 1));
    /* Fresh reading tick: add -> 4 (4 >= 5 false -> OK), then reset to 0. */
    TEST_ASSERT_EQUAL_INT(SAFE_OK,
        safety_check(&s, 80.0f, 1, 0.0f, 1, 1));
    /* Next stale tick: since_reading restarts at 1 -> OK (timer was reset). */
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
    /* 20 ticks of 1s, temp constant 80.
     * Tick 1 captures the baseline (win_elapsed 0 -> 1) and does NOT evaluate.
     * Ticks 2..20 accumulate (win_elapsed 2..20).  On the 20th tick
     * win_elapsed=20>=20, rise=0 < 2.0 -> SAFE_RUNAWAY.  The deferral of the
     * baseline tick does NOT shift this case: with 1 s ticks the window still
     * first reaches 20 s on tick 20 exactly as before the fix. */
    safety_fault_t f = SAFE_OK;
    for (int i = 0; i < 19; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 80.0f, 1, 100.0f, 1, 1));   /* ticks 1..19 OK */
    f = safety_check(&s, 80.0f, 1, 100.0f, 1, 1);        /* tick 20 trips   */
    TEST_ASSERT_EQUAL_INT(SAFE_RUNAWAY, f);
}

/* -----------------------------------------------------------------------
 * Genuine flat-temp runaway across multiple normal ticks STILL trips, and at
 * the same tick (20) as before the deferral fix.  This pins the no-regression
 * guarantee for the real safety case.
 * ----------------------------------------------------------------------- */
static void test_runaway_still_trips_flat_multiticks(void)
{
    safety_t s;
    safety_init(&s);
    safety_fault_t f = SAFE_OK;
    for (int i = 0; i < 19; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 150.0f, 1, 100.0f, 1, 1));   /* ticks 1..19 OK */
    /* tick 20: win_elapsed reaches 20 >= 20, rise 0 < 2.0 -> trips */
    f = safety_check(&s, 150.0f, 1, 100.0f, 1, 1);
    TEST_ASSERT_EQUAL_INT(SAFE_RUNAWAY, f);
}

/* -----------------------------------------------------------------------
 * Fail-safe edge: a SINGLE first heating tick with dt_s >= the runaway window
 * (e.g. a stalled/coalesced 25 s tick) must NOT spuriously trip runaway.  The
 * baseline-capture tick can never be the evaluation tick.  The earliest a trip
 * can occur is a LATER tick that closes a full window above the captured
 * baseline.
 * ----------------------------------------------------------------------- */
static void test_runaway_single_big_tick_no_false_trip(void)
{
    safety_t s;
    safety_init(&s);
    /* Isolate the runaway stage: raise the stall timeout so a large dt_s does
     * not trip SAFE_STALL first (stall has higher priority than runaway).  This
     * leaves the runaway window (20 s) as the only stage the big dt can reach. */
    s.stall_timeout_s = 1000;
    /* One huge first heating tick: dt 25 >= window 20.  Baseline captured at
     * 80 C; this tick must return SAFE_OK (no spurious runaway) because the
     * baseline tick can never also be the evaluation tick. */
    TEST_ASSERT_EQUAL_INT(SAFE_OK,
        safety_check(&s, 80.0f, 1, 100.0f, 1, 25));
    /* A second flat heating tick whose dt again covers the window is the
     * EARLIEST a trip can occur — and it does, now that a real baseline (80 C)
     * exists and the rise is 0 < 2.0. */
    TEST_ASSERT_EQUAL_INT(SAFE_RUNAWAY,
        safety_check(&s, 80.0f, 1, 100.0f, 1, 25));
}

/* -----------------------------------------------------------------------
 * Dropping below the heating threshold (duty <= 50) holds the window reset,
 * so a re-baseline after resuming heat needs a FULL fresh window before it can
 * trip — it can never trip earlier off a stale pre-cooldown baseline.
 * ----------------------------------------------------------------------- */
static void test_runaway_duty_crossing_50_rebaselines(void)
{
    safety_t s;
    safety_init(&s);
    /* Heat partway into the window: 10 ticks of 1s at flat 100 C. */
    for (int i = 0; i < 10; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 100.0f, 1, 100.0f, 1, 1));   /* win_elapsed -> 10 */
    /* Drop to not-heating for a few ticks: window held reset every tick. */
    for (int i = 0; i < 3; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 100.0f, 1, 0.0f, 1, 1));      /* win reset, OK    */
    /* Resume heating, flat temp.  Re-baseline on the first heating tick, then
     * a FULL fresh 20 s window is required: ticks 1..19 must be OK, trip on the
     * 20th — never earlier (the pre-cooldown 10 s does NOT carry over). */
    safety_fault_t f = SAFE_OK;
    for (int i = 0; i < 19; i++)
        TEST_ASSERT_EQUAL_INT(SAFE_OK,
            safety_check(&s, 100.0f, 1, 100.0f, 1, 1));    /* ticks 1..19 OK   */
    f = safety_check(&s, 100.0f, 1, 100.0f, 1, 1);         /* tick 20 trips    */
    TEST_ASSERT_EQUAL_INT(SAFE_RUNAWAY, f);
}

/* -----------------------------------------------------------------------
 * Stall overshoot: a single first tick with dt_s well over the stall timeout
 * still trips SAFE_STALL (the accumulate-then-check ordering is unchanged).
 * ----------------------------------------------------------------------- */
static void test_stall_large_dt_overshoot(void)
{
    safety_t s;
    safety_init(&s);
    /* fresh_reading=0, dt 10 >= stall_timeout 5 -> since_reading 10 >= 5. */
    TEST_ASSERT_EQUAL_INT(SAFE_STALL,
        safety_check(&s, 80.0f, 1, 0.0f, 0, 10));
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
    RUN_TEST(test_runaway_still_trips_flat_multiticks);
    RUN_TEST(test_runaway_single_big_tick_no_false_trip);
    RUN_TEST(test_runaway_duty_crossing_50_rebaselines);
    RUN_TEST(test_stall_large_dt_overshoot);
    RUN_TEST(test_runaway_rising_temp_ok);
    RUN_TEST(test_no_runaway_when_not_heating);
    RUN_TEST(test_healthy_tick_ok);
    return UNITY_END();
}
