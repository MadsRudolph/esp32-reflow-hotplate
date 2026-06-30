#include "pid.h"
#include <math.h>

void pid_init(pid_t *p, float kp, float ki, float kd, float out_min, float out_max)
{
    p->kp      = kp;
    p->ki      = ki;
    p->kd      = kd;
    p->out_min = out_min;
    p->out_max = out_max;
    p->integ   = 0.0f;
    p->prev_meas = 0.0f;
    p->started = 0;
}

void pid_reset(pid_t *p)
{
    p->integ   = 0.0f;
    p->prev_meas = 0.0f;
    p->started = 0;
}

float pid_step(pid_t *p, float setpoint, float measurement, float dt_s)
{
    float error = setpoint - measurement;

    /* Proportional term */
    float P = p->kp * error;

    /* Derivative on measurement (not on error) — skipped on first call to
       avoid a spike from an uninitialised prev_meas or a setpoint jump. */
    float D = 0.0f;
    if (p->started) {
        float dmeas = measurement - p->prev_meas;
        D = -p->kd * dmeas / dt_s;
    }

    /* Compute unclamped output (integral not yet updated) */
    float u = P + p->integ + D;

    /* Clamp */
    float out = u;
    if (out > p->out_max) out = p->out_max;
    if (out < p->out_min) out = p->out_min;

    /* Conditional integration (anti-windup):
       Only integrate when output is not saturated in the same direction
       as the integral contribution would push it.
       Equivalently: skip if the output is at the max limit AND error > 0,
       or at the min limit AND error < 0. */
    int saturated_high = (out >= p->out_max) && (error > 0.0f);
    int saturated_low  = (out <= p->out_min) && (error < 0.0f);
    if (!saturated_high && !saturated_low) {
        p->integ += p->ki * error * dt_s;
    }

    p->prev_meas = measurement;
    p->started   = 1;

    return out;
}
