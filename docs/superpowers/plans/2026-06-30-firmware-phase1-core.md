# Reflow Firmware — Phase 1: Core Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and unit-test the pure-C control core of the reflow firmware — PID, reflow profile model, run state machine, safety watchdog, and the profile settings store — entirely on the desktop (`native`) with Unity, with zero ESP-IDF dependencies.

**Architecture:** A PlatformIO project with two envs: `esp32dev` (framework=espidf, for later phases) and `native` (gcc + Unity, for these tests). The control core lives in `firmware/lib/core/` as a standalone C library with NO hardware/ESP-IDF includes, so it compiles and is unit-tested on the host. Later phases (HAL, UI, net) link this same library on the ESP32.

**Tech Stack:** PlatformIO 6.1.x, ESP-IDF (target env only, not exercised in this phase), C11, Unity test framework on the `native` platform.

## Global Constraints

- **Language:** C11, pure C. `firmware/lib/core/` must include ONLY the C standard library + its own headers — NO `esp_*`, `driver/*`, `freertos/*`, or Arduino headers (that is what keeps it native-testable). Verified by the `native` build compiling it with gcc.
- **Testing:** `native` env, Unity. Tests live under `firmware/test/`. Run with `pio test -e native`. Every `core/` module is TDD'd: failing Unity test first, then implementation.
- **Safety ceiling:** `SAFETY_CEILING_C = 260` (°C), defined once in `core/safety.h` and used by `profile_validate` and the over-temp trip (spec §4/§7).
- **Default profiles (seed data):** leaded **Sn63/Pb37** and lead-free **SAC305**, as stage tables (spec §2).
- **No hardware in this phase.** No `main.c`, no drivers, no FreeRTOS. Pure logic + tests only.
- **Commits:** never mention Claude/AI in commit messages.

## File Structure

```
firmware/
  platformio.ini            two envs: esp32dev (espidf), native (unity)
  partitions.csv            app + nvs (created now, used in Phase 2)
  lib/core/                 PURE C control library (native-testable)
    pid.h / pid.c           PID controller (struct + step fn)
    profile.h / profile.c   profile/stage model + setpoint interpolation + validation + defaults
    reflow.h / reflow.c      run state machine
    safety.h / safety.c      watchdog verdict + SAFETY_CEILING_C
    settings.h / settings.c  profile store over an injected storage_if (CRUD, seed)
  test/
    test_smoke/test_smoke.c  proves the native+Unity toolchain runs
    test_pid/test_pid.c
    test_profile/test_profile.c
    test_settings/test_settings.c
    test_reflow/test_reflow.c
    test_safety/test_safety.c
  README.md                 build/flash + native test instructions (seeded now)
```

---

### Task 1: PlatformIO scaffold + native Unity toolchain

**Files:**
- Create: `firmware/platformio.ini`, `firmware/partitions.csv`, `firmware/README.md`,
  `firmware/lib/core/.gitkeep`, `firmware/test/test_smoke/test_smoke.c`

**Interfaces:**
- Produces: a working `pio test -e native` that runs Unity on the host.

- [ ] **Step 1: Write `platformio.ini`**

```ini
[env:esp32dev]
platform = espressif32
framework = espidf
board = esp32doit-devkit-v1
board_build.partitions = partitions.csv
monitor_speed = 115200

[env:native]
platform = native
test_framework = unity
build_flags = -std=c11 -Wall -Wextra -I lib/core
```

- [ ] **Step 2: Write `partitions.csv`** (used in Phase 2; harmless now)

```csv
# Name,   Type, SubType, Offset,  Size,    Flags
nvs,      data, nvs,     0x9000,  0x6000,
phy_init, data, phy,     0xf000,  0x1000,
factory,  app,  factory, 0x10000, 0x2C0000,
```

- [ ] **Step 3: Write the smoke test** `firmware/test/test_smoke/test_smoke.c`

```c
#include <unity.h>
void setUp(void) {}
void tearDown(void) {}
static void test_toolchain_runs(void) { TEST_ASSERT_EQUAL_INT(4, 2 + 2); }
int main(void) { UNITY_BEGIN(); RUN_TEST(test_toolchain_runs); return UNITY_END(); }
```

- [ ] **Step 4: Run the native tests — expect PASS**

```bash
cd firmware && pio test -e native
```
Expected: `test_smoke ... PASSED`, 1 test, 0 failures. (If `pio` isn't found, use `python -m platformio test -e native`.)

- [ ] **Step 5: Seed `README.md`** with: project intro, `pio test -e native` (host tests),
  `pio run -e esp32dev` (build firmware, later phases), and the pin map from spec §3.1.

- [ ] **Step 6: Commit**

```bash
git add firmware/platformio.ini firmware/partitions.csv firmware/README.md firmware/lib/core/.gitkeep firmware/test/test_smoke
git commit -m "firmware: PlatformIO scaffold with native Unity test env"
```

---

### Task 2: PID controller (`core/pid`)

**Files:**
- Create: `firmware/lib/core/pid.h`, `firmware/lib/core/pid.c`, `firmware/test/test_pid/test_pid.c`

**Interfaces:**
- Produces:
  ```c
  typedef struct { float kp, ki, kd; float out_min, out_max;
                   float integ; float prev_meas; int started; } pid_t;
  void  pid_init(pid_t *p, float kp, float ki, float kd, float out_min, float out_max);
  void  pid_reset(pid_t *p);
  float pid_step(pid_t *p, float setpoint, float measurement, float dt_s); /* returns clamped output */
  ```
  Output clamped to `[out_min,out_max]`; integral anti-windup (no accumulation while
  saturated); derivative on measurement (`-kd*d(meas)/dt`), not on error.

- [ ] **Step 1: Write failing tests** `test_pid/test_pid.c` — proportional output, integral
  accumulation toward setpoint, anti-windup clamp at `out_max`, and derivative-on-measurement
  (a setpoint jump must NOT produce a derivative spike). Example:

```c
#include <unity.h>
#include "pid.h"
void setUp(void){} void tearDown(void){}
static void test_p_only(void){ pid_t p; pid_init(&p,2,0,0,0,100);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 20.0f, pid_step(&p,110,100,1.0f)); }   /* 2*(110-100)=20 */
static void test_clamp_and_antiwindup(void){ pid_t p; pid_init(&p,0,10,0,0,100);
    for(int i=0;i<100;i++) pid_step(&p,200,0,1.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f,100.0f, pid_step(&p,200,0,1.0f));      /* clamped */
    float integ_sat=p.integ; pid_step(&p,200,0,1.0f);
    TEST_ASSERT_TRUE(p.integ <= integ_sat+0.001f); }                      /* no windup */
static void test_deriv_on_measurement_no_setpoint_kick(void){ pid_t a,b;
    pid_init(&a,0,0,5,-1000,1000); pid_init(&b,0,0,5,-1000,1000);
    pid_step(&a,100,100,1.0f); float kick=pid_step(&a,140,100,1.0f);      /* setpoint jumps, meas steady */
    pid_step(&b,100,100,1.0f); float steady=pid_step(&b,100,100,1.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, steady, kick); }                      /* identical: no kick */
int main(void){ UNITY_BEGIN(); RUN_TEST(test_p_only); RUN_TEST(test_clamp_and_antiwindup);
    RUN_TEST(test_deriv_on_measurement_no_setpoint_kick); return UNITY_END(); }
```

- [ ] **Step 2: Run — expect FAIL** (`pio test -e native -f test_pid`): undefined `pid_*`.

- [ ] **Step 3: Implement `pid.h` + `pid.c`** — the struct/signatures above; in `pid_step`:
  `error=setpoint-meas; P=kp*error; integ += ki*error*dt (only if previous output not
  saturated in the same direction); D = -kd*(meas - prev_meas)/dt (skip on first call);
  out = clamp(P+integ+D, out_min, out_max); prev_meas=meas`.

- [ ] **Step 4: Run — expect PASS** (`pio test -e native -f test_pid`): 3/3.

- [ ] **Step 5: Commit**

```bash
git add firmware/lib/core/pid.h firmware/lib/core/pid.c firmware/test/test_pid
git commit -m "firmware/core: PID with anti-windup and derivative-on-measurement"
```

---

### Task 3: Reflow profile model (`core/profile`)

**Files:**
- Create: `firmware/lib/core/profile.h`, `firmware/lib/core/profile.c`, `firmware/test/test_profile/test_profile.c`

**Interfaces:**
- Consumes: `SAFETY_CEILING_C` (forward-declare in `profile.c` as `#define` mirror OR include
  `safety.h` once Task 6 exists; for Task 3, define `PROFILE_MAX_TEMP_C 260` in `profile.h`
  and have `safety.h` reuse it in Task 6 — single source).
- Produces:
  ```c
  #define PROFILE_MAX_STAGES 6
  #define PROFILE_NAME_LEN   16
  typedef struct { char name[PROFILE_NAME_LEN]; float target_c; int duration_s; } stage_t;
  typedef struct { char name[PROFILE_NAME_LEN]; int n_stages; stage_t stages[PROFILE_MAX_STAGES]; } profile_t;
  float profile_setpoint(const profile_t *p, int elapsed_s);   /* interpolated target at t */
  int   profile_total_s(const profile_t *p);
  int   profile_validate(const profile_t *p);                   /* 1 = valid, 0 = invalid */
  void  profile_default_leaded(profile_t *out);                 /* Sn63/Pb37 */
  void  profile_default_lead_free(profile_t *out);              /* SAC305 */
  ```
  Interpolation: linear ramp from the previous stage's target (or ambient 25 °C for the
  first) to the current stage target across that stage's duration; clamps past the end to
  the last target. `profile_validate`: `1<=n_stages<=PROFILE_MAX_STAGES`, each
  `duration_s>0`, each `0<target_c<=PROFILE_MAX_TEMP_C`, name non-empty.

- [ ] **Step 1: Write failing tests** — setpoint at t=0 (≈ambient), mid-ramp interpolation,
  at total time (= last target), past end (clamped); `profile_validate` accepts a default and
  rejects (a) >max temp, (b) zero duration, (c) zero stages; defaults have sane peaks (leaded
  peak 210–225 °C, lead-free 240–250 °C). Write concrete Unity cases.

- [ ] **Step 2: Run — expect FAIL** (`pio test -e native -f test_profile`).

- [ ] **Step 3: Implement** `profile.h` + `profile.c` with the interpolation, validation, and
  the two default tables (e.g. leaded: preheat 150 °C/90 s, soak 165 °C/90 s, reflow 215 °C/45 s,
  cool 50 °C/90 s; lead-free: preheat 150 °C/90 s, soak 180 °C/90 s, reflow 245 °C/45 s,
  cool 50 °C/90 s).

- [ ] **Step 4: Run — expect PASS** (`pio test -e native -f test_profile`).

- [ ] **Step 5: Commit**

```bash
git add firmware/lib/core/profile.h firmware/lib/core/profile.c firmware/test/test_profile
git commit -m "firmware/core: reflow profile model, interpolation, validation, defaults"
```

---

### Task 4: Profile settings store (`core/settings`)

**Files:**
- Create: `firmware/lib/core/settings.h`, `firmware/lib/core/settings.c`, `firmware/test/test_settings/test_settings.c`

**Interfaces:**
- Consumes: `profile_t`, `profile_validate`, `profile_default_*` (Task 3).
- Produces:
  ```c
  #define SETTINGS_MAX_PROFILES 8
  typedef struct {                       /* injected storage backend (NVS on device, fake in tests) */
      int (*load)(void *ctx, profile_t *out, int *n_out, int max);  /* 0 ok */
      int (*save)(void *ctx, const profile_t *arr, int n);          /* 0 ok */
      void *ctx;
  } storage_if;
  typedef struct { storage_if io; profile_t items[SETTINGS_MAX_PROFILES]; int n; } settings_t;
  int  settings_begin(settings_t *s, storage_if io);   /* load; if empty, seed 2 defaults + save */
  int  settings_count(const settings_t *s);
  const profile_t* settings_get(const settings_t *s, int idx);
  int  settings_upsert(settings_t *s, int idx, const profile_t *p); /* idx<0 => add; validates; persists */
  int  settings_delete(settings_t *s, int idx);                     /* persists; keeps >=1 */
  ```

- [ ] **Step 1: Write failing tests** with an **in-memory fake** `storage_if` (a static buffer
  the fake's load/save read/write): `settings_begin` on empty storage seeds exactly 2 valid
  defaults and persists them; `settings_upsert(-1, valid)` appends + persists; `upsert` of an
  invalid profile is rejected (returns nonzero, count unchanged); `delete` removes + persists
  and never drops below 1; a fresh `settings_begin` on the same fake buffer reloads what was
  saved (round-trip).

- [ ] **Step 2: Run — expect FAIL** (`pio test -e native -f test_settings`).

- [ ] **Step 3: Implement** `settings.h` + `settings.c` — `begin` calls `io.load`; if `n==0`,
  fill `items[0]=leaded, items[1]=lead_free`, `n=2`, `io.save`. `upsert` validates via
  `profile_validate` before mutating, then `io.save`. `delete` compacts the array, refuses if
  `n==1`, then `io.save`.

- [ ] **Step 4: Run — expect PASS** (`pio test -e native -f test_settings`).

- [ ] **Step 5: Commit**

```bash
git add firmware/lib/core/settings.h firmware/lib/core/settings.c firmware/test/test_settings
git commit -m "firmware/core: profile settings store with injected storage + seeding"
```

---

### Task 5: Reflow run state machine (`core/reflow`)

**Files:**
- Create: `firmware/lib/core/reflow.h`, `firmware/lib/core/reflow.c`, `firmware/test/test_reflow/test_reflow.c`

**Interfaces:**
- Consumes: `profile_t`, `profile_setpoint`, `profile_total_s` (Task 3).
- Produces:
  ```c
  typedef enum { RS_IDLE, RS_PREHEAT, RS_SOAK, RS_REFLOW, RS_COOL, RS_DONE, RS_FAULT } reflow_state_t;
  typedef struct { reflow_state_t state; const profile_t *prof; int elapsed_s;
                   float setpoint_c; int stage_idx; } reflow_t;
  void           reflow_init(reflow_t *r);
  int            reflow_start(reflow_t *r, const profile_t *p);   /* IDLE->PREHEAT; 0 ok */
  void           reflow_tick(reflow_t *r, float temp_c, int dt_s, int safety_fault);
  void           reflow_abort(reflow_t *r);                       /* -> COOL */
  void           reflow_ack(reflow_t *r);                         /* FAULT/DONE -> IDLE */
  reflow_state_t reflow_state(const reflow_t *r);
  ```
  `reflow_tick`: if `safety_fault` → `RS_FAULT` immediately. Else advance `elapsed_s += dt_s`,
  recompute `setpoint_c = profile_setpoint(prof, elapsed_s)` and `stage_idx` from elapsed time;
  map elapsed→stage→state (preheat/soak/reflow/cool); when elapsed ≥ total → cool until the
  cool stage ends → `RS_DONE`. `RS_DONE`/`RS_FAULT` are terminal until `reflow_ack`.

- [ ] **Step 1: Write failing tests** — `start` moves IDLE→PREHEAT; ticking through the
  default lead-free profile transitions PREHEAT→SOAK→REFLOW→COOL→DONE at the right elapsed
  boundaries; `setpoint_c` follows `profile_setpoint`; a tick with `safety_fault=1` forces
  RS_FAULT from any running state; `reflow_abort` → COOL; `reflow_ack` from DONE → IDLE.

- [ ] **Step 2: Run — expect FAIL** (`pio test -e native -f test_reflow`).

- [ ] **Step 3: Implement** `reflow.h` + `reflow.c` per the interface.

- [ ] **Step 4: Run — expect PASS** (`pio test -e native -f test_reflow`).

- [ ] **Step 5: Commit**

```bash
git add firmware/lib/core/reflow.h firmware/lib/core/reflow.c firmware/test/test_reflow
git commit -m "firmware/core: reflow run state machine with fault/abort transitions"
```

---

### Task 6: Safety watchdog (`core/safety`)

**Files:**
- Create: `firmware/lib/core/safety.h`, `firmware/lib/core/safety.c`, `firmware/test/test_safety/test_safety.c`

**Interfaces:**
- Produces:
  ```c
  #define SAFETY_CEILING_C 260.0f
  typedef enum { SAFE_OK=0, SAFE_OVERTEMP, SAFE_RUNAWAY, SAFE_TC_FAULT, SAFE_STALL } safety_fault_t;
  typedef struct { float runaway_min_rise_c; int runaway_window_s; int stall_timeout_s;
                   /* internal: */ float win_start_temp; int win_elapsed_s; int since_reading_s; } safety_t;
  void           safety_init(safety_t *s);   /* defaults: rise 2.0C, window 20s, stall 5s */
  safety_fault_t safety_check(safety_t *s, float temp_c, int tc_ok, float duty_pct,
                              int fresh_reading, int dt_s);  /* SAFE_OK or a fault */
  ```
  Returns the first tripped fault: `!tc_ok` or `isnan(temp_c)` → `SAFE_TC_FAULT`;
  `temp_c >= SAFETY_CEILING_C` → `SAFE_OVERTEMP`; no `fresh_reading` for ≥ `stall_timeout_s`
  → `SAFE_STALL`; while `duty_pct > 50` track a rolling window — if over `runaway_window_s`
  the temp rose < `runaway_min_rise_c` → `SAFE_RUNAWAY`. Any non-OK return MUST mean the
  caller drives the heater off (asserted in the integration phase).
- **Reconcile with Task 3:** make `profile.h`'s `PROFILE_MAX_TEMP_C` `#define` to
  `260` and have `safety.h` define `SAFETY_CEILING_C 260.0f` — OR include each other; keep
  the single numeric source. (Pick: `safety.h` owns `SAFETY_CEILING_C`; `profile.c` includes
  `safety.h` and validates against `(int)SAFETY_CEILING_C`. Update Task 3's file accordingly
  if already written.)

- [ ] **Step 1: Write failing tests** — over-temp at 260 trips `SAFE_OVERTEMP`; `tc_ok=0`
  trips `SAFE_TC_FAULT`; `NaN` temp trips `SAFE_TC_FAULT`; no fresh reading for ≥5 s trips
  `SAFE_STALL`; heating at duty 100 % with temp flat over the window trips `SAFE_RUNAWAY`;
  normal heating with rising temp returns `SAFE_OK`.

- [ ] **Step 2: Run — expect FAIL** (`pio test -e native -f test_safety`).

- [ ] **Step 3: Implement** `safety.h` + `safety.c`; reconcile the ceiling constant with
  `profile` (single source) and re-run `test_profile` to confirm no regression.

- [ ] **Step 4: Run — expect PASS** (`pio test -e native` — ALL suites green, including
  `test_profile` after the constant reconciliation).

- [ ] **Step 5: Commit**

```bash
git add firmware/lib/core/safety.h firmware/lib/core/safety.c firmware/test/test_safety firmware/lib/core/profile.h firmware/lib/core/profile.c
git commit -m "firmware/core: safety watchdog (overtemp/runaway/tc-fault/stall)"
```

---

## Self-Review notes (for the executor)
- **Native purity is the gate:** `lib/core/*` must compile under `pio test -e native` (gcc)
  — any accidental `esp_*`/`driver/*` include breaks the build and the phase's whole premise.
- **Single ceiling source:** `SAFETY_CEILING_C` (safety.h) is the one definition; `profile`
  validates against it (Task 6 reconciles Task 3). Don't leave two literals.
- **All native, no hardware:** Phase 1 ships a fully unit-tested control library and nothing
  device-specific. Phase 2 (HAL + FreeRTOS task + UI) consumes it; Phase 3 adds net/dashboard.
- **`pio test -e native` runs ALL suites** — the final task must end with every suite green.
