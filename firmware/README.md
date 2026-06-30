# ESP32 Reflow Hotplate — Firmware

Embedded C firmware for the ESP32 reflow hotplate, written on ESP-IDF via PlatformIO.
Implements PID-controlled reflow profiles, a local OLED+encoder UI, and a WiFi LAN
dashboard for live monitoring and profile management.

## Quick start

```bash
# Run host-side Unity unit tests (no hardware needed)
cd firmware
pio test -e native

# Build firmware for the ESP32 (requires ESP-IDF toolchain download on first run)
pio run -e esp32dev

# Flash and monitor
pio run -e esp32dev -t upload
pio device monitor -e esp32dev
```

## Pin map

| Signal         | GPIO  | Notes                                  |
|----------------|-------|----------------------------------------|
| HEATER_PWM     | 25    | Time-proportional slow PWM (~1–2 s window), fail-safe low |
| TC_SCK         | 18    | MAX31855 SPI clock                     |
| TC_SO          | 19    | MAX31855 SPI MISO (read-only; no MOSI) |
| TC_CS          | 5     | MAX31855 chip select                   |
| OLED_SDA       | 21    | SSD1306 I2C data                       |
| OLED_SCL       | 22    | SSD1306 I2C clock                      |
| ENC_A          | 32    | Rotary encoder channel A (PCNT)        |
| ENC_B          | 33    | Rotary encoder channel B (PCNT)        |
| ENC_SW         | 27    | Encoder push-switch (GPIO ISR)         |
| BTN_START      | 26    | Start/stop button                      |
| LED_STATUS     | 4     | Status LED                             |
| FAN_PWM        | 13    | 5 V cooling fan, split-range PID (low-side N-MOSFET); **not yet on the fabricated board — pending board revision** |

## Architecture

```
firmware/
  platformio.ini        env:esp32dev (espidf) + env:native (gcc + Unity)
  partitions.csv        app + nvs (profiles)
  src/
    core/   Pure C — no ESP-IDF deps; covered by native Unity tests
    hal/    ESP-IDF C drivers (bench-verified)
    ui/     OLED screens + encoder navigation
    net/    WiFi station + HTTP server + WebSocket dashboard
    app/main.c
  lib/core/             Pure-C library include path (for native env)
  test/test_smoke/      Smoke test: verifies toolchain and Unity work
```

## Safety

Hard over-temp cutoff at 260 °C (above SAC305 reflow peak, below damage threshold).
Runs are started and aborted **locally only** — the web dashboard is monitoring/profiles only.
WiFi credentials live in gitignored `src/net/wifi_config.h`.
