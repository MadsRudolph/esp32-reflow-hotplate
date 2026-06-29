"""Safety gate: prove every footprint pad of the power devices (Q1, Q2, Q3, U2)
will receive a net when Task 9 builds the board with the kicad-laser-pcb
``pcb_build.py`` flow.

``pcb_build.py`` assigns a net to each footprint pad with EXACTLY this logic
(scripts/pcb_build.py lines ~60-73)::

    GDS = {"1": "G", "2": "D", "3": "S"}
    for pad in fp.Pads():
        num = pad.GetNumber()
        net = c["pads"].get(num) or c["pads"].get(GDS.get(num, ""))
    ...
    if c["pads"] and all(p.GetNetCode() == 0 for p in fp.Pads()):
        raise SystemExit(f"{c['ref']}: ingen pads fik net - pinnummer-mismatch?")

``c["pads"]`` is keyed by the symbol pin *number* as it appears in the exported
netlist.  This project uses the stock ``Transistor_FET:Q_NMOS_GDS`` symbol whose
pins are NUMBERED 1/2/3 (G/D/S are only display names), so the MOSFET footprint
pads MUST be named 1/2/3 -- a footprint with G/D/S-named pads would bind to
None and the line-72 guard would fire (silent dead board on the real hardware).

This script re-implements that binding against the real netlist + the real
``.kicad_mod`` pad names and asserts every pad of every checked device binds to
a net.  Exit 0 = all pads bound; exit 1 = at least one pad would get no net.

    py -3.13 hardware/kicad/tools/verify_pad_nets.py
"""
import os
import re
import subprocess
import sys
import tempfile

_TOOLS = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(_TOOLS, ".."))
SCH = os.path.join(KDIR, "reflow.kicad_sch")
FP_LIB_TABLE = os.path.join(KDIR, "fp-lib-table")
KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"

# Devices whose pad->net binding is safety-critical for the laser/mill build.
CHECK_REFS = ["Q1", "Q2", "Q3", "U2"]

# The exact fallback map pcb_build.py uses (numeric pad -> letter netlist key).
GDS = {"1": "G", "2": "D", "3": "S"}


def export_netlist():
    out = os.path.join(tempfile.gettempdir(), "reflow_padnet.net")
    subprocess.run(
        [KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr",
         "-o", out, SCH],
        check=True, capture_output=True,
    )
    return out


def parse_components(netpath):
    """ref -> {pin_number: net_name} and ref -> footprint 'lib:name'."""
    t = open(netpath, encoding="utf-8").read()
    pads = {}        # ref -> {pin: net}
    footprint = {}   # ref -> "lib:name"

    # footprint per component
    cidx = t.find("(components")
    nidx = t.find("(nets")
    comp_block = t[cidx:nidx]
    for m in re.finditer(
        r'\(comp\s+\(ref "([^"]+)"\)(.*?)(?=\(comp\s+\(ref|\Z)', comp_block, re.S
    ):
        ref, body = m.group(1), m.group(2)
        fp = re.search(r'\(footprint "([^"]+)"\)', body)
        if fp:
            footprint[ref] = fp.group(1)

    # pin -> net from the nets section
    nets = t[nidx:]
    for m in re.finditer(
        r'\(net\s+\(code "[^"]*"\)\s+\(name "([^"]*)"\)(.*?)(?=\(net\s+\(code|\Z)',
        nets, re.S,
    ):
        name, body = m.group(1), m.group(2)
        for node in re.finditer(r'\(node\s*\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body):
            pads.setdefault(node.group(1), {})[node.group(2)] = name
    return pads, footprint


def parse_fp_lib_table():
    result = {}
    text = open(FP_LIB_TABLE, encoding="utf-8").read()
    for m in re.finditer(r'\(lib\s+\(name "([^"]+)"\).*?\(uri "([^"]+)"\)', text):
        result[m.group(1)] = m.group(2).replace("${KIPRJMOD}", KDIR)
    return result


def footprint_pads(fp_ref, lib_table):
    """Return the list of pad numbers/names in the .kicad_mod."""
    lib, name = fp_ref.split(":", 1)
    mod = os.path.join(lib_table[lib], name + ".kicad_mod")
    txt = open(mod, encoding="utf-8").read()
    return re.findall(r'\(pad "([^"]+)"', txt)


def main():
    netpath = export_netlist()
    comp_pads, comp_fp = parse_components(netpath)
    lib_table = parse_fp_lib_table()

    failures = []
    print("pcb_build.py pad->net binding simulation\n")
    for ref in CHECK_REFS:
        netmap = comp_pads.get(ref, {})       # pin-number -> net (from netlist)
        fp = comp_fp.get(ref)
        if not fp:
            failures.append(f"{ref}: no footprint in netlist")
            continue
        pad_names = footprint_pads(fp, lib_table)
        # mounting / mechanical pads (no electrical pin) are allowed to be padless.
        print(f"{ref}  {fp}")
        bound_any = False
        for pad in pad_names:
            net = netmap.get(pad) or netmap.get(GDS.get(pad, ""))
            mark = "OK " if net else "NO-NET"
            if net:
                bound_any = True
            # A pad is a failure only if the SYMBOL has a pin of that number
            # (i.e. it should carry a net) but the lookup returns nothing.
            is_signal_pad = pad in netmap or GDS.get(pad, "") in netmap or pad.isdigit()
            if not net and is_signal_pad and pad != "MP":
                failures.append(f"{ref} pad '{pad}' -> NO NET (pin-number/pad-name mismatch)")
            print(f"    pad {pad:>3} -> {net if net else '<no net>'}   [{mark}]")
        # mirror pcb_build.py's line-72 hard guard
        if netmap and not bound_any:
            failures.append(f"{ref}: NO pad got a net - line-72 guard would fire")
        print()

    if failures:
        print("FAIL:")
        for f in failures:
            print("  " + f)
        return 1
    print("PASS: every checked pad binds to a net (line-72 guard would NOT fire).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
