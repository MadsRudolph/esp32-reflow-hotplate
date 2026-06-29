# ESP32 SMD Reflow Hotplate — Design Spec

**Date:** 2026-06-29
**Status:** Approved (brainstorming complete; ready for implementation planning)

## 1. Goal

Build, entirely from scratch, an ESP32-controlled SMD reflow hotplate that reflows
small/medium SMD boards (up to ~100 × 100 mm) by tracking a PID-controlled reflow
temperature profile. Deliverables: a KiCad schematic, a CNC-milled single-sided control
board, ESP32 firmware, and 3D-printed enclosure parts.

### Non-goals (YAGNI)
- No mains-voltage (AC) heating. The whole build is 24 V DC.
- No WiFi/web UI in the first version (the ESP32 supports it; left as a later add-on).
- No reflow-camera, no automatic profile learning, no multi-zone heating.

## 2. Key decisions (from brainstorming)

| Decision | Choice | Reason |
|---|---|---|
| Heater | 24 V DC PTC aluminium plate, ~300 W (~13 A) | Mains-free; real reflow temps; ~100×100 mm board area |
| Power switch | IRFS4710 N-MOSFET (low-side), 12 V gate drive | Lowest Rds(on) in DTU shop (~14 mΩ); logic-level parts too hot at 13 A |
| Temp sensing | K-type thermocouple + MAX31855 (SPI) | Reflow standard; cold-junction compensated; open-TC fault detect |
| Logic supply | 24 V → 5 V via LM2576 switcher | Linear 7805 would dissipate ~9 W across the 19 V drop |
| Gate supply | 24 V → 12 V via LM7812 linear | Gate draws ~0 average (slow PWM), linear is fine |
| UI | SSD1306 OLED (I²C) + rotary encoder + start/stop button | Standalone, no phone/network needed |
| Control board | Single-sided through-hole, CNC-milled (Roland SRM-20) | Matches DTU mill/laser process and shop stock |
| Enclosure | 3D-printed, offset electronics box + metal-standoff plate mount | Plastic must never touch the ~250 °C plate |
| Architecture | Approach A: single control board, high-current path as wide copper pours | One milling job, one enclosure, isolated "power corner" |

## 3. Architecture

### 3.1 Power tree
```
24 V PSU ──┬─► LM2576 switching reg ──► 5 V ──► ESP32 DevKit VIN
           │                                    └► ESP32 3.3 V LDO ─► MAX31855, OLED, encoder
           ├─► LM7812 linear reg ─────► 12 V ──► MOSFET gate-drive rail
           └─► (fused, ~15 A) ─────────► heater(+) / IRFS4710 / return  [13 A power loop]
```

### 3.2 Power stage ("power corner")
- **IRFS4710** low-side N-MOSFET switches the heater negative return. ~2.4 W at 13 A →
  TO-220 heatsink + mica/silicon insulating pad (DTU shop).
- Gate drive: ESP32 3.3 V PWM → **two-stage BS170 level shifter (non-inverting overall)**
  → IRFS4710 gate at **12 V** through a gate resistor, plus a **gate-source pulldown**.
  The topology is **boot-safe**: GPIO high = heater ON; GPIO low / floating / ESP32
  unpowered / mid-reset = heater **OFF inherently** (no firmware required for the safe
  state). A single inverting shifter is explicitly rejected because it would drive the
  heater ON whenever the GPIO floats at boot/crash.
- Heater is resistive → no freewheel diode. **TVS** across 24 V input clamps transients.
- PWM is "slow" (≤ a few hundred Hz; thermal mass tolerates even ~2 Hz), so switching
  losses are negligible and gate-drive current is tiny.
- **High-current routing:** heater current flows only through short, wide copper **pours**
  (≈8–10 mm) between the screw terminals and the MOSFET — never through 1 mm signal
  traces. The mill isolates around the pour at no extra cost.

### 3.3 Temperature sensing
- K-type thermocouple bonded to the plate underside → **MAX31855** breakout on the ESP32
  hardware SPI bus (CS, SCK, SO — read-only; only SPI device). Provides ±2 °C accuracy,
  cold-junction compensation, and open/short fault flags consumed by the safety module.

### 3.4 Safety (layered)
1. **Hardware fail-safe:** non-inverting gate drive + gate-source pulldown → power-off /
   reset / crash / floating GPIO = heater off, with no firmware involvement.
2. **Inline thermal cutoff fuse** (~240 °C one-shot) in series with the heater element —
   independent of firmware.
3. **Fused 24 V input** (~15 A inline) + input TVS.
4. **Firmware watchdog:** thermal-runaway detection (heater commanded on but temperature
   not rising), hard over-temperature limit, MAX31855 open/short-TC fault → immediate
   shutdown; start/stop button forces idle at any time.

## 4. Components & sourcing

**From DTU component shop (through-hole lab stock):**
IRFS4710 (power MOSFET), 2× BS170 (non-inverting gate level shifter), LM2576 (5 V switcher), LM7812 (12 V),
TVS diode, all resistors/capacitors, 2- & 3-pole screw terminals (`TerminalBlock.pretty`),
rotary encoder, momentary pushbutton, TO-220 heatsink + thermal pad, headers/Molex,
IC sockets as needed.

**External modules / hardware (not lab stock — bring your own):**
ESP32 DevKit module, MAX31855 + K-type thermocouple module, SSD1306 OLED, 24 V DC PSU
(~15 A / 360 W), 24 V DC PTC aluminium heater plate (~100×100 mm, ~300 W), inline thermal
cutoff fuse, inline 24 V fuse holder + fuse.

A complete BOM with shop part numbers and quantities is produced during implementation
(`docs/BOM.md`).

## 5. Control board (KiCad 10)

- **Conventions reused from the DTU Electrical Energy Systems project:**
  - Footprints: `energy_system.pretty` — TO-220 **G/D/S** laser-pad variant for the MOSFET
    (avoids the numeric-vs-letter pad-name trap), plain TO-220 laser pad for regulators;
    `TerminalBlock.pretty` bornier P5.08 mm screw terminals.
  - Symbols: `energy_system.kicad_sym` where applicable; stock `Device:*` otherwise
    (e.g. `Device:Q_NMOS` paired with the `_GDS` footprint).
  - Project-local `fp-lib-table` with `${KIPRJMOD}` relative paths (portable across PCs).
  - KiCad **10.0** CLI/toolchain (file format 20260306).
- **Design rules:** single-sided, through-hole, **1.0 mm trace / 0.8 mm clearance**; top-
  layer nets realised as wire bridges, exported as `*_top_cu.dxf`.
- **Layout zoning:** isolated **power corner** (24 V-in / heater-out terminals → IRFS4710
  + heatsink → return, fat pours) kept physically clear of the **logic/analog zone**
  (ESP32 headers, MAX31855 header, OLED/encoder/button connectors, gate-drive small-signal).
- **Module mounting:** ESP32 DevKit, OLED, encoder mount on female headers / Molex so the
  board is low-profile and modules are replaceable; only shop through-hole parts are
  soldered to the board itself.
- **Connectors:** screw terminals for 24 V-in, heater-out, thermocouple; Molex/headers for
  OLED (I²C), encoder, start/stop button.
- **Production:** routed via the kicad-laser-pcb skill's rules, then milled on the SRM-20
  (SVG → 1000 dpi PNG → mods/`gerber2rml` → `.rml`/`.nc`), single setup, FR-1 preferred.

## 6. Firmware (ESP32, PlatformIO / Arduino framework)

Modular, each unit independently testable:

| Module | Responsibility | Depends on |
|---|---|---|
| `thermocouple` | MAX31855 SPI read; temperature + fault flags | SPI |
| `heater` | PWM duty → gate drive; fail-safe off; slow-PWM | GPIO/LEDC |
| `pid` | temperature error → heater duty (anti-windup) | — |
| `profile` | reflow curve as setpoint-vs-time (preheat→soak→reflow→cool) | — |
| `safety` | runaway / over-temp / TC-open watchdog; hard cutoff | thermocouple, heater |
| `ui` | OLED render + encoder/button input | I²C, GPIO |
| `controller` | top-level state machine (idle → run stages → cooldown → done) | all |

- **Built-in profiles:** leaded **Sn63/Pb37** and lead-free **SAC305**; profiles are data,
  so adding more is editing a table.
- **Control:** PID with anti-windup; conservative default gains plus a documented tuning
  procedure for first runs.
- **State machine:** idle/select → preheat → soak → reflow → cooldown → done; start/stop
  button and any safety fault transition to a safe idle with the heater forced off.

## 7. 3D-printed enclosure (Blender → STL/STEP)

**Critical thermal rule:** the ~250 °C plate must never contact printed plastic. The plate
mounts on **metal standoffs** rising from the base, with an **air gap** above the
electronics. Base printed in **PETG** (better heat tolerance than PLA); the hot zone is all
metal.

Parts:
1. **Base tray** — standoff bosses for the metal plate mounts, feet.
2. **Electronics box** — offset from the plate's heat plume; holds the control board.
3. **Front panel** — cut-outs for OLED, encoder, start/stop button.
4. **Cable path** — routed channel between box and plate; vents over regulators / MOSFET
   heatsink.

Modeled in Blender (MCP-connected), exported to STL (print) and STEP (CAD interchange).

## 8. Repository layout
```
docs/            this spec, BOM, sourcing + tuning notes
hardware/kicad/   KiCad 10 project (schematic + single-sided board) + project fp-lib-table
hardware/3d/      Blender sources + exported STL/STEP
firmware/         PlatformIO ESP32 project (modules per §6)
```

## 8.1 ESP32 GPIO pin map (hardware ↔ firmware contract)

Default module: **30-pin DOIT ESP32 DevKit V1** (2×15 female headers, 2.54 mm pitch,
22.86 mm row spacing). All listed GPIOs are exposed on this board. If a 38-pin
ESP32-DevKitC is used instead, only the footprint widens (to 2×19) — the pin map is
unchanged.

| Signal | GPIO | Notes |
|---|---|---|
| `HEATER_PWM` | GPIO25 | LEDC PWM → two-stage BS170 gate drive; low at reset = OFF |
| `TC_SCK` | GPIO18 | VSPI clock (MAX31855) |
| `TC_SO` (MISO) | GPIO19 | VSPI MISO (MAX31855 data out; read-only, no MOSI) |
| `TC_CS` | GPIO5 | MAX31855 chip select |
| `OLED_SDA` | GPIO21 | I²C data (SSD1306) |
| `OLED_SCL` | GPIO22 | I²C clock (SSD1306) |
| `ENC_A` | GPIO32 | Rotary encoder A, internal pull-up |
| `ENC_B` | GPIO33 | Rotary encoder B, internal pull-up |
| `ENC_SW` | GPIO27 | Encoder push, internal pull-up |
| `BTN_START` | GPIO26 | Start/stop + panic, internal pull-up |
| `LED_STATUS` | GPIO4 | Status LED (avoids strapping pins) |

Strapping pins (GPIO0/2/12/15) and flash pins (GPIO6–11) are deliberately unused.

## 9. Risks & open items
- **Heater plate spec:** exact PTC plate dimensions/wattage/voltage must be fixed before
  the plate-mount frame and fuse rating are finalised.
- **13 A on FR-1:** wide pours assumed adequate for 35 µm copper; verify pour width / temp
  rise during layout (target ≤ ~20 °C rise) and keep the power loop short.
- **Gate drive at 12 V:** confirm IRFS4710 is fully enhanced and within Vgs(max) ±20 V.
- **PID tuning:** first-run autotune/manual tuning expected; ship safe conservative gains.
- **PETG vs. heat:** confirm enclosure standoff geometry keeps all plastic well below the
  glass-transition temperature under sustained reflow runs.
