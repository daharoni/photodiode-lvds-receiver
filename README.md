# Photodiode LVDS Receiver

Optical receiver module for the next-generation wireless UCLA Miniscope data
uplink. It succeeds the receiver used with the Miniscope Zero link
(bioRxiv 10.64898/2026.09.05.745822). Target: 50 Mbps line rate (8b/10b,
40 Mbps payload, UI = 20 ns).

Signal chain: silicon APD (primary Hamamatsu S12023-10; FDS010 PIN only as a bench
fallback) on a programmable, temperature-compensated 100-220 V bias
(APD_BIAS) -> OPA857 transimpedance
amplifier -> AC-coupled VCA821 variable-gain amplifier -> level shift ->
TLV3605 comparator with LVDS output -> one LVDS pair to an ECP5 FPGA (ULX3S
first), which does clock recovery, 8b/10b decode and redundant-lane merging.
An analog AGC loop (fast high/low capture -> VMID slicer threshold, VSPAN ->
integrator -> VGA gain) keeps the signal centered. The architecture is
analog-first by decision; see `docs/decision-log.md`.

The module exposes only 5 V power, ground, one LVDS pair and debug pads. It is
intended for a shielded aluminum housing with a swappable optical bandpass
filter.

## Status

Pre-G1. No schematic, no PCB, no hardware, no measurements yet. Component
choices are provisional until the bring-up gates in `docs/bringup/gates.md`
pass. The APD bias supply, the fast high/low detector and OPA857 behavior at 6 pF are the largest open risks.

## Repo map

| Path | Contents |
|---|---|
| `docs/requirements.md` | Requirements, user answers, open items |
| `docs/architecture.md` | Block-by-block design and reasoning |
| `docs/decision-log.md` | Dated decisions and standing corrections |
| `docs/bringup/gates.md` | Gates G1-G4 and checklists |
| `docs/research/` | Component research; `downloads/` is raw untrusted input |
| `docs/datasheets/` | Datasheets |
| `docs/calculations/` | Design calculations |
| `hardware/pcb/` | KiCad project (`receiver-module/`) |
| `hardware/mechanical/` | Enclosure and filter holder (TBD) |
| `firmware/` | ECP5 gateware; SAMD51 code (location undecided) |
| `tools/` | Helper scripts |
| `CLAUDE.md` | Guide for Claude Code sessions |

## Opening the KiCad project

Requires KiCad 10 and the lab component library from
`~/Projects/kicad-lab-library`, installed with that repo's install script so
that `${AHARONI_LAB_KICAD_LIB}` resolves. Then open
`hardware/pcb/receiver-module/receiver-module.kicad_pro` (once it exists).
New parts are added to the lab library by PR, not as project-local symbols.

## Documents to read first

1. `docs/requirements.md`
2. `docs/architecture.md`
3. `docs/decision-log.md`
4. `docs/bringup/gates.md`
