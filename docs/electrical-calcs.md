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
| L1 | **100 µH** | Buck inductor, switch node → +5V | `Inductor,Through-hole,100µ 0.66A` |
| D2 | **1N5817** (1 A Schottky) | Catch diode, cathode at switch node, anode to GND | `Diode,Schottky,1N5817` |
| C2 | **1000 µF** electrolytic (≥ 16 V) | Output cap, +5V→GND | `Capacitor,Electrolytic,1000µF 50V` |

These match the LM2576-5.0 fixed-output reference design (100 µH / 1000 µF /
1N5817 are the datasheet-recommended values for this class of load).

#### Inductor current rating — note

Peak inductor current ≈ `Iout + ΔI_L/2`. With Vin = 24 V, Vout = 5 V,
f = 52 kHz, L = 100 µH the ripple is

```
ΔI_L = (Vout · (Vin − Vout)) / (Vin · L · f)
     = (5 · 19) / (24 · 100e-6 · 52e3) ≈ 0.76 A(pp)
```

so peak ≈ `0.5 + 0.38 ≈ 0.88 A`. The shop's 100 µH part is rated **0.66 A** —
adequate for the average current but **below the calculated peak**. This is the
one passive whose rating is marginal; see Concerns. A 100 µH inductor rated
≥ 1 A (saturation) is preferred for production. The 1N5817 (1 A) and the
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
only the inductor ripple (~0.76 A pp / √12 ≈ 0.22 A rms), again within a
standard 1000 µF/16 V (or the 50 V shop part) rating.

## 6. PWR_FLAG / ERC note

`+24V` and `GND` are fed only from passive/connector and power-*input* pins, so
each carries a `PWR_FLAG` to declare a driver to ERC. `+5V` and `+12V` are
driven by the regulator **output** pins (`power_out`) and therefore need no
flag. The Task-4 power-net ERC section (`U2`, `U3`, `L1`, `D2`, `D3`, `F1`,
`J1`, `C1`–`C4`) reports **no unconnected / no-driver errors**; remaining ERC
errors belong to the controller and power-stage sections wired in Tasks 5–6.
