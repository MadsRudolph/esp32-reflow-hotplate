# build_all.py -- Task 5: assembly, interference check, STL exports + enclosure.blend.
#
# Places all THREE parts (plate_frame, box, panel) in ONE scene at their
# assembled positions, runs a box<->panel interference check (boolean INTERSECT
# volume must be ~0 -- the walls must not pass through each other; only the rim
# screw bosses meet), re-exports all three STL into stl/, and saves the .blend.
#
# Multi-part-in-one-scene approach
# --------------------------------
# Each part's build() calls fresh_scene() (which selects-all + deletes) at its
# very start. To keep three parts alive in one scene we wrap the build sequence:
#   1) fresh_scene() once up front.
#   2) Temporarily neutralise the module-level `fresh_scene` to a no-op while we
#      drive the three builders, so a later build() cannot wipe earlier parts.
#   3) After each build() returns its object, rename it uniquely and translate it
#      to its assembled position so the next builder's geometry never overlaps it
#      in object terms.
#   4) Restore the real fresh_scene at the end.
#
# Assembled positions (origin = box floor centre at z=0):
#   - box     : at origin.
#   - panel   : translated UP by box_h so it sits on the box top rim (z=box_h).
#   - plate_frame : translated +X beside the box (box_x + 30 clearance).
#
# Requires params.py, build_common.py, build_box.py, build_panel.py,
# build_plate_frame.py to be exec'able from the same directory (this file
# exec's them into its own globals so PARAMS + helpers + contract fns are live).

import bpy, bmesh, os

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
    else r"C:/Users/Mads2/Documents/Projects/esp32-reflow-hotplate/hardware/3d"


def _exec_dep(name):
    """Exec a sibling build script into THIS module's globals (shared scope)."""
    with open(os.path.join(_HERE, name), "r", encoding="utf-8") as f:
        exec(compile(f.read(), name, "exec"), globals())


# Pull in PARAMS + helpers + the three builders' module-level names.
_exec_dep("params.py")            # -> PARAMS
_exec_dep("build_common.py")      # -> fresh_scene, add_box, add_cyl, boolean, verify, export_stl, ...
# The three builders each define a build(); exec them via dedicated namespaces so
# their build() functions don't clobber each other. We load their SOURCE and
# compile a renamed build for each.
def _load_builder(name, fn_alias):
    """Exec a builder file but expose its build() under a unique alias.

    The builder files reference PARAMS / helpers / contract fns from globals(),
    so we exec into globals() but capture the freshly-defined build() under an
    alias before the next builder overwrites it.
    """
    with open(os.path.join(_HERE, name), "r", encoding="utf-8") as f:
        src = f.read()
    exec(compile(src, name, "exec"), globals())
    globals()[fn_alias] = globals()["build"]


_load_builder("build_plate_frame.py", "_build_plate_frame")
_load_builder("build_box.py", "_build_box")          # also defines top_insert_centers(), board_post_centers()
_load_builder("build_panel.py", "_build_panel")      # needs top_insert_centers() in globals (provided above)


def _mesh_volume(obj):
    """Signed/closed-mesh volume in mm^3 from the object's evaluated mesh (world space)."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    bm.transform(obj.matrix_world)
    vol = abs(bm.calc_volume(signed=True))
    bm.free()
    return vol


def _intersect_volume(a, b):
    """Volume of the boolean INTERSECT of two solids (mm^3). Temp object deleted."""
    # Duplicate `a` and intersect with `b`; measure; delete the temp.
    dup = a.copy()
    dup.data = a.data.copy()
    dup.name = a.name + "_isect_tmp"
    bpy.context.collection.objects.link(dup)
    bpy.context.view_layer.objects.active = dup

    m = dup.modifiers.new("isect", 'BOOLEAN')
    m.operation = 'INTERSECT'
    m.object = b
    m.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=m.name)

    vol = _mesh_volume(dup)
    bpy.data.objects.remove(dup, do_unlink=True)
    return vol


def build_all():
    P = PARAMS

    # 1) Clean slate.
    fresh_scene()

    box_x = P["box_x"]
    box_h = P["box_h"]

    # 2) Neutralise fresh_scene so the part builders can't wipe earlier parts,
    #    then build + position each part. Restore afterwards.
    import builtins  # noqa: F401 (kept explicit for clarity)
    real_fresh = globals()["fresh_scene"]
    globals()["fresh_scene"] = lambda: None
    try:
        # --- box at origin -------------------------------------------------
        box = _build_box()
        box.name = "box"
        box.location = (0.0, 0.0, 0.0)

        # --- panel on the box top (z = box_h) ------------------------------
        panel = _build_panel()
        panel.name = "panel"
        panel.location = (0.0, 0.0, box_h)

        # --- plate frame beside the box, offset +X -------------------------
        plate_frame = _build_plate_frame()
        plate_frame.name = "plate_frame"
        plate_frame.location = (box_x + 30.0, 0.0, 0.0)
    finally:
        globals()["fresh_scene"] = real_fresh

    bpy.context.view_layer.update()

    # 3) Verify each part (manifold + fits bed). max_xy = bed_max.
    bed = P["bed_max"]
    r_plate = verify(plate_frame, bed)
    r_box = verify(box, bed)
    r_panel = verify(panel, bed)

    # 4) Interference check for the mating pair box <-> panel.
    #    With the panel translated to z=box_h it sits ON the rim. The only
    #    permitted contact is the rim/screw bosses meeting the panel underside;
    #    the box walls must NOT pass up through the panel body. Intersect volume
    #    should be ~0.
    isect_box_panel = _intersect_volume(box, panel)

    # 5) Export all three STL into stl/.
    stl_dir = os.path.join(_HERE, "stl")
    stl_plate = os.path.join(stl_dir, "plate_frame.stl")
    stl_box = os.path.join(stl_dir, "box.stl")
    stl_panel = os.path.join(stl_dir, "panel.stl")
    export_stl(plate_frame, stl_plate)
    export_stl(box, stl_box)
    export_stl(panel, stl_panel)

    # 6) Save the assembled .blend.
    blend_path = os.path.join(_HERE, "enclosure.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    return {
        "plate_frame": r_plate,
        "box": r_box,
        "panel": r_panel,
        "interference": {"box_panel": round(isect_box_panel, 4)},
        "stls": [stl_plate.replace("\\", "/"),
                 stl_box.replace("\\", "/"),
                 stl_panel.replace("\\", "/")],
        "blend": blend_path.replace("\\", "/"),
    }
