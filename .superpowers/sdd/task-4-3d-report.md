# Task 4 — Top control panel (`build_panel.py`) report

## Affine (board frame → panel frame)
The board is centred in the box, so the board centre `(pcb_x/2, pcb_y/2)` maps to
the panel centre `(0,0)`. placement.json positions are in board frame (origin at
board lower-left). The map is a pure translation:

```
panel_x = board_x - pcb_x/2   (= board_x - 52.0)
panel_y = board_y - pcb_y/2   (= board_y - 52.0)
```

Checks: SW1 (25.6,11.1)→(-26.4,-40.9); SW2 (41.9,7.8)→(-10.1,-44.2);
D1 (52.7,7.2)→(0.7,-44.8); J4 (5.8,9.6)→(-46.2,-42.4).

## What was built
PETG plate `box_x × box_y × panel_t` = 113×113×3, top face up (z=0..3). One
manifold object `panel`. Cuts (all booleaned through):
- Encoder shaft Ø7.5 (encoder_shaft_d) at SW1
- Push-button Ø12.5 (button_d) at SW2
- LED Ø5.5 (led_d) at D1
- OLED window 26×15 (oled_win_x × oled_win_y, X×Y) at J4
- Vent slots (4 × 2.5×18, pitch 6) over the regulator zone: centred at the
  midpoint of U2/U3 mapped through the affine (panel x≈-1.55, y≈-21.7), i.e. the
  power corner (placement.json `_doc`: lower-left) regulator/MOSFET band.
- 4 × Ø3.4 M3 clearance holes at `top_insert_centers()` = (±52.5, ±52.5).

## Verification (real Blender output)
```
verify = {"nonmanifold": 0, "bbox": (113, 113, 3),
          "manifold_ok": True, "fits_bed": True}
cut_centers = {"SW1": (-26.4,-40.9), "SW2": (-10.1,-44.2),
               "D1": (0.7,-44.8), "J4": (-46.2,-42.4)}
MATES box rim = True
hole_centers       = [(-52.5,-52.5),(-52.5,52.5),(52.5,-52.5),(52.5,52.5)]
top_insert_centers = [(-52.5,-52.5),(-52.5,52.5),(52.5,-52.5),(52.5,52.5)]
```
Single watertight solid. STL written: `hardware/3d/stl/panel.stl`.

## Files changed
- `hardware/3d/build_panel.py` (new)
- `hardware/3d/stl/panel.stl` (new)

## Concerns
- OLED window orientation assumed `oled_win_x` along panel X, `oled_win_y` along
  panel Y (J4 rotation in placement.json is 0). If the physical OLED module is
  rotated, the window may need swapping — low risk given the 0° placement.
- Vent slots are a small decorative/airflow row over the regulator zone; exact
  count/pitch chosen for manifold cleanliness, not validated against a thermal
  model.

## Review fix (vents from JSON + OLED rot)

### What changed
1. **Vent anchors from placement.json** (`build_panel.py` lines ~111-125): removed
   the two hardcoded board-x literals `42.5` (U2) and `58.4` (U3). The build
   function now reads `placement.json` keys `U2` and `U3` at runtime using
   `_pl.get("U2", [42.5, 30.3, 0])` / `_pl.get("U3", [58.4, 30.3, 0])`, maps
   them through the existing `_affine()` call, and computes `vent_cx`/`vent_cy`
   from those results. Fallback defaults (the original literals) are used only if
   a key is absent — no crash.

2. **J4 rotation assert** (`build_panel.py` before the OLED boolean): added
   `assert pl_j4_rot == 0` with a message explaining how to handle 90°/270°
   rotation (swap `oled_win_x`/`oled_win_y`). This will surface immediately if
   the board is respun with a rotated OLED header.

### JSON-derived vent anchors (from real Blender run)
| Component | Board frame (mm) | Panel frame (mm) |
|-----------|-----------------|-----------------|
| U2        | [42.5, 30.3]    | (-9.5, -21.7)   |
| U3        | [58.4, 30.3]    | (6.4, -21.7)    |
| vent_cx   | —               | -1.55           |
| vent_cy   | —               | -21.7           |

### Verification output (real Blender output)
```
verify = {'nonmanifold': 0, 'bbox': (113.0, 113.0, 3.0), 'manifold_ok': True, 'fits_bed': True}
cut_centers = {'SW1': (-26.4, -40.9), 'SW2': (-10.1, -44.2), 'D1': (0.7, -44.8), 'J4': (-46.2, -42.4)}
MATES = True
U2 board=[42.5, 30.3] -> panel=(-9.5, -21.7)
U3 board=[58.4, 30.3] -> panel=(6.4, -21.7)
vent_cx=-1.55, vent_cy=-21.7
STL exported OK
```
Still manifold; cut_centers unchanged; MATES True; STL re-exported.

## OLED window overhang fix

### Root cause
The OLED window (J4) was centred at panel (−46.2, −42.4), derived from the J4
board footprint via the affine transform. With `oled_win_x = 26 mm`, the window's
left edge fell at `−46.2 − 13.0 = −59.2 mm`, overhanging the panel half-width of
56.5 mm by **2.7 mm** — an open-sided notch instead of an enclosed window.

### Why the fix is a free design choice
The SSD1306 OLED module connects to J4 via a short 4-wire cable (JST), not by
sitting directly above the connector. The panel window position is therefore
**independent of J4's board coordinate** and can go anywhere on the panel
consistent with the geometry constraints.

### New OLED position
`_OLED_PANEL_X = −25.0 mm`, `_OLED_PANEL_Y = 20.0 mm` — upper-left quadrant of
the panel, clear of the SW1/SW2/D1 control row (which sits at y ≈ −41 to −45 mm).

Window edge coordinates (26×15 mm window, half-extents 13 and 7.5 mm):

| Edge   | Value (mm) | Panel limit (mm) | Margin (mm) |
|--------|-----------|-----------------|-------------|
| Left   | −38.0     | −53.5           | +15.5       |
| Right  | −12.0     | +53.5           | +65.5       |
| Bottom | +12.5     | −53.5           | +66.0       |
| Top    | +27.5     | +53.5           | +26.0       |

All four edges are well within ±53.5 mm. Nearest screw hole is at (−52.5, 52.5)
Ø3.4 mm; gap from screw edge to window edge ≥ 12.8 mm (requirement: ≥ 2 mm).

### The guard: `_assert_inside_outline()`
Added to `build_panel.py`. Checks every cut before the booleans run:
- **Control holes** (SW1 encoder, SW2 button, D1 LED): centre ± radius within
  ±(box/2 − 3 mm) = ±53.5 mm.
- **OLED window**: centre ± half-extent within ±53.5 mm.
- **Screw holes**: centre ± radius within ±(box/2 − 1 mm) = ±55.5 mm (corner
  holes are by design near panel corners within the wall zone; 1 mm physical
  margin is appropriate for them).

Called in `build()` immediately after `cut_centers()`. Raises `AssertionError`
with an explicit message identifying the offending cut and edge coordinate.

### Guard fires on the bad position
Temporarily overriding the OLED center to the original bad position (−46.2, −42.4)
triggers:
```
AssertionError: _assert_inside_outline: OLED window left edge -59.200 < -53.500
```
The guard has teeth — it catches the open-sided-notch class of bug that the
manifold check misses (a manifold solid can still have open-sided slots if the
panel outline itself is intact but a cut overhangs an edge).

### Verification output (real Blender run after fix)
```
verify = {'nonmanifold': 0, 'bbox': (113, 113, 3), 'manifold_ok': True, 'fits_bed': True}
cut_centers = {'SW1': (-26.4, -40.9), 'SW2': (-10.1, -44.2), 'D1': (0.7, -44.8), 'J4': (-25.0, 20.0)}
MATES = True
OLED edges: left=-38.0, right=-12.0, bottom=12.5, top=27.5  (all within ±53.5)
_assert_inside_outline: PASSED on new position
_assert_inside_outline: FIRES on bad position (-46.2, -42.4) with message above
STL re-exported: hardware/3d/stl/panel.stl
```
SW1/SW2/D1 centres unchanged. MATES True. Manifold. OLED fully enclosed.
