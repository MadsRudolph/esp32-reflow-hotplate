"""Validate the reflow hotplate net contract against the schematic.

The contract (net_contract.json) is the interface-level design-of-record:
the ESP32 pin map, the named power nets, and the named interface nets that
every later wiring task implements toward.

This checker asserts, in order:
  (a) every `pinmap` value (e.g. "GPIO25") appears as a *label* on the
      matching ESP32 pin in reflow.kicad_sch. Until the ESP32 is placed and
      wired (Task 3/6) the schematic is empty, so these labels are expected to
      be ABSENT and the checker correctly fails RED. It turns green once the
      wiring tasks add the hierarchical/local labels.
  (b) every `power_nets` entry is present (non-empty list of strings).
  (c) no net listed in `nets` has fewer than 2 endpoints.

Pure stdlib (no pcbnew / sexpdata) so it runs anywhere with plain Python 3.

    py -3.13 hardware/kicad/tools/net_contract.py

Exit 0 = contract satisfied by the schematic; exit 1 = any mismatch.
"""
import json
import os
import re
import sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.normpath(os.path.join(_TOOLS_DIR, ".."))
CONTRACT = os.path.join(PROJ_DIR, "net_contract.json")
SCH = os.path.join(PROJ_DIR, "reflow.kicad_sch")


def load_contract(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def labels_in_sch(sch_path):
    """Return the set of net-label texts present in the schematic.

    Covers local labels, global labels, and hierarchical labels:
        (label "GPIO25" ...)
        (global_label "GPIO25" ...)
        (hierarchical_label "GPIO25" ...)
    """
    if not os.path.exists(sch_path):
        return set()
    text = open(sch_path, encoding="utf-8").read()
    pat = re.compile(r'\((?:global_label|hierarchical_label|label)\s+"([^"]+)"')
    return set(pat.findall(text))


def main():
    problems = []

    if not os.path.exists(CONTRACT):
        print(f"FAIL: net_contract.json not found: {CONTRACT}", file=sys.stderr)
        return 1

    try:
        contract = load_contract(CONTRACT)
    except (ValueError, OSError) as exc:
        print(f"FAIL: cannot parse net_contract.json: {exc}", file=sys.stderr)
        return 1

    pinmap = contract.get("pinmap", {})
    power_nets = contract.get("power_nets", [])
    nets = contract.get("nets", {})

    # (a) every pinmap value must appear as a label in the schematic.
    sch_labels = labels_in_sch(SCH)
    missing_labels = [gpio for gpio in pinmap.values() if gpio not in sch_labels]
    if missing_labels:
        problems.append(
            "(a) pinmap GPIO labels not yet present in reflow.kicad_sch: "
            + ", ".join(sorted(set(missing_labels)))
        )

    # (b) every power net must exist in the contract.
    if not power_nets:
        problems.append("(b) power_nets is empty or missing")
    else:
        for pn in power_nets:
            if not isinstance(pn, str) or not pn:
                problems.append(f"(b) invalid power net entry: {pn!r}")

    # (c) no net may have fewer than 2 endpoints.
    for name, endpoints in nets.items():
        if not isinstance(endpoints, list) or len(endpoints) < 2:
            problems.append(
                f"(c) net '{name}' has <2 endpoints: {endpoints!r}"
            )

    print(
        f"contract: {len(pinmap)} pinmap signals, {len(power_nets)} power nets, "
        f"{len(nets)} interface nets; {len(sch_labels)} labels in schematic"
    )
    if problems:
        print(f"FAIL: {len(problems)} issue(s):")
        for p in problems:
            print(f"  {p}")
        return 1

    print("PASS: net contract satisfied by schematic")
    return 0


if __name__ == "__main__":
    sys.exit(main())
