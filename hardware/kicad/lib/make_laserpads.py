#!/usr/bin/env python3
"""Laver _LaserPads-varianter af TO-220/TO-126 i energy_system.pretty:
pad-bredden klemmes til 1.7 mm saa luften ved 2.54 mm pitch bliver 0.84 mm
(fiberlaser-guidens 0.8 mm clearance-regel). Hoejde/drill uaendret."""
import re
from pathlib import Path

SRC = Path(r"C:\Program Files\KiCad\9.0\share\kicad\footprints\Package_TO_SOT_THT.pretty")
DST = Path(__file__).parent / "energy_system.pretty"

for name in ["TO-220-3_Vertical", "TO-126-3_Vertical"]:
    txt = (SRC / f"{name}.kicad_mod").read_text(encoding="utf-8")

    def shrink(m):
        w, h = float(m.group(1)), float(m.group(2))
        return f"(size 1.7 {h})" if w > 1.7 else m.group(0)

    new = re.sub(r"\(size ([\d.]+) ([\d.]+)\)", shrink, txt)
    new = new.replace(f'(footprint "{name}"', f'(footprint "{name}_LaserPads"', 1)
    out = DST / f"{name}_LaserPads.kicad_mod"
    out.write_text(new, encoding="utf-8")
    print("wrote", out)
