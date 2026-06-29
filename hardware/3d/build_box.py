# build_box.py -- Task 3: electronics box for the ESP32 reflow hotplate (CORRECTED).
#
# Corrected 3-part top-panel architecture. The box is now an outer envelope
# (box_x x box_y x box_h = 113 x 113 x 30) shell with `wall` walls, a `floor`
# floor, and an OPEN top. It is sized to hold the 104x104 control board FLAT
# with `board_clear` gap to the inner walls.
#
# Coordinate convention (origin = centre of the box floor at z=0):
#   x in [-box_x/2, +box_x/2], y in [-box_y/2, +box_y/2]; floor occupies z=0..floor.
#
# The board has NO mounting holes: it simply RESTS on 4 corner support posts
# (Ø board_post_d x board_post_h) at board_post_centers() = (+-board_post_xy,
# +-board_post_xy). Posts are NOT bored -- no screws.
#
# Contract for Task 4 (top control panel), both deterministic (computed from PARAMS):
#   - top_insert_centers()  : 4 (x,y) top-rim insert bosses the panel screws into.
#   - board_post_centers()  : 4 (x,y) board support-post centres (not bored).
#
# Requires build_common.py and params.py exec'd first (helpers + PARAMS in scope).

import bpy

P = PARAMS


# --- Contract functions -------------------------------------------------------
def board_post_centers():
    """4 corner support-post centres (x, y). The board rests on these; not bored."""
    o = P["board_post_xy"]
    return [(-o, -o), (o, -o), (o, o), (-o, o)]


def top_insert_centers():
    """4 top-rim insert-boss centres (x, y), inset from the OUTER wall.

    Inset = insert_boss_wall + insert_bore_d/2 from each outer wall, so the boss
    body fits within the wall ring. Task 4 aligns its screws to these.
    """
    half_x = P["box_x"] / 2.0
    half_y = P["box_y"] / 2.0
    inset = P["insert_boss_wall"] + P["insert_bore_d"] / 2.0
    cx = half_x - inset
    cy = half_y - inset
    return [(-cx, -cy), (cx, -cy), (cx, cy), (-cx, cy)]


# --- Build --------------------------------------------------------------------
def build():
    fresh_scene()

    box_x = P["box_x"]
    box_y = P["box_y"]
    box_h = P["box_h"]
    wall = P["wall"]
    floor = P["floor"]

    # 1) Shell = outer box minus inner cavity (OPEN top). Outer base at z=0.
    outer = add_box("box", box_x, box_y, box_h, loc=(0, 0, box_h / 2.0))

    inner_x = box_x - 2 * wall
    inner_y = box_y - 2 * wall
    inner_h = box_h - floor
    # Cavity starts at z=floor and extends above the rim so the top is fully open.
    cav_h = inner_h + 10.0
    cavity = add_box("cavity", inner_x, inner_y, cav_h,
                     loc=(0, 0, floor + cav_h / 2.0))
    boolean(outer, cavity, 'DIFFERENCE')

    # 2) 4 board support posts (NOT bored): lift the board off the floor for the
    #    bottom lead tails. The board rests on top of these.
    pd = P["board_post_d"]
    ph = P["board_post_h"]
    for (x, y) in board_post_centers():
        post = add_cyl("board_post", pd, ph, loc=(x, y, floor + ph / 2.0))
        boolean(outer, post, 'UNION')

    # 3) Vent-slot row in the +Y wall, above the regulator/MOSFET zone. Slots are
    #    narrow in X (vent_slot_w) and tall in Z (vent_slot_l).
    vw = P["vent_slot_w"]
    vl = P["vent_slot_l"]
    n_vents = 4
    pitch = 12.0
    span = (n_vents - 1) * pitch
    vent_z = floor + ph + 2.0 + vl / 2.0     # above board level
    wall_y = box_y / 2.0
    for i in range(n_vents):
        vx = -span / 2.0 + i * pitch
        slot = add_box("vent", vw, wall * 3.0, vl, loc=(vx, wall_y, vent_z))
        boolean(outer, slot, 'DIFFERENCE')

    # 4) Terminal opening: rectangular cut in the -Y wall, near the floor, for
    #    the J1/J2 bornier terminal bodies (~12 mm tall x ~30 mm wide).
    term_w = 30.0
    term_h = 12.0
    term_z = floor + 1.0 + term_h / 2.0
    term = add_box("term", term_w, wall * 3.0, term_h,
                   loc=(0, -box_y / 2.0, term_z))
    boolean(outer, term, 'DIFFERENCE')

    # 5) 4 top-rim insert bosses + bores. Bosses rise from the inner floor up to
    #    the top rim; the top panel screws DOWN into the bores.
    boss_d = P["insert_bore_d"] + 2 * P["insert_boss_wall"]
    bore_d = P["insert_bore_d"]
    bore_depth = P["insert_bore_depth"]
    boss_h = box_h - floor
    boss_z = floor + boss_h / 2.0
    for (x, y) in top_insert_centers():
        boss = add_cyl("top_boss", boss_d, boss_h, loc=(x, y, boss_z))
        boolean(outer, boss, 'UNION')
    for (x, y) in top_insert_centers():
        bore = add_cyl("top_bore", bore_d, bore_depth + 0.2,
                       loc=(x, y, box_h - bore_depth / 2.0 + 0.1))
        boolean(outer, bore, 'DIFFERENCE')

    outer.name = "box"
    return outer
