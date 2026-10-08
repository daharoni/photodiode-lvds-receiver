# Controller sheet (`controller.kicad_sch`, as built)

Generator: `hardware/pcb/receiver-module/gen/controller.py`. Spec: `docs/schematic/rev-a-sheet-specs.md` section 7. Facts and citations: `docs/research/module-controller.md` (section numbers below). Status labels: VERIFIED (datasheet cited), PROPOSED, UNRESOLVED. Nothing here is measured or simulated; ERC and netlist export only (kicad-cli 10.0.5, scratch copy of the project with the root pointing at this sheet).

## Parts
| Ref | Part | Notes |
|---|---|---|
| U60 | ESP32-C6-MINI-1 | 3V3_D with C191 10u 0805 + C192 100n 0402 at pad 3; EN: R190 10k + C190 1u + TP60; BOOT (IO9): R191 10k + TP61; IO8: R192 10k |
| J60, U61 | USB4105-GF-A-120, USBLC6-2SC6 | programming only; VBUS only to U61 pin 5 (PWR_FLAG #FLG60); CC1/CC2 R200/R201 5.1k; shield C193 1n + R202 1M (DNP); D+/D- via R193/R194 (0R fitted, footprint allows 22R; UNRESOLVED) |
| U62 | MCP4728T-E_UN | 0x60; OUTA/B/C/D = DAC_GAIN/DAC_TH/DAC_HV/DAC_D each through 100R + 100n (R210-R213, C201-C204) |
| U63 | ADS1115IDGSR | 0x48 (ADDR = GND); AIN0..3 = HV_MON, VSPAN, VG, VMID each through 10k + 10n (R206-R209, C197-C200); ALERT/RDY no_connect |
| U64 | SN65HVD230D | RS = R199 10k to GND; Vref_OUT no_connect; CAN_H/CAN_L hierarchical; no termination on the module |
| D60 | LED + R203 1k | status, IO23 |

## Pin map (U60 pad: GPIO -> net) - PROPOSED
5 IO2 SDA; 6 IO3 SCL; 8 EN; 12 IO0 HV_DIS; 13 IO1 SHDN_N; 15 IO6 LDAC; 16 IO7 -> R204 1k -> AUX; 17 IO12 USB_D- ; 18 IO13 USB_D+; 19 IO14 -> R205 0R (DNP) -> LE_HYS; 22 IO8 strap; 23 IO9 BOOT; 24 IO18 CAN_TX; 25 IO19 CAN_RX; 26 IO20 LOS; 27 IO21 PGOOD_VGA; 28 IO22 DAC_RDY; 29 IO23 STATUS; 30 IO17 RXD0 (TP63); 31 IO16 TXD0 (TP62). IO4, IO5, IO15: no_connect.

## Deviations from the spec
- IO10 and IO11 do not exist on the MINI-1 (MINI datasheet v1.5 Table 3-1, p10-11: 22 GPIOs). LDAC moved to IO6 (pad 15) and AUX to IO7 (pad 16). These are the JTAG MTCK/MTDO pins; USB-Serial-JTAG is the debug path, so external JTAG is given up. PROPOSED.
- ESP32-C6 (U60), USB-C (J60), USBLC6 (U61) and SN65HVD230 (U64) power pins sit on the opposite side of the symbol from what a first reading suggests (3V3/VBUS/VCC on top, GND at the bottom); wiring follows the library symbols.
- The ADS1115 ALERT/RDY pin is a no_connect (spec item: IO23 is the LED).
- DAC rows use local nets DACO_A..D before the RC filter; the filtered OUTD net is `DAC_D` (TP68).

## ERC (scratch copy, root edited to point at this file)
Remaining: hier_label_mismatch (root has no sheet pins for the new nets yet, fixed by integration) and power_pin_not_driven on U60 3V3 (3V3_D is not wired at the root yet). Nothing else on this sheet.

## UNRESOLVED
USB series resistor values; auto-reset into download mode over USB (confirm on first board); DAC_GAIN/DAC_TH safe default direction; DAC_HV EEPROM default verification (General Call Read); measured 3V3_D current; antenna keep-out numbers and -1 versus -1U; VBUS back-feed against the 5 V rail; FPGA-end CAN termination (120 ohm, or 2 x 60 ohm + 4.7 nF, SLLA270 p8).
