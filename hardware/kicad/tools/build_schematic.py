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

import math
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # hardware/kicad
SCH = ROOT / "reflow.kicad_sch"
BACKUP = ROOT / f"reflow.kicad_sch.bak_{datetime.now():%Y%m%d_%H%M%S}"

# Source symbol libraries, keyed by lib nickname. Used to (a) populate the
# schematic's (lib_symbols) block with real pin geometry + electrical types
# -- without which ERC/connectivity collapses every pin onto the symbol origin
# -- and (b) compute absolute pin endpoints for the Task-4 power wiring.
KICAD_SYMBOL_DIR = Path(r"C:\Program Files\KiCad\10.0\share\kicad\symbols")
LIB_SOURCES = {
    "Device": KICAD_SYMBOL_DIR / "Device.kicad_sym",
    "Regulator_Switching": KICAD_SYMBOL_DIR / "Regulator_Switching.kicad_sym",
    "Regulator_Linear": KICAD_SYMBOL_DIR / "Regulator_Linear.kicad_sym",
    "Switch": KICAD_SYMBOL_DIR / "Switch.kicad_sym",
    "Connector": KICAD_SYMBOL_DIR / "Connector.kicad_sym",
    "Transistor_FET": KICAD_SYMBOL_DIR / "Transistor_FET.kicad_sym",
    "reflow": ROOT / "modules.kicad_sym",
}

# Project UUID taken from the existing reflow.kicad_sch header.
PROJ_UUID = "a1b2c3d4-0001-0001-0001-000000000001"

# Pin identifiers per lib_id. KiCad requires a (pin "<id>" ...) instance entry
# for every pin of the symbol; the identifier must match the library symbol's
# pin numbers exactly (note RotaryEncoder uses A/B/C/S1/S2, not 1..5).
PIN_IDS = {
    "reflow:ESP32_DevKitV1": [str(i) for i in range(1, 31)],
    "reflow:MAX31855_Module": ["1", "2", "3", "4", "5"],
    "reflow:OLED_SSD1306_I2C": ["1", "2", "3", "4"],
    "Regulator_Switching:LM2575BT-ADJ": ["1", "2", "3", "4", "5"],
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
    "Connector:Screw_Terminal_01x02": ["1", "2"],
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
    # Symbol lib_id is Connector:Screw_Terminal_01x02 (a real, resolvable 2-pin
    # screw-terminal symbol); the footprint stays the vendored bornier-2 part.
    # Task 3 had used "TerminalBlock:..." as the symbol lib_id, but no such
    # *symbol* library exists (TerminalBlock is a footprint lib only), so the
    # pins were unresolvable and could not be wired -- fixed here in Task 4.
    ("J1", "Connector:Screw_Terminal_01x02", "24V_IN",
     "TerminalBlock:TerminalBlock_bornier-2_P5.08mm", 30, 40, 0),
    ("F1", "Device:Fuse", "15A",
     "Fuse:Fuseholder_Cylinder-5x20mm_Schurter_FUP_0031.2510_Horizontal_Closed", 55, 40, 0),
    ("D3", "Device:D_TVS", "SMBJ26A",
     "Diode_THT:D_DO-201AD_P15.24mm_Horizontal", 75, 50, 0),

    # ---- 24V -> 5V buck (LM2575-ADJ + feedback divider) (top-left) ----
    # Task 8: the DTU component shop stocks the ADJUSTABLE LM2575 (shop row
    # "IC,Linear,LM2575,Step-Down Adjustable Voltage Switching Regulator"), not
    # the fixed LM2576-5.0. Swapped to LM2575BT-ADJ (KiCad stock symbol; same
    # 5-pin TO-220 pinout 1=Vin 2=Out 3=GND 4=FB 5=ON/OFF as the LM2576T-5) and a
    # +5V feedback divider (R7/R8) sets Vout via Vref=1.23 V. The footprint stays
    # the vendored 5-pin laser-pad part. See docs/electrical-calcs.md §3.
    ("U2", "Regulator_Switching:LM2575BT-ADJ", "LM2575-ADJ",
     "energy_system:TO-220-5_Vertical_LaserPads", 40, 80, 0),
    ("L1", "Device:L", "120uH",
     "Inductor_THT:L_Toroid_Vertical_L26.7mm_W14.0mm_P10.16mm_Pulse_D", 70, 75, 0),
    ("D2", "Device:D_Schottky", "1N5817",
     "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", 70, 95, 0),
    ("C1", "Device:C", "100uF",
     "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", 25, 95, 0),
    ("C2", "Device:C", "1000uF",
     "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", 90, 90, 0),

    # ---- LM2575-ADJ feedback divider (Task 8) ----
    # Vout = Vref*(1 + R7/R8), Vref = 1.23 V.  R7 (top) = 3K09, R8 (bot) = 1K00
    # -> Vout = 1.23 * (1 + 3090/1000) = 1.23 * 4.09 = 5.03 V.  Both E96 values
    # are stocked in the DTU shop (3K09, 1K00).  Divider: +5V - R7 - FB - R8 - GND.
    ("R7", "Device:R", "3k09",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 105, 75, 0),
    ("R8", "Device:R", "1k00",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 105, 90, 0),

    # ---- 24V -> 12V linear (LM7812) gate-drive rail (left) ----
    ("U3", "Regulator_Linear:LM7812_TO220", "LM7812",
     "energy_system:TO-220-3_Vertical_LaserPads", 40, 120, 0),
    # LM7812 datasheet bypass caps (DTU shop: 330n film / 100n ceramic).
    ("C3", "Device:C", "330nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 25, 135, 0),
    ("C4", "Device:C", "100nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 60, 135, 0),

    # ---- Heater power stage (bottom-right corner) ----
    ("Q1", "Transistor_FET:Q_NMOS_GDS", "IRFS4710",
     "energy_system:TO-220-3_Vertical_LaserPads", 330, 220, 0),
    ("J2", "Connector:Screw_Terminal_01x02", "HEATER",
     "TerminalBlock:TerminalBlock_bornier-2_P5.08mm", 380, 200, 0),

    # ---- Two-stage BS170 boot-safe gate drive (bottom-right) ----
    # Gate-drive resistor roles & values per task-5 brief (R1..R6):
    #   R1 100k  Q2.G->GND pulldown (floating logic input => Q2 off)
    #   R2 1k    HEATER_PWM -> Q2.G series
    #   R3 10k   GD_NODE1 -> +12V pull-UP (Q2 off => GD_NODE1 high => Q3 on)
    #   R4 10k   GATE_MAIN -> +12V pull-UP
    #   R5 100R  GATE_MAIN -> Q1.G series gate resistor
    #   R6 10k   Q1.G -> GND gate-source pulldown (belt-and-suspenders)
    ("Q2", "Transistor_FET:Q_NMOS_GDS", "BS170",
     "energy_system:TO-92_Inline_GDS", 270, 230, 0),
    ("Q3", "Transistor_FET:Q_NMOS_GDS", "BS170",
     "energy_system:TO-92_Inline_GDS", 300, 230, 0),
    ("R1", "Device:R", "100k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 255, 215, 0),
    ("R2", "Device:R", "1k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 285, 215, 0),
    ("R3", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 315, 215, 0),
    ("R4", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 315, 245, 0),
    ("R5", "Device:R", "100",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 345, 245, 0),
    ("R6", "Device:R", "10k",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 345, 220, 0),

    # ---- Heater-drain TVS clamp (Task 5; D4) ----
    # SMBJ33A-equivalent THT TVS across HEATER_RET -> GND (cathode at
    # HEATER_RET, anode at GND) to clamp inductive drain transients when Q1
    # switches the heater load. 33 V standoff sits above the 24 V rail with
    # margin and below Q1's Vds(max)=100 V.
    ("D4", "Device:D_TVS", "SMBJ33A",
     "Diode_THT:D_DO-201AD_P15.24mm_Horizontal", 355, 195, 0),

    # ---- Thermocouple header (UI / right) ----
    ("J3", "reflow:MAX31855_Module", "MAX31855",
     "reflow:Header_1x05_P2.54", 250, 90, 0),

    # ---- OLED header (UI / right) ----
    ("J4", "reflow:OLED_SSD1306_I2C", "OLED",
     "reflow:Header_1x04_P2.54", 250, 130, 0),

    # ---- Rotary encoder + start button + status LED (UI / right edge) ----
    ("SW1", "Device:RotaryEncoder_Switch", "ENC",
     "Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm", 330, 90, 0),
    ("SW2", "Switch:SW_Push", "START",
     "Button_Switch_THT:SW_PUSH_6mm", 330, 130, 0),
    ("D1", "Device:LED", "STATUS",
     "LED_THT:LED_D5.0mm", 380, 130, 0),
    # R13 = status-LED current-limit resistor (was R6 in Task-3 placement; R6 is
    # reassigned to the gate-drive pulldown per the Task-5 brief). Wired in Task 6.
    ("R13", "Device:R", "330",
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", 365, 130, 0),

    # ---- Decoupling + encoder debounce caps (Task 6) ----
    # NOTE (Task 6): R7-R12 were orphaned placeholder resistors from the Task-3
    # generic pool (intended as I2C pull-ups / encoder-button pull-ups). They are
    # NOT used by this design -- the SSD1306 OLED module carries its own I2C
    # pull-ups, and the encoder/start-button use the ESP32 internal pull-ups.
    # They have been removed so they do not appear as floating parts. The
    # resistor set is now exactly R1-R6 (gate drive) + R13 (LED).
    #
    # C5 100nF = J3 (MAX31855) VCC->GND decoupling.
    # C6 100nF = J4 (OLED) VCC->GND decoupling.
    # C7 10nF  = encoder A (SW1.A)->GND debounce.
    # C8 10nF  = encoder B (SW1.B)->GND debounce.
    ("C5", "Device:C", "100nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 250, 110, 0),
    ("C6", "Device:C", "100nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 250, 150, 0),
    ("C7", "Device:C", "10nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 345, 100, 0),
    ("C8", "Device:C", "10nF",
     "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 345, 80, 0),
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


# =============================================================================
# Task 4: lib_symbols population + power-net wiring
# =============================================================================
#
# Why lib_symbols must be populated: KiCad resolves pin *positions* and pin
# *electrical types* from the (lib_symbols ...) cache embedded in the .kicad_sch.
# With an empty (lib_symbols) every pin collapses onto the symbol origin and is
# typed "[???, ?]" -- ERC then cannot tell rails apart and net labels cannot
# bind to real pin endpoints (the classic silent-no-net trap). We therefore
# copy each used library symbol body into the cache, resolving `extends`.

_LIB_TEXT_CACHE: dict[str, str] = {}


def _lib_text(lib: str) -> str:
    if lib not in _LIB_TEXT_CACHE:
        _LIB_TEXT_CACHE[lib] = LIB_SOURCES[lib].read_text(encoding="utf-8")
    return _LIB_TEXT_CACHE[lib]


def _find_symbol_block(text: str, name: str) -> str | None:
    """Return the balanced ``(symbol "name" ...)`` s-expression, or None."""
    idx = text.find(f'(symbol "{name}"')
    if idx == -1:
        return None
    depth = 0
    for i in range(idx, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[idx:i + 1]
    return None


def lib_symbol_body(lib: str, name: str) -> str:
    """Self-contained ``(symbol "name" ...)`` body for the lib_symbols cache.

    Resolves ``(extends "parent")`` by splicing the parent's graphic/pin
    sub-symbol units (renamed to the child) onto the child's own properties.
    """
    text = _lib_text(lib)
    block = _find_symbol_block(text, name)
    if block is None:
        raise SystemExit(f"symbol not found: {lib}:{name}")
    m = re.search(r'\(extends\s+"([^"]+)"\)', block)
    if not m:
        return block
    parent = m.group(1)
    pblock = _find_symbol_block(text, parent)
    if pblock is None:
        raise SystemExit(f"parent symbol not found: {lib}:{parent}")
    child_inner = block[block.index(f'"{name}"') + len(name) + 2: block.rindex(")")]
    child_inner = re.sub(r'\s*\(extends\s+"[^"]+"\)', "", child_inner, count=1)
    units = re.findall(
        r'\(symbol\s+"' + re.escape(parent) + r'_\d+_\d+".*?\n\t\t\)',
        pblock, re.DOTALL,
    )
    units = [u.replace(f'"{parent}_', f'"{name}_') for u in units]
    return (
        f'(symbol "{name}"\n'
        + child_inner.rstrip()
        + "\n"
        + "\n".join("\t\t" + u for u in units)
        + "\n\t)"
    )


def parse_pins(lib: str, name: str) -> list[dict]:
    """Pin geometry (number, electrical type, local x/y) -- extends-resolved."""
    text = _lib_text(lib)
    block = _find_symbol_block(text, name)
    m = re.search(r'\(extends\s+"([^"]+)"\)', block) if block else None
    geom = _find_symbol_block(text, m.group(1)) if m else block
    out: list[dict] = []
    i = 0
    while True:
        j = geom.find("(pin ", i)
        if j == -1:
            break
        depth = 0
        k = j
        while k < len(geom):
            if geom[k] == "(":
                depth += 1
            elif geom[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        b = geom[j:k + 1]
        i = k + 1
        head = re.match(r"\(pin\s+(\w+)\s+(\w+)", b)
        at = re.search(r"\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)", b)
        num = re.search(r'\(number\s+"([^"]+)"', b)
        if head and at:
            out.append(dict(num=num.group(1) if num else "?", etype=head.group(1),
                            x=float(at.group(1)), y=float(at.group(2)),
                            ang=float(at.group(3))))
    return out


def pin_endpoint(px, py, sx, sy, sangle):
    """Absolute schematic coords of a pin's connection point.

    Symbol-local Y is up while schematic Y is down, so local Y is negated;
    the result is then rotated by the placement angle and translated to the
    component origin.
    """
    lx, ly = px, -py
    a = math.radians(sangle)
    rx = lx * math.cos(a) - ly * math.sin(a)
    ry = lx * math.sin(a) + ly * math.cos(a)
    return round(sx + rx, 4), round(sy + ry, 4)


# Placement lookup: ref -> (lib_id, x, y, angle), built from COMPONENTS.
PLACEMENT = {c[0]: (c[1], c[4], c[5], c[6]) for c in COMPONENTS}


def endpoint_of(ref: str, pin_num: str):
    """Absolute (x, y) of ``ref`` pin ``pin_num`` using its placed geometry."""
    lib_id, x, y, ang = PLACEMENT[ref]
    lib, name = lib_id.split(":", 1)
    for p in parse_pins(lib, name):
        if p["num"] == pin_num:
            return pin_endpoint(p["x"], p["y"], x, y, ang)
    raise SystemExit(f"pin {pin_num} not found on {ref} ({lib_id})")


def pin_outward(ref: str, pin_num: str):
    """Unit (dx, dy) in schematic space pointing away from the symbol body
    (the direction a wire should leave the pin). Used to route stubs so they
    never collide with an adjacent pin of the same component."""
    lib_id, _x, _y, sang = PLACEMENT[ref]
    lib, name = lib_id.split(":", 1)
    pin = next(p for p in parse_pins(lib, name) if p["num"] == pin_num)
    # In .kicad_sym a pin's (at .. ang) points outward from the body. The pin
    # body extends in (ang+180); so the *outward* direction the wire leaves is
    # (ang+180) in local space. Apply the Y-flip + placement rotation.
    a = math.radians(pin["ang"] + 180)
    lx, ly = math.cos(a), -math.sin(a)            # local outward, Y flipped
    sa = math.radians(sang)
    dx = lx * math.cos(sa) - ly * math.sin(sa)
    dy = lx * math.sin(sa) + ly * math.cos(sa)
    # snap to the dominant axis (pins are always axis-aligned)
    if abs(dx) >= abs(dy):
        return (1.0 if dx > 0 else -1.0), 0.0
    return 0.0, (1.0 if dy > 0 else -1.0)


# -----------------------------------------------------------------------------
# Power-net wiring spec (Task 4 only -- input, protection, both regulators).
#
# Each entry is (net_name, ref, pin_number). A short wire stub is emitted from
# the pin endpoint, with a net label sitting on that stub (a label on a bare
# pin counts as dangling in this project's experience -- it must touch a wire).
# Same-named labels are one net to ERC. PWR_FLAGs (below) give each rail a
# driver so ERC reports no "no-driver" error.
#
# LM2576-5.0 buck (TO-220-5: 1=Vin 2=Out 3=GND 4=FB 5=ON/OFF):
#   Vin=+24V, Out->D2.K & L1.in (local node SW_OUT), GND, FB=+5V, ON/OFF=GND.
#   L1.out=+5V; D2 (1N5817) K=SW_OUT A=GND; C1 100uF +24V/GND; C2 1000uF +5V/GND.
# LM7812 (1=IN 2=GND 3=OUT): IN=+24V GND=GND OUT=+12V; C3 0.33u in, C4 0.1u out.
# Input: J1.1->F1->+24V, J1.2=GND, D3 (TVS) across +24V/GND, J2.1=+24V.
# -----------------------------------------------------------------------------
NET_PINS = [
    # ---- +24V rail ----
    ("+24V", "F1", "2"),    # fuse output -> +24V rail (F1.1 ties to J1.1)
    ("+24V", "U2", "1"),    # LM2576 Vin
    ("+24V", "U3", "1"),    # LM7812 IN
    ("+24V", "J2", "1"),    # heater terminal + (rail tap; J2.2 is HEATER_RET, Task 5)
    ("+24V", "D3", "1"),    # TVS across input: pin1 (A1) on +24V
    ("+24V", "C1", "1"),    # LM2576 input bulk cap, + to +24V
    ("+24V", "C3", "1"),    # LM7812 input cap to +24V

    # ---- J1 input terminal ----
    # J1.1 (24V_IN +) reaches the fuse via a direct wire (PAIR_WIRES); the +24V
    # rail label is placed on the fuse *output* (F1.2) so the fuse is in series.
    ("GND", "J1", "2"),     # 24V_IN -  -> GND

    # ---- 5V buck output side ----
    ("SW_OUT", "U2", "2"),  # LM2576 switching output node
    ("SW_OUT", "D2", "1"),  # catch-diode cathode at switch node
    ("SW_OUT", "L1", "1"),  # inductor input at switch node
    ("+5V", "L1", "2"),     # inductor output = +5V rail
    ("+5V", "C2", "1"),     # output cap + to +5V

    # ---- LM2575-ADJ feedback divider (Task 8): +5V - R7 - VFB - R8 - GND ----
    # The ADJ part senses Vout through a divider into FB (pin 4), unlike the
    # fixed-5.0 part which tied FB straight to +5V.
    ("+5V", "R7", "1"),     # divider top -> +5V (sensed output)
    ("VFB", "R7", "2"),     # R7 bottom = feedback node
    ("VFB", "U2", "4"),     # LM2575 FB pin senses the divided output
    ("VFB", "R8", "1"),     # R8 top = feedback node
    ("GND", "R8", "2"),     # divider bottom -> GND

    # ---- 12V linear output side ----
    ("+12V", "U3", "3"),    # LM7812 OUT = +12V
    ("+12V", "C4", "1"),    # output cap to +12V

    # ---- GND endpoints (input + regulator section only) ----
    ("GND", "U2", "3"),     # LM2576 GND
    ("GND", "U2", "5"),     # ON/OFF tied low -> enabled
    ("GND", "U3", "2"),     # LM7812 GND
    ("GND", "D2", "2"),     # catch-diode anode to GND
    ("GND", "D3", "2"),     # TVS pin2 (A2) to GND
    ("GND", "C1", "2"),     # input bulk cap - to GND
    ("GND", "C2", "2"),     # output cap - to GND
    ("GND", "C3", "2"),     # LM7812 input cap to GND
    ("GND", "C4", "2"),     # LM7812 output cap to GND
]

# Direct pin-to-pin wires for adjacent connections that should be a plain wire
# rather than a named net (the J1.1 -> F1.1 input link).
PAIR_WIRES = [
    (("J1", "1"), ("F1", "1")),
]

# PWR_FLAG placements. Only rails WITHOUT an intrinsic power-output driver need
# a flag: +24V (fed from the input connector, all passive pins) and GND (only
# power-*input* pins). +5V and +12V are already driven by the regulator OUTPUT
# pins (power_out), so a flag there would be a second power_out -> pin_to_pin
# conflict. (net_name, ref, pin) -- flag dropped on that pin's stub endpoint.
PWR_FLAGS = [
    ("+24V", "U2", "1"),
    ("GND", "U2", "3"),
    # +3V3 is sourced by the ESP32 onboard LDO, but the module symbol types its
    # 3V3 pin as power_INPUT (passive consumer), so ERC sees +3V3 as driverless.
    # A PWR_FLAG on the A1.3V3 stub declares the driver (Task 6).
    ("+3V3", "A1", "30"),
    # +5V is driven by the LM2576 output *through* inductor L1, so the rail label
    # sits on L1.2 (a passive pin) rather than a power_out pin -- ERC therefore
    # sees +5V as driverless once a real consumer (A1.VIN) is attached. A PWR_FLAG
    # on the L1.2 (+5V) stub declares the driver. (Surfaced in Task 6 because
    # Task 4 had no +5V consumer connected yet; logically a Task-4 rail.)
    ("+5V", "L1", "2"),
]

# =============================================================================
# Task 5: heater power stage + boot-safe two-stage gate drive (NETS_POWERSTAGE)
# =============================================================================
#
# Q_NMOS_GDS pin map: 1 = Gate, 2 = Drain, 3 = Source (confirmed from the
# library symbol geometry). Same net-label connectivity as Task 4: a short
# outward wire stub per pin with a net label on its far endpoint; identical
# label names form one net.
#
# Non-inverting, boot-safe topology (GPIO high -> heater ON; low/floating/
# unpowered -> heater OFF inherently):
#
#   HEATER_PWM --R2(1k)--> Q2.G          R1(100k) Q2.G -> GND pulldown
#   Q2.S = GND, Q2.D = GD_NODE1          R3(10k)  GD_NODE1 -> +12V pull-UP
#   GD_NODE1 -> Q3.G                     Q3.S = GND
#   Q3.D = GATE_MAIN                     R4(10k)  GATE_MAIN -> +12V pull-UP
#   GATE_MAIN --R5(100R)--> Q1.G         R6(10k)  Q1.G -> GND pulldown
#   Q1.D = HEATER_RET (= J2.2), Q1.S = GND
#   D4 (TVS, cathode=HEATER_RET anode=GND) clamps drain transients
#
# Local (unnamed-by-rail) interconnect nodes are given explicit net labels so
# the series resistors stay in series:
#   Q2_GATE  = R2.2 + Q2.G(1) + R1.1     (logic input side of R2 -> Q2 gate)
#   GD_NODE1 = Q2.D(2) + Q3.G(1) + R3.2  (inter-stage)
#   GATE_MAIN= Q3.D(2) + R4.2 + R5.1     (stage-2 drain / gate rail)
#   Q1_GATE  = R5.2 + Q1.G(1) + R6.1     (gated node at the power MOSFET)
#   HEATER_RET = J2.2 + Q1.D(2) + D4.1
NETS_POWERSTAGE = [
    # ---- Stage 1 inverter (Q2) ----
    ("HEATER_PWM", "R2", "1"),   # gate-drive INPUT side (A1.GPIO25 wired Task 6)
    ("Q2_GATE", "R2", "2"),      # R2 series -> Q2 gate
    ("Q2_GATE", "Q2", "1"),      # Q2 gate
    ("Q2_GATE", "R1", "1"),      # R1 100k pulldown top
    ("GND", "R1", "2"),          # R1 pulldown to GND
    ("GND", "Q2", "3"),          # Q2 source = GND
    ("GD_NODE1", "Q2", "2"),     # Q2 drain = inter-stage node
    ("GD_NODE1", "R3", "2"),     # R3 10k pull-up bottom
    ("+12V", "R3", "1"),         # R3 pull-up to +12V

    # ---- Stage 2 inverter (Q3) ----
    ("GD_NODE1", "Q3", "1"),     # GD_NODE1 -> Q3 gate
    ("GND", "Q3", "3"),          # Q3 source = GND
    ("GATE_MAIN", "Q3", "2"),    # Q3 drain = gate rail
    ("GATE_MAIN", "R4", "2"),    # R4 10k pull-up bottom
    ("+12V", "R4", "1"),         # R4 pull-up to +12V
    ("GATE_MAIN", "R5", "1"),    # R5 100R series gate resistor (in)

    # ---- Power MOSFET gate node ----
    ("Q1_GATE", "R5", "2"),      # R5 series (out) -> Q1 gate
    ("Q1_GATE", "Q1", "1"),      # Q1 gate
    ("Q1_GATE", "R6", "1"),      # R6 10k gate-source pulldown top
    ("GND", "R6", "2"),          # R6 pulldown to GND

    # ---- Power loop ----
    ("HEATER_RET", "J2", "2"),   # heater return terminal (J2.1 = +24V, Task 4)
    ("HEATER_RET", "Q1", "2"),   # Q1 drain = heater return
    ("HEATER_RET", "D4", "1"),   # TVS cathode at HEATER_RET
    ("GND", "Q1", "3"),          # Q1 source = GND (low-side)
    ("GND", "D4", "2"),          # TVS anode to GND
]

# =============================================================================
# Task 6: controller / sensor / UI wiring (NETS_CTRL)
# =============================================================================
#
# Same net-label-on-outward-stub technique as Tasks 4-5. The contract checker
# (net_contract.py) asserts that each pinmap GPIO *name* (e.g. "GPIO18") appears
# as a label in the schematic, so the GPIO name is used directly as the local
# net label and is dropped on BOTH the A1 pin and the matching peripheral pin --
# that makes them one net AND satisfies the contract in a single pass.
#
# ESP32 A1 pin-number map (from modules.kicad_sym ESP32_DevKitV1):
#   VIN=15, GND=14, 3V3=30, GPIO32=6, GPIO33=7, GPIO25=8, GPIO26=9, GPIO27=10,
#   GPIO22=17, GPIO21=20, GPIO19=21, GPIO18=22, GPIO5=23, GPIO4=26.
# J3 MAX31855: VCC=1 GND=2 SCK=3 CS=4 SO=5.
# J4 OLED:     VCC=1 GND=2 SCL=3 SDA=4.
# SW1 RotaryEncoder_Switch: pins A/B/C/S1/S2 (number == letter).
# SW2 SW_Push: 1, 2.   D1 LED: 1=K(cathode), 2=A(anode).
#
# HEATER_PWM: A1.GPIO25 joins the existing HEATER_PWM net (its gate-drive end was
# wired in Task 5). Two labels share the GPIO25 stub node -- "HEATER_PWM" (for
# connectivity to GATEDRV.IN at R2.1) and "GPIO25" (for the contract checker).
#
# LED: A1.GPIO4 --R13(330)--> D1.A(anode); D1.K(cathode) --> GND. The series R13
# means GPIO4 lands on R13.1 (not directly on D1.A); R13.2 -> D1.A is the local
# LED_ANODE net. The contract enumerates LED_STATUS = [A1.GPIO4, D1.A] at the
# interface level; R13 is a passive interconnect (not enumerated), and the
# checker only requires the "GPIO4" label to be present, which it is on A1.GPIO4.
#
# Decoupling: C5 100nF across J3.VCC(+3V3)->GND, C6 100nF across J4.VCC(+3V3)->GND.
# Debounce:   C7 10nF A(GPIO32)->GND, C8 10nF B(GPIO33)->GND.
# No external I2C pull-ups (SSD1306 module has its own); encoder + button use the
# ESP32 internal pull-ups (no external R).
NETS_CTRL = [
    # ---- ESP32 (A1) power ----
    ("+5V", "A1", "15"),     # A1.VIN  <- +5V (from LM2576, Task 4)
    ("GND", "A1", "14"),     # A1.GND
    ("+3V3", "A1", "30"),    # A1.3V3  (onboard LDO output; PWR_FLAG added below)

    # ---- MAX31855 thermocouple (J3, SPI) ----
    ("+3V3", "J3", "1"),     # J3.VCC <- +3V3
    ("GND", "J3", "2"),      # J3.GND
    ("GPIO18", "J3", "3"),   # J3.SCK = A1.GPIO18 (TC_SCK)
    ("GPIO5", "J3", "4"),    # J3.CS  = A1.GPIO5  (TC_CS)
    ("GPIO19", "J3", "5"),   # J3.SO  = A1.GPIO19 (TC_SO)
    ("GPIO18", "A1", "22"),  # A1.GPIO18
    ("GPIO5", "A1", "23"),   # A1.GPIO5
    ("GPIO19", "A1", "21"),  # A1.GPIO19

    # ---- OLED (J4, I2C) ----
    ("+3V3", "J4", "1"),     # J4.VCC <- +3V3
    ("GND", "J4", "2"),      # J4.GND
    ("GPIO22", "J4", "3"),   # J4.SCL = A1.GPIO22 (OLED_SCL)
    ("GPIO21", "J4", "4"),   # J4.SDA = A1.GPIO21 (OLED_SDA)
    ("GPIO22", "A1", "17"),  # A1.GPIO22
    ("GPIO21", "A1", "20"),  # A1.GPIO21

    # ---- Rotary encoder (SW1) ----
    ("GPIO32", "SW1", "A"),  # SW1.A = A1.GPIO32 (ENC_A)
    ("GPIO33", "SW1", "B"),  # SW1.B = A1.GPIO33 (ENC_B)
    ("GPIO27", "SW1", "S1"), # SW1.S1 = A1.GPIO27 (ENC_SW)
    ("GND", "SW1", "C"),     # SW1.C common = GND
    ("GPIO32", "A1", "6"),   # A1.GPIO32
    ("GPIO33", "A1", "7"),   # A1.GPIO33
    ("GPIO27", "A1", "10"),  # A1.GPIO27

    # ---- Encoder debounce caps ----
    ("GPIO32", "C7", "1"),   # C7 A->GND debounce, top = ENC_A node
    ("GND", "C7", "2"),
    ("GPIO33", "C8", "1"),   # C8 B->GND debounce, top = ENC_B node
    ("GND", "C8", "2"),

    # ---- Start button (SW2) ----
    ("GPIO26", "SW2", "1"),  # SW2.1 = A1.GPIO26 (BTN_START)
    ("GND", "SW2", "2"),     # SW2.2 = GND
    ("GPIO26", "A1", "9"),   # A1.GPIO26

    # ---- Status LED (D1) via R13 ----
    ("GPIO4", "A1", "26"),   # A1.GPIO4 (LED_STATUS)
    ("GPIO4", "R13", "1"),   # R13.1 = GPIO4 side
    ("LED_ANODE", "R13", "2"),  # R13.2 -> D1 anode (local node)
    ("LED_ANODE", "D1", "2"),   # D1.A (anode) = pin 2
    ("GND", "D1", "1"),         # D1.K (cathode) = pin 1 -> GND

    # ---- Decoupling caps ----
    ("+3V3", "C5", "1"),     # C5 across J3.VCC->GND
    ("GND", "C5", "2"),
    ("+3V3", "C6", "1"),     # C6 across J4.VCC->GND
    ("GND", "C6", "2"),

    # ---- Heater PWM logic input (A1.GPIO25 -> existing HEATER_PWM net) ----
    ("HEATER_PWM", "A1", "8"),  # joins GATEDRV.IN (R2.1) wired in Task 5
]

# Extra labels that must share an existing stub node (same ref+pin) without a new
# wire. Used for the GPIO25 pin, which carries the HEATER_PWM net label (above)
# plus a second "GPIO25" label so the contract checker sees the GPIO25 name.
# (net_label, ref, pin)
NETS_CTRL_ALIASES = [
    ("GPIO25", "A1", "8"),
]

# =============================================================================
# Footprint-finalization no_connect markers (Task 8: folded in from the
# post-placement footprint-assignment pass so this script regenerates the
# finalized schematic faithfully -- ERC otherwise flags the unused ESP32 module
# pins and the encoder S2 pin as "unconnected").
#
# These coordinates are the absolute pin endpoints of A1's unused module pins
# and SW1.S2; KiCad accepts a (no_connect (at x y)) on the pin endpoint. They are
# stable because A1 (150,150) and SW1 (330,90) placements are fixed above.
# =============================================================================
NO_CONNECTS = [
    (137.30, 132.22), (137.30, 134.76), (137.30, 137.30), (137.30, 139.84),
    (137.30, 142.38), (137.30, 157.62), (137.30, 160.16), (137.30, 162.70),
    (162.70, 132.22), (162.70, 137.30), (162.70, 139.84), (162.70, 152.54),
    (162.70, 155.08), (162.70, 160.16), (162.70, 162.70), (162.70, 165.24),
    (337.62, 92.54),
]


def render_no_connect(x, y) -> str:
    return f'\t(no_connect\n\t\t(at {x} {y})\n\t\t(uuid "{uid()}")\n\t)'


# Net-label visual styling. KiCad treats SW_OUT / J1_HOT as ordinary local nets.
_STUB = 2.54  # mm wire-stub length from the pin endpoint


def render_wire(x1, y1, x2, y2) -> str:
    return (
        f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1} {y1}) (xy {x2} {y2})\n\t\t)\n'
        f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
        f'\t\t(uuid "{uid()}")\n\t)'
    )


def render_label(name, x, y, angle=0) -> str:
    return (
        f'\t(label "{name}"\n\t\t(at {x} {y} {angle})\n\t\t(effects\n'
        f'\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
        f'\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "{uid()}")\n\t)'
    )


def render_pwr_flag(x, y, idx) -> str:
    ref = f"#FLG{idx:03d}"
    return f'''\t(symbol
\t\t(lib_id "power:PWR_FLAG")
\t\t(at {x} {y} 0)
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(fields_autoplaced yes)
\t\t(uuid "{uid()}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {x} {round(y - 2.54, 2)} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Value" "PWR_FLAG"
\t\t\t(at {x} {round(y - 5.08, 2)} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(property "Datasheet" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t\t(pin "1"
\t\t\t(uuid "{uid()}")
\t\t)
\t\t(instances
\t\t\t(project "reflow"
\t\t\t\t(path "/{PROJ_UUID}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)'''


# PWR_FLAG library-symbol definition (must live in lib_symbols so the instances
# resolve). Indented two tabs to sit inside (lib_symbols ...).
PWR_FLAG_LIB = '''\t\t(symbol "power:PWR_FLAG"
\t\t\t(power)
\t\t\t(pin_numbers
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(pin_names
\t\t\t\t(offset 0)
\t\t\t\t(hide yes)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(property "Reference" "#FLG"
\t\t\t\t(at 0 1.905 0)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(hide yes)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "PWR_FLAG"
\t\t\t\t(at 0 3.81 0)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(hide yes)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Datasheet" ""
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(hide yes)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Special symbol for telling ERC where power comes from"
\t\t\t\t(at 0 0 0)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t\t(hide yes)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "PWR_FLAG_0_0"
\t\t\t\t(pin power_out line
\t\t\t\t\t(at 0 0 90)
\t\t\t\t\t(length 0)
\t\t\t\t\t(name "~"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "PWR_FLAG_0_1"
\t\t\t\t(polyline
\t\t\t\t\t(pts
\t\t\t\t\t\t(xy 0 0) (xy 0 1.27) (xy -1.016 1.905)
\t\t\t\t\t\t(xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)
\t\t\t\t\t)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type none)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(embedded_fonts no)
\t\t)'''


def render_lib_symbols() -> str:
    """Populate (lib_symbols ...) with every used symbol + PWR_FLAG."""
    used = []
    for lib_id in dict.fromkeys(c[1] for c in COMPONENTS):  # preserve order, dedupe
        lib, name = lib_id.split(":", 1)
        used.append((lib, name))
    bodies = [PWR_FLAG_LIB]
    for lib, name in used:
        body = lib_symbol_body(lib, name)
        # Re-key the symbol name to the full "Lib:Name" the schematic references,
        # and re-indent one extra tab to live inside (lib_symbols ...).
        body = body.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
        body = "\t\t" + body.replace("\n", "\n\t")
        bodies.append(body)
    return "\t(lib_symbols\n" + "\n".join(bodies) + "\n\t)"


def _stub_far(ref, pin):
    """Endpoint of the stub away from the pin (where label/flag attach)."""
    x, y = endpoint_of(ref, pin)
    dx, dy = pin_outward(ref, pin)
    return round(x + dx * _STUB, 4), round(y + dy * _STUB, 4)


def render_power_wiring() -> list[str]:
    """All Task-4 power connectivity: stubs+labels, pair wires, PWR_FLAGs.

    Each labelled pin gets a short wire stub routed *outward* (away from the
    symbol body) so the label sits on a wire endpoint that cannot land on an
    adjacent pin. Same-named labels form one net.
    """
    out: list[str] = []
    for net, ref, pin in NET_PINS:
        x, y = endpoint_of(ref, pin)
        fx, fy = _stub_far(ref, pin)
        out.append(render_wire(x, y, fx, fy))
        out.append(render_label(net, fx, fy))
    # Direct pin-to-pin wires (J1.1 -> F1.1 input link).
    for (r1, p1), (r2, p2) in PAIR_WIRES:
        x1, y1 = endpoint_of(r1, p1)
        x2, y2 = endpoint_of(r2, p2)
        out.append(render_wire(x1, y1, x2, y2))
    # PWR_FLAGs share the stub-far node of their pin (which also carries the
    # rail label), so flag + label + pin are one net.
    for i, (net, ref, pin) in enumerate(PWR_FLAGS, start=1):
        fx, fy = _stub_far(ref, pin)
        out.append(render_pwr_flag(fx, fy, i))
    return out


def render_powerstage_wiring() -> list[str]:
    """Task-5 power-stage + boot-safe gate-drive connectivity.

    Identical net-label-on-outward-stub technique as ``render_power_wiring``;
    only the net list (``NETS_POWERSTAGE``) differs. No new PWR_FLAGs: +12V and
    GND already have drivers/flags from Task 4, and the local gate nets
    (Q2_GATE, GD_NODE1, GATE_MAIN, Q1_GATE, HEATER_RET) are ordinary nets.
    """
    out: list[str] = []
    for net, ref, pin in NETS_POWERSTAGE:
        x, y = endpoint_of(ref, pin)
        fx, fy = _stub_far(ref, pin)
        out.append(render_wire(x, y, fx, fy))
        out.append(render_label(net, fx, fy))
    return out


def render_ctrl_wiring() -> list[str]:
    """Task-6 controller/sensor/UI connectivity.

    Identical net-label-on-outward-stub technique as Tasks 4-5. Each entry in
    ``NETS_CTRL`` emits a short outward stub from the pin endpoint with a net
    label on its far end; identical label names form one net. ``NETS_CTRL_ALIASES``
    drops an *extra* label on an existing stub-far node (no new wire) -- used so
    the GPIO25 pin carries both "HEATER_PWM" (connectivity) and "GPIO25" (the
    contract checker). The +3V3 PWR_FLAG (in PWR_FLAGS) is emitted by
    render_power_wiring and lands on the same A1.3V3 stub-far node.
    """
    out: list[str] = []
    for net, ref, pin in NETS_CTRL:
        x, y = endpoint_of(ref, pin)
        fx, fy = _stub_far(ref, pin)
        out.append(render_wire(x, y, fx, fy))
        out.append(render_label(net, fx, fy))
    for net, ref, pin in NETS_CTRL_ALIASES:
        fx, fy = _stub_far(ref, pin)
        out.append(render_label(net, fx, fy))
    return out


HEADER = '''(kicad_sch
\t(version 20250114)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid "a1b2c3d4-0001-0001-0001-000000000001")
\t(paper "A3")'''

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
    parts.append(render_lib_symbols())          # Task 4: real pin geometry/types
    for ref, lib_id, value, footprint, x, y, angle in COMPONENTS:
        parts.append(render_symbol(ref, lib_id, value, footprint, x, y, angle))
    wiring = render_power_wiring()              # Task 4: power-net connectivity
    wiring += render_powerstage_wiring()        # Task 5: gate drive + power loop
    wiring += render_ctrl_wiring()              # Task 6: controller/sensor/UI
    wiring += [render_no_connect(x, y) for x, y in NO_CONNECTS]  # Task 8: NC marks
    parts.extend(wiring)
    parts.append(FOOTER)

    SCH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {len(COMPONENTS)} components + {len(wiring)} wiring elements "
          f"to {SCH.name}")


if __name__ == "__main__":
    main()
