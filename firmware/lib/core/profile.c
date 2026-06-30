#include "profile.h"
#include <string.h>

/* Ambient start temperature used as the implicit setpoint before stage 0. */
#define AMBIENT_C 25.0f

/* --------------------------------------------------------------------------
 * profile_total_s
 * -------------------------------------------------------------------------- */
int profile_total_s(const profile_t *p)
{
    int total = 0;
    for (int i = 0; i < p->n_stages; i++)
        total += p->stages[i].duration_s;
    return total;
}

/* --------------------------------------------------------------------------
 * profile_setpoint
 *
 * Interpolation semantics:
 *   Each stage k ramps linearly from the previous stage's target (or AMBIENT_C
 *   for k=0) at the START of the stage to stages[k].target_c at the END.
 *   Past the last stage the value is clamped to the last stage's target.
 * -------------------------------------------------------------------------- */
float profile_setpoint(const profile_t *p, int elapsed_s)
{
    if (p->n_stages <= 0)
        return AMBIENT_C;

    float prev_target = AMBIENT_C;
    int   t_start     = 0;

    for (int i = 0; i < p->n_stages; i++) {
        int   dur  = p->stages[i].duration_s;
        float curr = p->stages[i].target_c;
        int   t_end = t_start + dur;

        if (elapsed_s <= t_end) {
            /* Within this stage: linear interpolation */
            if (dur <= 0)
                return curr;
            float frac = (float)(elapsed_s - t_start) / (float)dur;
            return prev_target + frac * (curr - prev_target);
        }

        prev_target = curr;
        t_start     = t_end;
    }

    /* Past the end: clamp to last stage's target */
    return p->stages[p->n_stages - 1].target_c;
}

/* --------------------------------------------------------------------------
 * profile_validate
 * -------------------------------------------------------------------------- */
int profile_validate(const profile_t *p)
{
    if (p->n_stages < 1 || p->n_stages > PROFILE_MAX_STAGES)
        return 0;
    if (p->name[0] == '\0')
        return 0;
    for (int i = 0; i < p->n_stages; i++) {
        if (p->stages[i].duration_s <= 0)
            return 0;
        if (p->stages[i].target_c <= 0.0f || p->stages[i].target_c > (float)PROFILE_MAX_TEMP_C)
            return 0;
    }
    return 1;
}

/* --------------------------------------------------------------------------
 * profile_default_leaded  — Sn63/Pb37
 *   preheat : 150 °C / 90 s
 *   soak    : 165 °C / 90 s
 *   reflow  : 215 °C / 45 s
 *   cool    :  50 °C / 90 s
 * -------------------------------------------------------------------------- */
void profile_default_leaded(profile_t *out)
{
    memset(out, 0, sizeof(*out));
    strncpy(out->name, "Leaded Sn63", PROFILE_NAME_LEN - 1);
    out->n_stages = 4;

    strncpy(out->stages[0].name, "Preheat", PROFILE_NAME_LEN - 1);
    out->stages[0].target_c   = 150.0f;
    out->stages[0].duration_s = 90;

    strncpy(out->stages[1].name, "Soak", PROFILE_NAME_LEN - 1);
    out->stages[1].target_c   = 165.0f;
    out->stages[1].duration_s = 90;

    strncpy(out->stages[2].name, "Reflow", PROFILE_NAME_LEN - 1);
    out->stages[2].target_c   = 215.0f;
    out->stages[2].duration_s = 45;

    strncpy(out->stages[3].name, "Cool", PROFILE_NAME_LEN - 1);
    out->stages[3].target_c   = 50.0f;
    out->stages[3].duration_s = 90;
}

/* --------------------------------------------------------------------------
 * profile_default_lead_free  — SAC305
 *   preheat : 150 °C / 90 s
 *   soak    : 180 °C / 90 s
 *   reflow  : 245 °C / 45 s
 *   cool    :  50 °C / 90 s
 * -------------------------------------------------------------------------- */
void profile_default_lead_free(profile_t *out)
{
    memset(out, 0, sizeof(*out));
    strncpy(out->name, "SAC305", PROFILE_NAME_LEN - 1);
    out->n_stages = 4;

    strncpy(out->stages[0].name, "Preheat", PROFILE_NAME_LEN - 1);
    out->stages[0].target_c   = 150.0f;
    out->stages[0].duration_s = 90;

    strncpy(out->stages[1].name, "Soak", PROFILE_NAME_LEN - 1);
    out->stages[1].target_c   = 180.0f;
    out->stages[1].duration_s = 90;

    strncpy(out->stages[2].name, "Reflow", PROFILE_NAME_LEN - 1);
    out->stages[2].target_c   = 245.0f;
    out->stages[2].duration_s = 45;

    strncpy(out->stages[3].name, "Cool", PROFILE_NAME_LEN - 1);
    out->stages[3].target_c   = 50.0f;
    out->stages[3].duration_s = 90;
}
