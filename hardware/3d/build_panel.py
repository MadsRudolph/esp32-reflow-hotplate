# build_panel.py -- Task 4: top control panel (closes the box + carries controls).
#
# This part replaces the old separate front panel AND lid. It is the TOP COVER
# the user looks down on: a flat PETG plate (box_x x box_y x panel_t = 113x113x3)
# that screws down onto the box top-rim inserts. The 104x104 control board lies
# flat in the box, CENTRED, with its controls pointing UP through this panel.
#
# Coordinate convention (origin = centre of the plate, panel-local):
#   x in [-box_x/2, +box_x/2], y in [-box_y/2, +box_y/2]; plate occupies z=0..panel_t.
#
# AFFINE (board-frame -> panel-frame):
#   The board is centred in the box, so the board's centre (pcb_x/2, pcb_y/2)
#   maps to the panel centre (0, 0). placement.json gives component positions in
#   board frame (origin at board lower-left corner). The map is therefore a pure
#   translation:
#       panel_x = board_x - pcb_x/2      (= board_x - 52.0)
#       panel_y = board_y - pcb_y/2      (= board_y - 52.0)
#
#   Checks (placement.json -> panel coords):
#       SW1 (25.6, 11.1) -> (-26.4, -40.9)   encoder shaft
#       SW2 (41.9,  7.8) -> (-10.1, -44.2)   button
#       D1  (52.7,  7.2) -> (  0.7, -44.8)   LED
#       J4  ( 5.8,  9.6) -> (-46.2, -42.4)   OLED window
#
# Power corner (placement.json _doc: "lower-left"): regulators U2/U3 +
# heater MOSFET Q1 sit at board y~30-70. Mapped through the affine the regulator
# zone lands near panel y~-21..18 in the lower-left quadrant; vent slots go there.
# Vent anchor positions are read live from placement.json (keys U2, U3) so they
# track the board layout automatically; defaults [42.5,30.3]/[58.4,30.3] are used
# as fallback only if a key is absent.
#
# Requires build_common.py, params.py and build_box.py exec'd first (helpers,
# PARAMS, and top_insert_centers() in scope).

import bpy, json, os

P = PARAMS

# placement.json lives at hardware/kicad/placement.json. This file is at
# hardware/3d/build_panel.py, so go up one and across.
_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
    else r"C:/Users/Mads2/Documents/Projects/esp32-reflow-hotplate/hardware/3d"
_PLACEMENT = os.path.normpath(os.path.join(_HERE, "..", "kicad", "placement.json"))


def _load_placement():
    with open(_PLACEMENT, "r", encoding="utf-8") as f:
        return json.load(f)


def _affine(bx, by):
    """Board-frame (x,y) -> panel-frame (x,y): board centre maps to panel centre."""
    return (bx - P["pcb_x"] / 2.0, by - P["pcb_y"] / 2.0)


# --- Contract functions -------------------------------------------------------
def cut_centers():
    """Panel-local (x,y) of the 4 control cut-outs, via the affine on placement.json.

    Returns {ref: (x, y)} for SW1 (encoder), SW2 (button), D1 (LED), J4 (OLED).
    """
    pl = _load_placement()
    out = {}
    for ref in ("SW1", "SW2", "D1", "J4"):
        bx, by, _rot = pl[ref]
        x, y = _affine(bx, by)
        out[ref] = (round(x, 4), round(y, 4))
    return out


def hole_centers():
    """4 M3 clearance-hole centres -- must equal box.top_insert_centers()."""
    return list(top_insert_centers())


# --- Build --------------------------------------------------------------------
def build():
    fresh_scene()

    box_x = P["box_x"]
    box_y = P["box_y"]
    t = P["panel_t"]

    # 1) Plate, top face up. Plate occupies z = 0 .. panel_t.
    plate = add_box("panel", box_x, box_y, t, loc=(0, 0, t / 2.0))

    cut_h = t + 2.0  # cutter taller than plate so booleans punch fully through
    cut_z = t / 2.0

    cuts = cut_centers()

    # 2) Encoder shaft hole at SW1.
    x, y = cuts["SW1"]
    boolean(plate, add_cyl("cut_enc", P["encoder_shaft_d"], cut_h, loc=(x, y, cut_z)),
            'DIFFERENCE')

    # 3) Push-button hole at SW2.
    x, y = cuts["SW2"]
    boolean(plate, add_cyl("cut_btn", P["button_d"], cut_h, loc=(x, y, cut_z)),
            'DIFFERENCE')

    # 4) LED hole at D1.
    x, y = cuts["D1"]
    boolean(plate, add_cyl("cut_led", P["led_d"], cut_h, loc=(x, y, cut_z)),
            'DIFFERENCE')

    # 5) OLED rectangular window at J4. oled_win_x along X, oled_win_y along Y.
    #    J4 rotation must be 0; if it's ever rotated, the window dims need swapping.
    pl_j4_rot = _load_placement()["J4"][2]
    assert pl_j4_rot == 0, (
        f"J4 rotation in placement.json is {pl_j4_rot}° (expected 0). "
        "If J4 is rotated 90°/270° swap oled_win_x and oled_win_y here."
    )
    x, y = cuts["J4"]
    boolean(plate, add_box("cut_oled", P["oled_win_x"], P["oled_win_y"], cut_h,
                           loc=(x, y, cut_z)), 'DIFFERENCE')

    # 6) Vent slots over the regulator/MOSFET (power) zone. U2/U3 positions are
    #    read from placement.json so the vent row tracks the board layout automatically.
    #    Fallback defaults match the current layout if a key is ever absent.
    _pl = _load_placement()
    _u2_bx, _u2_by, _ = _pl.get("U2", [42.5, 30.3, 0])
    _u3_bx, _u3_by, _ = _pl.get("U3", [58.4, 30.3, 0])
    u2x, u2y = _affine(_u2_bx, _u2_by)
    u3x, _u3y = _affine(_u3_bx, _u3_by)
    vw = P["vent_slot_w"]
    vl = P["vent_slot_l"]
    n_vents = 4
    pitch = 6.0
    span = (n_vents - 1) * pitch
    vent_cx = (u2x + u3x) / 2.0  # midpoint of U2..U3 in panel x
    vent_cy = u2y                 # both regulators share the same board y
    for i in range(n_vents):
        vx = vent_cx - span / 2.0 + i * pitch
        boolean(plate, add_box("vent", vw, vl, cut_h, loc=(vx, vent_cy, cut_z)),
                'DIFFERENCE')

    # 7) 4 M3 clearance holes at the box top-rim insert centres, so the panel
    #    screws DOWN into the box. Must equal top_insert_centers().
    cd = P["plate_hole_clear_d"]
    for (x, y) in hole_centers():
        boolean(plate, add_cyl("scr", cd, cut_h, loc=(x, y, cut_z)), 'DIFFERENCE')

    plate.name = "panel"
    return plate
