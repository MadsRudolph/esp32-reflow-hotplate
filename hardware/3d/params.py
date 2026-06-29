PARAMS = {
    "plate_x": 100.0, "plate_y": 100.0, "plate_t": 5.0,
    "plate_hole_inset": 6.0, "plate_hole_clear_d": 3.4,   # M3 clearance
    "standoff_h": 22.0, "standoff_boss_d": 9.0,
    "insert_bore_d": 4.0, "insert_bore_depth": 6.0, "insert_boss_wall": 2.0,
    "wall": 2.4, "floor": 2.4,
    # Box sized to hold the 104x104 board FLAT (inner = pcb + 2*board_clear): outer ~113.
    "box_x": 113.0, "box_y": 113.0, "box_h": 30.0,        # electronics box outer envelope
    "board_clear": 2.0,                                    # gap: board edge -> inner wall
    "board_post_xy": 48.0,                                 # corner support-post offset from centre (board rests on posts; no screw holes in the board)
    "board_post_d": 6.0, "board_post_h": 10.0,             # lift board off floor for bottom lead tails
    "panel_t": 3.0,
    "pcb_x": 104.0, "pcb_y": 104.0,                        # control board outline
    "vent_slot_w": 2.5, "vent_slot_l": 18.0,
    "bed_max": 220.0,
    "encoder_shaft_d": 7.5, "button_d": 12.5, "led_d": 5.5, "oled_win_x": 26.0, "oled_win_y": 15.0,
}
