# SRM-20 Milling Notes — ESP32 Reflow Hotplate

Board: `reflow.kicad_pcb` — single-sided (B.Cu traces), 86 F.Cu top jumpers (wire bridges), 3 high-current pours (+24V, HEATER_RET, GND).

---

## Production files

| File | Purpose |
|---|---|
| `reflow_mill_bcu.svg` | **Mirrored** B.Cu — feed to mods CE or gerber2rml for trace job |
| `reflow.dxf` | B.Cu + Edge.Cuts (DXF) |
| `reflow_top_cu.dxf` | F.Cu + Edge.Cuts — wire-bridge wiring guide |
| `reflow-F_Cu.dxf` | F.Cu standalone DXF |
| `reflow_silk_top.dxf` | F.Silkscreen (optional engraving) |
| `gerbers/reflow-B_Cu.gbl` | B.Cu Gerber |
| `gerbers/reflow-Edge_Cuts.gm1` | Board outline Gerber |
| `gerbers/reflow.drl` | Excellon drill file |
| `gerbers/reflow-*.g*` | Full Gerber set (masks, fab, silk) |

---

## Three SRM-20 jobs

### Job 1 — Traces (B.Cu)

- **Source file:** `reflow_mill_bcu.svg` (already mirrored — do NOT mirror again in mods)
- **Bit:** 1/64" (0.4 mm) flat end mill
- **mods CE settings:** `mill traces`, depth **0.10–0.15 mm**, offsets **2** (channels are 0.8 mm wide — 2 offsets clears them exactly; `-1` = clear all = very slow, use only if isolation fails)
- **Feed rate:** 4 mm/s (SRM-20 spindle tops at 7000 rpm — do not raise feed, 1/64" bits snap)
- **Travel/jog height:** 2–5 mm (don't set 12+ mm, just slow)

> **Wide-pour caveat:** the +24V, HEATER_RET, and GND pours have 0.8 mm clearance channels around them. The 1/64" bit just fits 2 offsets. If any pour boundary fails to isolate after milling, re-run that region with `-1` offsets (raster-clear) or touch up manually with a multimeter to verify.

### Job 2 — Holes

- **Source:** `gerbers/reflow.drl` (Excellon) or render `gerbers/reflow-Edge_Cuts.gm1` + `reflow.drl` to PNG in a Gerber viewer and mirror in GIMP — OR drill by hand after laser flow.
- **Bit:** 1/32" (0.8 mm)
- **mods CE settings:** `mill outline`, depth **0.6 mm/pass**, total **1.8 mm** (through 1.6 mm board)
- Note: **all three jobs are viewed from the underside** (copper face up in machine). Mirroring already done in SVG for job 1; apply same mirror to hole and outline PNGs if rendering.

### Job 3 — Board cutout (Edge.Cuts)

- **Source:** `gerbers/reflow-Edge_Cuts.gm1` (mirror as above)
- **Bit:** 1/32" (0.8 mm)
- **Settings:** same as holes — depth 0.6 mm/pass, total 1.8 mm

---

## Machine setup

### Material

Use **FR-1 (phenolic)** if available. FR-4 can be milled but glass-fibre dust wears 1/64" bits within 1–2 boards and is a health hazard — use a vacuum and dust mask. Ask the fablab shop for FR-1.

### Board preparation

- Stock size: any piece ≥ 110 × 110 mm (board is ~109 × 109 mm). SRM-20 work area is 203 × 152 mm.
- Mount on a sacrificial MDF plate with **double-sided tape over the entire back surface** — a 0.1 mm bump shows in milling depth. Press the board completely flat.

### Origin / Z-zero procedure

1. Jog the spindle to the **lower-left corner** of the board → `Set Origin X/Y` in VPanel.
2. **Z-zero:** lower the bit to just above the copper surface, loosen the collet set-screw so the bit drops and rests on the copper, re-tighten → `Set Origin Z`. (Classic SRM-20 trick — gives Z-zero exactly at the copper surface.)
3. Run **Job 1** (1/64" traces).
4. **Bit change:** swap to 1/32". Re-run Z-zero only (XY origin is preserved). Run **Jobs 2+3** (holes + cutout).

### Post-mill check

Multimeter **continuity check** of all adjacent trace pairs after milling. Pay particular attention to:
- **SW1 encoder** — ~0.5 mm intrinsic pad gap (near 0.4 mm bit limit)
- **D1 LED** — ~0.74 mm pad gap (near limit)

If any pair short, clean the channel with a sharp tool or fine sandpaper, then re-test.

---

## Hand-finish items — CRITICAL

The SRM-20 mill produces the B.Cu traces only. This board is **not complete from the mill alone**. The following must be done by hand:

### A) Top-side signal wire bridges (~86 jumpers)

Use `reflow_top_cu.dxf` (or `reflow-F_Cu.dxf`) as the wiring guide. Solder **thin insulated wire** (e.g. 28–30 AWG kynar wire-wrap or similar) for each F.Cu segment shown. Work systematically — mark each completed bridge.

### B) Two high-current wire bridges — USE THICK WIRE (18–20 AWG solid)

These two nets carry ~13 A heater current and are geometrically un-routable on single-sided B.Cu in this layout. The B.Cu corridors are too narrow to carry 13 A — **top-side wire bridges are required and must be short and thick.**

| Net | From | To | Notes |
|---|---|---|---|
| `+24V` | C3 pin 1 | F1 pin 2 | Only ~1 mm B.Cu corridor exists — bridge mandatory |
| `HEATER_RET` | D4 pin 1 | J2 pin 2 | ~2 mm clearance corridor — bridge mandatory |

Use 18–20 AWG solid tinned copper wire. Keep bridges as short as possible. Secure with a dab of hot glue or epoxy after soldering.

### C) Tight-isolation check

After milling, verify isolation with a multimeter on:
- **SW1 encoder** (~0.5 mm pad gap) — pads must not short
- **D1 LED** (~0.74 mm pad gap) — pads must not short

Do a manual touch-up with a sharp scribe or fine rotary tool if needed.

### D) Silkscreen / cosmetic (optional)

F.Silkscreen (`reflow_silk_top.dxf`) can be engraved separately on a laser engraver for reference designators, or skipped entirely. The two no-net laser-fill zone warnings and Q2/Q3 silk-overlap DRC items are cosmetic only — no connectivity impact.

---

## Toolchain reference

- **mods CE:** https://modsproject.org — browser-based, Fab Academy standard. `programs → open program → machines → Roland → SRM-20 mill → mill 2D PCB`
- **gerber2rml alternative:** `tools/srm-cam` — generates `.rml` or `.nc` directly from Gerbers, skips the PNG/mods step. Select `Roland SRM-20 (G-code)` in GUI or pass `--gcode` on CLI. Validated 2026-06-22 at 0.15 mm isolation with a sharp, short bit.
- **VPanel for SRM-20** (on the machine's PC): `Cut → Add → Output`

> Validated isolation depth: **0.15 mm** with a sharp, short 1/64" bit. A dull or long bit burns the copper and cuts too deep — inspect the bit before each job.
