# CLAUDE.md

Guide for Claude Code sessions in this repo.

## Purpose

Optical receiver module for the next-generation wireless UCLA Miniscope data
uplink. Chain: silicon APD (primary Hamamatsu S12023-10, 6 pF; fallback S12023-05; FDS010
only as a bench fallback) on a programmable, temperature-compensated 100-220 V
bias (APD_BIAS, HV) -> OPA857 TIA (3.3 V) -> AC coupling -> OPA855 fixed gain x7 ->
low-pass -> AC coupling to a 1.65 V baseline -> TLV3605 LVDS comparator -> one LVDS pair
to an ECP5 FPGA (ULX3S first). Slow range control (APD bias, TIA 20k/5k) by the on-module
ESP32-C6 over CAN (decisions 11, 12). Target 50 Mbps line rate (8b/10b), UI = 20 ns. Board input is 5 V from the system cable or a USB-C port through a TPS2121 priority mux (decision 13); the module can be programmed and self-tested from a laptop over USB alone.
Performance beats cost. No backward compatibility with the Miniscope Zero headstage is required; the headstage is co-designed with this receiver.

## Hard rules

1. Analog-first is a firm user decision: slicing is analog and the module
   decodes with the ESP32 unprogrammed. Do not propose an MCU/ADC-first
   architecture. The ESP32-C6 (decisions 11, 12) does slow range trim only
   (APD bias DAC, TIA gain select), monitors, slow GPIO and the CAN link.
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

- `docs/` : requirements, architecture, decision log, bringup, research, datasheets, calculations
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
- Sheets are generated: `hardware/pcb/receiver-module/gen/<sheet>.py` with
  `tools/kicad_sch` (run from `tools/`). Edit the generator and regenerate
  (order: power, frontend, slicer, control, connector, controller, root; `control.kicad_sch` is the Monitor sheet);
  specs in `docs/schematic/rev-a-sheet-specs.md`, as-built notes in
  `docs/schematic/<sheet>.md`. Reference-designator ranges per sheet are in the spec.
- CLI: `/Users/daharoni/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (KiCad 10.0.5; not on PATH) (ERC, DRC, exports).
- Six sheets since decision 12: Power, Front End, Slicer, Monitor, Connector, Controller (the detector/AGC sheets are gone).
- Fab outputs under `hardware/pcb/*/fab/` are ignored by git except under `release/`.

## Key standing corrections (details in decision-log.md)

Cathode to positive bias, anode to TIA IN; use 6 pF for the S12023-10 and FDS010 alike;
AC-couple everything after the TIA (OUTN is 1.83 V); comparator slices at the AC baseline
(decision 12 superseded the VGA/AGC corrections 1, 4, 5, 7, 8, 9); TLV3605 SHDN is
active-low and not a guaranteed zero; FPGA watchdog uses an independent clock; APD bias
100-220 V (HV safety rules: 200 V creepage/clearance, series current limit, keep-out from
TIA input, HV off until the ESP32 drives HV_DIS low); module DACs (MCP4728) are 12-bit.

## Bring-up gates

- G1 fast-path proof: APD facts (VBR, gain vs bias, tempco), APD bias supply, supplies, manual-gain optical eye, TIA->VGA interface.
- G2 detector proof: high/low capture vs eye histograms, error bounds, jitter added.
- G3 closed-loop proof: loop gain/phase, anti-windup, startup and fade behavior, LOS/latch.
- G4 system proof: BER against known truth, redundancy tests, pre-order CAD checks.
Do not order PCBs before the pre-order checks in G4 pass.

## Open risks

Detector is a silicon APD S12023-10 (decision-log entry 8) on the LT8365 bias
(entry 9). Biggest risks: the APD bias supply, OPA857 behavior at 6 pF source
capacitance, post-amp clipping/recovery and comparator noise at small overdrive
(decision 12, G1 measurements), and the firmware range-control loop (M vs
temperature, 20k/5k scheduling). Received power has
not been measured; any budget is an estimate from LED datasheets. Ambient light
is multiplied by M, so the optical bandpass filter is mandatory.
