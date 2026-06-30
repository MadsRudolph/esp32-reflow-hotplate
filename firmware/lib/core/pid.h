#ifndef PID_H
#define PID_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float kp, ki, kd;
    float out_min, out_max;
    float integ;
    float prev_meas;
    int   started;
} pid_t;

void  pid_init(pid_t *p, float kp, float ki, float kd, float out_min, float out_max);
void  pid_reset(pid_t *p);
float pid_step(pid_t *p, float setpoint, float measurement, float dt_s);

#ifdef __cplusplus
}
#endif

#endif /* PID_H */
