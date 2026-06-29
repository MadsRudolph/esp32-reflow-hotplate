# Parametric plate frame for the ESP32 reflow hotplate.
# Holds the ~250 C plate on ceramic standoffs over an open air gap.
# All dimensions come from PARAMS (see params.py). Relies on build_common.py
# helpers: fresh_scene, add_box, add_cyl, boolean, verify, export_stl.
#
# Geometry summary:
#   - Footprint plate_x+2*wall x plate_y+2*wall.
#   - A solid perimeter ring (outer box minus inner box) with a floor of
#     thickness `floor`. The centre is OPEN (air gap) so radiant/conductive
#     heat from the plate does not soak the frame.
#   - 4 standoff bosses (Ø standoff_boss_d, height standoff_h) at the plate
#     corner pattern, each bored Ø plate_hole_clear_d (M3 clearance) all the
#     way through. The ceramic standoff seats on the boss; the steel M3 passes
#     through into the plate above.
#   - A wire channel notch (vent_slot_w wide) on the electronics-facing edge.
#   - Short feet under the corners.
#
# `hole_centers()` returns the 4 boss/hole (x, y) tuples.
# `build()` constructs and returns the single manifold object `plate_frame`.

P = PARAMS

# Frame geometry derived constants
_FOOT_X = P["plate_x"] + 2 * P["wall"]   # outer footprint X
_FOOT_Y = P["plate_y"] + 2 * P["wall"]   # outer footprint Y
# Ring wall width: thick enough that the corner bosses (at the inset pattern)
# merge into the perimeter ring to form one solid. The bosses sit at
# plate_hole_inset from the plate edge; make the ring reach a touch past them.
_RING_W = P["plate_hole_inset"] + P["standoff_boss_d"] / 2.0 + P["wall"]

_FEET_D = P["standoff_boss_d"] + 2.0     # foot diameter (a bit wider than boss)
_FEET_H = 3.0                            # foot height below the frame floor


def hole_centers():
    """4 standoff-boss centres = plate corner pattern (matches params)."""
    hx = P["plate_x"] / 2.0 - P["plate_hole_inset"]
    hy = P["plate_y"] / 2.0 - P["plate_hole_inset"]
    return [(+hx, +hy), (-hx, +hy), (-hx, -hy), (+hx, -hy)]


def build():
    fresh_scene()

    # --- Perimeter ring ---------------------------------------------------
    # The ring spans the full frame height = floor + standoff_h so the bosses
    # are fully embedded in / flush with a solid wall, guaranteeing one solid.
    ring_h = P["floor"] + P["standoff_h"]
    z_mid = ring_h / 2.0

    outer = add_box("frame_outer", _FOOT_X, _FOOT_Y, ring_h, loc=(0, 0, z_mid))

    # Inner cavity: open above the floor, leaving `floor` at the bottom and
    # `_RING_W` of wall on each side. The cut starts at z = floor and goes up
    # past the top so it is a clean through-cut for the upper portion.
    inner_x = _FOOT_X - 2 * _RING_W
    inner_y = _FOOT_Y - 2 * _RING_W
    # Cavity tool: tall enough to clear the top, bottom face at z = floor.
    cav_h = ring_h  # generously tall
    cav_z = P["floor"] + cav_h / 2.0
    cavity = add_box("frame_cavity", inner_x, inner_y, cav_h, loc=(0, 0, cav_z))
    boolean(outer, cavity, 'DIFFERENCE')
    frame = outer

    # --- Standoff bosses --------------------------------------------------
    # Each boss rises from the floor to the full standoff height. They sit on
    # the perimeter ring (inset pattern lands within _RING_W), merging into it.
    for (cx, cy) in hole_centers():
        boss = add_cyl("boss", P["standoff_boss_d"], P["standoff_h"],
                       loc=(cx, cy, P["floor"] + P["standoff_h"] / 2.0))
        boolean(frame, boss, 'UNION')

    # --- Bore the standoff holes (M3 clearance, through) ------------------
    for (cx, cy) in hole_centers():
        bore_h = ring_h + 4.0
        bore = add_cyl("bore", P["plate_hole_clear_d"], bore_h,
                       loc=(cx, cy, ring_h / 2.0))
        boolean(frame, bore, 'DIFFERENCE')

    # --- Wire channel notch on the electronics-facing edge (-Y) -----------
    # A vent_slot_w-wide slot cut through the -Y wall so wiring from the plate
    # can pass to the electronics box below/behind.
    ch_w = P["vent_slot_w"]
    ch_depth = _RING_W + 2.0            # cut fully through the -Y wall
    ch_h = P["standoff_h"]             # channel height (above the floor)
    ch_y = -_FOOT_Y / 2.0 + ch_depth / 2.0 - 1.0
    ch_z = P["floor"] + ch_h / 2.0
    channel = add_box("wire_channel", ch_w, ch_depth, ch_h, loc=(0, ch_y, ch_z))
    boolean(frame, channel, 'DIFFERENCE')

    # --- Feet under the corners -------------------------------------------
    # Short cylindrical feet hanging below the frame floor at each corner,
    # merged into the frame for one solid.
    for (cx, cy) in hole_centers():
        foot = add_cyl("foot", _FEET_D, _FEET_H,
                       loc=(cx, cy, -_FEET_H / 2.0))
        boolean(frame, foot, 'UNION')

    frame.name = "plate_frame"
    frame.location = (0, 0, 0)
    return frame
