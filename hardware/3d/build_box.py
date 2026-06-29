# build_box.py -- Task 3: electronics box for the ESP32 reflow hotplate.
#
# Coordinate convention (origin = centre of the box floor at z=0):
#   x in [-OUT_X/2, +OUT_X/2], y in [-OUT_Y/2, +OUT_Y/2], floor sits on z=0..floor.
#   box_x/box_y/box_h are treated as the INNER cavity envelope; the outer shell
#   is the cavity plus a `wall` on each side and a `floor` underneath.
#
# Contract for Tasks 4 (panel) & 5 (lid):
#   - lid_insert_centers()  : 4 (x,y) on the top rim, inset INSET_RIM from outer corners.
#   - panel_insert_centers(): 2 (x,y) on the FRONT (-Y) face, at z = front bore height.
#   - pcb_boss_centers()    : 4 (x,y) PCB standoff bosses on the floor.
# These are deterministic (computed from PARAMS) so downstream tasks can align holes.

import bpy
import math

# --- Derived dimensions -------------------------------------------------------
WALL  = PARAMS["wall"]
FLOOR = PARAMS["floor"]
IN_X  = PARAMS["box_x"]          # inner cavity X = 90
IN_Y  = PARAMS["box_y"]          # inner cavity Y = 70
IN_H  = PARAMS["box_h"]          # inner cavity height = 40
OUT_X = IN_X + 2 * WALL          # 94.8
OUT_Y = IN_Y + 2 * WALL          # 74.8
OUT_H = IN_H + FLOOR             # 42.4 total outer height

BORE_D     = PARAMS["insert_bore_d"]      # 4.0 (M3 heat-set insert pilot)
BORE_DEPTH = PARAMS["insert_bore_depth"]  # 6.0
BOSS_WALL  = PARAMS["insert_boss_wall"]   # 2.0 wall around a bore
BOSS_D     = BORE_D + 2 * BOSS_WALL       # 8.0 outer Ø of an insert boss

# PCB standoff bosses: the 104x104 board is larger than the 94.8x74.8 outer
# footprint, so it overhangs the box on all sides and is supported on its own
# corner bosses INSET from the inner walls. We choose a boss-pitch rectangle of
# PCB_PITCH_X x PCB_PITCH_Y centred on the floor; the inset from each inner wall
# is (IN/2 - PITCH/2). With a 10 mm inset the bosses sit on a 70x50 rectangle.
PCB_INSET     = 10.0
PCB_PITCH_X   = IN_X - 2 * PCB_INSET      # 70
PCB_PITCH_Y   = IN_Y - 2 * PCB_INSET      # 50
PCB_BOSS_H    = 6.0                        # standoff boss height above the floor
PCB_BOSS_D    = BORE_D + 2 * 2.0          # 8.0 outer Ø

# Lid rim inserts: 4 corners, inset from the OUTER corner so the boss body fits
# within the wall ring.
INSET_RIM     = 6.0
RIM_BORE_DEPTH = BORE_DEPTH

# Panel (front, -Y face) inserts: 2 horizontally-spaced bores into the front
# wall, drilled along +Y, at a height centred on the cavity.
PANEL_SPACING = 60.0                       # centre-to-centre, symmetric about x=0
PANEL_Z       = FLOOR + IN_H * 0.5         # mid-height of the cavity

# Vent slots: a row of 4 slots cut THROUGH the floor, offset to +X half where
# the regulators + MOSFET heatsink sit.
VENT_W  = PARAMS["vent_slot_w"]            # 2.5
VENT_L  = PARAMS["vent_slot_l"]            # 18.0
VENT_N  = 4
VENT_PITCH = 6.0                           # centre-to-centre across the row
VENT_CX = IN_X * 0.22                      # row centred toward +X side of floor
VENT_CY = 0.0

# Terminal opening: rectangular cut in the +X wall for the J1/J2 bornier bodies.
TERM_W  = 30.0                             # width along Y
TERM_H  = 12.0                             # height along Z
TERM_Z0 = FLOOR + 1.0                      # bottom of opening, just above floor


# --- Contract functions -------------------------------------------------------
def pcb_boss_centers():
    hx, hy = PCB_PITCH_X / 2.0, PCB_PITCH_Y / 2.0
    return [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]

def lid_insert_centers():
    hx = OUT_X / 2.0 - INSET_RIM
    hy = OUT_Y / 2.0 - INSET_RIM
    return [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]

def panel_insert_centers():
    h = PANEL_SPACING / 2.0
    return [(-h, -OUT_Y / 2.0), (h, -OUT_Y / 2.0)]


# --- Build --------------------------------------------------------------------
def build():
    fresh_scene()

    # 1) Shell = outer box minus inner cavity (open top).
    outer = add_box("box", OUT_X, OUT_Y, OUT_H, loc=(0, 0, OUT_H / 2.0))
    # Inner cavity: starts at z=FLOOR, open at the top (extend above the rim).
    cav_h = IN_H + 10.0
    cavity = add_box("cavity", IN_X, IN_Y, cav_h,
                     loc=(0, 0, FLOOR + cav_h / 2.0))
    boolean(outer, cavity, 'DIFFERENCE')

    # 2) PCB standoff bosses on the floor, each with a blind bore on top.
    for (x, y) in pcb_boss_centers():
        boss = add_cyl("pcb_boss", PCB_BOSS_D, PCB_BOSS_H,
                       loc=(x, y, FLOOR + PCB_BOSS_H / 2.0))
        boolean(outer, boss, 'UNION')
    for (x, y) in pcb_boss_centers():
        top_z = FLOOR + PCB_BOSS_H
        bore = add_cyl("pcb_bore", BORE_D, BORE_DEPTH + 0.2,
                       loc=(x, y, top_z - BORE_DEPTH / 2.0 + 0.1))
        boolean(outer, bore, 'DIFFERENCE')

    # 3) Lid rim insert bosses (4 corners) at the top rim, with blind bores
    #    drilled DOWN from the rim.
    rim_z = OUT_H
    boss_h = RIM_BORE_DEPTH + 2.0
    for (x, y) in lid_insert_centers():
        boss = add_cyl("rim_boss", BOSS_D, boss_h,
                       loc=(x, y, rim_z - boss_h / 2.0))
        boolean(outer, boss, 'UNION')
    for (x, y) in lid_insert_centers():
        bore = add_cyl("rim_bore", BORE_D, RIM_BORE_DEPTH + 0.2,
                       loc=(x, y, rim_z - RIM_BORE_DEPTH / 2.0 + 0.1))
        boolean(outer, bore, 'DIFFERENCE')

    # 4) Panel (front -Y) insert bosses with bores drilled along +Y into the wall.
    #    Build the boss as a cylinder whose axis is along Y, hugging the inner
    #    face of the front wall.
    boss_len = RIM_BORE_DEPTH + 2.0
    inner_front_y = -IN_Y / 2.0           # inner face of front wall
    for (x, _y) in panel_insert_centers():
        boss = add_cyl("panel_boss", BOSS_D, boss_len,
                       loc=(x, inner_front_y + boss_len / 2.0, PANEL_Z))
        boss.rotation_euler[0] = math.radians(90)  # axis -> Y
        bpy.context.view_layer.objects.active = boss
        bpy.ops.object.transform_apply(rotation=True)
        boolean(outer, boss, 'UNION')
    for (x, _y) in panel_insert_centers():
        # bore from the outer front face inward
        outer_front_y = -OUT_Y / 2.0
        bore = add_cyl("panel_bore", BORE_D, RIM_BORE_DEPTH + 0.2,
                       loc=(x, outer_front_y + (RIM_BORE_DEPTH) / 2.0 - 0.1, PANEL_Z))
        bore.rotation_euler[0] = math.radians(90)
        bpy.context.view_layer.objects.active = bore
        bpy.ops.object.transform_apply(rotation=True)
        boolean(outer, bore, 'DIFFERENCE')

    # 5) Vent slots: a row of through-floor slots toward +X.
    start = -((VENT_N - 1) * VENT_PITCH) / 2.0
    for i in range(VENT_N):
        sx = VENT_CX + start + i * VENT_PITCH
        slot = add_box("vent", VENT_W, VENT_L, FLOOR + 1.0,
                       loc=(sx, VENT_CY, FLOOR / 2.0))
        boolean(outer, slot, 'DIFFERENCE')

    # 6) Terminal opening: rectangular cut through the +X wall.
    term = add_box("term", WALL + 2.0, TERM_W, TERM_H,
                   loc=(OUT_X / 2.0, 0.0, TERM_Z0 + TERM_H / 2.0))
    boolean(outer, term, 'DIFFERENCE')

    outer.name = "box"
    return outer
