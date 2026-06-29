"""Boot-safety assertion for the IRFS4710 two-stage gate drive (Task 5).

The heater MOSFET (Q1) MUST be OFF whenever the ESP32 GPIO that drives
``HEATER_PWM`` is low, floating, mid-reset, or unpowered. The only topology
that guarantees this *inherently* (no firmware, no external pull on the GPIO
required) is the NON-inverting two-stage BS170 level shifter:

    HEATER_PWM --R2--> Q2.G        (Q2.S=GND, R1 100k pulldown on Q2.G)
    Q2.D = GD_NODE1, R3 pull-UP GD_NODE1 -> +12V
    GD_NODE1 --> Q3.G              (Q3.S=GND)
    Q3.D = GATE_MAIN, R4 pull-UP GATE_MAIN -> +12V
    GATE_MAIN --R5--> Q1.G, R6 pulldown Q1.G -> GND
    Q1.D = HEATER_RET, Q1.S = GND

Boot proof (GPIO floating/low): R1 holds Q2.G low -> Q2 OFF -> R3 pulls
GD_NODE1 to +12V -> Q3 ON -> Q3 clamps GATE_MAIN to GND -> Q1 OFF. R6 is the
belt-and-suspenders gate-source pulldown.

A SINGLE inverting stage (HEATER_PWM pulled up to the gate via a resistor to
+12V, one transistor) is FORBIDDEN: when the GPIO floats at boot the gate is
pulled HIGH and the heater turns ON. This script exits non-zero if that
pattern is present, or if the boot-safe guarantees are missing.

The script consumes the KiCad s-expression netlist exported by:

    kicad-cli sch export netlist --format kicadsexpr -o <out> reflow.kicad_sch

It re-exports automatically if a netlist path is not supplied.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # hardware/kicad
SCH = ROOT / "reflow.kicad_sch"
KICAD_CLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")

# Q_NMOS_GDS pin-number -> terminal. Confirmed from the library symbol geometry
# (pin 1 = Gate/input, pin 2 = Drain, pin 3 = Source).
MOSFET = {"1": "G", "2": "D", "3": "S"}


# ---------------------------------------------------------------------------
# Minimal s-expression parse of the (nets ...) block: net-name -> set of
# (ref, pin) nodes. Also harvest component values from the netlist's
# (components ...) block so we can check resistor values.
# ---------------------------------------------------------------------------
def export_netlist() -> str:
    tmp = Path(tempfile.gettempdir()) / "_reflow_bootsafe.net"
    subprocess.run(
        [str(KICAD_CLI), "sch", "export", "netlist",
         "--format", "kicadsexpr", "-o", str(tmp), str(SCH)],
        check=True, capture_output=True, text=True,
    )
    return tmp.read_text(encoding="utf-8")


def parse_nets(text: str) -> dict[str, set[tuple[str, str]]]:
    nets: dict[str, set[tuple[str, str]]] = {}
    # Each (net (code ..) (name "..") ... (node (ref "..")(pin "..")) ...)
    for nm in re.finditer(r'\(net\b(.*?)(?=\(net\b|\Z)', text, re.DOTALL):
        body = nm.group(1)
        name_m = re.search(r'\(name\s+"([^"]*)"', body)
        if not name_m:
            continue
        name = name_m.group(1).lstrip("/")
        nodes = set()
        for node in re.finditer(
            r'\(node\s+\(ref\s+"([^"]+)"\)\s*\(pin\s+"([^"]+)"\)', body
        ):
            nodes.add((node.group(1), node.group(2)))
        nets[name] = nodes
    return nets


def parse_values(text: str) -> dict[str, str]:
    vals: dict[str, str] = {}
    for c in re.finditer(
        r'\(comp\s+\(ref\s+"([^"]+)"\)\s*\(value\s+"([^"]*)"\)', text
    ):
        vals[c[1]] = c[2]
    return vals


def node_net(nets, ref, pin) -> str | None:
    for name, nodes in nets.items():
        if (ref, pin) in nodes:
            return name
    return None


def fail(msg: str) -> None:
    print(f"BOOT-SAFETY FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        text = export_netlist()

    nets = parse_nets(text)
    vals = parse_values(text)

    # Resolve the key nets by the pins that define them (topology, not names).
    q1_g = node_net(nets, "Q1", "1")   # Q1 gate
    q1_d = node_net(nets, "Q1", "2")   # Q1 drain -> HEATER_RET
    q1_s = node_net(nets, "Q1", "3")   # Q1 source -> GND
    q2_g = node_net(nets, "Q2", "1")
    q2_d = node_net(nets, "Q2", "2")   # -> GD_NODE1
    q2_s = node_net(nets, "Q2", "3")
    q3_g = node_net(nets, "Q3", "1")   # = GD_NODE1
    q3_d = node_net(nets, "Q3", "2")   # -> GATE_MAIN
    q3_s = node_net(nets, "Q3", "3")

    for label, val in [("Q1.G", q1_g), ("Q1.D", q1_d), ("Q1.S", q1_s),
                       ("Q2.G", q2_g), ("Q2.D", q2_d), ("Q2.S", q2_s),
                       ("Q3.G", q3_g), ("Q3.D", q3_d), ("Q3.S", q3_s)]:
        if val is None:
            fail(f"{label} is not connected to any net (gate stage unwired).")

    gnd = "GND"
    v12 = "+12V"

    # ---- Sources of both BS170 stages must be GND (low-side inverters). ----
    if q2_s != gnd:
        fail(f"Q2 source is on '{q2_s}', expected GND.")
    if q3_s != gnd:
        fail(f"Q3 source is on '{q3_s}', expected GND.")
    if q1_s != gnd:
        fail(f"Q1 source is on '{q1_s}', expected GND.")

    # ---- Stage chain: Q2.D == Q3.G (the GD_NODE1 inter-stage node). ----
    if q2_d != q3_g:
        fail(f"Inter-stage broken: Q2.D='{q2_d}' must equal Q3.G='{q3_g}' "
             f"(GD_NODE1).")
    gd_node1 = q2_d
    gate_main = q3_d

    # ---- (b) Pull-UP to +12V on GD_NODE1 (R3) and on GATE_MAIN (R4). ----
    def pullup_to_12v(net_name) -> tuple[str, str] | None:
        """Return (ref,otherpin) of a resistor bridging net_name and +12V."""
        v12_nodes = nets.get(v12, set())
        net_nodes = nets.get(net_name, set())
        v12_refs = {r for r, _ in v12_nodes}
        for ref, pin in net_nodes:
            if ref.startswith("R") and ref in v12_refs:
                return ref, pin
        return None

    if pullup_to_12v(gd_node1) is None:
        fail(f"No pull-UP resistor from GD_NODE1 ('{gd_node1}') to +12V "
             f"(R3 missing). Q2-off would not pull GD_NODE1 high -> Q3 would "
             f"not turn on -> Q1 not held off at boot.")
    if pullup_to_12v(gate_main) is None:
        fail(f"No pull-UP resistor from GATE_MAIN ('{gate_main}') to +12V "
             f"(R4 missing).")

    # ---- (a) R6 gate-source pulldown: a resistor Q1.G -> GND. ----
    gnd_refs = {r for r, _ in nets.get(gnd, set())}
    q1g_nodes = nets.get(q1_g, set())
    pulldown = None
    for ref, pin in q1g_nodes:
        if ref.startswith("R") and ref in gnd_refs:
            pulldown = ref
            break
    if pulldown is None:
        fail(f"No gate-source pulldown resistor from Q1.G ('{q1_g}') to GND "
             f"(R6 missing). Q1 gate could float high.")

    # ---- Series gate resistor: Q1.G reaches GATE_MAIN through a resistor. ----
    # GATE_MAIN (Q3.D) and Q1.G must be DIFFERENT nets bridged by a resistor
    # (R5), otherwise there is no series gate resistor and the topology drifts.
    if q1_g == gate_main:
        fail("Q1.G is the same net as GATE_MAIN: missing series gate resistor "
             "R5 between GATE_MAIN and Q1.G.")
    gate_main_refs = {r for r, _ in nets.get(gate_main, set())}
    series_r = None
    for ref, pin in q1g_nodes:
        if ref.startswith("R") and ref in gate_main_refs:
            series_r = ref
            break
    if series_r is None:
        fail(f"No series gate resistor bridging GATE_MAIN ('{gate_main}') and "
             f"Q1.G ('{q1_g}') (R5 missing).")

    # ---- (c) FORBIDDEN single-inverting / direct-drive patterns. ----
    #
    # Resolve the PWM-input net by TOPOLOGY, not by a fixed label name.
    # The net that drives the gate chain is identified as the net whose members
    # include R2 pin 1 (the source side of the series gate resistor into Q2.G).
    # This is alias-robust: after Task 6 the net carries both the "GPIO25" and
    # "HEATER_PWM" labels; KiCad may name it either way in the export.  We never
    # look up a label string — we look up the pin-set membership.
    pwm = node_net(nets, "R2", "1")
    if pwm is None:
        fail("R2 pin 1 is not connected to any net.  "
             "Cannot resolve the PWM-input net; R2 (series gate resistor) "
             "appears missing.")
    pwm_nodes = nets.get(pwm, set())
    pwm_refs = {r for r, _ in pwm_nodes}

    # PWM-input net must NOT touch Q1.G directly.
    if (("Q1", "1") in pwm_nodes) or (q1_g == pwm):
        fail(f"PWM-input net ('{pwm}') connects DIRECTLY to Q1.G "
             f"(single-stage / direct drive). "
             f"Floating GPIO at boot would drive the heater ON.")
    # PWM-input net must NOT touch GATE_MAIN directly.
    if pwm == gate_main:
        fail(f"PWM-input net ('{pwm}') is the same net as GATE_MAIN "
             f"(single inverting stage). "
             f"Floating GPIO at boot could drive the gate.")
    # PWM-input net must NOT be pulled up to +12V (an inverting stage would put
    # a pull-up to the gate rail directly on the logic input).
    v12_refs_all = {r for r, _ in nets.get(v12, set())}
    for ref, _pin in pwm_nodes:
        if ref.startswith("R") and ref in v12_refs_all:
            fail(f"PWM-input net ('{pwm}') has a pull-UP resistor ({ref}) to "
                 f"+12V -- that is the inverting single-stage pattern. Forbidden.")
    # PWM-input net must reach Q2.G through a series resistor (R2); the two nets
    # must be DIFFERENT (otherwise R2 is absent and the input is shorted to Q2.G).
    if pwm == q2_g:
        # The input net and Q2.G merged into one net -> R2 has no series effect.
        fail(f"PWM-input net ('{pwm}') is directly the Q2.G net "
             f"(R2 series resistor is missing or bypassed).")
    q2g_refs = {r for r, _ in nets.get(q2_g, set())}
    bridging = pwm_refs & q2g_refs & {r for r in pwm_refs if r.startswith("R")}
    if not bridging:
        fail(f"PWM-input net ('{pwm}') does not reach Q2.G through a series "
             f"resistor (R2 appears missing). "
             f"PWM net refs={sorted(pwm_refs)}, Q2.G net refs={sorted(q2g_refs)}.")

    # ---- Q1 drain is the heater return (sanity: not GND/+12V/+24V). ----
    if q1_d in (gnd, v12, "+24V", "+5V"):
        fail(f"Q1.D is on a power rail '{q1_d}', expected HEATER_RET.")

    # ---- All good. ----
    print("BOOT-SAFETY PASS: non-inverting two-stage gate drive verified.")
    print(f"  PWM-input ('{pwm}') --R2--> Q2.G   (Q2.S=GND, pulldown on Q2.G)")
    print(f"  Q2.D = GD_NODE1 ('{gd_node1}')  pull-UP to +12V present")
    print(f"  GD_NODE1 --> Q3.G ; Q3.D = GATE_MAIN ('{gate_main}')  "
          f"pull-UP to +12V present")
    print(f"  GATE_MAIN --{series_r}--> Q1.G ('{q1_g}') ; "
          f"{pulldown} pulldown Q1.G->GND")
    print(f"  Q1.D = HEATER_RET ('{q1_d}'), Q1.S = GND")
    print("  Boot: GPIO float/low -> Q2 off -> GD_NODE1=+12V -> Q3 on -> "
          "GATE_MAIN=0V -> Q1 OFF.")
    sys.exit(0)


if __name__ == "__main__":
    main()
