#include "reflow.h"
#include <stddef.h>

/* Return nonzero if s is a RUNNING (non-terminal, non-idle) state. */
static int is_running(reflow_state_t s)
{
    return s == RS_PREHEAT || s == RS_SOAK || s == RS_REFLOW || s == RS_COOL;
}

/* Map a stage index to its run state.
 *
 * Rule (robust for the 4-stage defaults, well-defined for any n_stages>=1):
 *   - The LAST stage (idx == n_stages-1) is always the cool stage -> RS_COOL.
 *   - Earlier stages map by index: 0 -> RS_PREHEAT, 1 -> RS_SOAK, 2 -> RS_REFLOW.
 *   - Any earlier stage at idx >= 3 (only possible with >4 stages) is treated
 *     as RS_REFLOW (a "hot" stage) until the final cool stage is reached.
 * stage_idx is assumed already clamped to [0, n_stages-1] by the caller.
 */
static reflow_state_t stage_to_state(int stage_idx, int n_stages)
{
    if (stage_idx >= n_stages - 1)
        return RS_COOL;            /* final stage is always cool */
    switch (stage_idx) {
        case 0:  return RS_PREHEAT;
        case 1:  return RS_SOAK;
        default: return RS_REFLOW; /* idx 2 and any earlier-but-higher idx */
    }
}

/* Compute the active stage index from elapsed time by walking cumulative
 * stage durations.  A stage owns the half-open boundary at its end inclusively
 * here in the sense that elapsed exactly equal to a cumulative end stays in
 * that stage (matches profile_setpoint's elapsed <= t_end semantics).
 * Result is clamped to [0, n_stages-1]. */
static int stage_from_elapsed(const profile_t *p, int elapsed_s)
{
    int t_end = 0;
    for (int i = 0; i < p->n_stages; i++) {
        t_end += p->stages[i].duration_s;
        if (elapsed_s <= t_end)
            return i;
    }
    return p->n_stages - 1;
}

void reflow_init(reflow_t *r)
{
    r->state      = RS_IDLE;
    r->prof       = NULL;
    r->elapsed_s  = 0;
    r->setpoint_c = 0.0f;
    r->stage_idx  = 0;
    r->aborted    = 0;
}

int reflow_start(reflow_t *r, const profile_t *p)
{
    if (r->state != RS_IDLE)
        return 1;
    if (p == NULL)
        return 1;
    if (!profile_validate(p))
        return 1;

    r->prof       = p;
    r->elapsed_s  = 0;
    r->stage_idx  = 0;
    r->state      = RS_PREHEAT;
    r->setpoint_c = profile_setpoint(p, 0);
    r->aborted    = 0;
    return 0;
}

void reflow_tick(reflow_t *r, float temp_c, int dt_s, int safety_fault)
{
    (void)temp_c;  /* accepted for interface symmetry; unused this phase */

    /* Terminal/idle states do not advance. */
    if (!is_running(r->state))
        return;

    /* A safety fault while running latches RS_FAULT without advancing time. */
    if (safety_fault) {
        r->state = RS_FAULT;
        return;
    }

    /* Latched abort: durable cooldown that NEVER reverts to a hot stage.
     * Advance time toward DONE but FORCE the cool target as the setpoint so we
     * never command heat (and never replay the cool ramp's hot initial value).
     * Skips the normal stage->state mapping entirely. */
    if (r->aborted) {
        int last = r->prof->n_stages - 1;
        r->elapsed_s += dt_s;
        r->stage_idx  = last;
        r->setpoint_c = r->prof->stages[last].target_c;
        r->state      = (r->elapsed_s >= profile_total_s(r->prof))
                            ? RS_DONE : RS_COOL;
        return;
    }

    r->elapsed_s += dt_s;
    r->setpoint_c = profile_setpoint(r->prof, r->elapsed_s);

    if (r->elapsed_s >= profile_total_s(r->prof)) {
        r->stage_idx = r->prof->n_stages - 1;
        r->state     = RS_DONE;
        return;
    }

    r->stage_idx = stage_from_elapsed(r->prof, r->elapsed_s);
    r->state     = stage_to_state(r->stage_idx, r->prof->n_stages);
}

/* Abort: from any running state latch a durable cooldown.  Set state=RS_COOL,
 * mark `aborted` so reflow_tick will keep commanding the cool target and never
 * revert to a hot stage, and position the timeline at the START of the final
 * cool stage so the existing elapsed >= total path still drives it to DONE.
 * From idle/terminal states this is a no-op — there is nothing to cool. */
void reflow_abort(reflow_t *r)
{
    if (!is_running(r->state))
        return;

    int last = r->prof->n_stages - 1;
    r->aborted    = 1;
    r->state      = RS_COOL;
    r->stage_idx  = last;
    r->elapsed_s  = profile_total_s(r->prof) - r->prof->stages[last].duration_s;
    r->setpoint_c = r->prof->stages[last].target_c;
}

void reflow_ack(reflow_t *r)
{
    if (r->state == RS_FAULT || r->state == RS_DONE)
        reflow_init(r);
}

reflow_state_t reflow_state(const reflow_t *r)
{
    return r->state;
}
