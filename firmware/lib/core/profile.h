#ifndef PROFILE_H
#define PROFILE_H

#ifdef __cplusplus
extern "C" {
#endif

/* Maximum temperature ceiling for any reflow stage.
 * NOTE (Task 6): When safety.h is introduced it will define SAFETY_CEILING_C.
 * At that point, reconcile so there is a single source of truth — either have
 * safety.h include this header and reuse PROFILE_MAX_TEMP_C, or move the
 * constant there and #include "safety.h" here.  Do NOT pre-create safety.h. */
#define PROFILE_MAX_TEMP_C  260

#define PROFILE_MAX_STAGES  6
#define PROFILE_NAME_LEN    16

typedef struct {
    char  name[PROFILE_NAME_LEN];
    float target_c;
    int   duration_s;
} stage_t;

typedef struct {
    char    name[PROFILE_NAME_LEN];
    int     n_stages;
    stage_t stages[PROFILE_MAX_STAGES];
} profile_t;

/* Return the interpolated temperature setpoint (°C) at elapsed_s seconds into
 * the profile.  Clamps past the end to the last stage's target. */
float profile_setpoint(const profile_t *p, int elapsed_s);

/* Return the total duration of the profile in seconds (sum of all stage
 * duration_s values).  Returns 0 for an empty profile. */
int   profile_total_s(const profile_t *p);

/* Validate the profile.  Returns 1 if valid, 0 otherwise.
 * Valid iff: 1 <= n_stages <= PROFILE_MAX_STAGES,
 *            every duration_s > 0,
 *            every 0 < target_c <= PROFILE_MAX_TEMP_C,
 *            name is non-empty. */
int   profile_validate(const profile_t *p);

/* Populate *out with the default leaded (Sn63/Pb37) solder profile. */
void  profile_default_leaded(profile_t *out);

/* Populate *out with the default lead-free (SAC305) solder profile. */
void  profile_default_lead_free(profile_t *out);

#ifdef __cplusplus
}
#endif

#endif /* PROFILE_H */
