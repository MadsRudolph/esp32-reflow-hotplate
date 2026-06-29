# ESP32 SMD Reflow Hotplate

A from-scratch SMD reflow hotplate built around an ESP32, a 24 V DC PTC heater plate,
and a custom CNC-milled single-sided control board. Designed to reflow small/medium
SMD boards (up to ~100 × 100 mm) using PID-controlled reflow profiles.

> **Status:** in design. See [`docs/`](docs/) for the design spec.

## Why DC PTC (not mains)

The heater runs on **24 V DC**, switched by a power MOSFET — no mains voltage anywhere
in the build. Safer to build, debug, and leave running than an SSR + AC element.

## System overview

| Subsystem | Choice |
|---|---|
| Controller | ESP32 DevKit module |
| Heater | 24 V DC PTC aluminium plate, ~300 W (~13 A) |
| Power switch | IRFS4710 N-MOSFET, 12 V gate drive |
| Temp sensing | K-type thermocouple + MAX31855 (SPI) |
| Logic supply | 24 V → 5 V via LM2576 switching regulator |
| Gate-drive supply | 24 V → 12 V via LM7812 |
| UI | SSD1306 OLED + rotary encoder + start/stop button |
| Control board | Single-sided, through-hole, CNC-milled (Roland SRM-20) |
| Enclosure | 3D-printed (offset electronics box + metal-standoff plate mount) |

Most passives, the MOSFET, regulators, connectors and the encoder come from the **DTU
component shop** (through-hole lab stock). The ESP32 DevKit, MAX31855 thermocouple
module, OLED, 24 V PSU and the PTC heater plate are external modules/hardware.

## Repository layout

```
docs/            design spec, BOM, sourcing notes
hardware/kicad/   KiCad 10 project (schematic + single-sided board)
hardware/3d/      Blender sources + exported STL/STEP for printing
firmware/         ESP32 reflow-control firmware
```

## Production

- **PCB:** CNC-milled on a Roland SRM-20 (FR-1), single-sided, top nets as wire bridges.
  Design rules match the DTU laser/mill process: 1.0 mm trace / 0.8 mm clearance.
- **Enclosure:** FDM 3D print. The hot-plate mount uses **metal standoffs** with an air
  gap from the plastic — the plate reaches ~250 °C and must never touch printed parts.

## Safety

Mains-free by design, but reflow temperatures are dangerous. Planned protections:
hardware gate pulldown (power-off = heater-off), an inline thermal cutoff fuse on the
heater, a fused 24 V input, and firmware thermal-runaway / over-temperature watchdogs.
