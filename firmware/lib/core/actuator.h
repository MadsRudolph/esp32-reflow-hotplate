#ifndef ACTUATOR_H
#define ACTUATOR_H

#ifdef __cplusplus
extern "C" {
#endif

/* Split-range mapping of a bipolar PID effort in [-100,+100] onto two
 * non-overlapping duty outputs.  Positive effort drives the heater, negative
 * effort drives the cooling fan, with a deadband around zero where both are
 * off.  Heater and fan are NEVER both on. */
typedef struct {
    float heater_pct; /* 0..100 */
    float fan_pct;    /* 0..100 */
} drive_t;

/* effort_pct in [-100,100]; deadband_pct >= 0. */
drive_t actuator_split(float effort_pct, float deadband_pct);

#ifdef __cplusplus
}
#endif

#endif /* ACTUATOR_H */
