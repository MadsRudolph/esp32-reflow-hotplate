#include "safety.h"
#include <math.h>

/* --------------------------------------------------------------------------
 * safety_init — defaults plus zeroed internal state.
 * -------------------------------------------------------------------------- */
void safety_init(safety_t *s)
{
    s->runaway_min_rise_c = 2.0f;
    s->runaway_window_s   = 20;
    s->stall_timeout_s    = 5;

    s->win_start_temp     = 0.0f;
    s->win_elapsed_s      = 0;
    s->since_reading_s    = 0;
}

/* --------------------------------------------------------------------------
 * safety_check
 *
 * Faults are evaluated in fixed priority order; the FIRST that trips is
 * returned immediately:
 *   1. TC fault   — !tc_ok or NaN temperature.
 *   2. Over-temp  — temp_c >= SAFETY_CEILING_C.
 *   3. Stall      — too long since the last fresh reading.
 *   4. Runaway    — heating hard but temperature not rising.
 * -------------------------------------------------------------------------- */
safety_fault_t safety_check(safety_t *s, float temp_c, int tc_ok, float duty_pct,
                            int fresh_reading, int dt_s)
{
    /* 1. Thermocouple fault — highest priority, beats over-temp. */
    if (!tc_ok || isnan(temp_c))
        return SAFE_TC_FAULT;

    /* 2. Over-temperature — at or above the absolute ceiling. */
    if (temp_c >= SAFETY_CEILING_C)
        return SAFE_OVERTEMP;

    /* 3. Stall detection.
     * Ordering (deterministic, pinned by the tests):
     *   a) ADD dt_s to the since_reading accumulator.
     *   b) CHECK >= stall_timeout_s and trip SAFE_STALL if reached.
     *   c) RESET the accumulator to 0 only AFTER the check, when this tick
     *      carries a fresh reading.
     * Consequence: a fresh reading arriving on the very tick that would
     * otherwise stall still trips (check precedes reset); a fresh reading
     * only protects the NEXT tick. */
    s->since_reading_s += dt_s;
    if (s->since_reading_s >= s->stall_timeout_s)
        return SAFE_STALL;
    if (fresh_reading)
        s->since_reading_s = 0;

    /* 4. Runaway detection — only meaningful while actively heating.
     * Window mechanics (fail-safe invariant: the baseline-capture tick and the
     * evaluation tick are ALWAYS different ticks):
     *   - When duty_pct <= 50 (idle/cooldown) the window is held reset
     *     (start temp = current temp, elapsed = 0) so it can never trip.
     *   - On the FIRST heating tick after a (re)set (win_elapsed_s == 0) we
     *     capture win_start_temp and accumulate win_elapsed_s += dt_s, but we do
     *     NOT evaluate this tick.  This defers the rise check past the baseline
     *     tick so that a single huge dt_s on the first heating tick (dt_s >=
     *     runaway_window_s, e.g. a stalled/coalesced tick) can never trip
     *     runaway against a zero-rise baseline it just captured.
     *   - On subsequent heating ticks (win_elapsed_s > 0) we accumulate, and
     *     when win_elapsed_s >= runaway_window_s we evaluate the rise:
     *     if temp_c - win_start_temp < runaway_min_rise_c -> SAFE_RUNAWAY.
     *     Either way the window then rolls over (new start = temp_c,
     *     elapsed = 0) so the check is continuous and rolling. */
    if (duty_pct > 50.0f) {
        if (s->win_elapsed_s == 0) {
            /* window opens here — capture baseline, defer evaluation a tick */
            s->win_start_temp = temp_c;
            s->win_elapsed_s += dt_s;
        } else {
            s->win_elapsed_s += dt_s;
            if (s->win_elapsed_s >= s->runaway_window_s) {
                float rise = temp_c - s->win_start_temp;
                int   runaway = (rise < s->runaway_min_rise_c);
                /* roll the window over for the next interval */
                s->win_start_temp = temp_c;
                s->win_elapsed_s  = 0;
                if (runaway)
                    return SAFE_RUNAWAY;
            }
        }
    } else {
        /* not heating — hold the window reset so cooldown/idle never trips */
        s->win_start_temp = temp_c;
        s->win_elapsed_s  = 0;
    }

    return SAFE_OK;
}
