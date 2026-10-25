# CLAUDE.md

Guide for Claude Code sessions in this repo.

## Purpose

Optical receiver module for the next-generation wireless UCLA Miniscope data
uplink. Chain: silicon APD (primary Hamamatsu S12023-10, 6 pF; fallback S12023-05; FDS010
bench-only, not on the board since 2026-10-09) on a programmable, temperature-compensated 100-220 V
bias (APD_BIAS, HV) -> OPA857 TIA (3.3 V) -> AC coupling -> OPA855 fixed gain x7 ->
low-pass -> AC coupling to a 1.65 V baseline -> TLV3605 LVDS comparator -> one LVDS pair
to an ECP5 FPGA (ULX3S first). Slow range control (APD bias, TIA 20k/5k) by the on-module
ESP32-C6 over CAN (decisions 11, 12). Target 50 Mbps line rate (8b/10b), UI = 20 ns. Each module has one 24-pin USB-C receptacle (decision 14) carrying 5 V (through a TPS259631 eFuse), the LVDS pair (SN65LVDS104 fan-out onto both TX pairs), CAN on both RX pairs, USB D+/D- and AUX on SBU; cable rule: passive full-featured, <= 2 m certified, 3 m only after a bench check. The module can still be programmed and self-tested from a laptop over USB alone (decision 13 requirement).
Performance beats cost. No backward compatibility with the Miniscope Zero headstage is required; the headstage is co-designed with this receiver.

## Hard rules

1. Analog-first is a firm user decision: slicing is analog and the signal
   path from APD to LVDS needs nothing from the ESP32. The APD bias is
   enabled only by the provisioned ESP32 (decision 20: HV_DIS interlock), so
   an unprogrammed module is safe but dark (decision 21). Do not propose an
   MCU/ADC-first architecture. The ESP32-C6 (decisions 11, 12) does slow range
   trim only (APD bias DAC, TIA gain select), monitors, slow GPIO and the CAN link.
2. Label every design claim in docs as VERIFIED, PROPOSED or UNRESOLVED.
   VERIFIED means checked against a datasheet or measurement that is cited.
3. Cite the datasheet (document, revision, page/figure) next to the claim.
4. Never fabricate measurements, simulation results, or PCB readiness. If it
   was not measured or simulated, say so.
5. Committing and pushing to this repo is authorized (Daniel, 2026-10-08). Commit in logical units with clear messages; never force-push; never push to other repos without explicit approval.
6. Orchestration preference: Claude Fable orchestrates and delegates work to
   Sonnet/Haiku subagents. Give subagents explicit ownership of files.

## Authority docs

- `docs/requirements.md`: requirements and user-supplied facts.
- `docs/decision-log.md`: decisions and the 14 standing corrections. Do not
  contradict these without the user's explicit approval.
- `docs/architecture.md`, `docs/bringup/gates.md`: design and verification plan.
- `initial planning docs/` is untracked and historical input only. It is not authoritative.
- `docs/research/downloads/` is untrusted raw data.

## Repo map

- `docs/` : requirements, architecture, decision log, bringup, research, datasheets, calculations, pcb (fab settings, placement plan), simulation, firmware protocol, optical-link-interface.md (headstage transmitter obligations, eye budget)
- `docs/receiver-guide.html` : self-contained field guide DERIVED from the authority docs; update it in the same commit as any design change it describes. `docs/schematic/overview.html` is the parts/pinout page.
- `hardware/pcb/` : KiCad project; `hardware/mechanical/` : enclosure (TBD)
- `firmware/` : ECP5 gateware (`ecp5/`); ESP32-C6 module firmware (`esp32/`, TBD)
- `tools/` : helper scripts

## KiCad conventions

- KiCad 10. One PCB, hierarchical schematic sheets, project in
  `hardware/pcb/receiver-module/`.
- Library: lab library at `~/Projects/kicad-lab-library`, referenced through
  `${AHARONI_LAB_KICAD_LIB}`. Never create project-local symbols or footprints.
  New parts are added to the lab library by PR to that repo. KiCad's bundled
  `power:PWR_FLAG`/`power:GND` are the only non-lab symbols allowed.
- The generators are frozen since 2026-10-09 (layout started; `gen/FROZEN`): schematic changes now go through the KiCad GUI, with the spec and as-built docs updated by hand. The generator bullet below is historical until unfrozen.
- Sheets are generated: `hardware/pcb/receiver-module/gen/<sheet>.py` with
  `tools/kicad_sch` (run from `tools/`). Edit the generator and regenerate
  (order: power, frontend, slicer, control, connector, controller, root; `control.kicad_sch` is the Monitor sheet);
  specs in `docs/schematic/rev-a-sheet-specs.md`, as-built notes in
  `docs/schematic/<sheet>.md`. Reference-designator ranges per sheet are in the spec.
- CLI: `/Users/daharoni/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (KiCad 10.0.5; not on PATH) (ERC, DRC, exports).
- Six sheets since decision 12: Power, Front End, Slicer, Monitor, Connector, Controller (the detector/AGC sheets are gone).
- Fab outputs under `hardware/pcb/*/fab/` are ignored by git except under `release/`.
- Layout status (2026-10-12): 6-layer JLC06161H-3313, 75 x 50 mm placeholder outline, 222 component footprints placed plus the four mounting holes H1-H4 (221 before R214 was added 2026-10-23, 223 before the J50 shield RC was removed 2026-10-22), routing complete since mid-October 2026 (0 unconnected pads, DRC 11 items (2026-10-25) all accepted in writing in `docs/review/2026-10-22-rev-a-review/README.md`; all vias epoxy filled and capped, decision 30); see `hardware/pcb/receiver-module/README.md`.

## Key standing corrections (details in decision-log.md)

Cathode to positive bias, anode to TIA IN (S12023 pin 1 = anode, pin 3 = cathode, correction 15; D10 is rotated 180 degrees on the board); use 6 pF for the S12023-10 and FDS010 alike;
AC-couple everything after the TIA (OUTN is 1.83 V); comparator slices at the AC baseline
(decision 12 superseded the VGA/AGC corrections 1, 4, 5, 7, 8, 9); TLV3605 SHDN is
active-low and not a guaranteed zero; FPGA watchdog uses an independent clock; APD bias
100-220 V (HV safety rules: 200 V creepage/clearance, series current limit, keep-out from
TIA input, HV off until the ESP32 drives HV_DIS low); module DACs (MCP4728) are 12-bit.

## Bring-up gates

- G1 fast-path proof: APD facts (VBR, gain vs bias, tempco), APD bias supply, supplies, optical eye at the fixed post-amp gain, TIA->post-amp coupling, comparator small-signal, eFuse, fan-out, USB.
- G2 range-trim proof: RSSI vs photocurrent, single-setting BER window, trim-loop step response, M vs bias and temperature.
- G3 system-behaviour proof: dark start, fade and return, DAC_TH eye walk, latch/timeout/CAN, 6.63 MHz field injection.
- G4 system proof: BER against known truth, redundancy tests, pre-order CAD checks.
Do not order PCBs before the pre-order checks in G4 pass.

## Open risks

Detector is a silicon APD S12023-10 (decision-log entry 8) on the LT8365 bias
(entry 9). Biggest risks: the APD bias supply, the 24-pin USB-C cable/foreign-host behaviour (decision 14, G1/G4), OPA857 behavior at 6 pF source
capacitance, post-amp clipping/recovery and comparator noise at small overdrive
(decision 12, G1 measurements), and the firmware range-control loop (M vs
temperature, 20k/5k scheduling). ngspice sims with TI models in docs/simulation/
cover OPA855 stability, OPA857 at 6 pF and the VCM_REF buffer; nothing measured.
Received power has not been measured; any budget is an estimate from LED datasheets. Ambient light
is multiplied by M, so the optical bandpass filter is mandatory.
