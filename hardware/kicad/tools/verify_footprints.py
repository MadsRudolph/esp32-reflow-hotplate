"""Verify every Footprint property in reflow.kicad_sch resolves to a .kicad_mod
file under a library registered in the project fp-lib-table.

Pure stdlib (no pcbnew) — runs anywhere with plain Python 3.
Run from the repo root or from inside hardware/kicad/:

    py -3.13 hardware/kicad/tools/verify_footprints.py

Exit 0 = all good (or 0 footprints); exit 1 = unresolved footprints found.
"""
import os
import re
import sys

# Paths relative to this script's location: tools/ -> kicad/ -> hardware/
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.normpath(os.path.join(_TOOLS_DIR, ".."))
SCH = os.path.join(PROJ_DIR, "reflow.kicad_sch")
FP_LIB_TABLE = os.path.join(PROJ_DIR, "fp-lib-table")


def parse_fp_lib_table(path):
    """Return dict nickname -> raw URI (may contain ${KIPRJMOD})."""
    result = {}
    if not os.path.exists(path):
        return result
    text = open(path, encoding="utf-8").read()
    for m in re.finditer(r'\(lib\s+\(name "([^"]+)"\).*?\(uri "([^"]+)"\)', text):
        result[m.group(1)] = m.group(2)
    return result


def resolve_uri(uri, proj_dir):
    return os.path.normpath(uri.replace("${KIPRJMOD}", proj_dir))


def footprints_in_sch(sch_path):
    """Return list of (lib_nick, fp_name) tuples for every Footprint property."""
    text = open(sch_path, encoding="utf-8").read()
    return re.findall(r'\(property "Footprint" "([^":]+):([^"]+)"', text)


def main():
    if not os.path.exists(SCH):
        print(f"ERROR: schematic not found: {SCH}", file=sys.stderr)
        return 1

    lib_table = parse_fp_lib_table(FP_LIB_TABLE)
    fps = footprints_in_sch(SCH)
    unresolved = []

    for lib_nick, fp_name in fps:
        if lib_nick not in lib_table:
            unresolved.append(f"{lib_nick}:{fp_name}  -> lib '{lib_nick}' not in fp-lib-table")
            continue
        raw_uri = lib_table[lib_nick]
        pretty_dir = resolve_uri(raw_uri, PROJ_DIR)
        mod_path = os.path.join(pretty_dir, fp_name + ".kicad_mod")
        if not os.path.isdir(pretty_dir):
            unresolved.append(f"{lib_nick}:{fp_name}  -> .pretty dir missing: {pretty_dir}")
        elif not os.path.exists(mod_path):
            unresolved.append(f"{lib_nick}:{fp_name}  -> .kicad_mod missing: {mod_path}")

    n = len(fps)
    m = len(unresolved)
    print(f"{n} footprints checked, {m} unresolved")
    for issue in unresolved:
        print(f"  {issue}")
    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
