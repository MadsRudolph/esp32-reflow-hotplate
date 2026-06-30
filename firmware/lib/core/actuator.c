#include "actuator.h"

static inline float clampf(float v, float lo, float hi)
{
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

drive_t actuator_split(float effort_pct, float deadband_pct)
{
    drive_t d = { 0.0f, 0.0f };

    if (effort_pct > deadband_pct) {
        d.heater_pct = clampf(effort_pct, 0.0f, 100.0f);
    } else if (effort_pct < -deadband_pct) {
        d.fan_pct = clampf(-effort_pct, 0.0f, 100.0f);
    }
    /* within [-deadband_pct, +deadband_pct] inclusive: both remain 0 */

    return d;
}
