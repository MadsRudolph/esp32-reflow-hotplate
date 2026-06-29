"""Place all schematic components for the ESP32 reflow hotplate (Task 3).

PLACEMENT ONLY: every component from the design-of-record is emitted as a
KiCad-10 ``(symbol ...)`` block with a fresh UUID. No wires, no net labels,
no power-flag symbols -- those are added in the wiring tasks (4-6).

Reference designators follow ``hardware/kicad/net_contract.json`` (the
authoritative design-of-record). Where the task brief and the contract
disagree, the contract wins:

    contract                       brief said      ->  used here
    SW1 = rotary encoder           RV1             ->  SW1
    SW2 = start push button        SW1             ->  SW2
    D1  = status LED               D3              ->  D1
    (TVS diode, brief D1)          D1              ->  D3  (D1 taken by LED)

The module symbol/footprint library is registered under the nickname
``reflow`` (Task 2), not ``modules``.

The energy_system symbol library is empty (no LM2576/LM7812 symbols), so the
regulators use stock KiCad symbols:
    U2  Regulator_Switching:LM2576T-5   (5-pin TO-220 buck)
    U3  Regulator_Linear:LM7812_TO220   (3-pin TO-220 linear)
There is NO separate 3V3 regulator (3V3 comes from the ESP32 onboard LDO).

KiCad-10 file format (version 20250114, generator_version 10.0); matches the
header that Task 1 wrote into reflow.kicad_sch.
"""

import shutil
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # hardware/kicad
SCH = ROOT / "reflow.kicad_sch"
BACKUP = ROOT / f"reflow.kicad_sch.bak_{datetime.now():%Y%m%d_%H%M%S}"

# Project UUID taken from the existing reflow.kicad_sch header.
PROJ_UUID = "a1b2c3d4-0001-0001-0001-000000000001"

# Pin identifiers per lib_id. KiCad requires a (pin "<id>" ...) instance entry
# for every pin of the symbol; the identifier must match the library symbol's
# pin numbers exactly (note RotaryEncoder uses A/B/C/S1/S2, not 1..5).
PIN_IDS = {
    "reflow:ESP32_DevKitV1": [str(i) for i in range(1, 31)],
    "reflow:MAX31855_Module": ["1", "2", "3", "4", "5"],
    "reflow:OLED_SSD1306_I2C": ["1", "2", "3", "4"],
    "Regulator_Switching:LM2576T-5": ["1", "2", "3", "4", "5"],
    "Regulator_Linear:LM7812_TO220": ["1", "2", "3"],
    "Transistor_FET:Q_NMOS_GDS": ["1", "2", "3"],
    "Device:RotaryEncoder_Switch": ["A", "B", "C", "S1", "S2"],
    "Switch:SW_Push": ["1", "2"],
    "Device:D_TVS": ["1", "2"],
    "Device:D_Schottky": ["1", "2"],
    "Device:LED": ["1", "2"],
    "Device:Fuse": ["1", "2"],
    "Device:L": ["1", "2"],
    "Device:R": ["1", "2"],
    "Device:C": ["1", "2"],
    "TerminalBlock:TerminalBlock_bornier-2_P5.08mm": ["1", "2"],
}

# -----------------------------------------------------------------------------
# Component placement: (ref, lib_id, value, footprint, x, y, angle)
# A3 sheet = 420 x 297 mm. Logical zones:
#   - Controller centre        : A1 ESP32 (~x=150, y=150)
#   - Power section top-left   : J1, F1, D3(TVS), U2 buck + L1/D2, U3 linear
#   - Power corner bottom-right: Q1 heater MOSFET, Q2/Q3 gate-drive, J2 heater
#   - UI right edge            : J3 (MAX31855), J4 (OLED), SW1 enc, SW2 btn, D1 LED
# Decoupling caps / gate-drive R+C placed near their consumers (values TBD in
# wiring tasks).
# -----------------------------------------------------------------------------
COMPONENTS = [
    # ---- Controller (centre) ----
    ("A1", "reflow:ESP32_DevKitV1", "ESP32-DevKitV1",
     "reflow:ESP32_DevKitV1_2x15_P2.54_W22.86", 150, 150, 0),

    # ---- Power input + protection (top-left) ----
    ("J1", "TerminalBlock:TerminalBlock_bornier-2_P5.08mm", "24V_IN",
     "TerminalBlock:TerminalBlock_bornier-2_P5.08mm", 30, 40, 0),
    ("F1", "Device:Fuse", "15A",
     "Fuse:Fuseholder_Cylinder-5x20mm_Schurter_FAB_0031.8201_Horizontal_Closed", 55, 40, 0),
    ("D3", "Device:D_TVS", "SMBJ26A",
     "Diode_THT:D_DO-201AD_P15.24mm_Horizontal", 75, 50, 0),

    # ---- 24V -> 5V buck (LM2576) (top-left) ----
    ("U2", "Regulator_Switching:LM2576T-5", "LM2576-5.0",
     "energy_system:TO-220-3_Vertical_LaserPads", 40, 80, 0),
    ("L1", "Device:L", "100uH",
     "Inductor_THT:L_Toroid_Vertical_L20.0mm_D7.0mm_P10.16mm", 70, 75, 0),
    ("D2", "Device:D_Schottky", "1N5817",
     "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", 70, 95, 0),
    ("C1", "Device:C", "100uF",
     "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", 25, 95, 0),
    ("C2", "Device:C", "1000uF",
     "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", 90, 90, 0),

    # ---- 24V -> 12V linear (LM7812) gate-drive rail (left) ----
    ("U3", "Regulator_Linear:LM7812_TO220", "LM7812",
     "energy_system:TO-220-3_Vertical_LaserPads", 40, 120, 0),
    ("C3", "Device:C", "100nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 25, 135, 0),
    ("C4", "Device:C", "10uF",
     "Capacitor_THT:CP_Radial_D5.0mm_P2.50mm", 60, 135, 0),

    # ---- Heater power stage (bottom-right corner) ----
    ("Q1", "Transistor_FET:Q_NMOS_GDS", "IRFS4710",
     "energy_system:TO-220-3_Vertical_LaserPads_GDS", 330, 220, 0),
    ("J2", "TerminalBlock:TerminalBlock_bornier-2_P5.08mm", "HEATER",
     "TerminalBlock:TerminalBlock_bornier-2_P5.08mm", 380, 200, 0),

    # ---- Two-stage BS170 gate drive (bottom-right) ----
    ("Q2", "Transistor_FET:Q_NMOS_GDS", "BS170",
     "Package_TO_SOT_THT:TO-92_Inline", 270, 230, 0),
    ("Q3", "Transistor_FET:Q_NMOS_GDS", "BS170",
     "Package_TO_SOT_THT:TO-92_Inline", 300, 230, 0),
    ("R1", "Device:R", "1k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 255, 215, 0),
    ("R2", "Device:R", "1k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 285, 215, 0),
    ("R3", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 315, 215, 0),
    ("R4", "Device:R", "100",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 315, 245, 0),
    ("R5", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 345, 245, 0),

    # ---- Thermocouple header (UI / right) ----
    ("J3", "reflow:MAX31855_Module", "MAX31855",
     "reflow:Header_1x05_P2.54", 250, 90, 0),

    # ---- OLED header (UI / right) ----
    ("J4", "reflow:OLED_SSD1306_I2C", "OLED",
     "reflow:Header_1x04_P2.54", 250, 130, 0),

    # ---- Rotary encoder + start button + status LED (UI / right edge) ----
    ("SW1", "Device:RotaryEncoder_Switch", "ENC",
     "Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch", 330, 90, 0),
    ("SW2", "Switch:SW_Push", "START",
     "Button_Switch_THT:SW_PUSH_6mm", 330, 130, 0),
    ("D1", "Device:LED", "STATUS",
     "LED_THT:LED_D5.0mm", 380, 130, 0),
    ("R6", "Device:R", "330",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 365, 130, 0),

    # ---- I2C pull-ups + encoder/button debounce + misc passives ----
    ("R7", "Device:R", "4.7k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 210, 120, 0),
    ("R8", "Device:R", "4.7k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 210, 135, 0),
    ("R9", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 300, 75, 0),
    ("R10", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 315, 75, 0),
    ("R11", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 330, 75, 0),
    ("R12", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 300, 150, 0),
    ("C5", "Device:C", "100nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 250, 110, 0),
    ("C6", "Device:C", "100nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 250, 150, 0),
    ("C7", "Device:C", "100nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 330, 110, 0),
    ("C8", "Device:C", "100nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 330, 150, 0),
]


def uid() -> str:
    return str(uuid.uuid4())


def pin_ids(lib_id: str):
    if lib_id not in PIN_IDS:
        raise SystemExit(f"Unknown lib_id (no pin map): {lib_id}")
    return PIN_IDS[lib_id]


def render_symbol(ref, lib_id, value, footprint, x, y, angle) -> str:
    pin_block = "\n".join(
        f'\t\t(pin "{p}" (uuid "{uid()}"))' for p in pin_ids(lib_id)
    )
    return f'''\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {x} {y} {angle})
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(fields_autoplaced yes)
\t\t(uuid "{uid()}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {x + 5.08} {y - 2.54} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(justify left)
\t\t\t)
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {x + 5.08} {y + 2.54} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(justify left)
\t\t\t)
\t\t)
\t\t(property "Footprint" "{footprint}"
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Datasheet" "~"
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Description" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
{pin_block}
\t\t(instances
\t\t\t(project "reflow"
\t\t\t\t(path "/{PROJ_UUID}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)'''


HEADER = '''(kicad_sch
\t(version 20250114)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid "a1b2c3d4-0001-0001-0001-000000000001")
\t(paper "A3")
\t(lib_symbols)'''

FOOTER = '''\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
'''


def main() -> None:
    if SCH.exists():
        shutil.copy2(SCH, BACKUP)
        print(f"Backed up to {BACKUP.name}")

    parts = [HEADER]
    for ref, lib_id, value, footprint, x, y, angle in COMPONENTS:
        parts.append(render_symbol(ref, lib_id, value, footprint, x, y, angle))
    parts.append(FOOTER)

    SCH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {len(COMPONENTS)} components to {SCH.name}")


if __name__ == "__main__":
    main()
