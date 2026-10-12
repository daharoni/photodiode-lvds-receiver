# Module command and telemetry protocol (CAN and USB console)

Labels: VERIFIED (cited), PROPOSED (design intent), UNRESOLVED (open). Written 2026-10-09. Nothing here is implemented, simulated or measured. Plan and boot sequence: `firmware/esp32/README.md`. Tooling facts: `docs/research/esp32-usb-tooling.md`.

One parameter model, two transports. Every parameter has one name, one numeric type, one unit and an access flag. The USB console accepts human units (`hv set 180` = volts); CAN carries the same parameter as a 32-bit integer in fixed-point units. PROPOSED.

## 1. CAN link

| Item | Value | Label |
|---|---|---|
| Physical | SN65HVD230 on IO19 (TX) / IO18 (RX) (swapped 2026-10-10 for layout); one split termination at the FPGA end; 125 kbit/s, bit time 8 us | PROPOSED (docs/research/module-controller.md s.3; SLLA270 p.8-9 for termination and stub rules, VERIFIED there) |
| Controller | ESP32-C6 TWAI: CAN 2.0, 11/29-bit IDs, 1 kbit/s to 1 Mbit/s, listen-only and self-test modes | VERIFIED (C6 DS p.4; MINI DS s.5.2.1.7 p.21) |
| ID format | 11-bit standard IDs only (29-bit not used) | PROPOSED |
| Byte order | little endian; signed integers two's complement | PROPOSED |
| Master | FPGA side (node 0); candidate: the ULX3S's own ESP32 (firmware/esp32/README.md s.10) | UNRESOLVED |
| Capacity | 14 modules (node IDs 1..14) on one bus. Node 0 = master, 15 = broadcast. More modules need a wider node field or a second bus | PROPOSED |

### 1.1 ID layout (lower ID wins arbitration)

`ID[10:8]` class, `ID[7:4]` function, `ID[3:0]` node (the sender for node-to-master frames, the target for master-to-node frames).

| Class | Meaning | Direction | Functions (ID = class x 256 + func x 16 + node) |
|---|---|---|---|
| 0 | Fault and boot events (most urgent) | node to master | 0 FAULT_EVENT 0x00n; 1 BOOT 0x01n |
| 1 | Commands and master status | master to node(s) | 0 GET 0x10n; 1 SET 0x11n; 2 IDENTIFY 0x12n; 15 LINK_ALL 0x1F0 (broadcast, node 0) |
| 2 | Responses | node to master | 0 GET/SET reply 0x20n; 1 SELFTEST_RESULT 0x21n |
| 3 | Periodic telemetry | node to master | 0 TLM_ANALOG 0x30n; 1 TLM_STATE 0x31n; 2 TLM_SLOW 0x32n |
| 7 | Enumeration | both | 0 ENUM_REQ 0x70F (master broadcast); 1 ENUM_ANNOUNCE 0x71n (node already assigned); 2 ENUM_ANNOUNCE_NEW 0x72h (unassigned node, h = 4-bit hash of its MAC); 3 ASSIGN 0x73F (master broadcast) |

Classes 4-6 are reserved. PROPOSED. A node must never transmit an ID with another node's number; two nodes sending the same ID with different data is a CAN error condition, which is why unassigned nodes use func 2 with a MAC hash in the node field.

### 1.2 Module identity and enumeration

- Unique identity: the 48-bit factory MAC read from eFuse (EFUSE_MAC, BLOCK1, TRM Table 6.3-3; field existence VERIFIED, uniqueness assumed per Espressif convention, PROPOSED). Board serial and revision: `serial` (u32) and `board_rev` (u8) in the NVS `factory` namespace, written once with the console `serial set` command (write-once by firmware rule, not by eFuse, so a mistake is recoverable by erasing NVS). PROPOSED. Burning the serial into EFUSE_USR_DATA (BLOCK3, 256 bits, irreversible) is possible later and not planned.
- Node ID: u8 in NVS, 0 = unassigned. Console `node set <1..14>` or the ENUM/ASSIGN exchange.
- ENUM flow (PROPOSED): (1) master broadcasts ENUM_REQ `[round u8, slot_ms u8]` with slot_ms >= 2 (a frame is 1.08 ms worst case, section 3). (2) Each node waits `slot = crc16(mac) mod 64` slots, then answers: assigned nodes with 0x71n, unassigned with 0x72h. Payload (8 B): `mac[6], node_id u8 (0 = unassigned), fw u8 = major<<4 | minor`. (3) Master replies ASSIGN `[mac[6], node_id u8, flags u8]` (flags bit0 = persist); the node whose MAC matches adopts the ID and stores it in NVS. (4) Repeat ENUM_REQ until no 0x72h arrives. Slot collisions are possible (same slot); the next round resolves them. UNRESOLVED: bench test with 2-3 nodes.
- Cable-to-node association (PROPOSED): the master drives the AUX line (SBU1/SBU2 tied on the USB-C receptacle, ESP32 IO7; no orientation interpretation is needed, decision 14) high on one lane at a time; every module reports `aux_in` in `TLM_STATE`/GET so the dashboard can map CAN node to LVDS lane. AUX is a spare GPIO (docs/schematic/rev-a-sheet-specs.md revision 4; AUX2 is removed). UNRESOLVED: master firmware not written.
- IDENTIFY (0x12n, DLC 1, `[seconds u8]`): the module blinks its STATUS LED in a distinctive pattern (section 6).

### 1.3 Command frames

GET (0x10n, DLC 2): `[param u16]`. SET (0x11n, DLC 6): `[param u16, value i32]`. Reply (0x20n, DLC 7): `[param u16, status u8, value i32]` (the value read back after the operation). Broadcast (node 15) commands get no reply. Status: 0 OK, 1 unknown param, 2 read-only, 3 out of range, 4 refused in current state, 5 locked (write-once), 6 busy. Only node-0 command frames are accepted. Broadcast SET (node 15) of `hv_cmd` = 1 and of `dac_hv` is ignored by the module; a broadcast `hv_cmd` = 0 (off) is accepted (PROPOSED, 2026-10-12: these two commands affect the bias and must name one node). A SET changes RAM only; persisting needs SET `save` = 1. PROPOSED.

### 1.4 Telemetry frames (node to master, 8 bytes each)

| Frame | Rate (default) | Bytes (little endian) |
|---|---|---|
| TLM_ANALOG 0x30n | 10 Hz | `hv_dv u16` (APD bias, 0.1 V, = HV_MON x 101), `rssi_mv u16` (ADS1115 AIN1 raw millivolts), `vth_mv u16` (AIN2), `m_x10 u16` (estimated M x 10; 0xFFFF = unknown) |
| TLM_STATE 0x31n | 2 Hz and on change | byte0: bits 2:0 `hv_state`, bit3 `tia` (1 = 20k), bit4 `mode` (1 = bus), bit5 `comp_en`, bit6 `link_valid` (last LINK_ALL nibble), bit7 `tia_auto`; byte1 `loop_state`; bytes 2-3 `faults u16`; bytes 4-5 `dac_hv u16` (12-bit code); byte6 `link_err` (0-7 echo of the master nibble); byte7 bits 1:0 `selftest_last` (0 never, 1 pass, 2 fail), bit2 `aux_in`, bits 4:3 `src` (0 `system` = LINK_ALL heard, 1 `host` = SOF seen without LINK_ALL, 2 `unknown`); `cc_class` and `cc_orient` are console/GET only unless 4 bits (class 2, orientation 2) are reserved in TLM_SLOW (UNRESOLVED, byte layout open) |
| TLM_SLOW 0x32n | 0.2 Hz | `uptime_s u32`, `temp_dc i16` (die temperature, 0.1 C), `can_tec u8`, `can_rec u8` |

Enumerations. `hv_state`: 0 OFF, 1 RAMP, 2 ON, 3 HOLD, 4 FAULT. `loop_state`: 0 OFF, 1 RAMP, 2 SEARCH, 3 TRACK, 4 LOS, 5 MANUAL, 6 FAULT. Fault bits: section 5.

### 1.5 Master status: LINK_ALL (0x1F0, broadcast, 20 Hz, DLC 8)

Bytes 0-6 hold one nibble per module: node n is in byte (n-1)/2, low nibble for odd n, high nibble for even n. Byte 7 is a sequence counter. Nibble: bit3 `valid` (8b/10b framing locked and code-valid), bits 2:0 error class from the FPGA's invalid-code count per 100 ms window (0 none, 1 = 1-2, 2 = 3-8, 3 = 9-32, 4 = 33-128, 5 = more than 128, 7 = LOS: no decodable activity or independent-clock timeout). Class thresholds are PROPOSED and are implemented on the FPGA side in `firmware/ecp5/rtl/lane_monitor.v` (100 ms windows; class 7 when the independent-clock watchdog reports LOS or lock was lost in the window); the gateware sends the 7 nibble bytes to the master over a UART every 50 ms as `0xA5, seq u8, nib[0..6], crc8` (firmware/ecp5/README.md s.7), and the master copies them into LINK_ALL unchanged. Invalid-code counts are not a BER measurement (standing correction 12). Receipt of LINK_ALL is also the node's bus heartbeat.

### 1.6 Fault and boot frames

FAULT_EVENT 0x00n, sent on any change of the fault word and re-sent every 1 s while a fault is latched: `faults u16, new_faults u16, hv_state u8, loop_state u8, reset_reason u8, rsvd u8`. BOOT 0x01n at every reset: `reset_reason u8, fw_major u8, fw_minor u8, fw_patch u8, node u8, rsvd[3]`. `reset_reason`: 1 power-on, 2 software, 3 brown-out, 4 task watchdog, 5 interrupt watchdog, 6 other. SELFTEST_RESULT 0x21n: `pass u8, steps_run u8, fail_mask u16, hv_peak_dv u16, rsvd u16`.

## 2. Parameter table (shared by CAN and the console)

CAN id = u16 `param`. Console unit = what you type or read. CAN unit = the i32 on the wire. Access: R read-only, W writable, S persisted by `save`, A write-once (`serial`, `board_rev`).

| Name | Param id | Console unit | CAN unit | Acc | Meaning |
|---|---|---|---|---|---|
| fw_ver | 0x0001 | text `0.1.0` | major<<16 + minor<<8 + patch | R | firmware version |
| serial | 0x0002 | integer | integer | A,S | board serial number |
| board_rev | 0x0003 | integer | integer | A,S | PCB revision |
| node | 0x0004 | 1..14 | 0..14 | W,S | CAN node ID (0 = unassigned) |
| uptime | 0x0005 | s | s | R | seconds since boot |
| hv_cmd | 0x0010 | `hv on` / `hv off` | 1 / 0 | W | HV request (drives HV_DIS through the boot gate) |
| hv_state | 0x0011 | text | enum | R | OFF/RAMP/ON/HOLD/FAULT |
| hv_set | 0x0012 | V | 0.1 V | W,S | requested APD bias trim target (see firmware README s.6 for what it means with the NTC) |
| hv_mon | 0x0013 | V (APD_BIAS) | 0.1 V | R | measured bias = AIN0 x 101 |
| hv_min | 0x0014 | V | 0.1 V | W,S | lower limit, default 100.0 V (docs/calculations/apd-bias-design.md: firmware limit to 100 V and above) |
| hv_max | 0x0015 | V | 0.1 V | W,S | upper limit, default 200.0 V; absolute cap 220.0 V in code |
| dac_hv | 0x0016 | code 0..4095 | code | W | manual DAC_HV code (4095 = minimum bias); refused unless loop is MANUAL and no self-test runs; with HV off any code is written, with HV on a slew-limited target clamped to [hv_min, hv_max] (PROPOSED), refused while ramping |
| m_est | 0x0017 | M | M x 10 | R | estimated APD gain (section 4 of firmware README) |
| m_target | 0x0018 | M | M x 10 | W,S | loop target, default 45 |
| vbr | 0x0019 | V | 0.1 V | W,S | per-unit breakdown voltage at 25 C (`cal vbr`) |
| tia | 0x0020 | `20k` / `5k` | 1 / 0 | W | OPA857 gain (IO20) |
| tia_auto | 0x0021 | `tia auto` | 1 / 0 | W,S | let the loop schedule 20k/5k |
| rssi | 0x0022 | mV | mV | R | AIN1, falls with light |
| rssi_drop | 0x0023 | mV | mV | R | idle level minus current (positive with light) |
| vth_mon | 0x0024 | mV | mV | R | AIN2 comparator threshold node |
| th | 0x0025 | mV of threshold offset | 0.1 mV | W,S | DAC_TH trim; 0 = DAC at VCM_REF (code 2048 at 3.3 V ref) |
| comp_en | 0x0026 | `comp on` / `comp off` | 1 / 0 | W | TLV3605 SHDN_N (0 = shutdown; not a guaranteed zero output, standing correction 11) |
| loop | 0x0030 | `loop auto\|manual` | 1 / 0 | W,S | range loop mode (manual holds bias and TIA) |
| loop_state | 0x0031 | text | enum | R | state machine state |
| link_valid | 0x0040 | 0/1 | 0/1 | R | from the FPGA over CAN (LINK_ALL) |
| link_err | 0x0041 | 0..7 | 0..7 | R | FPGA error class |
| faults | 0x0050 | hex | bitmask | R | latched fault word |
| faults_clear | 0x0051 | `faults clear` | 1 | W | clear latched faults that are no longer true |
| tlm_ms | 0x0060 | ms | ms | W,S | TLM_ANALOG period (min 50, default 100); other frames scale |
| bus_timeout | 0x0061 | ms | ms | W,S | master heartbeat timeout in bus mode, default 2000 |
| hv_auto | 0x0062 | 0/1 | 0/1 | W,S | enable HV automatically when a master is heard and no fault is latched (firmware README s.4 step 8c); default 0 |
| temp | 0x0070 | C | 0.1 C | R | die temperature (not APD temperature) |
| selftest_run | 0x0080 | `selftest [quick\|full]` | 1 quick, 2 full | W | start self-test (async result) |
| save | 0x0090 | `save` | 1 | W | persist all S parameters to NVS |
| reboot | 0x0091 | `reboot` | 1 | W | software reset (HV drops first) |
| defaults | 0x0092 | `defaults` | 1 | W | erase NVS user parameters (not `serial`, `board_rev`, calibration unless `defaults all`) |

PROPOSED, not frozen until the firmware exists.

## 3. Bus load arithmetic (PROPOSED, calculated)

Standard-frame length with N data bytes: 47 + 8N bits including 3 bits of interframe space; worst-case stuffing adds floor((34 + 8N - 1) / 4) bits (stuffing applies from SOF to the end of the CRC, 34 + 8N bits). N = 8: 111 + 24 = 135 bits = 1.08 ms at 8 us/bit. N = 7: 125 bits; N = 6: 115; N = 4: 95; N = 2: 75. (Stuffing rule recalled from ISO 11898 / CAN 2.0, not read from a document in this repo: UNRESOLVED citation, the arithmetic is the standard textbook worst case.)

| Traffic | Frames/s | Bits/s (135 b worst case) | Share of 125 kbit/s |
|---|---|---|---|
| One module: TLM_ANALOG 10 Hz + TLM_STATE 2 Hz + TLM_SLOW 0.2 Hz | 12.2 | 1647 | 1.3 % |
| 14 modules telemetry | 170.8 | 23 058 | 18.4 % |
| LINK_ALL, 20 Hz | 20 | 2700 | 2.2 % |
| Master commands, budget 46 frames/s | 46 | 6210 | 5.0 % |
| Total, 14 modules, defaults | about 237 | about 31 970 | about 25.6 % |

Worst case for a high-priority frame: it waits for one frame in progress, at most 1.08 ms (plus arbitration). Rate limit: `tlm_ms` minimum 50 ms keeps 14 modules x 20 Hz x 135 bits = 37.8 kbit/s (30 %) from TLM_ANALOG alone. 10 Hz is chosen because the physical signal changes at animal-motion speed (sub-10 Hz, Daniel's constraint) so 10 Hz telemetry shows every visible change; the dashboard cannot gain from more. The 25 % figure is a design budget, not a measured number; the 30-40 % ceiling used here is an engineering rule of thumb, not cited. If the bus is shared with unknown traffic, lower `tlm_ms` first.

## 4. USB console (esp_console over USB Serial/JTAG)

The console is the ESP-IDF REPL on the USB CDC port (CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG; docs/research/esp32-usb-tooling.md s.3). Line-oriented, LF-terminated; also usable from a script or Web Serial page without a terminal emulator. Replies: a human line beginning `ok` or `err <reason>`; machine lines begin with `{`. Logging is at WARN or above and every log line starts with a level letter and `(`, so parsers ignore anything not starting with `{`. PROPOSED.

| Command | Does | Param |
|---|---|---|
| `help`, `version` | list commands, firmware version | fw_ver |
| `status` / `status -j` | table of identity and live values / the same as one JSON line (includes `ver`, `sn`, `rev`, `mac`, `node`, `uptime`) | many |
| `hv on` / `hv off` | request HV; `on` runs the soft-start sequence (README s.4); refused in FAULT or when `selftest` is running | hv_cmd |
| `hv set 180` | bias target in volts, clamped to hv_min/hv_max | hv_set |
| `hv limits 100 200` | set hv_min and hv_max | hv_min, hv_max |
| `dac hv <code>` | manual DAC_HV code, only with `loop manual` | dac_hv |
| `tia 20k`, `tia 5k`, `tia auto` | OPA857 gain, or hand it to the loop | tia, tia_auto |
| `th 0`, `th -5.0` | threshold offset in mV (authority +-16 mV, docs/schematic/slicer.md) | th |
| `comp on` / `comp off` | TLV3605 SHDN_N | comp_en |
| `loop auto`, `loop manual` | range loop mode | loop |
| `m target 45` | loop target gain | m_target |
| `get <name>`, `set <name> <value>` | generic access to any parameter in section 2 in console units | all |
| `stream on [ms]`, `stream off` | start/stop NDJSON telemetry, default 100 ms, minimum 50 ms | tlm_ms |
| `cal vbr`, `cal vop <M> <V>`, `cal rssi-idle`, `cal clear` | calibrations, firmware README s.6 | vbr |
| `save`, `defaults [all]` | persist / erase parameters | save, defaults |
| `selftest [quick\|full]` | built-in test, section 6 | selftest_run |
| `identify [s]` | blink LED | (IDENTIFY) |
| `serial set <n>`, `rev set <n>` | write-once identity | serial, board_rev |
| `node set <1..14>` | CAN node ID | node |
| `dac show` / `dac provision` | read MCP4728 input registers and EEPROM / program the power-on defaults (guarded, asks `dac provision confirm`) | |
| `can stat` | TEC, REC, bus state, frames seen, master heartbeat age | |
| `faults`, `faults clear` | list / clear | faults |
| `reboot` | reset | reboot |

### 4.1 JSON telemetry line (`stream on`)

One JSON object per line, keys always present, unknown values `null`:

```
{"t":123456,"node":3,"sn":17,"ver":"0.1.0","up":812,
 "hv":"on","hv_v":142.3,"hv_set":142.0,"dac_hv":2310,
 "m":48.2,"rssi_mv":1923,"rssi_drop":41,"vth_mv":1651,"th_mv":0.0,
 "tia":"20k","comp":1,"loop":"TRACK","link":1,"err":0,
 "faults":0,"temp_c":31.4,"can_tec":0,"can_rec":0,"mode":"usb","src":"host","cc_class":"default","cc_orient":"cc1"}
```

| Field | Source | Notes |
|---|---|---|
| t | ms since boot | |
| node, sn, ver, up | identity | |
| hv, hv_v, hv_set, dac_hv | hv_state, AIN0 x 101, set point, DAC code | bias is HV_MON x 101; ADS1115 LSB 125 uV at the 4.096 V range gives about 12.6 mV of bias per count (calculated) |
| m | estimated M | null until calibrated (README s.6) |
| rssi_mv, rssi_drop | AIN1 | relative, not a calibrated optical power |
| vth_mv, th_mv | AIN2, threshold trim | |
| tia, comp | OPA857 gain, SHDN_N | |
| loop | state | |
| link, err | FPGA-reported link_valid and error class | null in standalone USB mode (no master) |
| faults, temp_c, can_tec, can_rec, mode, src, cc_class, cc_orient | fault word, die temperature, CAN counters, `usb` or `bus`, source (`system`, `host`, `unknown`), CC class (`default`, `1.5A`, `3.0A`, `none`) and orientation (`cc1`, `cc2`, `none`) from IO4/IO5 | cc_* are hints only |

The CAN master (FPGA side) emits the same keys from the TLM frames so one dashboard handles both transports. PROPOSED.

## 5. Fault word (u16, latched; shared by CAN and console)

| Bit | Name | Condition | HV action |
|---|---|---|---|
| 0 | I2C_DAC | MCP4728 NACK or readback mismatch | HV off |
| 1 | I2C_ADC | ADS1115 NACK or conversion timeout | HV off |
| 2 | DAC_EEPROM | EEPROM defaults not as expected at boot | HV stays off, no enable accepted |
| 3 | HV_OVER | AIN0 x 101 above hv_max + 5 V | HV off |
| 4 | HV_UNDER | bias did not reach target within the ramp timeout, or collapsed below 70 % of set | HV off |
| 5 | HV_STUCK | bias above 20 V more than 30 s after HV_DIS was driven high (should have decayed; LT8365 output is not actively discharged) | none possible; report |
| 6 | CAN_BUSOFF | TWAI bus-off | HV off |
| 7 | CAN_TIMEOUT | no LINK_ALL for bus_timeout (bus mode only) | HV off |
| 8 | BROWNOUT | last reset was brown-out | HV stays off until commanded |
| 9 | WDT | last reset was a watchdog | HV stays off until commanded |
| 10 | RSSI_RAIL | RSSI below 0.3 V (TIA output pulled to rail) with TIA at 5k | none, telemetry |
| 11 | TIA_5K_SAT | RSSI rail at 5k and bias at hv_min: no further range | none |
| 12 | SELFTEST | last self-test failed | none |
| 13 | LOOP_LIMIT | bias pinned at hv_min or hv_max for more than 10 s | none |
| 14 | NVS | parameters failed CRC or limits at boot; factory defaults loaded (firmware README s.4 step 2) | none, telemetry |
| 15 | reserved | | |

PROPOSED. Which faults force HV_DIS high follows firmware README s.5.

## 6. Self-test (`selftest`, console and CAN)

Defined in `firmware/esp32/README.md` s.8: steps, pass criteria and the LED patterns; the result is one JSON line, also sent as SELFTEST_RESULT on CAN:

```
{"selftest":{"mode":"full","sn":17,"ver":"0.1.0","pass":true,
 "steps":[{"id":"i2c","r":"pass"},{"id":"dac_eeprom","r":"pass"}, ...],
 "hv_peak_v":107.2,"hv_floor_v":107.1,"usb_ma_est":null}}
```

Step result values: `pass`, `fail`, `skip`, `info`. UNRESOLVED: nothing measured; every window in the README is a first guess until the first board.
