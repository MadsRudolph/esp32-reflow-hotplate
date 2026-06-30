#ifndef SAFETY_H
#define SAFETY_H

#ifdef __cplusplus
extern "C" {
#endif

/* Single source of truth for the absolute temperature ceiling (°C).
 * profile.h derives PROFILE_MAX_TEMP_C from this; do NOT add a second
 * numeric 260 literal anywhere else.  safety.h must NOT include profile.h
 * (profile.h includes safety.h, not the other way round). */
#define SAFETY_CEILING_C 260.0f

typedef enum {
    SAFE_OK = 0,
    SAFE_OVERTEMP,
    SAFE_RUNAWAY,
    SAFE_TC_FAULT,
    SAFE_STALL
} safety_fault_t;

typedef struct {
    /* configuration */
    float runaway_min_rise_c;  /* min °C rise required per window while heating */
    int   runaway_window_s;    /* rolling runaway evaluation window (s)         */
    int   stall_timeout_s;     /* max seconds without a fresh reading (s)       */
    /* internal state — set to 0 by safety_init, do not touch externally */
    float win_start_temp;      /* temp captured when the runaway window opened  */
    int   win_elapsed_s;       /* seconds accumulated in the current window     */
    int   since_reading_s;     /* seconds since the last fresh reading          */
} safety_t;

/* Initialise *s with default thresholds (rise 2.0 °C, window 20 s, stall 5 s)
 * and zeroed internal state. */
void safety_init(safety_t *s);

/* Evaluate one tick of the safety watchdog and return the FIRST tripped fault
 * (in priority order: TC fault, over-temp, stall, runaway) or SAFE_OK.
 *   temp_c        : measured temperature (°C); NaN -> TC fault
 *   tc_ok         : nonzero if the thermocouple reading is valid
 *   duty_pct      : commanded heater duty (0..100); runaway only checked >50
 *   fresh_reading : nonzero if this tick carries a new sensor reading
 *   dt_s          : seconds elapsed since the previous call */
safety_fault_t safety_check(safety_t *s, float temp_c, int tc_ok, float duty_pct,
                            int fresh_reading, int dt_s);

#ifdef __cplusplus
}
#endif

#endif /* SAFETY_H */
