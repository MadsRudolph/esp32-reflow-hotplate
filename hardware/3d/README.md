# ESP32 Reflow Hotplate — 3D Enclosure

Parametric 3-part enclosure for the ESP32 reflow hotplate: a **plate frame** that
holds the ~250 °C heater plate on ceramic standoffs over an open air gap, an
**electronics box** that carries the 104×104 mm control board flat, and a **top
control panel** that closes the box and exposes the encoder, button, LED and OLED.

The whole model is parametric. Everything geometry-relevant lives in
[`params.py`](params.py); change a value there (e.g. the real plate dimensions)
and re-run [`build_all.py`](build_all.py) to regenerate all parts, the assembled
`enclosure.blend`, and the STL set.

---

## Files

| File | Role |
|------|------|
| `stl/plate_frame.stl`, `stl/box.stl`, `stl/panel.stl` | **Print these.** One STL per part. |
| `enclosure.blend` | Assembled scene (box at origin, panel on top, plate frame beside). Parametric source-of-truth render. |
| `params.py` | All dimensions/parameters. **Edit here**, then re-run. |
| `build_common.py` | Blender helpers (booleans, manifold check, STL export, verify). |
| `build_plate_frame.py`, `build_box.py`, `build_panel.py` | Per-part parametric builders (`build()` each). |
| `build_all.py` | Assembles all three, runs the box↔panel interference check, exports STL, saves `.blend`. |

**STEP export** is intentionally out of scope — Blender has no native STEP
exporter. If a STEP/CAD hand-off is needed, it is an optional FreeCAD follow-up
(import the STL or rebuild from `params.py`). The `.blend` + `build_*.py` are the
parametric source.

### Regenerating everything

In a running Blender (5.x) with the MCP/console:

```python
exec(open(r".../hardware/3d/build_all.py").read())
r = build_all()
print(r)
# all three parts -> manifold_ok True, fits_bed True
# interference.box_panel ~ 0  (box walls do NOT pass through the panel)
# 3 STL written to stl/, enclosure.blend saved
```

The build asserts each part is **manifold/watertight** (`nonmanifold == 0`) — a
non-watertight STL is never exported. The box↔panel interference is measured by a
temporary boolean INTERSECT whose volume must be ≈ 0 (only the rim/screw bosses
touch the panel underside; the walls must not intersect the panel body).

---

## Print settings

- **Material:** PETG (chosen for higher glass-transition temp and toughness near
  the warm enclosure; the plate itself is held off all plastic — see thermal note).
- **Walls / perimeters:** **≥ 3** (the screw bosses and standoff bosses rely on
  solid walls for thread/insert retention).
- **Infill:** **~25–40%** (gyroid or grid). Toward the higher end for the box if
  you want extra rigidity under the board + panel.
- **Layer height:** 0.2 mm is fine for all parts.
- **Supports:** enable for overhangs — specifically the **box terminal opening**
  (the rectangular J1/J2 cut-out in the −Y wall) and any **panel cut-out
  overhang**. The vent slots and bores are bridgeable but inspect them.
- **Orientation:** print box and plate frame floor-down (open side up); print the
  panel flat, control face up.

---

## Heat-set inserts

- **Type:** M3 brass heat-set inserts.
- **Boss bore:** **Ø 4.0 mm** (`insert_bore_d`), ~6 mm deep (`insert_bore_depth`)
  in each of the 4 box top-rim bosses.
- **Install:** push each insert in with a **soldering iron** set to ~200–230 °C —
  let the brass melt into the bore until flush with the boss top, then back the
  iron out straight so the insert stays square.

---

## Hardware BOM

| Qty | Item | Notes |
|-----|------|-------|
| 4 | **M3 ceramic standoffs — FEMALE-THREADED** | **CRITICAL:** the plate-frame bosses are **blind** (solid foot below, no through-clearance for a bottom nut). The standoff must be **female-threaded** and **seat on the boss top**; the M3 screw threads **UP into the plate** from above. A plain spacer that needs a nut underneath the frame **will NOT fit.** |
| 4 | M3 steel screws (for the plate) | Thread up through the plate into the female ceramic standoffs. Length to suit plate thickness + a few mm of engagement. |
| 4 | M3 brass heat-set inserts | Pressed into the box top-rim bosses (Ø4.0 bore). |
| 4 | M3 screws (box↔panel) | Pass down through the panel clearance holes into the box-rim inserts. |
| 4 | Rubber feet | Stick-on, under the box (and/or plate frame). |
| 0 | Board screws | **None needed.** The control board has no mounting holes — it **rests on the box's 4 corner posts** and is captured from above by the top panel. |

---

## Assembly order

1. **Press the heat-set inserts** into the **box top-rim bosses** (4×, Ø4.0 bore)
   with a soldering iron; let them seat flush and square.
2. **Bolt the plate** to the **plate frame** on the **ceramic standoffs**: seat a
   female-threaded ceramic standoff on each boss, then run an M3 steel screw
   **up** from the standoff into the plate.
3. **Drop the control board** onto the box's **4 corner support posts** (no
   screws — it simply rests on the posts, lifted off the floor for the bottom
   lead tails).
4. **Wire the OLED module to J4** and seat it under the **panel's OLED window**.
5. **Screw the top control panel down** onto the box (4× M3 into the heat-set
   inserts). This captures the board and aligns the encoder / button / LED / OLED
   with their panel cut-outs.
6. **Stick the rubber feet** on the underside.
7. **Wire the power side** through the **terminal opening** in the box −Y wall:
   24 V-in (**J1**) and the heater output (**J2**), plus the **two thick power
   wire-bridges** and the **signal jumpers** per the PCB `MILL_NOTES`.

---

## Thermal safety

- The heater plate runs at roughly **~250 °C**. **Ceramic standoffs** plus the
  **22 mm air gap** (`standoff_h`) keep that plate off **all** plastic — nothing
  printed ever touches the hot plate.
- The **electronics box is physically offset** from the plate (separate part,
  placed beside it), keeping the control board out of the heat plume.
- This is a conservative starting point. **Re-verify** the standoff height / air
  gap and the box offset **once the real plate's sustained surface temperature is
  known** — if the production plate runs hotter or the plume is wider than
  assumed, increase `standoff_h` (and/or the box offset) in `params.py` and
  re-run `build_all.py`.
