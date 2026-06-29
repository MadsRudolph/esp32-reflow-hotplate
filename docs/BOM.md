# Bill of Materials — ESP32 reflow hotplate

> Generated from `hardware/kicad/reflow.kicad_sch` (the schematic is
> produced by `hardware/kicad/tools/build_schematic.py`). Every
> **board-soldered** line below resolves to a row in the DTU component
> shop catalogue (`components-inventory/dtu_component_shop(1).csv`),
> verified by `hardware/kicad/tools/check_bom_against_shop.py` (exit 0).
> Modules and bring-your-own hardware are listed separately under
> **External / bring-your-own**.

## Board-soldered parts (DTU component shop)

| Ref | Value | Shop Part_Number | Shop category | Description / role | Footprint |
|---|---|---|---|---|---|
| C1 | 100uF | `100µF` | Capacitor / Electrolytic | Buck input bulk cap, +24V->GND (use >=35V can) | `CP_Radial_D8.0mm_P3.50mm` |
| C2 | 1000uF | `1000µF` | Capacitor / Electrolytic | Buck output cap, +5V->GND (>=16V; 50V shop part) | `CP_Radial_D10.0mm_P5.00mm` |
| C3 | 330nF | `330n` | Capacitor / Film | LM7812 input bypass, +24V->GND | `C_Disc_D5.0mm_W2.5mm_P2.50mm` |
| C4 | 100nF | `100n` | Capacitor / Ceramic | LM7812 output bypass, +12V->GND | `C_Disc_D5.0mm_W2.5mm_P2.50mm` |
| C5 | 100nF | `100n` | Capacitor / Ceramic | MAX31855 (J3) VCC decoupling | `C_Disc_D5.0mm_W2.5mm_P2.50mm` |
| C6 | 100nF | `100n` | Capacitor / Ceramic | OLED (J4) VCC decoupling | `C_Disc_D5.0mm_W2.5mm_P2.50mm` |
| C7 | 10nF | `10n` | Capacitor / Ceramic | Encoder A debounce | `C_Disc_D5.0mm_W2.5mm_P2.50mm` |
| C8 | 10nF | `10n` | Capacitor / Ceramic | Encoder B debounce | `C_Disc_D5.0mm_W2.5mm_P2.50mm` |
| D1 | LED 5MM GRØN | `LED 5MM GRØN` | LED / 5mm | Status LED (GPIO4 via R13) | `LED_D5.0mm` |
| D2 | 1N5817 | `1N5817` | Diode / Schottky | Buck catch diode (Schottky) | `D_DO-41_SOD81_P10.16mm_Horizontal` |
| D3 | P6KE24P | `P6KE24P` | Diode / TVS | 24V input-rail TVS clamp | `D_DO-201AD_P15.24mm_Horizontal` |
| D4 | 1.5KE36A | `1.5KE36A` | Diode / TVS Zener | Heater-drain (HEATER_RET) TVS clamp | `D_DO-201AD_P15.24mm_Horizontal` |
| J1 | 2 pol skrueterminal | `2 pol skrueterminal` | Connector / Terminal | 24V input screw terminal | `TerminalBlock_bornier-2_P5.08mm` |
| J2 | 2 pol skrueterminal | `2 pol skrueterminal` | Connector / Terminal | Heater output screw terminal | `TerminalBlock_bornier-2_P5.08mm` |
| L1 | 120uH | `120µ 1A` | Inductor / Through-hole | Buck inductor (switch node -> +5V) | `L_Toroid_Vertical_L26.7mm_W14.0mm_P10.16mm_Pulse_D` |
| Q1 | IRFS4710 | `IRFS4710` | Transistor / N-MOSFET | Heater low-side power MOSFET | `TO-220-3_Vertical_LaserPads` |
| Q2 | BS170 | `BS170` | Transistor / N-MOSFET | Gate-drive stage-1 level shifter (BS170) | `TO-92_Inline_GDS` |
| Q3 | BS170 | `BS170` | Transistor / N-MOSFET | Gate-drive stage-2 level shifter (BS170) | `TO-92_Inline_GDS` |
| R1 | 100k | `100K` | Resistor / E96 Standard | Q2.G -> GND pulldown (boot-safe) | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| R2 | 1k | `1K00` | Resistor / E96 Standard | HEATER_PWM -> Q2.G series | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| R3 | 10k | `10K0` | Resistor / E96 Standard | GD_NODE1 -> +12V pull-up | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| R4 | 10k | `10K0` | Resistor / E96 Standard | GATE_MAIN -> +12V pull-up | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| R5 | 100 | `100R` | Resistor / E96 Standard | GATE_MAIN -> Q1.G series gate resistor | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| R6 | 10k | `10K0` | Resistor / E96 Standard | Q1.G -> GND gate-source pulldown | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| R7 | 3k09 | `3K09` | Resistor / E96 Standard | LM2575-ADJ FB divider top (+5V->VFB) | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| R8 | 1k00 | `1K00` | Resistor / E96 Standard | LM2575-ADJ FB divider bottom (VFB->GND) | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| R13 | 330 | `330R` | Resistor / E96 Standard | Status-LED current-limit resistor | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` |
| SW1 | Rotary 1x12 EYE | `Rotary 1x12 EYE` | Encoder / Rotary | Rotary encoder (UI) | `RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm` |
| SW2 | Pushbutton | `Pushbutton` | Hardware / Switch | Start push button (UI) | `SW_PUSH_6mm` |
| U2 | LM2575-ADJ | `LM2575` | IC / Linear | 24V->5V buck regulator (LM2575-ADJ + R7/R8 divider) | `TO-220-5_Vertical_LaserPads` |
| U3 | LM7812 | `LM7812` | IC / Voltage Regulator | 24V->12V linear regulator (gate-drive rail) | `TO-220-3_Vertical_LaserPads` |

### Consolidated purchase list (board parts)

| Qty | Shop Part_Number | Category |
|---|---|---|
| 3 | `100n` | Capacitor/Ceramic |
| 3 | `10K0` | Resistor/E96 Standard |
| 2 | `10n` | Capacitor/Ceramic |
| 2 | `1K00` | Resistor/E96 Standard |
| 2 | `2 pol skrueterminal` | Connector/Terminal |
| 2 | `BS170` | Transistor/N-MOSFET |
| 1 | `1.5KE36A` | Diode/TVS Zener |
| 1 | `1000µF` | Capacitor/Electrolytic |
| 1 | `100K` | Resistor/E96 Standard |
| 1 | `100R` | Resistor/E96 Standard |
| 1 | `100µF` | Capacitor/Electrolytic |
| 1 | `120µ 1A` | Inductor/Through-hole |
| 1 | `1N5817` | Diode/Schottky |
| 1 | `330R` | Resistor/E96 Standard |
| 1 | `330n` | Capacitor/Film |
| 1 | `3K09` | Resistor/E96 Standard |
| 1 | `IRFS4710` | Transistor/N-MOSFET |
| 1 | `LED 5MM GRØN` | LED/5mm |
| 1 | `LM2575` | IC/Linear |
| 1 | `LM7812` | IC/Voltage Regulator |
| 1 | `P6KE24P` | Diode/TVS |
| 1 | `Pushbutton` | Hardware/Switch |
| 1 | `Rotary 1x12 EYE` | Encoder/Rotary |

## External / bring-your-own (not board-soldered shop parts)

| Ref | Part | Description | Note |
|---|---|---|---|
| A1 | ESP32-DevKitV1 | 30-pin DOIT ESP32 DevKit V1 controller module | Hand-soldered 2x15 pin-header module (not a discrete shop part) |
| J3 | MAX31855 | MAX31855 K-type thermocouple amplifier breakout + thermocouple | Module on a 1x05 header; thermocouple is bring-your-own |
| J4 | OLED (SSD1306) | 0.96" SSD1306 128x64 I2C OLED module | Module on a 1x04 header |
| F1 | 24V fuse holder + element | 5x20mm cartridge fuse holder, ~15A fuse element | Fuse holder soldered; the fuse element is user-supplied (bring-your-own) |
| PSU | 24V DC supply | External 24V mains PSU feeding J1 | Bring-your-own; sized for the ~310W heater + logic |
| HTR | PTC hotplate element | 24V PTC heating plate wired to J2 | Bring-your-own heating element (~13A) |
| TF | Inline thermal fuse | Series thermal cutoff on the heater feed | Bring-your-own over-temperature safety cutoff |

