#include <unity.h>
#include <math.h>
#include <stdio.h>
#include "profile.h"
#include "reflow.h"

/* Lead-free (SAC305) default stage layout, confirmed from profile.c:
 *   stage 0 preheat 150C / 90s   -> cumulative end  90s  -> RS_PREHEAT
 *   stage 1 soak    180C / 90s   -> cumulative end 180s  -> RS_SOAK
 *   stage 2 reflow  245C / 45s   -> cumulative end 225s  -> RS_REFLOW
 *   stage 3 cool     50C / 90s   -> cumulative end 315s  -> RS_COOL (final stage)
 * total = 315s, at which point elapsed >= total -> RS_DONE.
 */

static profile_t g_lf;

void setUp(void)   { profile_default_lead_free(&g_lf); }
void tearDown(void){}

/* ----------------------------------------------------------------------- */
static void test_init_yields_idle(void)
{
    reflow_t r;
    reflow_init(&r);
    TEST_ASSERT_EQUAL_INT(RS_IDLE, reflow_state(&r));
    TEST_ASSERT_NULL(r.prof);
    TEST_ASSERT_EQUAL_INT(0, r.elapsed_s);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, r.setpoint_c);
    TEST_ASSERT_EQUAL_INT(0, r.stage_idx);
}

/* ----------------------------------------------------------------------- */
static void test_start_from_idle_ok(void)
{
    reflow_t r;
    reflow_init(&r);
    int rc = reflow_start(&r, &g_lf);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_INT(RS_PREHEAT, reflow_state(&r));
    TEST_ASSERT_EQUAL_PTR(&g_lf, r.prof);
    TEST_ASSERT_EQUAL_INT(0, r.elapsed_s);
    TEST_ASSERT_EQUAL_INT(0, r.stage_idx);
    TEST_ASSERT_EQUAL_FLOAT(profile_setpoint(&g_lf, 0), r.setpoint_c);
}

/* ----------------------------------------------------------------------- */
static void test_start_null_profile_fails(void)
{
    reflow_t r;
    reflow_init(&r);
    int rc = reflow_start(&r, NULL);
    TEST_ASSERT_NOT_EQUAL(0, rc);
    TEST_ASSERT_EQUAL_INT(RS_IDLE, reflow_state(&r));
}

/* ----------------------------------------------------------------------- */
static void test_start_invalid_profile_fails(void)
{
    reflow_t r;
    reflow_init(&r);
    profile_t bad;
    profile_default_lead_free(&bad);
    bad.n_stages = 0;                 /* makes profile_validate fail */
    int rc = reflow_start(&r, &bad);
    TEST_ASSERT_NOT_EQUAL(0, rc);
    TEST_ASSERT_EQUAL_INT(RS_IDLE, reflow_state(&r));
}

/* ----------------------------------------------------------------------- */
static void test_start_when_not_idle_fails(void)
{
    reflow_t r;
    reflow_init(&r);
    TEST_ASSERT_EQUAL_INT(0, reflow_start(&r, &g_lf));   /* now PREHEAT */
    int rc = reflow_start(&r, &g_lf);                    /* second start */
    TEST_ASSERT_NOT_EQUAL(0, rc);
    TEST_ASSERT_EQUAL_INT(RS_PREHEAT, reflow_state(&r));
}

/* ----------------------------------------------------------------------- */
/* Tick through the lead-free profile asserting state just-before and
 * just-after each cumulative boundary (90/180/225/315). */
static void test_tick_transitions_through_profile(void)
{
    reflow_t r;
    reflow_init(&r);
    reflow_start(&r, &g_lf);

    /* Helper pattern: tick 1 second at a time, no fault. */
    /* Advance to elapsed=89 -> still PREHEAT */
    for (int i = 0; i < 89; i++) reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(89, r.elapsed_s);
    TEST_ASSERT_EQUAL_INT(RS_PREHEAT, reflow_state(&r));

    /* elapsed=90 -> end of preheat. profile_setpoint walks stage where
     * elapsed <= t_end, so stage_idx at exactly 90 is still preheat(0). */
    reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(90, r.elapsed_s);
    TEST_ASSERT_EQUAL_INT(RS_PREHEAT, reflow_state(&r));

    /* elapsed=91 -> SOAK */
    reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(91, r.elapsed_s);
    TEST_ASSERT_EQUAL_INT(RS_SOAK, reflow_state(&r));

    /* advance to elapsed=180 -> still SOAK (boundary inclusive) */
    while (r.elapsed_s < 180) reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(180, r.elapsed_s);
    TEST_ASSERT_EQUAL_INT(RS_SOAK, reflow_state(&r));

    /* elapsed=181 -> REFLOW */
    reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(RS_REFLOW, reflow_state(&r));

    /* advance to elapsed=225 -> still REFLOW (boundary inclusive) */
    while (r.elapsed_s < 225) reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(225, r.elapsed_s);
    TEST_ASSERT_EQUAL_INT(RS_REFLOW, reflow_state(&r));

    /* elapsed=226 -> COOL (final stage) */
    reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(RS_COOL, reflow_state(&r));

    /* advance to elapsed=314 -> still COOL */
    while (r.elapsed_s < 314) reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(314, r.elapsed_s);
    TEST_ASSERT_EQUAL_INT(RS_COOL, reflow_state(&r));

    /* elapsed=315 == total -> DONE */
    reflow_tick(&r, 25.0f, 1, 0);
    TEST_ASSERT_EQUAL_INT(315, r.elapsed_s);
    TEST_ASSERT_EQUAL_INT(RS_DONE, reflow_state(&r));
}

/* ----------------------------------------------------------------------- */
static void test_setpoint_tracks_profile_after_tick(void)
{
    reflow_t r;
    reflow_init(&r);
    reflow_start(&r, &g_lf);
    reflow_tick(&r, 25.0f, 30, 0);
    TEST_ASSERT_EQUAL_INT(30, r.elapsed_s);
    TEST_ASSERT_EQUAL_FLOAT(profile_setpoint(&g_lf, 30), r.setpoint_c);
}

/* ----------------------------------------------------------------------- */
static void test_safety_fault_forces_fault_and_is_terminal(void)
{
    reflow_t r;
    reflow_init(&r);
    reflow_start(&r, &g_lf);
    reflow_tick(&r, 25.0f, 10, 0);
    int elapsed_before = r.elapsed_s;

    /* fault during a running state -> RS_FAULT, time not advanced */
    reflow_tick(&r, 25.0f, 5, 1);
    TEST_ASSERT_EQUAL_INT(RS_FAULT, reflow_state(&r));
    TEST_ASSERT_EQUAL_INT(elapsed_before, r.elapsed_s);

    /* subsequent normal tick stays FAULT (terminal until ack) */
    reflow_tick(&r, 25.0f, 5, 0);
    TEST_ASSERT_EQUAL_INT(RS_FAULT, reflow_state(&r));
    TEST_ASSERT_EQUAL_INT(elapsed_before, r.elapsed_s);
}

/* ----------------------------------------------------------------------- */
static void test_abort_from_running_goes_cool(void)
{
    reflow_t r;
    reflow_init(&r);
    reflow_start(&r, &g_lf);
    reflow_tick(&r, 25.0f, 10, 0);   /* PREHEAT */
    reflow_abort(&r);
    TEST_ASSERT_EQUAL_INT(RS_COOL, reflow_state(&r));
}

/* ----------------------------------------------------------------------- */
static void test_ack_from_done_resets_to_idle(void)
{
    reflow_t r;
    reflow_init(&r);
    reflow_start(&r, &g_lf);
    /* drive to DONE */
    while (reflow_state(&r) != RS_DONE) reflow_tick(&r, 25.0f, 5, 0);
    reflow_ack(&r);
    TEST_ASSERT_EQUAL_INT(RS_IDLE, reflow_state(&r));
    TEST_ASSERT_NULL(r.prof);
    TEST_ASSERT_EQUAL_INT(0, r.elapsed_s);
}

/* ----------------------------------------------------------------------- */
static void test_ack_from_fault_resets_to_idle(void)
{
    reflow_t r;
    reflow_init(&r);
    reflow_start(&r, &g_lf);
    reflow_tick(&r, 25.0f, 5, 1);    /* -> FAULT */
    TEST_ASSERT_EQUAL_INT(RS_FAULT, reflow_state(&r));
    reflow_ack(&r);
    TEST_ASSERT_EQUAL_INT(RS_IDLE, reflow_state(&r));
}

/* ----------------------------------------------------------------------- */
static void test_tick_in_terminal_or_idle_does_nothing(void)
{
    /* IDLE */
    reflow_t r;
    reflow_init(&r);
    reflow_tick(&r, 25.0f, 10, 0);
    TEST_ASSERT_EQUAL_INT(RS_IDLE, reflow_state(&r));
    TEST_ASSERT_EQUAL_INT(0, r.elapsed_s);

    /* DONE */
    reflow_init(&r);
    reflow_start(&r, &g_lf);
    while (reflow_state(&r) != RS_DONE) reflow_tick(&r, 25.0f, 5, 0);
    int done_elapsed = r.elapsed_s;
    reflow_tick(&r, 25.0f, 10, 0);
    TEST_ASSERT_EQUAL_INT(RS_DONE, reflow_state(&r));
    TEST_ASSERT_EQUAL_INT(done_elapsed, r.elapsed_s);

    /* FAULT */
    reflow_init(&r);
    reflow_start(&r, &g_lf);
    reflow_tick(&r, 25.0f, 5, 1);
    int fault_elapsed = r.elapsed_s;
    reflow_tick(&r, 25.0f, 10, 0);
    TEST_ASSERT_EQUAL_INT(RS_FAULT, reflow_state(&r));
    TEST_ASSERT_EQUAL_INT(fault_elapsed, r.elapsed_s);
}

/* ----------------------------------------------------------------------- */
int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_init_yields_idle);
    RUN_TEST(test_start_from_idle_ok);
    RUN_TEST(test_start_null_profile_fails);
    RUN_TEST(test_start_invalid_profile_fails);
    RUN_TEST(test_start_when_not_idle_fails);
    RUN_TEST(test_tick_transitions_through_profile);
    RUN_TEST(test_setpoint_tracks_profile_after_tick);
    RUN_TEST(test_safety_fault_forces_fault_and_is_terminal);
    RUN_TEST(test_abort_from_running_goes_cool);
    RUN_TEST(test_ack_from_done_resets_to_idle);
    RUN_TEST(test_ack_from_fault_resets_to_idle);
    RUN_TEST(test_tick_in_terminal_or_idle_does_nothing);
    return UNITY_END();
}
