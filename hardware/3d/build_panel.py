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
#       J4  ( 5.8,  9.6) -> (-46.2, -42.4)   OLED connector (NOTE: J4 coordinate NOT
#                                              used for the OLED window; see below)
#
# OLED WINDOW POSITION NOTE:
#   The SSD1306 OLED module connects to J4 via a short cable (4-wire JST), so the
#   panel window does NOT need to sit above J4's board footprint. The window position
#   is a FREE design choice. The J4 connector sits only 5.8 mm from the board's left
#   edge; centring the 26 mm-wide window on that coordinate would place the window's
#   left edge at -59.2 mm, overhanging the 56.5 mm panel half-width by 2.7 mm and
#   creating an open-sided notch instead of an enclosed window.
#
#   Fix: the OLED window is placed at panel coords (-25.0, 20.0) — upper-left
#   quadrant, clear of the SW1/SW2/D1 control row (which is at y ≈ −41 to −45) and
#   well inside the panel on all four sides:
#       left  -38.0 mm  (panel limit −53.5 mm, margin 15.5 mm)
#       right −12.0 mm  (panel limit +53.5 mm, margin 65.5 mm)
#       bottom 12.5 mm  (panel limit −53.5 mm, margin 66.0 mm)
#       top   27.5 mm   (panel limit +53.5 mm, margin 26.0 mm)
#   Nearest screw hole: (−52.5, 52.5) Ø3.4; gap to window ≥ 12.8 mm (>>2 mm).
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


# OLED window panel-local centre (independent of J4 board coordinate).
# See header note for rationale. The OLED module connects to J4 via a cable,
# so this position is a free design choice constrained only by panel geometry.
_OLED_PANEL_X = -25.0   # mm, panel-local
_OLED_PANEL_Y =  20.0   # mm, panel-local


# --- Contract functions -------------------------------------------------------
def cut_centers():
    """Panel-local (x,y) of the 4 control cut-outs.

    SW1 / SW2 / D1 are driven by placement.json via the affine transform.
    J4 (OLED) uses the fixed panel position _OLED_PANEL_X/_OLED_PANEL_Y
    (independent of the J4 board coordinate — the module is wired via cable).

    Returns {ref: (x, y)} for SW1 (encoder), SW2 (button), D1 (LED), J4 (OLED).
    """
    pl = _load_placement()
    out = {}
    for ref in ("SW1", "SW2", "D1"):
        bx, by, _rot = pl[ref]
        x, y = _affine(bx, by)
        out[ref] = (round(x, 4), round(y, 4))
    # OLED window: fixed inboard position, not tied to J4 board coordinate.
    out["J4"] = (round(_OLED_PANEL_X, 4), round(_OLED_PANEL_Y, 4))
    return out


def hole_centers():
    """4 M3 clearance-hole centres -- must equal box.top_insert_centers()."""
    return list(top_insert_centers())


def _assert_inside_outline():
    """Raise AssertionError if any cut breaches the panel outline minus a margin.

    Checks every circular hole (SW1 encoder, SW2 button, D1 LED, 4 screw holes)
    and the rectangular OLED window against the panel half-extents. This catches
    the open-sided-notch class of bug (where a cut runs off the panel edge) that
    manifold checks cannot detect.

    Margins applied:
      - Control holes (SW1/SW2/D1) and OLED window: 3 mm from each panel edge
        (lim = box/2 - 3). These are free-space cuts that must be well inboard.
      - Screw holes: 1 mm from each panel edge (lim = box/2 - 1). The screw
        bosses are by design near the panel corners (inset = insert_boss_wall +
        insert_bore_d/2 = 4 mm from the outer edge), so they sit within the wall
        zone; a tight physical margin is correct for them.
    """
    box_x = P["box_x"]
    box_y = P["box_y"]
    half_x = box_x / 2.0
    half_y = box_y / 2.0
    margin_cut = 3.0                      # for free-space control cuts and OLED window
    margin_screw = 1.0                    # for corner screw holes (structurally near edge)
    lim_x = half_x - margin_cut          # 53.5 mm for a 113 mm panel
    lim_y = half_y - margin_cut
    lim_x_screw = half_x - margin_screw  # 55.5 mm
    lim_y_screw = half_y - margin_screw

    cuts = cut_centers()
    holes = hole_centers()

    # Circular control holes: check that centre ± radius stays inside ±lim_cut
    circ_checks = [
        ("SW1/encoder", cuts["SW1"], P["encoder_shaft_d"] / 2.0),
        ("SW2/button",  cuts["SW2"], P["button_d"] / 2.0),
        ("D1/LED",      cuts["D1"],  P["led_d"] / 2.0),
    ]
    for label, (cx, cy), r in circ_checks:
        assert cx - r >= -lim_x, (
            f"_assert_inside_outline: {label} left edge {cx - r:.3f} < {-lim_x:.3f}"
        )
        assert cx + r <= lim_x, (
            f"_assert_inside_outline: {label} right edge {cx + r:.3f} > {lim_x:.3f}"
        )
        assert cy - r >= -lim_y, (
            f"_assert_inside_outline: {label} bottom edge {cy - r:.3f} < {-lim_y:.3f}"
        )
        assert cy + r <= lim_y, (
            f"_assert_inside_outline: {label} top edge {cy + r:.3f} > {lim_y:.3f}"
        )

    # Rectangular OLED window: check that centre ± half-extent stays inside ±lim_cut
    ox, oy = cuts["J4"]
    hw_x = P["oled_win_x"] / 2.0
    hw_y = P["oled_win_y"] / 2.0
    assert ox - hw_x >= -lim_x, (
        f"_assert_inside_outline: OLED window left edge {ox - hw_x:.3f} < {-lim_x:.3f}"
    )
    assert ox + hw_x <= lim_x, (
        f"_assert_inside_outline: OLED window right edge {ox + hw_x:.3f} > {lim_x:.3f}"
    )
    assert oy - hw_y >= -lim_y, (
        f"_assert_inside_outline: OLED window bottom edge {oy - hw_y:.3f} < {-lim_y:.3f}"
    )
    assert oy + hw_y <= lim_y, (
        f"_assert_inside_outline: OLED window top edge {oy + hw_y:.3f} > {lim_y:.3f}"
    )

    # Screw holes: designed near corners; use smaller margin (must be within panel)
    screw_r = P["plate_hole_clear_d"] / 2.0
    for i, (hx, hy) in enumerate(holes):
        assert hx - screw_r >= -lim_x_screw, (
            f"_assert_inside_outline: screw[{i}] left edge {hx - screw_r:.3f} < {-lim_x_screw:.3f}"
        )
        assert hx + screw_r <= lim_x_screw, (
            f"_assert_inside_outline: screw[{i}] right edge {hx + screw_r:.3f} > {lim_x_screw:.3f}"
        )
        assert hy - screw_r >= -lim_y_screw, (
            f"_assert_inside_outline: screw[{i}] bottom edge {hy - screw_r:.3f} < {-lim_y_screw:.3f}"
        )
        assert hy + screw_r <= lim_y_screw, (
            f"_assert_inside_outline: screw[{i}] top edge {hy + screw_r:.3f} > {lim_y_screw:.3f}"
        )


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

    # Guard: verify every cut lies fully within the panel outline before building.
    _assert_inside_outline()

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

    # 5) OLED rectangular window. Position is _OLED_PANEL_X/_OLED_PANEL_Y (fixed
    #    inboard coordinates) rather than the J4 board footprint: the SSD1306 module
    #    is wired to J4 via a short cable, so the window is free to sit anywhere on
    #    the panel. The J4 connector coordinate lands near the board's left edge and
    #    would push the window off the panel; see header note for full rationale.
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
