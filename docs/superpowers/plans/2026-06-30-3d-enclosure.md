# Reflow Hotplate — 3D Enclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a parametric Blender model of the reflow-hotplate enclosure (plate frame, electronics box, front panel, lid) and export a manifold, bed-fitting STL per part.

**Architecture:** A single `params.py` holds every dimension. `build_common.py` provides bpy helpers + the verification harness (manifold check, bounding-box check, STL export). One `build_<part>.py` per printed part constructs its geometry procedurally (primitives + boolean cuts) from `params`. `build_all.py` assembles all parts, runs an interference check, exports every STL, and saves `enclosure.blend`. All geometry is built and verified inside a live Blender via the Blender MCP (`mcp__blender__execute_blender_code`); the `.py` files are the committed source of truth.

**Tech Stack:** Blender (bpy) via the Blender MCP, Python 3.x (bmesh for manifold checks), STL export (`bpy.ops.wm.stl_export` / `export_mesh.stl`).

## Global Constraints

- **Tooling:** geometry is built/verified by running each script's body through `mcp__blender__execute_blender_code` (the Blender MCP — load it via ToolSearch: `select:mcp__blender__execute_blender_code`). Commit the `.py` source files; they must be runnable as `exec(open(path).read())` inside Blender.
- **Deliverables:** one **manifold STL per part** under `hardware/3d/stl/` + the saved `hardware/3d/enclosure.blend`. **STEP is NOT produced** (Blender has no native STEP export); the `.blend` + `.py` are the CAD source. A STEP conversion (FreeCAD) is an optional later follow-up — do not block on it.
- **Material/parametric:** PETG; every dimension comes from `hardware/3d/params.py` `PARAMS` — no magic numbers in the part builders.
- **Heat-set inserts:** M3 brass → boss bore **Ø4.0 mm**, depth **6 mm**, boss outer wall ≥ **2.0 mm** around the bore. Used for box↔panel, box↔lid, and PCB↔box joints.
- **Plate mount:** ceramic standoffs; the plate frame gets **Ø3.4 mm** clearance holes (steel M3) at the plate's corner pattern; standoff/air-gap height **22 mm** (`standoff_h`).
- **Panel cut-outs** are driven by `hardware/kicad/placement.json` board coordinates for SW1 (encoder), SW2 (button), D1 (LED), J4 (OLED module) — NOT hardcoded.
- **Print limits:** every part's XY bounding box ≤ **220 × 220 mm** (`bed_max`); wall thickness ≥ **2.4 mm** (`wall`).
- **Verification = manifold + fit:** every part must be watertight (0 non-manifold edges) and pass its dimensional fit checks before its task is done.
- **Commits:** never mention Claude/AI in commit messages.

## File Structure

```
hardware/3d/
  params.py              # PARAMS dict — single source of all dimensions
  build_common.py        # bpy helpers + verification (manifold/bbox/export/self-test)
  build_plate_frame.py   # Part 1: plate frame (ceramic-standoff bosses + air gap + wire channel + feet)
  build_box.py           # Part 2: electronics box (PCB bosses, vents, terminal openings, insert bosses)
  build_panel.py         # Part 3: front panel (cut-outs from placement.json + insert holes)
  build_lid.py           # Part 4: lid (vents + insert holes matching box rim)
  build_all.py           # assemble + interference check + export all STL + save .blend
  stl/                   # exported STL per part
  enclosure.blend        # saved Blender source
  README.md              # print settings, insert/hardware BOM, assembly steps
```

---

### Task 1: Params + common helpers + verification harness

**Files:**
- Create: `hardware/3d/params.py`, `hardware/3d/build_common.py`

**Interfaces:**
- Produces: `PARAMS` (dict); and in `build_common`: `fresh_scene()`, `add_box(name,x,y,z,loc)->obj`, `add_cyl(name,d,h,loc)->obj`, `boolean(obj,tool,op='DIFFERENCE')`, `nonmanifold_edges(obj)->int`, `bbox_mm(obj)->(x,y,z)`, `export_stl(obj,path)`, `verify(obj,max_xy)->dict`.

- [ ] **Step 1: Write `params.py`** — every dimension the parts use:

```python
PARAMS = {
    "plate_x": 100.0, "plate_y": 100.0, "plate_t": 5.0,
    "plate_hole_inset": 6.0, "plate_hole_clear_d": 3.4,   # M3 clearance
    "standoff_h": 22.0, "standoff_boss_d": 9.0,
    "insert_bore_d": 4.0, "insert_bore_depth": 6.0, "insert_boss_wall": 2.0,
    "wall": 2.4, "floor": 2.4,
    "box_x": 90.0, "box_y": 70.0, "box_h": 40.0,          # electronics box inner-ish envelope
    "panel_t": 3.0,
    "pcb_x": 104.0, "pcb_y": 104.0,                        # control board outline
    "vent_slot_w": 2.5, "vent_slot_l": 18.0,
    "bed_max": 220.0,
    "encoder_shaft_d": 7.5, "button_d": 12.5, "led_d": 5.5, "oled_win_x": 26.0, "oled_win_y": 15.0,
}
```

- [ ] **Step 2: Write the verification harness FIRST** in `build_common.py` (this is the "test" infrastructure every part reuses):

```python
import bpy, bmesh, os

def fresh_scene():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()

def add_box(name, x, y, z, loc=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object; o.name = name; o.scale = (x, y, z)
    bpy.ops.object.transform_apply(scale=True); return o

def add_cyl(name, d, h, loc=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=d/2, depth=h, location=loc)
    o = bpy.context.active_object; o.name = name; return o

def boolean(obj, tool, op='DIFFERENCE'):
    m = obj.modifiers.new("b", 'BOOLEAN'); m.operation = op; m.object = tool; m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(tool, do_unlink=True)

def nonmanifold_edges(obj):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    n = sum(1 for e in bm.edges if not e.is_manifold); bm.free(); return n

def bbox_mm(obj):
    d = obj.dimensions; return (round(d.x,2), round(d.y,2), round(d.z,2))

def export_stl(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try: bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    except Exception: bpy.ops.export_mesh.stl(filepath=path, use_selection=True)

def verify(obj, max_xy):
    nm = nonmanifold_edges(obj); x,y,z = bbox_mm(obj)
    return {"nonmanifold": nm, "bbox": (x,y,z),
            "manifold_ok": nm == 0, "fits_bed": x <= max_xy and y <= max_xy}
```

- [ ] **Step 3: Run the harness self-test in Blender — expect manifold pass + non-manifold detection.** Via `mcp__blender__execute_blender_code`, exec `build_common.py`, then:

```python
fresh_scene()
b = add_box("t", 10, 20, 5)
print("BOX", verify(b, PARAMS["bed_max"]))      # expect nonmanifold 0, bbox (10,20,5), manifold_ok True
# break manifoldness: delete a face
bm = bmesh.new(); bm.from_mesh(b.data); bm.faces.ensure_lookup_table(); bm.faces.remove(bm.faces[0]); bm.to_mesh(b.data); bm.free()
print("BROKEN", nonmanifold_edges(b))            # expect > 0
```
Expected: `BOX` → `manifold_ok True`, `bbox (10.0,20.0,5.0)`; `BROKEN` → a number > 0. (Proves the manifold check has teeth.)

- [ ] **Step 4: Commit**

```bash
git add hardware/3d/params.py hardware/3d/build_common.py
git commit -m "3d: parametric params + bpy verification harness (manifold/bbox/export)"
```

---

### Task 2: Plate frame

**Files:**
- Create: `hardware/3d/build_plate_frame.py`

**Interfaces:**
- Consumes: `PARAMS`, `build_common` helpers.
- Produces: object `plate_frame`; STL `hardware/3d/stl/plate_frame.stl`.

Geometry (all from `PARAMS`): an open frame footprint `plate_x+2*wall × plate_y+2*wall`, a perimeter floor `floor` thick, and **4 standoff bosses** (Ø`standoff_boss_d`, height `standoff_h`) at the plate's corner pattern (corner inset `plate_hole_inset`), each bored Ø`plate_hole_clear_d` through (the ceramic standoff seats on the boss, steel M3 passes through into the plate). The centre is **open** (air gap) — only the perimeter + corner bosses are solid. A `vent_slot_w`-wide **wire channel** notch on the electronics-facing edge. Short feet under the corners.

- [ ] **Step 1: Write the failing fit-check** (run after build): assert frame is manifold, bbox ≤ bed, and the 4 boss-hole centres equal the plate corner pattern `(±(plate_x/2 - plate_hole_inset), ±(plate_y/2 - plate_hole_inset))`. Write `build_plate_frame.py` to also expose `hole_centers()` returning those 4 (x,y).

- [ ] **Step 2: Run the check with no build — expect failure** (object missing). Via the MCP, exec the check before the build body; expect a NameError / `plate_frame` not found.

- [ ] **Step 3: Implement `build_plate_frame.py`** — construct the perimeter (big box minus inner box to leave `wall`/`floor`), add the 4 bosses at `hole_centers()`, boolean-subtract the Ø`plate_hole_clear_d` bores and the wire channel, join into one `plate_frame` object.

- [ ] **Step 4: Run build + verify in Blender:**

```python
exec(open(".../build_common.py").read()); exec(open(".../build_plate_frame.py").read())
o = build()  # returns plate_frame
print(verify(o, PARAMS["bed_max"]))               # manifold_ok True, fits_bed True
print("HOLES", hole_centers())                    # 4 corner coords match the formula
print("AIRGAP", PARAMS["standoff_h"] >= 20)       # True (thermal-safety floor)
export_stl(o, ".../stl/plate_frame.stl")
```
Expected: `manifold_ok True`, `fits_bed True`, 4 correct hole centres, airgap True, STL written.

- [ ] **Step 5: Commit**

```bash
git add hardware/3d/build_plate_frame.py hardware/3d/stl/plate_frame.stl
git commit -m "3d: parametric plate frame with ceramic-standoff bosses and air gap"
```

---

### Task 3: Electronics box

**Files:**
- Create: `hardware/3d/build_box.py`

**Interfaces:**
- Consumes: `PARAMS`, `build_common`. Produces object `box`, STL `stl/box.stl`, and `top_insert_centers()` / `board_post_centers()` (lists of (x,y)) for Task 4 (top control panel) to align to.

Geometry: a `box_x × box_y × box_h` shell (walls `wall`, floor `floor`, **open top**) — sized (113×113) to hold the **104×104 board flat** with `board_clear` gap to the walls. Inside floor: **4 board support POSTS** (Ø`board_post_d`, height `board_post_h`) at `board_post_centers()` = `(±board_post_xy, ±board_post_xy)` — the board RESTS on these (it has **no mounting holes**), lifted `board_post_h` off the floor for the bottom lead tails; do NOT bore them (no screw). **Vent slots** (`vent_slot_w`×`vent_slot_l`, a row of ~4) in a wall above where the regulators + MOSFET heatsink sit. **Terminal openings** on one wall for the J1/J2 screw terminals (≈12 mm tall × ~30 mm wide near the floor). **Top-rim insert bosses** at `top_insert_centers()` (4 corners, inset `insert_boss_wall+insert_bore_d/2` from the outer wall) with Ø`insert_bore_d`×`insert_bore_depth` bores — the top control panel screws into these.

- [ ] **Step 1: Write the fit-check** (post-build): manifold; bbox ≤ bed (113 ≤ 220); `board_post_centers()` has 4 entries inside the box; `top_insert_centers()` has 4; each top-insert bore Ø == `insert_bore_d`; vent slots + terminal opening present (assert `len(board_post_centers())==4 and len(top_insert_centers())==4`, and that the board fits: `box_x - 2*wall >= pcb_x` and `box_y - 2*wall >= pcb_y`).

- [ ] **Step 2: Run check pre-build — expect failure** (`box` missing).

- [ ] **Step 3: Implement `build_box.py`** — shell via box-minus-inner (open top); add 4 board posts (no bore); subtract vent-slot row; subtract terminal opening; add 4 top-rim insert bosses + bores; join to `box`. Expose `board_post_centers()` and `top_insert_centers()`.

- [ ] **Step 4: Build + verify in Blender:**

```python
exec(.../build_common.py); exec(.../build_box.py)
o = build(); print(verify(o, PARAMS["bed_max"]))
print("POSTS", board_post_centers(), "TOP", top_insert_centers())
print("BOARD FITS", PARAMS["box_x"]-2*PARAMS["wall"] >= PARAMS["pcb_x"])  # True
export_stl(o, ".../stl/box.stl")
```
Expected: `manifold_ok True`, `fits_bed True`, 4 board posts, 4 top-insert centres, BOARD FITS True, STL written.

- [ ] **Step 5: Commit**

```bash
git add hardware/3d/build_box.py hardware/3d/stl/box.stl
git commit -m "3d: electronics box sized for the board, corner support posts, vents, terminal openings, top-rim inserts"
```

---

### Task 4: Top control panel (closes the box + carries the controls)

**Files:**
- Create: `hardware/3d/build_panel.py`

**Interfaces:**
- Consumes: `PARAMS`, `build_common`, `box.top_insert_centers()`, and `hardware/kicad/placement.json`. Produces object `panel`, STL `stl/panel.stl`.

This part replaces the old separate front panel **and** lid: it is the **top cover** of the box that the user looks down on, with the control cut-outs aligned to the board's components below. The board lies flat in the box, centred, controls pointing **up** at this panel.

Geometry: a plate `box_x × box_y × panel_t` (the box top). Read `placement.json`; the board is centred in the box, so map each board (x,y) to panel-local coords with the affine **`panel_x = board_x − pcb_x/2`, `panel_y = board_y − pcb_y/2`** (board centre → panel centre). Document it in the file. Cut: **encoder shaft** Ø`encoder_shaft_d` at SW1; **button** Ø`button_d` at SW2; **LED** Ø`led_d` at D1; **OLED window** `oled_win_x × oled_win_y` at J4. Add **vent slots** over the regulator/MOSFET zone. Add Ø3.4 mm M3 **clearance holes** at `box.top_insert_centers()` so it screws down into the box top-rim inserts.

- [ ] **Step 1: Write the cut-position check** (post-build): manifold; bbox ≤ bed; the 4 control cut centres equal the mapped placement.json coords (expose `cut_centers()` → `{ref:(x,y)}`; assert against the affine applied to SW1 25.6/11.1, SW2 41.9/7.8, D1 52.7/7.2, J4 5.8/9.6 → e.g. SW1 → `(25.6−52, 11.1−52)=(−26.4,−40.9)`); and the clearance-hole centres equal `box.top_insert_centers()` (panel mates the box rim).

- [ ] **Step 2: Run check pre-build — expect failure** (`panel` missing).

- [ ] **Step 3: Implement `build_panel.py`** — load JSON, compute `cut_centers()` via the affine, build the plate, boolean-subtract the 4 control cut-outs + vents + the 4 clearance holes at `box.top_insert_centers()`; name it `panel`. (Exec `build_box.py` first so `top_insert_centers()` is available.)

- [ ] **Step 4: Build + verify in Blender:**

```python
exec(.../build_common.py); exec(.../build_box.py); exec(.../build_panel.py)
o = build(); print(verify(o, PARAMS["bed_max"]))
print("CUTS", cut_centers())              # SW1/SW2/D1/J4 at the centred coords
print("MATES box rim:", sorted(hole_centers()) == sorted(top_insert_centers()))
export_stl(o, ".../stl/panel.stl")
```
Expected: `manifold_ok True`, `fits_bed True`, cut centres match the mapped placement.json coords, clearance holes == box rim insert centres (True), STL written.

- [ ] **Step 5: Commit**

```bash
git add hardware/3d/build_panel.py hardware/3d/stl/panel.stl
git commit -m "3d: top control panel with cut-outs from placement.json, mates the box rim"
```

---

### Task 5: Assembly, interference check, exports + README

**Files:**
- Create: `hardware/3d/build_all.py`, `hardware/3d/README.md`
- Produce: `hardware/3d/enclosure.blend`, all **three** STL re-exported (plate_frame, box, panel).

- [ ] **Step 1: Write the assembly interference check** in `build_all.py`: build all THREE parts in one scene at their assembled positions (box at origin; **panel on the box top** at `z = box_h`; plate frame beside the box, offset in +X). For the MATING pair **box↔panel**, assert overlap ≤ tolerance: compute via a temporary BOOLEAN INTERSECT and check the intersection volume ≈ 0 (only the rim/screws meet, not through the walls). Report the intersection volume.

- [ ] **Step 2: Run it pre-implementation — expect failure** (`build_all` undefined).

- [ ] **Step 3: Implement `build_all.py`** — exec each part builder, position them (box origin; panel at z=`box_h`; plate frame at +X beside), run the interference check, export all three STL into `stl/`, and `bpy.ops.wm.save_as_mainfile(filepath=".../enclosure.blend")`.

- [ ] **Step 4: Run in Blender + verify everything green:**

```python
exec(.../build_all.py); r = build_all()
print(r)   # {'plate_frame':{manifold_ok:True,fits_bed:True}, 'box':..., 'panel':...,
           #  'interference':{'box_panel':~0}, 'stls':[3 paths], 'blend':saved}
```
Expected: all three parts `manifold_ok True` + `fits_bed True`; the box↔panel intersection ≈ 0; 3 STL written; `enclosure.blend` saved.

- [ ] **Step 5: Write `hardware/3d/README.md`** — print settings (PETG, ≥3 walls, ~25–40% infill, supports note for overhangs); the **heat-set insert** size (M3 → Ø4.0 bore) + install note; the **hardware BOM** — **4× FEMALE-THREADED M3 ceramic standoffs** (the plate-frame blind bosses require female-threaded standoffs that seat on the boss top; the M3 screw threads UP into the plate, NOT down through the frame — a plain spacer needing a bottom nut will NOT work) + M3 steel screws; M3 brass heat-set inserts + screws for the box↔panel joint; rubber feet; the board **rests on the box corner posts** (no board screws). The **assembly order**; and the **thermal-safety note** (ceramic standoffs + 22 mm air gap; nothing plastic touches the plate; re-check once the real plate's temp is known). Note STL is the print output; STEP is an optional FreeCAD follow-up.

- [ ] **Step 6: Commit**

```bash
git add hardware/3d/build_all.py hardware/3d/README.md hardware/3d/enclosure.blend hardware/3d/stl
git commit -m "3d: assembly interference check, STL exports, enclosure.blend, and build README"
```

---

## Self-Review notes (for the executor)

- **Plate spec is parametric (spec §8):** all plate-dependent geometry reads `PARAMS["plate_*"]`; swapping the real plate is a one-file edit + re-run. Don't hardcode.
- **Panel ↔ board coupling (spec §3.3):** `build_panel.py` reads `placement.json` live; if the board is re-placed, re-run the panel. The affine mapping must be documented in the file.
- **Manifold is the hard gate:** boolean ops (esp. EXACT solver) can yield non-manifold geometry — every part task ends on `nonmanifold_edges == 0`. Do not export a non-watertight STL.
- **STEP:** intentionally out of scope (Blender limitation); `.blend` + `.py` are the parametric source. Flagged, not silently dropped.
