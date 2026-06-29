# ESP32 Reflow Hotplate — 3D Enclosure Design Spec

**Date:** 2026-06-30
**Status:** Approved (brainstorming complete; ready for implementation planning)
**Parent project:** ESP32 SMD Reflow Hotplate (see `2026-06-29-esp32-reflow-hotplate-design.md` §7)

## 1. Goal

Design the 3D-printable enclosure for the reflow hotplate: hold the ~250 °C heater plate
safely above the electronics, house the CNC-milled control board, and present the OLED +
encoder + button + LED on a front panel. Deliverables: parametric Blender source + exported
STL (print) and STEP (CAD interchange) for each part.

### Non-goals (YAGNI)
- No active cooling (no fan) — passive vents only.
- No latching/hinged lid — the lid is screwed.
- No enclosure for the 24 V PSU (external brick stays separate).

## 2. Key decisions (from brainstorming)

| Decision | Choice | Reason |
|---|---|---|
| Heater plate | Parametric around 100×100 mm aluminium PTC, 4× corner M3 holes | No specific plate yet; adapt later by changing variables |
| Layout | Electronics box **offset to the side** of the plate | Keeps all plastic out of the rising heat plume — safest |
| Thermal isolation | Plate on **ceramic standoffs** (~20–25 mm) + open air gap | Ceramic conducts little heat → PETG base stays well below its ~80 °C Tg |
| Fastening | **M3 brass heat-set inserts** in PETG for the box↔top-panel joint; plate uses steel M3 screws through **female-threaded** ceramic standoffs; the control board **rests on corner posts** (it has no mounting holes) | Durable, re-openable threads; the board needs no holes |
| Parts | **3 printed: plate frame, electronics box, top control panel** | The board's controls point up, so one TOP panel both closes the box and carries the cut-outs (it is also the lid) |
| Material | PETG (base/box); hot zone is all metal/ceramic | Better heat tolerance than PLA; nothing plastic touches the plate |
| Modeling | Blender (MCP), parametric variables | **STL + the parametric `.blend`/`.py`** (Blender has no native STEP export; STEP is an optional FreeCAD follow-up) |

> **Design correction (2026-06-30, mid-build):** the original 4-part plan (vertical front panel + separate lid) was geometrically wrong — the 104×104 board is larger than the first box envelope, has no mounting holes, and its through-hole controls (SW1/SW2/D1) point *up*, so they must come through a panel parallel and above the board. Corrected to the 3-part design below.

## 3. Architecture (3 printed parts + hardware)

### 3.1 Plate frame
PETG base/ring that the heater plate bolts onto via **4 female-threaded ceramic standoffs** (the
standoff seats on the frame's blind boss; a steel M3 screw threads UP through the standoff into
the plate's corner hole — NOT down through the frame). The standoffs raise the plate ~22 mm with
an **open air gap** beneath, and the ceramic is the only thermal path to the printed part —
breaking conduction. Footprint and hole pattern are parametric to the plate. A routed channel
carries the plate's heater wires toward the electronics side. Feet under the corners.

### 3.2 Electronics box
Sits **beside** the plate frame, out of the heat plume, sized (~113×113 mm) to hold the **104×104
control board flat**. The board **rests on 4 corner support posts** (lifted off the floor for the
bottom lead tails) — it has no mounting holes, so it is captured from above by the top panel, not
bolted. Features:
- Vent slots above the LM2575 / LM7812 regulators and the Q1 (IRFS4710) TO-220 heatsink.
- Side openings for the 24 V-in (J1) and heater-out (J2) screw terminals.
- **Heat-set inserts on the top rim** to receive the top control panel.

### 3.3 Top control panel (also the lid)
A PETG plate that **closes the box top** and carries the controls — the user looks down on it.
Cut-outs **aligned to the control board's on-board component positions** (from
`hardware/kicad/placement.json`, board centred under the panel): the rotary encoder (SW1) shaft,
the start button (SW2), the status LED (D1), and an **OLED window** for the J4-connected SSD1306
module. Vent slots over the heat-generating zone. Bolts down into the box top-rim heat-set inserts
with M3 screws.

### 3.4 Hardware (bring-your-own)
- Plate: 4× **female-threaded** ceramic standoffs + 4× steel M3 screws.
- Box↔panel: M3 brass heat-set inserts + M3 screws.
- 4× rubber feet. (The control board needs no screws — it rests on the box posts.)

## 4. Thermal safety rationale
The ~250 °C plate never contacts printed plastic: it stands on ceramic over an air gap, and the
electronics box is laterally offset from the plume. PETG (Tg ~80 °C) is used for structure; the
ceramic standoffs + air gap keep the frame's screw bosses far below softening even on sustained
runs. (The plate-mount geometry should be sanity-checked against the real plate's wattage during
implementation.)

## 5. Parametric variables (Blender)
Single source of truth so the model adapts to the real plate and board:
- `plate_x`, `plate_y`, `plate_thickness` (default 100, 100, ~5 mm)
- `plate_hole_inset`, `plate_hole_dia` (corner M3 pattern)
- `standoff_height` (air gap, default ~22 mm), `standoff_dia`
- `insert_dia_m3`, `insert_depth` (heat-set boss geometry)
- `panel_cutouts`: SW1/SW2/D1/OLED positions + sizes, driven by the board's
  `placement.json` coordinates
- `wall_thickness`, `bed_max` (220 mm) for part-splitting checks

## 6. Repository layout
```
hardware/3d/
  enclosure.blend           Blender source (parametric)
  stl/                      exported STL per part (print)
  step/                     exported STEP per part (CAD)
  README.md                 print settings, insert sizes, assembly + hardware BOM
```

## 7. Verification (the 3D equivalent of tests)
- Each part exports a manifold (watertight) STL — checked in Blender (no non-manifold edges / holes).
- Fit checks against parameters: plate-hole pattern matches `plate_*`; panel cutout coords match
  `placement.json`; heat-set boss bores match the chosen insert (e.g. M3 → ~4.0 mm).
- Every part's bounding box ≤ 220×220 mm (bed); flag any that needs splitting.
- Wall thickness ≥ a printable minimum; standoff/air-gap height ≥ the thermal-safety value.
- Assembly dry-run in Blender: parts mate without interference (box ↔ panel ↔ lid; plate frame
  standoff spacing).

## 8. Risks & open items
- **Plate spec (still the key input):** exact plate dimensions/holes/thickness and the real wire
  exit must be confirmed before the final print; the parametric model makes this a variable change.
- **Standoff height vs. heat:** ~22 mm air gap assumed safe; re-check once the plate's sustained
  surface/edge temperature is known.
- **Panel ↔ board alignment:** cut-out positions depend on `placement.json`; if the board is ever
  re-placed, regenerate the panel.
- **Insert pull-out:** boss walls must be thick enough for M3 heat-set inserts under panel/lid load.
