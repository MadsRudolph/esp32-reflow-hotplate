# Electrical calculations

Design-of-record: `hardware/kicad/net_contract.json`. This document captures the
quantitative justification for the power tree wired in Task 4 (24 V input
protection + the two regulators). Other sections (heater power stage, gate
drive, controller) are documented with their respective tasks.

## 1. Power tree overview

```
24 V DC ──[F1 fuse]──┬── +24V rail ──┬── U2  LM2576-5.0 buck ── +5V  (ESP32 + OLED)
        (D3 TVS to GND)              ├── U3  LM7812 linear   ── +12V (gate-drive VCC)
                                     └── J2.1 heater terminal (switched low-side by Q1)
```

- **U2 = LM2576T-5** — SIMPLE SWITCHER step-down (buck), fixed 5.0 V output.
- **U3 = LM7812** — TO-220 linear regulator, fixed 12 V output.
- There is **no separate 3V3 regulator**: +3V3 is produced by the ESP32
  DevKit's on-board LDO from +5V (handled in Task 6).

Input fusing and protection: F1 (fuse) in series with the 24 V hot lead, and
D3 (TVS) clamping +24V → GND at the input.

## 2. Load budget

| Rail | Consumers | Estimated load |
|------|-----------|----------------|
| +5V  | ESP32-DevKitV1 (Wi-Fi idle/active), SSD1306 OLED, MAX31855 | ~0.30–0.50 A (use **0.5 A** worst case) |
| +12V | Two-stage BS170 gate drive for the heater MOSFET — average current is only the gate-charge shuttling current at the PWM rate | **a few mA** average (see §4) |

## 3. LM2576-5.0 buck (24 V → 5 V)

A buck converter's loss is dominated by switching + conduction in the internal
switch and the catch diode, **not** by `(Vin − Vout)·Iload` (that term is the
linear-regulator penalty a switcher specifically avoids).

- Output power delivered: `Pout = 5 V × 0.5 A = 2.5 W`.
- LM2576 typical efficiency at this operating point (Vin = 24 V, Vout = 5 V,
  Io = 0.5 A) is roughly **75–80 %** per the TI datasheet efficiency curves.
- Input power: `Pin ≈ Pout / η ≈ 2.5 / 0.77 ≈ 3.25 W`, drawing
  `Iin ≈ 3.25 W / 24 V ≈ 0.14 A` from the 24 V rail.
- Regulator dissipation: `Pdiss ≈ Pin − Pout ≈ 0.75 W`, shared between the IC
  switch and the external catch diode D2.

By comparison, a **linear** 24 V → 5 V regulator at 0.5 A would burn
`(24 − 5) × 0.5 = 9.5 W` — which is exactly why the buck is used here. With
~0.75 W spread across the package and diode, the LM2576 needs only a modest
clip-on heatsink (or none, with copper pour) for this load; it is rated to 3 A.

### Support passives (LM2576-5.0 fixed-output application circuit)

Values are TI datasheet "typical application" parts, chosen from the DTU
component shop (`components-inventory/dtu_component_shop(1).csv`):

| Ref | Value | Role | Shop part |
|-----|-------|------|-----------|
| C1 | **100 µF** electrolytic (≥ 35 V) | Input bulk cap, +24V→GND | `Capacitor,Electrolytic,100µF` (use a ≥ 35 V can for the 24 V rail) |
| L1 | **120 µH** | Buck inductor, switch node → +5V | `Inductor,Through-hole,120µ 1A` |
| D2 | **1N5817** (1 A Schottky) | Catch diode, cathode at switch node, anode to GND | `Diode,Schottky,1N5817` |
| C2 | **1000 µF** electrolytic (≥ 16 V) | Output cap, +5V→GND | `Capacitor,Electrolytic,1000µF 50V` |

These match the LM2576-5.0 fixed-output reference design (100 µH / 1000 µF /
1N5817 are the datasheet-recommended values for this class of load).

#### Inductor current rating

Peak inductor current ≈ `Iout + ΔI_L/2`. With Vin = 24 V, Vout = 5 V,
f = 52 kHz, L = 120 µH the ripple is

```
ΔI_L = Vout · (1 − Vout/Vin) / (L · f)
     = 5 · (1 − 5/24) / (120e-6 · 52e3)
     = 5 · 0.792 / 6.24 ≈ 0.63 A(pp)
```

so peak ≈ `0.5 + 0.32 ≈ 0.82 A`. The shop's 120 µH part is rated **1 A** —
the 1 A rating exceeds the 0.82 A peak with approximately 20 % margin, so
saturation is not a concern at this load. The 1N5817 (1 A) and the
electrolytics are comfortably within rating.

## 4. LM7812 linear (24 V → 12 V), gate-drive rail

The +12V rail only powers the two-stage BS170 gate-drive (Task 5). A gate driver
draws essentially **no static current** — its average supply current is the
charge needed to swing the heater-MOSFET gate, delivered once per PWM edge:

```
I_avg ≈ Qg · f_pwm
```

For a logic-level / standard power MOSFET `Qg ≈ 60–100 nC`. The heater PWM is
slow (reflow control runs at a few Hz to ~1 kHz; take an upper bound
`f_pwm = 1 kHz`):

```
I_avg ≈ 100 nC × 1 kHz = 0.1 mA   (gate-charge component)
```

Even adding the BS170 stages' bias/leakage and a generous margin, the +12V draw
is only **a few milliamps**. LM7812 dissipation:

```
P_diss = (Vin − Vout) × I_avg = (24 − 12) × ~3 mA ≈ 0.036 W  (< 0.1 W)
```

This is far below the LM7812's ~1 W free-air (no-heatsink) limit, so **no
heatsink is required** on U3. (Even a pessimistic 20 mA load gives
`12 × 0.02 = 0.24 W`, still no-heatsink territory.)

### Support passives (LM7812 datasheet)

| Ref | Value | Role | Shop part |
|-----|-------|------|-----------|
| C3 | **0.33 µF** (330 nF) | Input bypass, +24V→GND at U3.IN | `Capacitor,Film,330n` |
| C4 | **0.1 µF** (100 nF) | Output bypass, +12V→GND at U3.OUT | `Capacitor,Ceramic,100n` |

0.33 µF in / 0.1 µF out are the 78xx-series datasheet-recommended bypass values
(needed for stability when the regulator is far from the bulk caps).

## 5. Input cap ripple-current rating

The buck's input capacitor C1 sees the chopped switch current. Worst-case input
RMS ripple for a buck is bounded by

```
I_C,rms ≈ Iout · √(D · (1 − D)),   D = Vout/Vin = 5/24 ≈ 0.21
        ≈ 0.5 · √(0.21 · 0.79) ≈ 0.5 · 0.41 ≈ 0.20 A(rms)
```

A standard 100 µF / 35 V aluminium electrolytic is rated well above 200 mA
ripple at 100 kHz, so C1's ripple-current rating is **not** the limiting factor
here. (Voltage rating is: the 24 V rail demands a ≥ 35 V can — the 100 µF shop
part must be selected in a ≥ 35 V voltage class.) The 1000 µF output cap C2 sees
only the inductor ripple (~0.63 A pp / √12 ≈ 0.18 A rms), again within a
standard 1000 µF/16 V (or the 50 V shop part) rating.

## 6. PWR_FLAG / ERC note

`+24V` and `GND` are fed only from passive/connector and power-*input* pins, so
each carries a `PWR_FLAG` to declare a driver to ERC. `+5V` and `+12V` are
driven by the regulator **output** pins (`power_out`) and therefore need no
flag. The Task-4 power-net ERC section (`U2`, `U3`, `L1`, `D2`, `D3`, `F1`,
`J1`, `C1`–`C4`) reports **no unconnected / no-driver errors**; remaining ERC
errors belong to the controller and power-stage sections wired in Tasks 5–6.

## 7. Heater power stage + boot-safe gate drive (Task 5)

### 7.1 Topology (non-inverting, boot-safe)

```
HEATER_PWM --R2(1k)--> Q2.G        Q2.S=GND   R1(100k) Q2.G->GND pulldown
Q2.D = GD_NODE1                    R3(10k)    GD_NODE1->+12V pull-UP
GD_NODE1 --> Q3.G                  Q3.S=GND
Q3.D = GATE_MAIN                   R4(10k)    GATE_MAIN->+12V pull-UP
GATE_MAIN --R5(100R)--> Q1.G       R6(10k)    Q1.G->GND gate-source pulldown
Q1.D = HEATER_RET (= J2.2), Q1.S = GND
D4 = SMBJ33A TVS, cathode=HEATER_RET, anode=GND (drain-transient clamp)
```

**Boot-state proof.** GPIO25 (`HEATER_PWM`) floating/low/unpowered →
R1 holds Q2.G low → **Q2 off** → R3 pulls GD_NODE1 to +12 V → **Q3 on** →
Q3 clamps GATE_MAIN to ≈0 V → R5 passes 0 V to Q1.G, and R6 also holds Q1.G
to GND → **Q1 off → heater OFF**. The heater can only turn ON when the GPIO is
actively driven HIGH (Q2 on → GD_NODE1 low → Q3 off → R4 pulls GATE_MAIN to
+12 V → Q1 on). This is inherently fail-safe: no firmware, no GPIO pull, and no
power on the ESP32 is required to keep the heater off. A single inverting stage
is forbidden — it would pull the gate HIGH (heater ON) on a floating boot GPIO.

### 7.2 Q1 (IRFS4710) conduction loss

Heater: 24 V resistive element drawing ~13 A (≈ 1.85 Ω, ~310 W class). The
IRFS4710 is a low-side switch in series with the element, Rds(on) ≈ 14 mΩ
(0.014 Ω) at Vgs = 10 V / Tj = 25 °C (the DTU-shop reason for this part —
lowest Rds(on) available).

```
P_cond = I² · Rds(on) = 13² × 0.014 = 169 × 0.014 ≈ 2.37 W
```

At elevated Tj, Rds(on) rises (≈ 1.4× at 100 °C) so a hot-state worst case is
~3.3 W. A bare TO-220 in still air is ~62 °C/W (junction-to-ambient) — far too
hot for 2.4 W (ΔT ≈ 150 °C). **Q1 therefore requires a heatsink**: with a
clip-on TO-220 heatsink (~20 °C/W) plus the device Rθjc (~1 °C/W) and an
insulating pad (~1–2 °C/W), Tj ≈ Ta + 3.3 W × ~23 °C/W ≈ 25 + 75 ≈ 100 °C —
acceptable, with margin to the 175 °C rating. Use a TO-220 heatsink + thermal
pad. (The heater itself is the real power dissipator; Q1's 2.4 W is the switch
overhead.)

### 7.3 Gate drive — switching time ≪ PWM period

The control loop uses **slow PWM** (LEDC, on the order of 1 kHz or slower; PWM
period ≥ 1 ms). The IRFS4710 gate charge Qg ≈ 150 nC (total, to 10 V). With the
12 V rail through the stage-2 pull-up R4 = 10 kΩ as the dominant turn-ON path:

```
I_charge,avg ≈ V/R = 12 / 10 000 = 1.2 mA  (worst case, pull-up-limited)
t_on ≈ Qg / I = 150e-9 / 1.2e-3 ≈ 125 µs
```

Turn-OFF is faster: Q3 sinks the gate to GND through R5 = 100 Ω
(t_off ≈ Qg·R5/12 ≈ 150e-9·100/12 ... dominated by R5 ≈ a few µs). Even the
slow ~125 µs turn-ON edge is ≪ the ≥ 1 ms PWM period, so switching loss is
negligible relative to the 2.4 W conduction loss, and the edge is well within
one PWM slot. (R4 sizing trades turn-on speed against the +12 V quiescent
current when Q3 is on: 12 V / 10 kΩ = 1.2 mA through R4 — negligible for the
LM7812 rail.)

### 7.4 Vgs verification

- Gate is driven to the **+12 V** rail (GATE_MAIN pulled up by R4 when Q1 is on).
- IRFS4710 Vgs(max) = **±20 V** → 12 V is comfortably inside the safe window
  (60 % of max, headroom for ringing).
- IRFS4710 Vgs(th) ≈ **2–4 V** → 12 V ≫ Vgs(th): the device is **fully
  enhanced**, putting it deep in the ohmic region so the 14 mΩ Rds(on) figure
  applies. Logic-level 3.3 V direct drive would NOT fully enhance it (hence the
  12 V two-stage level shifter).

### 7.5 D4 TVS clamp

D4 = **SMBJ33A** (DTU-shop unidirectional TVS), standoff 33 V, clamping
≈ 53 V. Placed cathode→HEATER_RET, anode→GND it clamps inductive/parasitic
drain transients when Q1 interrupts the heater current. 33 V standoff sits
above the 24 V rail (no conduction in normal operation) and the ≈ 53 V clamp is
well below Q1's Vds(max) = **100 V**, protecting the MOSFET drain.

### 7.6 Resistor values (DTU shop, E24/E96)

| Ref | Value | Role |
|-----|-------|------|
| R1 | 100 kΩ | Q2.G → GND pulldown (floating logic input = Q2 off) |
| R2 | 1 kΩ   | HEATER_PWM → Q2.G series (limits GPIO current) |
| R3 | 10 kΩ  | GD_NODE1 → +12 V pull-UP (stage-1 load) |
| R4 | 10 kΩ  | GATE_MAIN → +12 V pull-UP (stage-2 load / Q1 turn-on) |
| R5 | 100 Ω  | GATE_MAIN → Q1.G series gate resistor (damps gate ringing) |
| R6 | 10 kΩ  | Q1.G → GND gate-source pulldown (belt-and-suspenders) |

All are standard E24 values stocked in `components-inventory/dtu_component_shop(1).csv`.
