"""Cross-check every BOARD-SOLDERED part against the DTU component shop (Task 8).

Reads the components + their values from the KiCad netlist exported from
``reflow.kicad_sch``, EXCLUDES the modules and bring-your-own hardware (A1 ESP32
DevKit, J3 MAX31855, J4 OLED -- these are pin-header modules, not soldered
parts), normalises each remaining part's value, and asserts it resolves to a
``Part_Number`` or ``Value`` row in::

    components-inventory/dtu_component_shop(1).csv

Normalisation handles the format gaps between KiCad value strings and the shop's
catalogue notation:

  * micro sign:        ``120uH`` == ``120µH`` == shop inductor code ``120µ``
  * ohm/R suffix:      ``100`` == ``100R`` == ``100Ω``
  * k/K and E96 codes: ``10k`` == shop ``10K0``; ``1k00`` == ``1K00``;
                       ``3k09`` == ``3K09``; ``330`` == ``330R``
  * caps:              ``100nF`` == shop ceramic ``100n``; ``1000uF`` ==
                       electrolytic ``1000µF``; ``330nF`` == film ``330n``
  * semis / regs:      matched on Part_Number (``IRFS4710``, ``BS170``,
                       ``1N5817``, ``LM7812``, ``LM2575``) directly.
  * TVS / connectors / switches / LED / fuse: matched on Part_Number/Value.

Every part with no shop match is printed; exit code is the number of unmatched
board parts (0 = all resolve).

    py -3.13 hardware/kicad/tools/check_bom_against_shop.py
    py -3.13 hardware/kicad/tools/check_bom_against_shop.py <shop.csv> <sch>
"""
from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
import tempfile

# Force UTF-8 stdout so Ω/µ in shop tokens don't crash the Windows cp1252 console.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

_TOOLS = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(_TOOLS, ".."))
SCH = os.path.join(KDIR, "reflow.kicad_sch")
REPO = os.path.normpath(os.path.join(KDIR, "..", ".."))
DEFAULT_CSV = os.path.normpath(
    os.path.join(REPO, "..", "components-inventory", "dtu_component_shop(1).csv")
)
KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"

# Modules + bring-your-own hardware: NOT board-soldered parts. They live in the
# "External / bring-your-own" section of the BOM and are excluded from the
# shop cross-check (they are not stocked discrete components):
#   A1 ESP32 DevKit, J3 MAX31855 module, J4 SSD1306 OLED module  (pin-header modules)
#   F1 24 V fuse HOLDER -- the fuse element is user-supplied (bring-your-own).
EXCLUDE_REFS = {"A1", "J3", "J4", "F1"}


# ---------------------------------------------------------------------------
# Netlist export + parse (ref -> value).
# ---------------------------------------------------------------------------
def export_netlist() -> str:
    out = os.path.join(tempfile.gettempdir(), "reflow_bomcheck.net")
    subprocess.run(
        [KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr",
         "-o", out, SCH],
        check=True, capture_output=True, text=True,
    )
    return open(out, encoding="utf-8").read()


def parse_components(text: str) -> dict[str, str]:
    """ref -> value, from the netlist (components ...) block."""
    vals: dict[str, str] = {}
    for m in re.finditer(
        r'\(comp\s+\(ref\s+"([^"]+)"\)\s*\(value\s+"([^"]*)"\)', text
    ):
        vals[m.group(1)] = m.group(2)
    return vals


# ---------------------------------------------------------------------------
# Shop catalogue.
# ---------------------------------------------------------------------------
def load_shop(csv_path: str) -> list[dict]:
    rows = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Value normalisation helpers.
# ---------------------------------------------------------------------------
def _u(s: str) -> str:
    """Lower-case, strip spaces, fold the micro sign to 'u'."""
    return s.strip().replace("µ", "u").replace("μ", "u").replace("Ω", "r").replace("ω", "r").lower()


def _r_canon(s: str) -> str | None:
    """Canonical resistance token, e.g. '10k'->'10000', '3k09'->'3090',
    '100'->'100', '100r'->'100', '330r'->'330', E96 '10K0'->'10000',
    '1K00'->'1000'.  Returns the resistance in ohms as an int-ish string, or
    None if not parseable as a resistance."""
    t = _u(s)
    t = t.replace("ohm", "").replace("ω", "r")
    # forms: <digits>[.<digits>] optional multiplier r/k/m as decimal point too
    # e.g. 10k, 10k0, 1k00, 3k09, 4r7, 100r, 330, 1m00
    m = re.fullmatch(r"(\d+)([rkm])(\d*)", t)
    if m:
        whole, mult, frac = m.group(1), m.group(2), m.group(3)
        num = float(f"{whole}.{frac}") if frac else float(whole)
        scale = {"r": 1.0, "k": 1e3, "m": 1e6}[mult]
        return _fmt_ohms(num * scale)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([rkm])", t)  # 10k, 4.7k, 100r
    if m:
        num = float(m.group(1))
        scale = {"r": 1.0, "k": 1e3, "m": 1e6}[m.group(2)]
        return _fmt_ohms(num * scale)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)r?", t)  # bare ohms: 330, 100, 100r already handled
    if m:
        return _fmt_ohms(float(m.group(1)))
    return None


def _fmt_ohms(v: float) -> str:
    return str(int(round(v))) if abs(v - round(v)) < 1e-6 else f"{v:g}"


def _cap_canon(s: str) -> str | None:
    """Canonical capacitance in farads (scientific-ish), tolerating the shop's
    p/n/u codes and KiCad's '100nF'/'1000uF' strings."""
    t = _u(s).replace("f", "")  # drop trailing F
    # coded forms: 100n, 1n0, 4u7, 22p, 2u2  (multiplier as decimal point)
    m = re.fullmatch(r"(\d+)([pnu])(\d*)", t)
    if m:
        whole, mult, frac = m.group(1), m.group(2), m.group(3)
        num = float(f"{whole}.{frac}") if frac else float(whole)
        scale = {"p": 1e-12, "n": 1e-9, "u": 1e-6}[mult]
        return _fmt_farads(num * scale)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([pnu])", t)  # 100n, 1000u, 4.7u, 330n
    if m:
        scale = {"p": 1e-12, "n": 1e-9, "u": 1e-6}[m.group(2)]
        return _fmt_farads(float(m.group(1)) * scale)
    return None


def _fmt_farads(v: float) -> str:
    # round to 1e-15 to avoid float dust
    return f"{v:.4e}"


def _ind_canon(s: str) -> str | None:
    """Canonical inductance in henries from KiCad '120uH' / shop '120µ'."""
    t = _u(s).replace("h", "")
    m = re.fullmatch(r"(\d+)([pnum])(\d*)", t)   # 120u, 1u2, 0u1, 2m7
    if m:
        whole, mult, frac = m.group(1), m.group(2), m.group(3)
        num = float(f"{whole}.{frac}") if frac else float(whole)
        scale = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3}[mult]
        return _fmt_farads(num * scale)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([pnum])", t)  # 120u, 4.7u
    if m:
        scale = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3}[m.group(2)]
        return _fmt_farads(float(m.group(1)) * scale)
    return None


def _shop_index(shop: list[dict]):
    """Sets of normalised shop tokens, by domain, plus a raw part-number set."""
    part_numbers = set()
    values_raw = set()
    res = set()
    cap = set()
    ind = set()
    for row in shop:
        pn = (row.get("Part_Number") or "").strip()
        val = (row.get("Value") or "").strip()
        cat = (row.get("Category") or "").strip()
        if pn:
            part_numbers.add(pn.upper())
        if val:
            values_raw.add(val.upper())
        # domain canonicalisation by category
        if cat == "Resistor":
            for tok in (pn, val):
                c = _r_canon(tok)
                if c is not None:
                    res.add(c)
        elif cat == "Capacitor":
            for tok in (pn, val):
                c = _cap_canon(tok)
                if c is not None:
                    cap.add(c)
        elif cat == "Inductor":
            for tok in (pn, val):
                c = _ind_canon(tok)
                if c is not None:
                    ind.add(c)
    return part_numbers, values_raw, res, cap, ind


# ---------------------------------------------------------------------------
# Per-part resolution.  Returns (ok, shop_hint).
# ---------------------------------------------------------------------------
def resolve(ref: str, value: str, idx) -> tuple[bool, str]:
    part_numbers, values_raw, res, cap, ind = idx
    cls = re.match(r"^[A-Za-z]+", ref).group(0).upper()
    v = value.strip()
    vu = v.upper()

    # Direct part-number / value hit (semiconductors, regs, TVS, connectors...).
    if vu in part_numbers:
        return True, f"Part_Number {v}"
    if vu in values_raw:
        return True, f"Value {v}"

    if cls == "R":
        c = _r_canon(v)
        if c is not None and c in res:
            return True, f"resistor {c}Ω"
    if cls == "C":
        c = _cap_canon(v)
        if c is not None and c in cap:
            return True, f"capacitor {v}"
    if cls == "L":
        c = _ind_canon(v)
        if c is not None and c in ind:
            return True, f"inductor {v}"

    # Semiconductor / regulator: substring of a stocked part number (e.g.
    # 'LM2575-ADJ' value -> shop 'LM2575'; 'LM2575BT-ADJ' symbol value also OK).
    if cls in {"Q", "U", "D"}:
        base = re.match(r"[A-Za-z0-9]+", vu)
        for pn in part_numbers:
            if pn == vu or vu.startswith(pn) or pn.startswith(vu):
                return True, f"Part_Number {pn}"
        # LM2575-ADJ family: KiCad value 'LM2575-ADJ' -> shop 'LM2575'
        m = re.match(r"(LM\d+)", vu)
        if m and m.group(1) in part_numbers:
            return True, f"Part_Number {m.group(1)}"

    return False, ""


# ---------------------------------------------------------------------------
# Map a refdes-class to a human label for the report.
# ---------------------------------------------------------------------------
def main() -> int:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    global SCH
    if len(sys.argv) > 2:
        SCH = sys.argv[2]

    if not os.path.exists(csv_path):
        print(f"shop CSV not found: {csv_path}")
        return 2

    shop = load_shop(csv_path)
    idx = _shop_index(shop)
    comps = parse_components(export_netlist())

    board = {r: v for r, v in comps.items()
             if r not in EXCLUDE_REFS and not r.startswith("#")}

    print(f"DTU shop cross-check: {len(board)} board-soldered parts "
          f"(excluded modules: {', '.join(sorted(EXCLUDE_REFS))})\n")
    unmatched = []
    for ref in sorted(board, key=lambda r: (re.match(r'^[A-Za-z]+', r).group(0), r)):
        value = board[ref]
        ok, hint = resolve(ref, value, idx)
        mark = "OK  " if ok else "MISS"
        print(f"  [{mark}] {ref:<4} {value:<14} {('-> ' + hint) if ok else '-> NO SHOP MATCH'}")
        if not ok:
            unmatched.append((ref, value))

    print()
    if unmatched:
        print(f"FAIL: {len(unmatched)} board part(s) do not resolve to the DTU shop:")
        for ref, value in unmatched:
            print(f"  {ref} = '{value}'")
        return len(unmatched)
    print("PASS: all board parts resolve to DTU shop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
