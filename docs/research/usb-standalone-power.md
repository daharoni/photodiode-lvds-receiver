# USB-standalone power, buttons and VBUS sensing: research and proposed spec text

Note (2026-10-09): decision 14 replaced the two-source mux (TPS2121, `+5V_CABLE`, PWR_SRC, VBUS_SENSE) described below with a single-VBUS TPS259631 eFuse on one 24-pin USB-C connector. The USB-standalone requirement itself is unchanged. Current power-path design: `docs/research/usbc-power-path.md` and `docs/research/decision-14-draft-usbc-single-connector.md`; spec: `docs/schematic/rev-a-sheet-specs.md` revision 4. The sections below are kept as history, and their TPS2121 sections are superseded.

Date 2026-10-09. Scope: let one receiver module be powered, programmed and self-tested from a laptop USB-C port alone (no FPGA, no system cable), and coexist safely when USB and the 12-pin system cable are both plugged in. This is research and a proposal only. Nothing was implemented in the generators, sheets, spec, decision log or architecture. Nothing here was simulated or measured.

Labels: VERIFIED (checked against a cited document, revision and page), PROPOSED (design intent), UNRESOLVED (open). Page numbers are PDF pages unless stated.

Documents used (all in `docs/datasheets/` with MANIFEST rows unless marked):
- "TPS2121": TI TPS2120/TPS2121 SLVSEA3F, Aug 2020 (`tps2121.pdf`; printed page = PDF page).
- "LM66100": TI LM66100 SLVSEZ8A, Jun 2019 (`lm66100.pdf`).
- "HDG": Espressif ESP32-C6 Hardware Design Guidelines, "Release master" docs build dated 2026-10-09, no version number (`esp32-c6-hw-design-guidelines.pdf`).
- "MINI DS": ESP32-C6-MINI-1/-1U datasheet v1.5. "C6 DS": ESP32-C6 series datasheet v1.5.
- "TRM": ESP32-C6 Technical Reference Manual Version 1.2 (`docs/datasheets/esp32-c6-trm.pdf` and `docs/research/downloads/esp32-c6-trm/`, added by another session; read here, no new copy made).
- "TPS799": SBVS056L (p.4 abs max). "LT8365": Rev. A (via `docs/calculations/apd-bias-design.md`, "ABD"). "SN65HVD230": SLOS346O.
- "USB-C guide": Espressif IoT Solution "USB Type-C Hardware Design Guide" web page, saved as `docs/research/downloads/usb-standalone/espressif-usbc-hw-guide.html` (retrieved 2026-10-09; vendor web page, not a standards document; untrusted download, parsed with `python3 -I`).
- Not obtained: the USB Type-C Specification and USB 2.0 Specification themselves (usb.org), and the ST USBLC6-2 datasheet (st.com was unreachable from the sandbox: `curl` returned no connection, WebFetch timed out). Every claim that would need them is labelled accordingly.

## 0. Recommendation in five lines

1. Merge the two 5 V sources with a TI TPS2121 priority power mux (U5, already in the lab library with a 12-pad RUX0012A footprint): system cable on IN1 (priority), USB VBUS on IN2 (fallback), OUT is the existing internal rail named `+5V`, so U1, U3, U4 and the HV gate need no change. The cable rail is renamed `+5V_CABLE` on the Connector sheet and on the new Power hierarchical input.
2. The TPS2121 hardware blocks reverse current in both directions (fast reverse-current blocking plus a 1 uA-class leakage spec), so USB can never source the FPGA 5 V rail and the cable rail can never back-drive the laptop; with both plugged in the cable powers the module and USB carries only data.
3. Worst-case 5 V input current is about 0.19 A (about 0.24 A with 25 % margin), below the 0.5 A default USB limit; the mux current limit is set to its minimum (RILM 100 k, 1.24 A typ), which doubles as the "current-limited 5 V switch" that `apd-bias-design.md` section 7 item 10 asked for. It does NOT protect a 0.5 A budget; the laptop port does.
4. Add RESET (EN) and BOOT (IO9) tactile switches (new library part needed; none exists), fit R193/R194 as 22 ohm per the HDG, add a VBUS_SENSE divider on IO4 and the mux status pin PWR_SRC on IO5, so firmware knows "USB present" and "which source is powering".
5. HV safety rules are unchanged; USB power adds one new condition (the HV supply must also tolerate a USB source that is weaker than the cable): the LT8365 EN/UVLO already trips at 3.1 to 3.8 V, far below any legal USB rail, so no change, but the USB-alone self-test must keep HV_DIS default-off and set DAC_HV before enabling.

## 1. Power path

### 1.1 Candidates

| Option | Priority (cable over USB) | Reverse blocking | Soft start / inrush | Current limit | Max input | Parts and library status |
|---|---|---|---|---|---|---|
| (a) TPS2121 mux | Yes. IN1 wins when PR1 >= VREF (1.01 to 1.10 V); otherwise IN2 (TPS2121 p.18 Table 9-3) | Fast reverse-current blocking in each channel (p.15, 9.3.6); standby leakage IN to OUT <= +/-1 uA at 25 C (+/-5 uA to 85 C) for |VIN - VOUT| <= 5 V (p.7) | SS pin: settling timer then a CSS-set output slew; 100 nF = 780 V/s, 1 uF = 88 V/s at 5 V (p.12-13, Table 9-1) | Programmable, RILM 18 to 100 k; ILM = 65.2 / RILM^0.861 (RILM in kohm, p.13 Eq. 2); fast OCP trip at 2.4 x ILM (p.14) | 24 V abs max, 22 V operating (p.6) | Symbol `AharoniLab_Power:TPS2121RUXR` and footprint `AharoniLab_Package_DFN_QFN:RUX0012A` exist (checked 2026-10-09: 12 pads; symbol pins IN1 7, IN2 2, OUT 1+8, PR1 6, OV1 5, OV2 4, CP2 3, ST 9, ILM 10, SS 11, GND 12, which match the TPS2121 pin table p.4-5). Symbol `Validated: No` |
| (b) 2 x LM66100 | No native priority. CE compares against VIN, not logic: ON at CE - VIN < -80 mV (max), OFF at > 0 to +80 mV (LM66100 p.5), so with two near-equal 5 V rails the higher one wins and the band between is undefined. Priority needs extra logic | Yes, comparator blocks reverse flow (p.1) | None specified beyond turn-on time ~40 us (p.5) | None (1.5 A abs) | 6 V abs max on VIN, VOUT, CE (p.4); a hot-plug ring on a 5 V cable can exceed that | No LM66100 symbol or SC-70-6 footprint in the lab library: two new parts to add. Rejected |
| (c) Schottky OR | No. Higher rail minus Vf wins | Yes (diode) | None | None | Any | A 30 to 40 V low-Vf Schottky is not in the library (DFLS1150 is 150 V, high Vf); costs 0.3 to 0.45 V at the load (typical Schottky behaviour, not read from a datasheet here: PROPOSED). Rejected |

PROPOSED choice: (a). Reasons: it is the only option with an explicit priority input, controlled switchover, soft start, OV supervision, a 24 V input rating that survives hot-plug rings (TI's own hot-plug plot rings a 12 V source above 30 V with a 15 ft cable and no TVS, p.32; a 5 V source scales to roughly 13 V by the same ratio, still under 24 V: ratio is arithmetic on that plot, PROPOSED), and a status output. RON 56 mohm typ, 70 mohm max at 25 C, 85 mohm at 85 C (p.7), so at 0.24 A the dropout is 13 to 20 mV. Its own current limit is a free bonus. Quiescent current is 300 uA typ, 400 uA max from the enabled input and 15 uA typ from the disabled one (p.7), irrelevant against a 190 mA load (an LM66100 pair would be 0.15 uA each, p.5; not a deciding factor here).

### 1.2 Priority: the system cable wins, USB is the fallback

PROPOSED, with reasons:
- The cable rail is the FPGA board's 5 V (shared by several modules). Powering from it when present keeps the laptop port out of the system and keeps USB data-only during a real experiment, which is also the path measured for G3/G4.
- If the cable rail is absent or sags, the module keeps running from USB. That is a feature for self-test and costs the FPGA rail nothing.
- Counter-argument considered: USB priority would keep a battery-less FPGA board unloaded. Rejected, because the module draws about 0.2 A from either and the cable is the intended supply.

Truth table (TPS2121 p.18, Table 9-3, with CP2 grounded and PR1 above VREF means IN1): only one input valid (above UV, below OV): that input powers OUT; both valid and PR1 >= VREF: IN1 (cable); both valid and PR1 < VREF: IN2 (USB); neither: OUT Hi-Z. ST is high when OUT is Hi-Z or IN1, low when IN2 powers the output (p.18). UVLO: IN rising 2.5/2.65/2.8 V, falling 2.4/2.55/2.7 V (p.7).

Coexistence behaviour, derived from the table and the leakage spec (PROPOSED, not tested):
- USB alone: IN1 floats; ILK from OUT to IN1 is <= +/-1 uA at 25 C (p.7) so the J50 +5V pins sit near 0 V with negligible leakage; ST low.
- Cable alone: IN2 (VBUS) sees the same <= 1 uA leakage; the VBUS net sits near 0 V; nothing sources the laptop.
- Both: IN1 powers OUT, IN2 is off; reverse-current blocking (threshold IRCB 0.2 to 2 A, response 10 us, p.7) stops any current from OUT into either input. USB current into the FPGA rail is impossible through the mux; the only other VBUS loads are the USBLC6 and the VBUS_SENSE divider (about 21 uA at 5.25 V), none of which connect to +5V_CABLE.
- Cable unplugged while running on it: PR1 falls, the mux switches to IN2 after tSW 100 us typ (CP2 low, p.7). OUT must hold up for that time: 100 us x 0.24 A / (about 20 uF effective) is about 1 V of droop (arithmetic; effective capacitance after X5R derating is an estimate), which the 3V3 and 3V3_D LDOs (1.7 V headroom) and the LT8365 UVLO (falling min 3.09 V at the EN divider) ride through. PROPOSED, not measured.

PR1 divider (so priority is dropped when the cable rail is bad, not only when absent): R35 294 k (+5V_CABLE to PR1), R36 100 k (PR1 to GND). With VREF rising 1.01 to 1.10 V and falling 0.99 to 1.09 V (p.8) the cable regains priority at 3.98 to 4.33 V and loses it at 3.90 to 4.10 V (calculated; resistor tolerance ignored). Cable minimum is 4.75 V with 5 percent rail, so the cable is always selected when healthy. Hysteresis is only about 20 mV on PR1 (about 0.08 V on the rail): a slowly sagging cable could chatter between sources; the mux switchover is controlled, so this is acceptable. UNRESOLVED: chatter behaviour with a real ULX3S rail. Divider current 13 uA at 5.25 V. CP2 to GND so XREF/fast switchover is not used (CP2 grounded = ignored, p.18).

OV supervisors (recommended): OV1 and OV2 each from a 464 k / 100 k divider (R39/R40 on +5V_CABLE, R41/R42 on VBUS). The channel turns off when OVx reaches VREF (rising 1.01 to 1.10 V, p.8): trip 5.58 to 6.20 V (calculated). Why: TPS799 absolute maximum on IN is 7.0 V (recommended maximum 6.5 V, TPS799 p.4 and the Recommended Operating Conditions), so a miswired 12 V on the cable pin would destroy U1; TPS2121 OV removes the channel and the other source takes over. OV pin range is 0 to 5.5 V (TPS2121 p.6, satisfied: 1.06 V at trip). The OV divider on VBUS is not strictly needed for legal USB (VBUS max is 5.25 V in USB 2.0 and a Type-C source is 5 V at default; neither number was read in the specs here: UNRESOLVED) but costs two 0603 parts and guards a faulty adapter. TPS7A2033 and LT8365 abs max were not rechecked.

### 1.3 Inrush, soft start and current limit

- CSS: 220 nF X7R 10 V (C32). Table 9-1 (p.13): 100 nF gives 780 V/s and 1 uF gives 88 V/s at 5 V; the relation is close to 1/C, so 220 nF is about 350 to 400 V/s, a 5 V ramp in about 13 to 14 ms (estimate by scaling the table, PROPOSED). Inrush is C x dV/dt: for about 25 uF effective behind the mux, 25 uF x 400 V/s is about 10 mA plus load (TI example, p.24: dV/dt limit = IINRUSH / CL). Same value as the LT8365 SS capacitor, so it adds no new part value.
- The settling time before the first source is selected (tSETx, p.12) has no stated formula in the text (only Figure 9-3). UNRESOLVED: measure the time to +5V on first plug-in; budget about one to a few tens of ms.
- Input capacitors: C33 4.7 uF 10 V X5R 0805 on +5V_CABLE and C34 4.7 uF on VBUS. TI recommends a larger input capacitor to damp cable ringing (p.33, section 11); the USB limit on capacitance seen at attach (10 uF in USB 2.0, from memory) was not checked against the spec: UNRESOLVED. Because the module's bulk capacitance (C1 10 uF, LT8365 input filter 10 uF + 4.7 uF + 10 uF at 50 V rating, LDO input caps) sits behind the soft-start mux, the capacitance the USB port sees directly is only C34, plus the mux's own settle behaviour. This is another argument for the mux over a diode.
- Current limit: RILM = 100 k (R38) is the maximum allowed value (RILM 18 to 100 k, p.6), giving ILM = 65.2 / 100^0.861 = 1.24 A typ; the datasheet table gives 1.5 A typ (1 to 2 A) at 80 k (p.8), so at 100 k the minimum limit is probably just above 1 A (UNRESOLVED: the table has no 100 k row, only the equation). The fast short-circuit trip is 2.4 x ILM, about 3 A, 25 ms off-time (p.14). Role: protects U5 and the cable and satisfies `apd-bias-design.md` section 7 item 10 ("add a polyfuse or current-limited 5 V switch if the rail can source amps"): an LT8365 output short can pull its input to the switch limit 1.5 to 2.7 A (LT8365 p.3 via ABD). With USB, the laptop port's own limit (not known, 0.5 A default per the USB-C guide) acts first; a port current trip during a faulted HV start is therefore possible: PROPOSED consequence, accepted for a bench self-test, with HV started at a low DAC code (section 4).
- Regulation behaviour: when ILM is reached the device regulates, dissipating the drop and heating; thermal shutdown 160 C with auto-restart (p.13-14). RthJA 72.2 C/W (p.6).

### 1.4 What a 5.1 k Rd advertises, and the budget

- VERIFIED (USB-C guide, vendor page, tolerance +/-20 % stated for all): the source advertises current by its pull-up Rp: 56 k default power, 22 k 1.5 A at 5 V, 10 k 3 A at 5 V (for a source driving Rp from 5 V). The sink's Rd is 5.1 k on each of CC1/CC2 (R200/R201). The sink's 5.1 k Rd does not advertise anything; it only says "a sink is attached". Default power means 500 mA for USB 2.0 and 900 mA after USB 3.x enumeration ("Important" note in the same guide). The module has no CC voltage reader, so it must assume the default: budget 500 mA.
- UNRESOLVED (not read in the USB 2.0 spec): a USB 2.0 device that is unconfigured is supposed to draw at most 100 mA before enumeration and up to 500 mA after configuration (recalled, not verified). The module's analog 3V3 rail and ESP32 alone exceed 100 mA at attach (section 1.5). Laptop root ports do not generally enforce 100 mA, but an unpowered bus-powered hub port may. PROPOSED: document "use a laptop root port or a powered hub"; optional Rev B mitigation is a load switch on the analog 3V3 enabled after enumeration (not recommended for Rev A).

### 1.5 Worst-case 5 V input current (derivation)

All numbers are datasheet maximums or estimates already in the repo; the LT8365 line uses an ASSUMED 70 % efficiency from ABD ("ASM"); nothing measured.

| Item | Current | Basis |
|---|---|---|
| 3V3 analog (U1 TPS79901) | 66 mA | `docs/schematic/power.md` revision 2: OPA857 26.8 + OPA855 19.5 + TLV3605 17.5 + OPA2320 about 2 mA, all maxima. An LDO passes its load current 1:1 to its input (plus its own Iq, not read, a few tens of uA) |
| ESP32-C6, radio never started | 38 mA | C6 DS Table 6-7 p.28 as quoted in `module-controller.md` section 1: CPU running at 160 MHz with all peripheral clocks on 38 mA (27 mA with peripheral clocks off). The datasheet has no "radio never started" figure; flash-write peaks are not in the tables: UNRESOLVED |
| SN65HVD230 | 17 mA | ICC max, p.7 of SLOS346O (via `module-controller.md` section 2); typical 10 mA |
| MCP4728 | 1.4 mA | IDD max (DS22187E p.5, via `module-controller.md` section 4) |
| ADS1115 | 0.3 mA | 150 uA typ continuous (SBAS444E, via the same section), doubled as margin |
| Status LED + 3V3_D loss through U4 | 2 mA | R203 1 k from 3.3 V to a LED, about 1.3 to 2 mA |
| 3V3_D subtotal (U4 passes it 1:1) | about 59 mA | sum of the five lines above |
| LT8365 APD bias at 220 V, 0.5 mA load | 36 mA | Pout = 220 V x 0.5 mA = 110 mW, plus 5.8 mW divider (26.5 uA at 220 V, ABD) plus 0.5 mW HV_MON; Pin = Pout / 0.7 = 166 mW (ASM); at 4.75 V that is 35 mA, plus 1.2 mA active IQ (LT8365 p.3 via ABD): about 36 mA |
| LT8365 design bound, 1 mA load | 69 mA | ABD script: Pin 0.314 W at 1 mA, 220 V (66 mA at 4.75 V) plus 1.2 mA IQ; the real APD photocurrent is clamped near 150 to 172 uA (ABD section 4) so the true load is below 0.5 mA |
| TPS2121 quiescent | 0.4 mA | 400 uA max (p.7) |

Total at 0.5 mA HV load: 66 + 59 + 36 + 0.4 = about 161 mA. Total at the 1 mA design bound: 66 + 59 + 69 + 0.4 = about 194 mA, call it 0.19 A at 4.75 V, or about 0.97 W at 5 V. With 25 % margin for the unmeasured items (ESP32 flash/boot peaks, LDO Iq, efficiency at tiny loads which is probably worse than 70 % in pulse-skip: "hundreds of uA" extra, LT8365 p.9 via ABD): about 0.24 A. Margins: 0.24 A is 48 % of the 500 mA default limit, 16 % of the 1.5 A Rp=22 k level, and 20 % of the TPS2121 1.24 A typical limit.
The case that breaks the budget is the radio: Wi-Fi TX peak 251 to 382 mA (C6 DS Tables 6-4 to 6-6, via `module-controller.md`) exceeds U4's 300 mA rating and would push total above 0.5 A; the radio MUST stay disabled (already a rule on the Power sheet).

## 2. BOOT and RESET buttons

- VERIFIED recommended EN circuit: RC delay R = 10 k, C = 1 uF at the EN/CHIP_PU pin, adjusted to the power supply (MINI DS p.40; HDG p.10). EN must not float (HDG p.10). Already built (R190 10 k, C190 1 uF, TP60). VERIFIED that HDG p.10 also says: slow rise, frequent power cycling or an unstable supply may need a supervisor with a threshold around 3.0 V; the mux adds a 13 ms soft start on 5 V but 3V3_D follows 5 V through an LDO, so the 10 ms RC (R x C) is similar to the rail ramp: UNRESOLVED, check the 3V3_D rise versus EN rise on the scope. A 3.0 V supervisor is not proposed for Rev A.
- VERIFIED boot strapping: GPIO9 low with GPIO8 high at the rising edge of EN enters Joint Download Boot (MINI DS Table 4-3 p.13; HDG p.15 Table 4: Download Boot GPIO8 = 1, GPIO9 = 0). GPIO9 has a weak internal pull-up and R191 10 k to 3V3_D is already fitted; R192 10 k holds GPIO8 high.
- Espressif publishes no debounce network for EN or BOOT in the documents read (I did not find one in the HDG or MINI DS). PROPOSED: the existing R190 + C190 is the RESET debounce (a press discharges C190 to GND and release recharges it over about 10 ms, tau = R x C = 10 ms); BOOT needs no debounce because the strap is only sampled at EN rising; no extra capacitor on IO9 (an added capacitor would slow the strap and is unnecessary). I recommend NOT adding a series resistor between the button and EN or IO9 (not in the documents). Static protection: the button sits on the board edge and a finger discharge on EN is possible; an EN-side ESD diode is not in any document read: UNRESOLVED, fit a DNP 0402 footprint for a TPD1E10B06-class diode only if the review wants it (`AharoniLab_Passive:TPD1E10B06DPYR` exists in the lab library; its footprint `DPY0002A` is in `AharoniLab_Package_DFN_QFN`).
- Auto-reset over USB: VERIFIED that the USB Serial/JTAG controller can reset the chip and enter download mode from the host: RTS/DTR on the CDC-ACM port map to "set download mode flag" (RTS 0, DTR 1) and "reset ESP32-C6" (RTS 1, DTR 0) (TRM PDF p.1030, Table 32.3-2; MINI DS p.20 "Host controllable chip reset and entry into download mode"). So buttons are NOT needed for ordinary flashing with esptool-style tooling. They stay recommended because (a) with an empty flash the first download needs Joint Download Boot (HDG p.30), (b) HDG p.30 states USB auto-download is disabled when the application disables the USB PHY, uses USB for host or another device class, or re-assigns the USB pins to other peripherals, and recommends retaining control of the strapping pins, and (c) eFuses can disable the reset/download path (TRM p.1030). Whether the esptool sequence actually works with this board's R193/R194 and the USBLC6 in series was not tested: UNRESOLVED (confirm on first board). See also `docs/research/esp32-usb-tooling.md` (another session's file, not read).
- Library: no pushbutton or switch symbol exists in the lab library (`symbols/` has Passive, Connector, MCU, Power, ... Misc; grep for SW, Push, tactile found nothing) and no switch footprint exists in `footprints/`. New parts are needed:
  - Preferred part PROPOSED: C&K PTS810 SJM 250 SMTR LFS, 4.2 x 3.2 mm top-actuated SMD tactile, 2.5 mm tall. KiCad stock footprint `Button_Switch_SMD:SW_SPST_PTS810` exists (checked in the installed KiCad 10 library; description cites the PTS810 datasheet). Digi-Key P/N CKN10504CT-ND (from memory, not verified; not checked for stock).
  - Smaller alternative: Omron B3U-1000P, 3 x 2.5 mm, footprint `Button_Switch_SMD:SW_SPST_B3U-1000P` (exists in the stock library). Harder to press; not preferred.
  - Library PR contents (see `~/Projects/kicad-lab-library/docs/CONTRIBUTING.md` and `CONVENTIONS.md`): (1) `library_rules.yaml`: add a `AharoniLab_Switch` category (reference prefix `SW`, pins min 2, max 4), because the validator ties categories to reference prefixes and `AharoniLab_Misc` requires `U` and 3 or more pins; (2) new `symbols/AharoniLab_Switch.kicad_sym` with symbol `PTS810` (Validated No, Datasheet URL, MPN, Description, ki_keywords); (3) new footprint directory `footprints/AharoniLab_Switch_SMD.pretty/` (the library groups footprints by type or package family) with `SW_SPST_PTS810.kicad_mod`; (4) new `3dmodels/AharoniLab_Switch_SMD.3dshapes/` STEP model, with the footprint `(model ...)` path using `${AHARONI_LAB_KICAD_LIB}` (CI enforces it); (5) `sym-lib-table` and `fp-lib-table` rows, best regenerated with `python -m validator --generate-tables`. The receiver project's library table references `${AHARONI_LAB_KICAD_LIB}`, so no project change beyond the new lib names.

## 3. USB details

- D+/D- series resistors: VERIFIED that the HDG recommends reserving series resistors on D+/D- (initial value 22 or 33 ohm) and capacitors to ground (initially unpopulated), placed close to the chip (HDG PDF p.18, section 1.3.13 with its USB RC schematic; also note there that D+ fluctuates at power-up and an external pull-up gives a stable initial level, relevant only if D+ state at boot matters). MINI DS Figure 9-1 (p.40) leaves R6/R7 and C7/C8 as TBD, consistent with this. PROPOSED: fit R193/R194 as 22 ohm (not 0 ohm) and add two DNP 0402 capacitor footprints to GND (C206, C207) on the chip side of R193/R194. Note this is not a "direct connection" recommendation; 0 ohm is not the Espressif starting value. Whether 22 ohm helps or hurts at the USBLC6 and a USB4105 receptacle was not tested: UNRESOLVED (trim on first board). The USBLC6 sits upstream of the resistors (connector side), as built, which is the usual order.
- VBUS sensing: VERIFIED that the ESP32-C6 USB Serial/JTAG chapter in TRM v1.2 has no VBUS-detect pin or register (a search of the full TRM text for "vbus" and "session valid" found nothing; absence of a statement, not a positive spec). The controller does let software override the D+/D- pull resistors (USB_SERIAL_JTAG_PAD_PULL_OVERRIDE, DP_PULLUP; pull-up 2.2 k or 1.1 k, TRM PDF p.1042). PROPOSED: a divider on a GPIO is therefore the only way for firmware to learn "USB present". R215 100 k from VBUS to VBUS_SENSE, R216 150 k to GND, C205 1 nF to GND, on IO4: ratio 0.6, giving 2.64 V at 4.4 V, 3.15 V at 5.25 V and 3.3 V at 5.5 V (calculated); logic high needs 0.75 x VDD = 2.475 V (MINI DS Table 6-3 p.26, via `module-controller.md`), so it reads high above VBUS = 4.1 V and low below about 1.4 V (VIL 0.25 x VDD). Load 21 uA at 5.25 V. The pin stays at or below 3.3 V even at VBUS 5.5 V, but if VBUS were present with 3V3_D absent the pin would be driven above the rail through the pin clamp diode: not possible here because 3V3_D is derived from VBUS whenever USB is the only source, and the cable source gives 3V3_D with VBUS floating.
- Mux status on IO5: PWR_SRC from TPS2121 ST (open-drain, pull-up 6 to 20 kohm, p.6; R37 10 k to 3V3_D on the Power sheet). High = cable (or OUT Hi-Z), low = USB. Together with VBUS_SENSE this gives firmware four states: cable only, USB only, both (cable powering), neither. IO4 and IO5 are strapping pins (MTMS, MTDI) but only select SDIO sampling edges (MINI DS Table 4-4 p.14, `module-controller.md`); SDIO is unused, so a defined level at reset is harmless: PROPOSED, based on the table not on a test. Both are currently `no_connect`.
- CC/shield: unchanged (R200/R201 5.1 k, C193 + R202 DNP shield). No problem found. The USB-C guide says CC1 and CC2 each need a 5.1 k pull-down (same page).
- ESD: the symbol `USBLC6-2SC6` as wired (pins 1 and 6 = I/O1, 3 and 4 = I/O2, 5 = VBUS, 2 = GND; the lab symbol pin map was read in the library) puts D+ on pins 1/6, D- on pins 3/4 and VBUS on pin 5, so all three nets are on the part. UNRESOLVED: whether pin 5 contains a TVS clamp to GND or only steering diodes was NOT verified, because the ST datasheet could not be downloaded here (web-search snippets of third-party copies gave only per-I/O ratings: 5 V standoff, 6 V minimum breakdown, 10 V at 1 A, and said nothing reliable about a VBUS clamp). Do not count the USBLC6 as the VBUS surge protection. VBUS surge and hot-plug protection is the TPS2121 (24 V abs max, section 1.1) with C34 4.7 uF on VBUS; a TVS on VBUS is not proposed because the mux's 24 V rating covers the estimated ring, PROPOSED.
- USB backdrive when only the cable powers the module and a USB cable is plugged into an unpowered or sleeping host port: the C6 pull-up on D+ is on whenever the USB Serial/JTAG controller is enabled (not explicit in the docs read; the override register above exists), so D+ could be driven to 3.3 V through 1.1 to 2.2 k (TRM p.1042) into an unpowered host. Magnitude and behaviour UNRESOLVED; firmware can clear the pull-up when VBUS_SENSE is low.
- Ground: laptop USB ground, FPGA board ground and the cable ground all join; a ground loop or an offset between an isolated battery laptop and a mains-earthed FPGA supply is possible. UNRESOLVED: not analysed. The shield network (C193 + R202 1 M DNP) is already provisioned.

## 4. Interaction with HV safety

Rules that still apply unchanged (decision log, `power.md`, `apd-bias-design.md` section 7, `CLAUDE.md`):
- HV is OFF until the ESP32 drives HV_DIS low: R33 100 k pulls the Q3 gate to 3V3_D so an unprogrammed or Hi-Z ESP32 means EN/UVLO is pulled to GND (`power.md` HV disable logic). With USB alone, a freshly flashed or unflashed module powers up with HV off. The J1 "HV FORCE ON" jumper stays DNP in anything that is plugged into a laptop.
- Series current limit (R1/R2 chain 5.95 mA at 220 V short, ABD), 200 V creepage and clearance (1.5 mm external, 2 mm from the TIA input), no bare APD_BIAS pad, HV_MON is the only observation point, HV net class 1.0 mm: all layout and parts rules are independent of the 5 V source. The APD current clamp is unchanged.
- Bring-up order from `module-controller.md` section 4 still applies: program MCP4728 EEPROM so DAC_HV powers up at the safe end, read it back, then release HV_DIS. USB-alone self-test must follow it; the ESP32 must not release HV_DIS because "USB is present".

What USB power changes:
- Weaker source: a USB rail may sag more than the FPGA 5 V rail, especially with a long cable and an adapter dongle. LT8365 EN/UVLO is set by R22/R23 200 k / 200 k from 5V_HVIN: rising 3.15 to 3.80 V and falling 3.09 to 3.29 V (ABD section 3.2, LT8365 p.4: EN/UVLO rising 1.576/1.68/1.90 V, falling 1.545/1.60/1.645 V). Any legal USB or cable rail (about 4.4 V and up at the module after the mux drop) is above that threshold by more than 1 V, so UVLO does not guard against a USB rail sag in the range that matters; U1 and U4 would drop out first only below about 3.5 V (their dropout was not read here). The 5 V sag at boost start is the pi filter and the LT8365 DCM pulse (0.36 A peak at 220 V, 1 mA, ABD) through the mux's 56 to 70 mohm and the cable: tens of mV, not a UVLO concern (arithmetic, not measured).
- Real concern: a faulted or shorted HV node pulling the input to the TPS2121 limit (about 1.2 A) collapses a USB port that trips at 0.5 to 1 A, taking the logic rails with it. Mitigation (PROPOSED): in USB-alone mode, firmware raises HV in steps starting from the low-bias end of DAC_HV (code 0xFFF = 55 V hardware floor, ABD section 3.2) and watches HV_MON and the ADS1115 supply sag before each step; stored HV energy at 220 V is 2.3 mJ and discharges in about 0.5 s (ABD). This is a firmware item for the other agent, noted here only.
- The SS ramp of the mux and the LT8365's own soft start (176 ms upper bound, ABD) are in series: HV rises only after +5V is stable, which matches "sequence EN after the TIA rail".
- Hot-unplug of USB with HV on (cable absent): 5 V collapses, Q3 and the EN divider lose 3V3_D/5V together, HV discharges through the divider with tau about 0.37 s (ABD section 4). The gate R33 pull-up has no 3V3_D during the collapse, which is the existing UNRESOLVED floating-gate corner in `power.md`; unchanged by this proposal but now reachable by a user yanking a cable: still UNRESOLVED.
- Self-test coverage limit: with no FPGA and no optical source the self-test can verify supplies, DAC set and read back (DAC_TH vs VTH_MON), HV_MON versus DAC_HV, RSSI dark level, TIA_CTRL toggle and the STATUS LED. It cannot prove the comparator or LVDS output, because LVDS_P/N goes only to J50. UNRESOLVED: whether to add a comparator-output tap to an ESP32 GPIO (none free except IO15, a strapping pin) or an on-board optical test LED. Not proposed here.

## 5. Proposed spec text (ready to lift into `rev-a-sheet-specs.md`)

Naming decision, with the least churn: only the Power sheet consumes the cable rail (`grep +5V` in `gen/*.py` shows it appears in connector.py, power.py, root.py only). Keep `+5V` as the name of the merged rail inside the Power sheet (U1, U3 via 5V_HVIN, U4, C1, C2 and the net labels are untouched) and rename the cable side: Connector output pin and the Power hierarchical input become `+5V_CABLE`. VBUS gets a new hierarchical output on the Controller sheet and a hierarchical input on the Power sheet. `3V3_D` already goes Power to Controller, so PWR_SRC is a new Power to Controller pin. The alternative (keep `+5V` on the cable side and rename every consumer net to `5V_SYS`) touches many more labels.

### Section 1 (power) additions

Replace the "Pins" line of section 1 with: `Pins: in +5V_CABLE, VBUS, DAC_HV, HV_DIS; out 3V3, 3V3_D, APD_BIAS, HV_MON, PWR_SRC.` Reference ranges: add U5, R35-R42, C32-C34 (inside the existing Power ranges).

Replace section 1.1 with:

```
### 1.1 Input: source mux U5 (TPS2121RUXR)
- U5 AharoniLab_Power:TPS2121RUXR, footprint AharoniLab_Package_DFN_QFN:RUX0012A. IN1 (pin 7) = +5V_CABLE (system cable, priority). IN2 (pin 2) = VBUS (USB-C, fallback). OUT (pins 1 and 8) = +5V, the internal merged rail used by U1, U3 (via the L2 pi filter) and U4. GND pin 12. CP2 (pin 3) = GND.
- Priority: PR1 (pin 6) from +5V_CABLE through R35 294k / R36 100k (1 %, 0603): cable selected above about 3.98-4.33 V rising, dropped below about 3.90-4.10 V. PROPOSED (TPS2121 SLVSEA3F p.7-8 VREF 0.99-1.10 V, p.18 Table 9-3).
- Overvoltage: OV1 (pin 5) from +5V_CABLE through R39 464k / R40 100k; OV2 (pin 4) from VBUS through R41 464k / R42 100k (1 %, 0603); trip about 5.6-6.2 V, below the TPS799 7.0 V abs max (SBVS056L p.4). PROPOSED.
- ST (pin 9): R37 10k pull-up to 3V3_D, output net PWR_SRC (hierarchical output): high = cable (or OUT Hi-Z), low = USB. VERIFIED behaviour p.18; R range 6-20k p.6.
- ILM (pin 10): R38 100k to GND (maximum RILM; ILM = 65.2/RILM^0.861 = 1.24 A typ, p.13). SS (pin 11): C32 220 nF X7R 10 V 0603 to GND (about 350-400 V/s, p.13 Table 9-1 scaled). PROPOSED; settling and inrush time UNRESOLVED until measured.
- Caps: C33 4.7 uF 10 V X5R 0805 on +5V_CABLE at IN1, C34 4.7 uF 10 V X5R 0805 on VBUS at IN2, as close to the pins as possible; C1 10 uF and C2 100 nF stay on the +5V (OUT) rail. No TVS (24 V abs max, p.6).
- No back-feed: reverse-current blocking and <= 1 uA leakage (p.7, p.15) mean neither source is back-driven. Both present: cable powers, USB idle. J50 pins 1,2 are +5V_CABLE. PWR_FLAG on +5V_CABLE moves to the root (see below); +5V (U5 OUT, power_out) needs no flag.
- Budget: worst case about 0.19 A (0.24 A with margin) from +5V, against 0.5 A USB default and U5 ILM 1.24 A typ (docs/research/usb-standalone-power.md section 1.5). Radio must stay disabled.
```

Add to section 1.5 (3V3_D): "R37 ST pull-up returns to 3V3_D." Add a line to 1.4: "USB-alone: HV_DIS default-off and the DAC_HV safe-end rule are unchanged; firmware starts HV at the low-bias end in steps."

Root changes (spec section 0 / root.py): Power sheet pins: in `+5V_CABLE`, `VBUS`, DAC_HV, HV_DIS; out 3V3, 3V3_D, APD_BIAS, HV_MON, `PWR_SRC`. Connector output pin `+5V` becomes `+5V_CABLE` (connector.py line 26: hier name; local label on pin 2 follows). Controller gets new pins `VBUS` (output) and `PWR_SRC` (input). Root wires: Connector.+5V_CABLE to Power.+5V_CABLE; Controller.VBUS to Power.VBUS; Power.PWR_SRC to Controller.PWR_SRC. The root `#FLG04` PWR_FLAG moves from Power.+5V to the +5V_CABLE net; VBUS already has `#FLG60` inside the Controller sheet (keep). Update the Hierarchical-nets paragraph: `+5V_CABLE` (Connector to Power), `VBUS` (Controller to Power), `PWR_SRC` (Power to Controller).

### Section 7 (controller) additions

Replace the Pins line with: `Pins: in 3V3_D, HV_MON, RSSI, VTH_MON, PWR_SRC; out DAC_TH, DAC_HV, HV_DIS, SHDN_N, LE_HYS, TIA_CTRL, VBUS; bidirectional CAN_H, CAN_L, AUX, AUX2.`

Add:

```
- USB-C: VBUS now leaves the sheet as hierarchical output `VBUS` (to Power U5 IN2) in addition to U61 pin 5. Keep #FLG60 PWR_FLAG. CC1/CC2 R200/R201 5.1k, shield C193 + R202, unchanged.
- D+/D- series R193/R194: change from 0R to 22R (HDG esp-hardware-design-guidelines-esp32c6 PDF p.18: reserve 22/33 ohm and capacitors to ground). Add C206 and C207 (DNP, C_0402_1005Metric_N, 4.7 pF-class placeholder, value TBD on the first board) from USB_DP_E and USB_DM_E to GND on the module side of R193/R194.
- Buttons (new lab part, see library list): SW60 RESET from EN to GND, SW61 BOOT from BOOT (IO9) to GND, footprint AharoniLab_Switch_SMD:SW_SPST_PTS810. TP60/TP61 stay in parallel. R190 10k + C190 1u is the reset debounce and the recommended EN RC (MINI DS p.40, HDG p.10); no series resistor, no extra capacitor on IO9. Fit both buttons even though RTS/DTR auto-reset exists (TRM p.1030): recovery for empty flash or a disabled USB PHY (HDG p.30).
- VBUS sense: R215 100k (VBUS to VBUS_SENSE), R216 150k (VBUS_SENSE to GND), C205 1n (VBUS_SENSE to GND), 0603/0402; VBUS_SENSE -> U60 pad 9 (IO4), replacing its no_connect. High above VBUS about 4.1 V.
- PWR_SRC: hierarchical input from Power U5 ST (open-drain, pull-up on the Power sheet) -> U60 pad 10 (IO5), replacing its no_connect. Low = USB powers the module, high = cable.
- Pin map additions: 9 IO4 VBUS_SENSE; 10 IO5 PWR_SRC. IO15 only remains no_connect.
- Text: firmware states by (VBUS_SENSE, PWR_SRC): (0,1) cable only; (1,0) USB only (standalone self-test); (1,1) both, cable powers; (0,0) cannot occur with power present. The ESP32 must not clear HV_DIS on the basis of these inputs alone.
```

### Section 6 (connector) change

Rename the hierarchical output `+5V` to `+5V_CABLE` and the J50 pin 1 hierarchical label to match; pin 2 local label follows. Text: "+5V_CABLE is the system rail, mux priority input, never sourced by the module".

## 6. Lab-library parts that must be added

| Part | Symbol library | Footprint library | Digi-Key | Needed for |
|---|---|---|---|---|
| C&K PTS810 SJM 250 SMTR LFS tactile switch (SW60, SW61) | new `AharoniLab_Switch.kicad_sym` (symbol `PTS810`, plus `library_rules.yaml` category `AharoniLab_Switch`, reference SW, pins 2 to 4) | new `AharoniLab_Switch_SMD.pretty/SW_SPST_PTS810` (+ 3D model dir `AharoniLab_Switch_SMD.3dshapes`), `sym-lib-table` and `fp-lib-table` rows | CKN10504CT-ND (from memory, not verified) | RESET and BOOT |

Already in the library and sufficient: TPS2121RUXR (symbol + RUX0012A footprint, Validated No), USB4105-GF-A-120 and its footprint, USBLC6-2SC6, generic R/C with `R_0603_1608Metric_N`, `C_0603_1608Metric_N`, `C_0805_2012Metric_N`, `C_0402_1005Metric_N`. No LM66100 and no new Schottky are needed (rejected). The TPS2121 symbol property says `Validated No`: its first use here is the real validation, via a library PR flipping it after bring-up.

## 7. UNRESOLVED items (consolidated)

1. USB Type-C Specification and USB 2.0 Specification were not read: VBUS limits (5.25/5.5 V), the 100 mA unconfigured and 500 mA configured rules, and the 10 uF attach capacitance limit are recalled, not verified. Effect: C34 4.7 uF and the "unconfigured 100 mA" warning (section 1.4) are PROPOSED.
2. ST USBLC6-2 datasheet not read (download blocked): VBUS pin clamp behaviour, line capacitance, clamping voltage, peak pulse current unknown. Section 3.
3. RILM = 100 k limit minimum (table has no 100 k row; equation gives 1.24 A typ), and tSET/first-plug settling time of the mux (no formula in the datasheet text).
4. Cable-rail chatter near the PR1 threshold with a real ULX3S rail; 13 ms soft start versus the 10 ms EN RC at 3V3_D; EN-side ESD diode.
5. Esptool-style auto reset through R193/R194 (22 ohm) and the USBLC6, untested; value of 22 ohm and the optional D+/D- capacitors.
6. D+ pull-up backdrive into an unpowered host when the cable powers the module; firmware pull-up override exists (TRM p.1042), policy unresolved.
7. Ground offset or loop between laptop USB ground and the FPGA/cable ground.
8. Holes in the current estimate: ESP32 flash write and boot peaks, LDO quiescent currents, LT8365 efficiency at 0.5 mA and 220 V (70 percent is an assumption; pulse-skip IQ extra "hundreds of uA"), TPS7A2033 and LT8365 abs max not rechecked. Worst case 0.19 A, 0.24 A with margin, not measured.
9. HV safety: a port current trip during a faulted HV start; the existing floating Q3 gate corner when 3V3_D collapses during a USB unplug; firmware stepping policy (other agent's file).
10. Self-test coverage: no way to prove comparator and LVDS output without an FPGA or an optical source.
11. Digi-Key number for PTS810 not verified; PTS810 versus B3U choice; library PR mechanics (new category, new .pretty, tables) are as read in CONTRIBUTING.md and CONVENTIONS.md but not executed.
12. USB Serial/JTAG controller absence of any VBUS-detect feature is based on a text search of TRM v1.2, not on a statement.
