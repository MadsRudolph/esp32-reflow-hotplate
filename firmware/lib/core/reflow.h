#ifndef REFLOW_H
#define REFLOW_H

#include "profile.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Reflow run state machine.
 *
 * RUNNING states are RS_PREHEAT, RS_SOAK, RS_REFLOW, RS_COOL.
 * TERMINAL/idle states are RS_IDLE, RS_DONE, RS_FAULT (do not advance on tick;
 * cleared via reflow_ack for DONE/FAULT).  RS_COOL is NOT terminal — it keeps
 * ticking toward DONE.
 */
typedef enum {
    RS_IDLE,
    RS_PREHEAT,
    RS_SOAK,
    RS_REFLOW,
    RS_COOL,
    RS_DONE,
    RS_FAULT
} reflow_state_t;

typedef struct {
    reflow_state_t  state;
    const profile_t *prof;
    int             elapsed_s;
    float           setpoint_c;
    int             stage_idx;
    int             aborted;     /* internal: latched-abort cooldown flag */
} reflow_t;

/* Reset to a clean idle state. */
void reflow_init(reflow_t *r);

/* Begin a run.  Only valid from RS_IDLE with a non-NULL, valid profile.
 * On success: prof=p, elapsed_s=0, stage_idx=0, state=RS_PREHEAT,
 * setpoint_c=profile_setpoint(p,0); returns 0.
 * On failure (not idle / NULL / invalid profile): returns nonzero, no mutation. */
int reflow_start(reflow_t *r, const profile_t *p);

/* Advance the run by dt_s seconds.
 *  - In a terminal/idle state (IDLE/DONE/FAULT): no-op.
 *  - safety_fault nonzero while running: state=RS_FAULT immediately, no time advance.
 *  - Otherwise: elapsed_s += dt_s; recompute setpoint and stage_idx; map stage to
 *    state; when elapsed_s >= profile_total_s(prof) -> RS_DONE.
 * temp_c is accepted for interface symmetry; it does not drive transitions here. */
void reflow_tick(reflow_t *r, float temp_c, int dt_s, int safety_fault);

/* Abort: from any running state -> RS_COOL (let it cool).  No-op otherwise. */
void reflow_abort(reflow_t *r);

/* Acknowledge a finished/faulted run: RS_FAULT or RS_DONE -> reset to RS_IDLE.
 * No-op in any other state. */
void reflow_ack(reflow_t *r);

/* Return the current state. */
reflow_state_t reflow_state(const reflow_t *r);

#ifdef __cplusplus
}
#endif

#endif /* REFLOW_H */
