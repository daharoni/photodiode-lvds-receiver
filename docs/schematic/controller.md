# Controller sheet (`controller.kicad_sch`, as built, revision 2 / decision 12)

Generator: `hardware/pcb/receiver-module/gen/controller.py`. Spec: `docs/schematic/rev-a-sheet-specs.md` section 7.

## Role (PROPOSED)
Slow trims and housekeeping only, never the data path: range trim (DAC_HV toward the Q(M) optimum; TIA_CTRL 20k/5k scheduling from RSSI and FPGA validity), threshold trim (DAC_TH, read back on VTH_MON), HV gating (HV_DIS; HV_MON readback), module identity and status over CAN. Hierarchical pins: in 3V3_D, HV_MON, RSSI, VTH_MON; out DAC_TH, DAC_HV, HV_DIS, SHDN_N, LE_HYS, TIA_CTRL; bidirectional CAN_H, CAN_L, AUX, AUX2.

Unprogrammed ESP32: the module decodes. TIA_CTRL floats and the Front End pull-up gives 20 k; SHDN_N pull-up keeps the comparator on. HV_DIS is pulled up on the Power sheet, so an unprogrammed module has NO APD bias; bench jumper J1 (HV FORCE ON, Power sheet) forces it on. Facts and citations: `docs/research/module-controller.md` (section numbers below). Status labels: VERIFIED (datasheet cited), PROPOSED, UNRESOLVED. Nothing here is measured or simulated; ERC and netlist export only (kicad-cli 10.0.5, scratch copy of the project with the root pointing at this sheet).

## Parts
| Ref | Part | Notes |
|---|---|---|
| U60 | ESP32-C6-MINI-1 | 3V3_D with C191 10u 0805 + C192 100n 0402 at pad 3; EN: R190 10k + C190 1u + TP60; BOOT (IO9): R191 10k + TP61; IO8: R192 10k |
| J60, U61 | USB4105-GF-A-120, USBLC6-2SC6 | programming only; VBUS only to U61 pin 5 (PWR_FLAG #FLG60); CC1/CC2 R200/R201 5.1k; shield C193 1n + R202 1M (DNP); D+/D- via R193/R194 (0R fitted, footprint allows 22R; UNRESOLVED) |
| U62 | MCP4728T-E_UN | 0x60; OUTA/B/C/D = DAC_A (test pad TP68, spare) / DAC_TH / DAC_HV / DAC_D (test pad TP69) each through 100R + 100n (R210-R213, C201-C204) |
| U63 | ADS1115IDGSR | 0x48 (ADDR = GND); AIN0..3 = HV_MON, RSSI, VTH_MON, GND (AIN3 spare, tied to GND through its RC) each through 10k + 10n (R206-R209, C197-C200); ALERT/RDY no_connect |
| U64 | SN65HVD230D | RS = R199 10k to GND; Vref_OUT no_connect; CAN_H/CAN_L hierarchical; no termination on the module |
| D60 | LED + R203 1k | status, IO23 |

## Pin map (U60 pad: GPIO -> net) - PROPOSED
5 IO2 SDA; 6 IO3 SCL; 8 EN; 12 IO0 HV_DIS; 13 IO1 SHDN_N; 15 IO6 LDAC; 16 IO7 -> R204 1k -> AUX; 17 IO12 USB_D- ; 18 IO13 USB_D+; 19 IO14 -> R205 0R (DNP) -> LE_HYS; 22 IO8 strap; 23 IO9 BOOT; 24 IO18 CAN_TX; 25 IO19 CAN_RX; 26 IO20 TIA_CTRL (hierarchical output, direct wire; the pull-up is on the Front End); 27 IO21 -> R214 1k -> AUX2 (bidirectional); 28 IO22 DAC_RDY; 29 IO23 STATUS; 30 IO17 RXD0 (TP63); 31 IO16 TXD0 (TP62). IO4, IO5, IO15: no_connect.

## Deviations from the spec
- IO10 and IO11 do not exist on the MINI-1 (MINI datasheet v1.5 Table 3-1, p10-11: 22 GPIOs). LDAC moved to IO6 (pad 15) and AUX to IO7 (pad 16). These are the JTAG MTCK/MTDO pins; USB-Serial-JTAG is the debug path, so external JTAG is given up. PROPOSED.
- ESP32-C6 (U60), USB-C (J60), USBLC6 (U61) and SN65HVD230 (U64) power pins sit on the opposite side of the symbol from what a first reading suggests (3V3/VBUS/VCC on top, GND at the bottom); wiring follows the library symbols.
- IO15 is a strapping pin, so TIA_CTRL uses IO20 (the old LOS input). The TP numbering stays within TP60-TP69; the status LED has no test pad.
- The ADS1115 ALERT/RDY pin is a no_connect (spec item: IO23 is the LED).
- DAC rows use local nets DACO_A..D before the RC filter; the filtered OUTA/OUTD nets are `DAC_A` (TP68) and `DAC_D` (TP69).

## ERC (scratch copy of the project; the root is stale, other sheets rebuilt concurrently)
Remaining on /Controller/: hier_label_mismatch for AUX2, TIA_CTRL, RSSI and VTH_MON only (the root has no sheet pins for these yet; fixed by root integration). Nothing else on this sheet. Netlist checked for U60, U62 and U63 pin-to-net mapping. Title-block title shortened so it fits the frame. Not measured or simulated.

## UNRESOLVED
USB series resistor values; auto-reset into download mode over USB (confirm on first board); DAC_TH safe default direction; firmware range-trim and TIA_CTRL scheduling algorithm; DAC_HV EEPROM default verification (General Call Read); measured 3V3_D current; antenna keep-out numbers and -1 versus -1U; VBUS back-feed against the 5 V rail; FPGA-end CAN termination (120 ohm, or 2 x 60 ohm + 4.7 nF, SLLA270 p8).
