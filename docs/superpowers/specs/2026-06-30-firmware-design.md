# ESP32 Reflow Hotplate — Firmware Design Spec

**Date:** 2026-06-30
**Status:** Approved (brainstorming complete; ready for implementation planning)
**Parent project:** ESP32 SMD Reflow Hotplate (see `2026-06-29-esp32-reflow-hotplate-design.md` §6)

## 1. Goal

Firmware for the ESP32 reflow hotplate: read the plate temperature, run a PID-controlled
reflow profile to drive the 13 A heater safely, present a local OLED + encoder UI, and
serve a WiFi web dashboard on the LAN for live monitoring and profile management.
Written in **embedded C on ESP-IDF** (PlatformIO), with the safety-critical control logic
isolated as pure C and unit-tested natively.

### Non-goals (YAGNI)
- No remote start/abort of reflow runs — runs are started/aborted **locally only** (a 13 A
  heater must not be started unattended over the network).
- No cloud/internet dependency — the dashboard is served by the device on the LAN.
- No OTA firmware update in v1.
- No multi-plate / multi-zone control.

## 2. Key decisions (from brainstorming)

| Decision | Choice | Reason |
|---|---|---|
| Language / framework | **Embedded C on ESP-IDF** (PlatformIO `framework = espidf`) | Pure C, no C++/Arduino; native C driver APIs + FreeRTOS |
| Control loop | **PID**, position form, anti-windup, derivative-on-measurement; fixed conservative default gains | Reliable reflow tracking; tune once per plate |
| Heater output | **Time-proportional control** (slow ~1–2 s PWM window on GPIO25), fail-safe low | Standard for thermal/heater control |
| Testability | `core/` is pure C (no ESP-IDF deps) → **PlatformIO `native` Unity tests**; HAL bench-verified | Fast TDD for the safety-critical logic |
| Profiles | **Editable, persisted to NVS** (`nvs_flash`); seeded with leaded Sn63/Pb37 + lead-free SAC305 | Tweak without reflash; managed from OLED and web |
| Local UI | SSD1306 OLED + rotary encoder + start/stop button | Standalone operation |
| Network | **WiFi station + `esp_http_server`**; embedded SPA dashboard; WebSocket live telemetry; REST profile CRUD | LAN monitoring + profile management |
| Dashboard scope | **Monitor + manage profiles**; runs start/abort LOCAL only | Fire-safety for a 13 A heater |
| Safety ceiling | Hard over-temp cutoff **260 °C** | Above SAC305 peak, below damage |
| WiFi credentials | Gitignored `wifi_config.h` (or NVS) | Simple; never commit creds |

## 3. Architecture (layered for isolation + testability)

```
firmware/                         PlatformIO project (framework = espidf)
  platformio.ini                  env:esp32dev (espidf) + env:native (gcc + Unity)
  partitions.csv                  app + nvs (profiles)
  src/
    core/      PURE C — NO ESP-IDF/Arduino deps → native Unity tests
      pid.c/.h        position PID, anti-windup clamp, derivative-on-measurement
      profile.c/.h    profile model (stages) + setpoint-vs-time interpolation + validation
      reflow.c/.h     run state machine (idle→preheat→soak→reflow→cool→done / fault)
      safety.c/.h     watchdog: pure verdict from (temp, duty, dt, flags)
      settings.c/.h   profile store; storage behind a struct-of-fn-pointers (fake in tests)
    hal/       ESP-IDF C drivers (bench-verified, not native-tested)
      tc_max31855.c   driver/spi_master: read 32-bit word, parse temp + fault bits
      oled_ssd1306.c  driver/i2c_master: minimal text/line/bar driver
      heater.c        time-proportional slow-PWM on GPIO25; fail-safe low
      encoder.c       PCNT peripheral (A/B) + GPIO ISR for switch
      button.c, led.c GPIO
    ui/ui.c           OLED screens + encoder navigation (depends on core + hal)
    net/       WiFi + web (independent of the control loop)
      wifi.c          esp_wifi station; creds from gitignored wifi_config.h
      httpd.c         esp_http_server: serves SPA + REST + WebSocket
      api.c           endpoints; reads run snapshot, writes profiles via settings.c
      www/            dashboard SPA (HTML/CSS/JS), embedded into flash (EMBED_FILES)
    app/main.c        app_main: nvs init, HAL init, wifi/httpd start, control FreeRTOS task
  test/native/        Unity tests for core/*
  README.md           pinout, build/flash, bench-verification steps
```

### 3.1 Pin map (from `hardware/kicad/net_contract.json`)
`HEATER_PWM=GPIO25, TC_SCK=GPIO18, TC_SO=GPIO19, TC_CS=GPIO5, OLED_SDA=GPIO21,
OLED_SCL=GPIO22, ENC_A=GPIO32, ENC_B=GPIO33, ENC_SW=GPIO27, BTN_START=GPIO26,
LED_STATUS=GPIO4`. SPI is read-only (no MOSI); MAX31855 is the only SPI device.

## 4. Control core (`core/`)

- **`pid`** — position-form PID; output 0–100 % duty. Anti-windup (integral clamp on
  saturation); derivative on the measurement (not the error) to avoid a setpoint kick at
  stage boundaries. Conservative default `Kp/Ki/Kd` in config; documented tuning procedure.
- **`profile`** — a profile is an ordered list of stages `{name, target_c, duration_s}`
  for preheat → soak → reflow(peak) → cool. `profile_setpoint(profile, elapsed_s)` returns
  the interpolated target. `profile_validate()` enforces: stage count/limits, monotonic
  time, each `target_c ≤ SAFETY_CEILING`, sane durations — used by both OLED edits and
  web uploads.
- **`reflow`** — the run state machine: `IDLE → PREHEAT → SOAK → REFLOW → COOL → DONE`,
  plus `FAULT`. Advances stages by the profile; computes the live setpoint; consumes the
  `safety` verdict to abort. Publishes a run snapshot.
- **`safety`** — pure function evaluated every tick; forces heater OFF + `FAULT` on:
  over-temp (`≥ 260 °C`), thermal runaway (heater high but temp not rising ≥ ~2 °C / 20 s),
  thermocouple fault (open/short/NaN/out-of-band), sensor stall (no fresh reading in
  timeout). Faults latch until acknowledged.
- **`settings`** — profile CRUD over an injected `storage_if` (struct of read/write fn
  pointers). On-device it binds to NVS; in native tests, to an in-memory fake. Seeds the
  two default profiles on first boot.

## 5. HAL (`hal/`, ESP-IDF C)
Thin wrappers, no business logic: `tc_max31855` (SPI word → °C + fault), `oled_ssd1306`
(I²C text/line/bar), `heater` (time-proportional slow-PWM, fail-safe low on init/abort),
`encoder` (PCNT quadrature + GPIO ISR switch), `button`, `led`. Verified on the bench; the
steps are documented in `firmware/README.md`.

## 6. Local UI (`ui/`)
```
IDLE/SELECT → rotate: pick profile → press: MENU {RUN, EDIT}
EDIT  → pick stage field (temp/time), adjust, save → NVS
RUN   → live: target vs actual °C, stage, elapsed, duty bar  (button aborts)
DONE/COOLDOWN → "remove board, cooling" until cool → IDLE
FAULT → reason; button acknowledges → IDLE
```
Encoder rotate = navigate/adjust, encoder press = select, dedicated button = start/abort.

## 7. Network dashboard (`net/`)
- **`wifi`** — station mode; joins the LAN using creds from a gitignored `wifi_config.h`
  (SSID/pass) — never committed. WiFi/web failure must NOT affect the control loop.
- **`httpd`/`api`** — `esp_http_server`:
  - `GET /` → embedded SPA (HTML/CSS/JS in flash; no internet dependency).
  - `GET /ws` → WebSocket pushing live telemetry ~2–4×/s: `t, target, actual, duty, stage,
    state, fault`.
  - `GET /api/status` → snapshot (first paint / non-WS clients).
  - `GET /api/profiles`, `GET /api/profiles/{id}` → read.
  - `POST /api/profiles`, `PUT /{id}`, `DELETE /{id}` → create/edit/upload/delete a profile
    (JSON), `profile_validate()`d, then persisted to NVS via `settings`.
- **Dashboard SPA** — live temperature chart (target vs actual) + stage/duty/state/fault
  tiles; a profile manager (list → edit form → save/upload/delete). Self-contained.
- **Concurrency / safety boundary** — the control FreeRTOS task owns the heater and run
  state and publishes a snapshot (mutex/atomic). The httpd task only *reads* the snapshot
  and *enqueues validated profile writes*; it can never command the heater or start a run.

## 8. Telemetry
During a run, also stream one CSV line per tick over USB serial (`t,target,actual,duty,
stage`) for plotting and PID tuning.

## 9. Concurrency model (FreeRTOS)
- **Control task** (fixed tick, e.g. 250 ms, high priority): TC read → `safety` → `pid` →
  `heater` duty → publish snapshot → `ui` update + serial CSV. Owns all heater control.
- **httpd task** (esp_http_server): serves dashboard, reads the published snapshot, pushes
  WS telemetry, handles profile CRUD (enqueues writes consumed by the control/settings side).
- **wifi** events handled async. The control + safety loop is independent of WiFi/web state.

## 10. Testing (PlatformIO `native` env, Unity)
- `pid`: step response, anti-windup saturation, no derivative kick at setpoint change.
- `profile`: interpolation across stage boundaries; `profile_validate` accepts good /
  rejects bad (non-monotonic, over-ceiling, zero-duration); defaults correct.
- `reflow`: full state-machine path + abort + fault transitions.
- `safety`: each trip fires and forces heater off; **fakes feed adversarial inputs** —
  the regression net for a 13 A heater.
- `settings`: CRUD + persist + reload through the in-memory `storage_if` fake.
HAL, UI, and net are bench/integration-verified (documented in README), not native-tested.

## 11. Repository layout
```
firmware/   the PlatformIO ESP-IDF project above (src/, test/native/, platformio.ini, README.md)
```

## 12. Risks & open items
- **PID tuning:** ship conservative gains; first-run tuning expected (serial CSV + dashboard
  chart aid this). Re-tune for the real plate's thermal mass.
- **OLED/encoder C drivers:** minimal hand-rolled drivers (no Adafruit) — budget bench time.
- **WiFi creds:** gitignored `wifi_config.h`; document the template. Provisioning portal is
  a later option.
- **Heater fail-safe:** `heater` must drive GPIO25 low on init, abort, fault, and task crash;
  this complements the hardware boot-safe gate. Covered explicitly in tests/bench checks.
- **Flash size for the embedded SPA:** keep the dashboard self-contained and small; verify it
  fits the app partition.
