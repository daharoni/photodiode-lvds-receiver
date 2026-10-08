# CLAUDE.md

Guide for Claude Code sessions in this repo.

## Purpose

Optical receiver module for the next-generation wireless UCLA Miniscope data
uplink. Chain: silicon APD (primary Hamamatsu S12023-10, 6 pF; fallback S12023-05; FDS010
only as a bench fallback) on a programmable, temperature-compensated 100-220 V
bias (APD_BIAS, HV) -> OPA857 TIA (3.3 V) -> AC-coupled VCA821 (+/-3.7 V) -> level shift to
~1.65 V -> TLV3605 LVDS comparator -> one LVDS pair to an ECP5 FPGA (ULX3S
first). Target 50 Mbps line rate (8b/10b), UI = 20 ns. Board input is 5 V.
Performance beats cost. No backward compatibility with the Miniscope Zero headstage is required; the headstage is co-designed with this receiver.

## Hard rules

1. Analog-first is a firm user decision. Do not propose an MCU/ADC-first
   architecture. The on-module ESP32-C6 (decision 11) is a supervisor only:
   trims (I2C DAC), monitors (I2C ADC), slow GPIO, CAN link to the FPGA side.
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
  (order: power, frontend, slicer, control, detector, connector, mcu, root);
  specs in `docs/schematic/rev-a-sheet-specs.md`, as-built notes in
  `docs/schematic/<sheet>.md`. Reference-designator ranges per sheet are in the spec.
- CLI: `/Users/daharoni/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (KiCad 10.0.5; not on PATH) (ERC, DRC, exports).
- The fast high/low level detector is built as a disconnectable, swappable sub-circuit.
- Fab outputs under `hardware/pcb/*/fab/` are ignored by git except under `release/`.

## Key standing corrections (details in decision-log.md)

AC-couple OPA857 outputs into the VCA821; cathode to positive bias; use 6 pF
for the S12023-10 and FDS010 alike; rails +/-3.7 V (VCA821 min +/-3.5 V); AGC is a true integrator
(100k/47 nF); VSPAN/VMID use matched 10k 0.1% networks; TLV3605 SHDN is
active-low and not a guaranteed zero; FPGA watchdog uses an independent clock;
APD bias 100-220 V (HV safety rules: 200 V creepage/clearance, series current limit, keep-out from TIA input); module DACs (MCP4728) are 12-bit; HOLD_N is a direct FPGA wire, never via CAN.

## Bring-up gates

- G1 fast-path proof: APD facts (VBR, gain vs bias, tempco), APD bias supply, supplies, manual-gain optical eye, TIA->VGA interface.
- G2 detector proof: high/low capture vs eye histograms, error bounds, jitter added.
- G3 closed-loop proof: loop gain/phase, anti-windup, startup and fade behavior, LOS/latch.
- G4 system proof: BER against known truth, redundancy tests, pre-order CAD checks.
Do not order PCBs before the pre-order checks in G4 pass.

## Open risks

Detector is a silicon APD S12023-10 (decision-log entry 8) on the LT8365 bias
(entry 9). Biggest risks: the APD bias supply, the fast high/low
detector, the AGC loop (VG upper bound vs VCA821 2 V range, anti-windup; LOS
does not freeze the integrator, entry 10), and OPA857 behavior at 6 pF source capacitance. Received power has
not been measured; any budget is an estimate from LED datasheets. Ambient light
is multiplied by M, so the optical bandpass filter is mandatory.
