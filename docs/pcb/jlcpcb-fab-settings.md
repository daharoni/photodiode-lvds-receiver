# JLCPCB fabrication settings and KiCad 10 setup (Rev A)

Status: research, read 2026-10-09. Labels: VERIFIED = read on a cited JLCPCB (or KiCad) page on 2026-10-09; PROPOSED = design recommendation or own calculation; UNRESOLVED = open. Nothing here was measured; no impedance was simulated with JLCPCB's tool. Raw pages (untrusted data) and hashes: `docs/research/downloads/jlcpcb/` (MANIFEST.md). Short names for sources used below:

- CAP = https://jlcpcb.com/capabilities/pcb-capabilities
- IMP = https://jlcpcb.com/impedance (stackups, Er, mask)
- CALC = https://jlcpcb.com/pcb-impedance-calculator and its guide https://jlcpcb.com/help/article/User-Guide-to-the-JLCPCB-Impedance-Calculator (last updated Sep 16, 2026)
- KC9 = https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9 (updated Sep 24, 2026; the KiCad 10 Gerber article was not found, the BOM/CPL article is KiCad 10)
- BOM = https://jlcpcb.com/help/article/how-to-generate-the-bom-and-centroid-file-from-kicad (written on KiCad 10.0.3)
- KM = https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html (KiCad 10 manual)
- IPC = IPC-2221 Table 6-1 as reproduced by https://www.ema-eda.com/ema-resources/blog/pcb-clearance-and-creepage-distance-table/ (secondary source; the standard itself was not read; IPC-2221B values, revision C not checked)

**Ordering note (2026-10-09):** the board must be ordered with the JLCPCB quote option "Min via hole size/diameter" = 0.25 mm/(0.35/0.4 mm) (the high-precision tier; JLCPCB then auto-selects "4-Wire Kelvin Test" and "FR4 Tg155", extra cost) because the J50 receptacle's through-hole B row is below the standard-tier hole minima; JLCPCB's DFM accepted it with that option (Daniel, test board `hardware/pcb/j50-dfm-test`; see `docs/pcb/j50-receptacle-dfm.md`). The capability table below is the standard tier and still governs everything except J50.

## 1. JLCPCB multilayer capability (FR-4, 1.6 mm, 4 and 6 layer)

All rows VERIFIED from CAP unless noted. Where JLCPCB gives one multilayer figure it applies to both 4 and 6 layers.

| Item | JLCPCB value | Note |
|---|---|---|
| Layer count, controlled impedance | impedance offered on 4/6/8/.. layers; tolerance +/-10 % standard; +/-5 % on special request (extra verification) | CAP table and FAQ. Price of impedance control: NOT stated on the pages read (UNRESOLVED, see the order page) |
| Min trace/space, 1 oz outer | multilayer 0.09/0.09 mm (3.5 mil) | 2 oz: 0.15/0.15 mm. Width tolerance +/-20 % |
| Inner vs outer trace/space | CAP gives no separate inner figure; same multilayer 0.09/0.09 (1 oz). Inner copper weights 0.5 / 1 / 2 oz, default 0.5 oz | outer multilayer 1 oz or 2 oz |
| Min via hole / via diameter | 0.15 mm / 0.25 mm (0.1/0.2 only for boards <= 1 mm, ENIG/OSP). Via diameter at least 0.1 mm (0.15 preferred) larger than hole. Preferred minimum hole 0.2 mm | 0.1 or 0.15 mm hole with any pad, and 0.2/0.25 mm hole with pad < 0.45 mm, cost more |
| Min PTH annular ring | multilayer 1 oz: recommended >= 0.20 mm, absolute minimum 0.15 mm; 2 oz: >= 0.254 mm | NPTH pad ring >= 0.45 mm |
| Hole sizes | min NPTH 0.50 mm; PTH recommended >= 0.5 mm; PTH tolerance +0.13/-0.08 mm; multilayer plated slot >= 0.35 mm, NPTH slot >= 1.0 mm | no rectangular holes |
| Hole-to-hole | via 0.2 mm; pad (component) hole 0.45 mm | |
| Hole to copper / track | via hole to track 0.2 mm; PTH to track 0.28 mm (0.35 recommended); NPTH to track 0.2 mm; inner-layer via hole to copper 0.2 mm; inner-layer PTH hole to copper 0.3 mm | |
| Pad/track clearances | pad to track 0.1 mm; SMD pad to pad (different nets) 0.15 mm; same-net track spacing 0.25 mm | |
| Copper to board edge | routed edge >= 0.2 mm; V-cut >= 0.4 mm | |
| Soldermask | expansion 1:1 allowed (LDI upgrade June 2025); keep >= 0.09 mm between mask opening and neighbouring trace; min bridge 0.10 mm (1 oz, green/red/yellow/blue/purple), 0.13 mm (black/white), 0.20 mm (2 oz) | mask Er 3.8, thickness >= 10 um |
| Silkscreen | min line width 0.15 mm; min text height 1.0 mm (40 mil); width:height 1:6 preferred; pad to silkscreen 0.15 mm | |
| Outer copper | 1 oz or 2 oz (multilayer) | the impedance calculator supports only 1 oz outer |
| Board thickness | FR-4 0.4/0.6/0.8/1.0/1.2/1.6/2.0 mm; tolerance +/-10 % at >= 1.0 mm (1.6 mm: 1.44-1.76 mm) | |
| Surface finish | HASL (leaded / lead-free), ENIG, OSP. FR-4 with 6 or more layers does NOT support HASL | so 6 layers implies ENIG or OSP |
| Via-in-pad / filled vias | "Epoxy filled & capped" or "copper paste filled & capped", via diameter 0.15-0.55 mm; "default for 6-layer and above" (CAP wording); vias plugged with mask must be <= 0.5 mm with >= 0.35 mm clearance to mask openings | Cost of filling not stated on CAP (UNRESOLVED) |
| Castellations | not needed (CAP: 0.5 mm min if ever used) | |
| Impedance as order option | Yes, multilayer only; calculator-defined stackup | |

Recommendation (PROPOSED): ENIG. Reasons: forced on 6 layers (CAP), flat pads for the 0.5 mm pitch USB-C (Wuerth 632723300011), WSON/DSG, QFN, and the ESP32 module castellations; JLCPCB lists 0.2-0.25 mm BGA pads as ENIG-only, which shows ENIG is their fine-feature finish. Cost delta not read.

## 2. JLCPCB impedance-control stackups (IMP)

Common parameters (VERIFIED, IMP and CALC): prepreg Er 7628 = 4.4, 3313 = 4.1, 1080 = 3.91, 2116 = 4.16; core Er 4.6; mask Er 3.8, 1.2 mil on substrate, 0.6 mil over trace, 1.2 mil between traces; outer copper 1 oz = 0.035 mm in the stackup tables (1.6 mil in the calculator parameters), inner 0.5 oz = 0.0152 mm (0.6 mil), 1 oz = 1.2 mil; trace top width = base width - 0.7 mil; 4-8 layer cores are Nan Ya NP-155F. Diff pair accepted range 50-150 ohm; single-ended 20-90 ohm (CALC guide). 3313 replaced 2313 (same thickness and Er).

### 4-layer (layer order L1 Cu / prepreg / L2 Cu - core - L3 Cu / prepreg / L4 Cu; copper 0.035 / 0.0152 / 0.0152 / 0.035 mm)

| Stackup | L1-L2 prepreg | L2-L3 core | L3-L4 prepreg |
|---|---|---|---|
| JLC04161H-7628 | 7628, 0.2104 mm | 1.065 mm (1.1 mm with Cu) | 7628, 0.2104 mm |
| JLC04161H-3313 | 3313, 0.0994 mm | 1.265 mm (1.3 mm with Cu) | 3313, 0.0994 mm |
| JLC04161H-1080 | 1080, 0.0764 mm | 1.265 mm | 1080, 0.0764 mm |
| JLC04161H-2116 | 2116, 0.1164 mm | 1.265 mm | 2116, 0.1164 mm |

IMP lists 19 four-layer variants in total (7628A, 3313A, 1080A, 7628B, 2116A..E, 7628C-G, 1080B ...) with two-prepreg builds; the four above are the single-prepreg ones. The "no requirement" 4-layer stackup is the 7628 build.

### 6-layer (L1 / prep / L2 - core - L3 / prep / L4 - core - L5 / prep / L6; inner Cu 0.0152 mm, outer 0.035 mm)

| Stackup | L1-L2 | L2-L3 core | L3-L4 | L4-L5 core | L5-L6 | Sum of layers listed |
|---|---|---|---|---|---|---|
| JLC06161H-3313 | 3313 0.0994 | 0.55 | 2116 0.1088 | 0.55 | 3313 0.0994 | 1.538 mm (+ mask ~0.06 = 1.60) |
| JLC06161H-7628 | 7628 0.2104 | 0.4 | 7628 0.2028 | 0.4 | 7628 0.2104 | 1.555 mm |
| JLC06161H-1080 | 1080 0.0764 | 0.55 | 7628 0.2104 | 0.55 | 1080 0.0764 | 1.594 mm |
| JLC06161H-2116A | 2116 0.1164 | 0.13 | 2116+0.7 core+2116 (0.9328) | 0.13 | 2116 0.1164 | ~1.56 mm |
| "No requirement" | 3313 0.0994 | 0.55 | 2116 0.1164 | 0.55 | 3313 0.0994 | |

IMP lists 17 six-layer variants (3313C/D/E, 1080A/B/C, 2116, 2116B/C, 7628A/B/D ...). IMP does not state which thickness (1.2/1.6/2.0 mm) each variant produces; the sums above are my arithmetic, so confirm "6 layers, 1.6 mm" in the calculator (UNRESOLVED).

### Calculator output

CALC is client-side JavaScript; the fetched page is only the empty shell, so JLCPCB's own widths and gaps for 90/100/50 ohm were NOT obtained (UNRESOLVED). I computed them instead (PROPOSED):

- Method: 2D finite-difference electrostatic solver (numpy, conjugate gradient) of the real cross-section: trapezoid trace (top = base - 0.7 mil, thickness 1.6 mil outer / 0.6 mil inner), JLCPCB dielectric thicknesses and Er above, mask layers per CALC (1.2 mil on substrate, 0.6 mil over trace, Er 3.8), ground plane below, open air with a far wall above. Z0 = 376.73 / sqrt(C * C_vacuum) per unit length; Zdiff = 2 * Zodd (odd mode, +1 V / -1 V). Code: `tools/impedance_fd/` (`tl2d.py`, `tl2.py`, `run_outer.py`, `run_checks.py`).
- Checks: converges with mesh refinement (55.2 vs 55.5 ohm at 2x mesh); against the Hammerstad-Jensen zero-thickness microstrip formula it is 3-4 % lower, as expected for a 12.7 um conductor. Not validated against JLCPCB's calculator or a coupon. Treat results as +/-5 % and confirm with CALC at order time (PROPOSED).
- Width tolerance +/-20 % (CAP) alone moves Zdiff by roughly +/-8 % (computed: 0.116 mm -> 98 ohm, 0.145 -> 90.7, 0.174 -> 83 ohm on JLC06161H-3313 at 0.15 mm gap), so +/-10 % is tight and JLCPCB's width compensation is the thing to confirm.

Outer layers, 1 oz, mask-covered. Single-ended 50 ohm width and differential widths for the given gap (mm):

| Stackup (outer dielectric) | 50 ohm SE | 90 ohm: gap 0.10 / 0.15 / 0.20 | 100 ohm: gap 0.10 / 0.15 / 0.20 |
|---|---|---|---|
| 4L or 6L -7628 (0.2104, Er 4.4) | 0.329 | 0.193 / 0.245 / 0.290 | 0.137 / 0.184 / 0.225 |
| 4L or 6L -2116A/2116 (0.1164, Er 4.16) | 0.184 | 0.133 / 0.167 / 0.184 | 0.098 / 0.129 / 0.145 |
| 4L or 6L -3313 (0.0994, Er 4.1) | 0.155 | 0.117 / 0.145 / 0.161 | 0.086 / 0.112 / 0.127 |
| 4L or 6L -1080 (0.0764, Er 3.91) | 0.120 | 0.101 / 0.120 / 0.130 | 0.075 / 0.093 / 0.103 |

(Gaps are quantised to the solver mesh, within 0.005 mm of the nominal.) 4L and 6L give identical outer-layer values because both reference the adjacent plane L2 / L(n-1) at the same prepreg; only the inner stack differs.

Inner layer L3 of JLC06161H-3313 (reference L4 plane 0.1088 mm above, L2 plane 0.55 mm below, inner Cu 0.6 mil): 50 ohm SE 0.130 mm; 90 ohm 0.120 mm at gap 0.146 and 0.133 mm at gap 0.198; 100 ohm 0.094 mm at gap 0.146 and 0.105 mm at gap 0.198 (PROPOSED, valid only if L4 is a solid plane under the pair).

## 3. Recommendation: 6 layers, JLC06161H-3313 (PROPOSED)

Chosen stackup: **JLC06161H-3313**, 1.6 mm, outer 1 oz, inner 0.5 oz (JLCPCB default inner), ENIG, impedance control ordered, +/-10 %.

Layer assignment:

| Layer | KiCad name | Use |
|---|---|---|
| L1 | F.Cu | Components, fast analog path (OPA857/OPA855/TLV3605), USB-C SuperSpeed pairs, LVDS, HV (APD bias) outer routing. 90/100 ohm and 50 ohm referenced to L2 |
| L2 | In1.Cu | Solid GND, no splits, no routing |
| L3 | In2.Cu | Slow signals (ESP32 GPIO, I2C, SPI, ADC taps) and power-rail routing; no controlled-impedance pairs |
| L4 | In3.Cu | Power pours (VBUS 5 V, 3V3, 3V3_D) with remaining area GND-filled and stitched; L3/L4 spacing is only 0.1088 mm, so L3 signals see L4 as their close reference |
| L5 | In4.Cu | Solid GND |
| L6 | B.Cu | Bottom components (decoupling, ESP32 antenna keep-out side per module datasheet), slow routing, USB/CAN pairs if needed. Same geometry as L1 (3313 0.0994 mm to L5) |

Differential and single-ended geometry on routable controlled layers (L1 and L6 identical; computed, PROPOSED, confirm with CALC):

| Class | Target | Width | Gap | Source row |
|---|---|---|---|---|
| DIFF90 (four SuperSpeed pairs), USB90 (USB_DP/USB_DN, USB_ESD_DP/USB_ESD_DN, USB_E_DP/USB_E_DN), CAN90 (CAN_P/CAN_N) | 90 ohm diff | 0.145 mm | 0.15 mm | 90.7 ohm computed at 0.143 mm / 0.149 mm |
| DIFF90 relaxed alternative | 90 ohm diff | 0.16 mm | 0.20 mm | 89.8 ohm computed |
| DIFF100 (LVDS_P/LVDS_N, U20 to R180) | 100 ohm diff | 0.11 mm | 0.15 mm | 100.2 ohm computed at 0.112 / 0.149 |
| 50 ohm single-ended (if ever needed) | 50 ohm | 0.155 mm | n/a | 50.0 ohm computed |
| L3 (not used for controlled pairs) | - | - | - | see section 2 inner numbers |

Reasoning:

1. 6 layers gives two solid GND planes (L2, L5) with the fast analog path and USB pairs on L1 over an unbroken plane 0.0994 mm away, and the HV generator, ESP32 and slow digital kept on other layers. A 4-layer board has one inner GND plane only if L3 carries power and signal, and JLC04161H-3313 places the L2-L3 core at 1.265 mm, so L3 is a poor second reference.
2. Return paths: 50 Mb/s LVDS and the USB-C pairs (edge rate, not data rate, sets the return-path need; UI = 20 ns) stay on L1 referenced to L2; layer changes carry GND stitching vias within about 1 mm (PROPOSED).
3. HV section (APD_BIAS 100-220 V): route HV nets on L1/L6 only, no HV copper or HV vias on inner layers, keep L2/L5 GND solid under HV tracks (dielectric 0.0994 mm; no JLCPCB dielectric-withstand figure was found, UNRESOLVED) and apply the HV clearance of section 4; add rule-area copper keepouts (all layers) around the HV island and the TIA input node (PROPOSED, check OPA857 layout guidance for a ground-plane cut-out under the input node; not checked here, UNRESOLVED).
4. Density: about 220 parts (many 0402) plus an ESP32-C6-MINI-1 and a 24-pin hybrid USB-C is routable on 4 layers, but the controlled pairs, the HV keep-outs and the quiet analog area compete for the same two outer layers; the extra inner layers remove that conflict.
5. Cost is secondary (Daniel: performance beats cost); JLCPCB prices not read.
6. Fallback if 0.145 mm / 0.15 mm gap proves hard to hold: JLC06161H-7628 (outer prepreg 0.2104 mm) gives 90 ohm at 0.245 / 0.15 mm and 0.29 / 0.20 mm, at the price of more TIA-adjacent plane coupling.
7. Note in KiCad: the L3/L4 pair is only 0.1088 mm apart; do not route fast signals on L3 without a solid L4 beneath.

## 4. KiCad 10 settings (for editing `.kicad_pro` / `.kicad_pcb`)

Current project values (read from receiver-module.kicad_pro, not changed): min_clearance 0.0, min_track_width 0.2, min_via_diameter 0.5, min_via_annular_width 0.1, min_hole_clearance 0.25, min_hole_to_hole 0.25, min_copper_edge_clearance 0.5, min_text_height 0.8; netclasses Default (0.2/0.2, via 0.6/0.3), HV (clearance 1.0, track 0.3), LVDS (0.2/0.2) with patterns `LVDS_*`, `HV_*`, `/Power/HV_*`, `/Front End/HV_*`, `APD_BIAS`.

### 4.1 Board Setup > Board Editor Layers

Copper layers: 6 (F.Cu, In1.Cu, In2.Cu, In3.Cu, In4.Cu, B.Cu).

### 4.2 Board Setup > Physical Stackup (all PROPOSED from IMP; thicknesses mm)

| Item | Type | Thickness | Material / Er |
|---|---|---|---|
| F.Silkscreen | silk | - | white |
| F.Paste | paste | - | - |
| F.Mask | solder mask | 0.0305 | Er 3.8 (IMP: 1.2 mil) |
| F.Cu | copper | 0.035 | finish ENIG |
| Dielectric 1 | prepreg | 0.0994 | 3313, Er 4.1 |
| In1.Cu | copper | 0.0152 | |
| Dielectric 2 | core | 0.55 | Er 4.6 |
| In2.Cu | copper | 0.0152 | |
| Dielectric 3 | prepreg | 0.1088 | 2116, Er 4.16 |
| In3.Cu | copper | 0.0152 | |
| Dielectric 4 | core | 0.55 | Er 4.6 |
| In4.Cu | copper | 0.0152 | |
| Dielectric 5 | prepreg | 0.0994 | 3313, Er 4.1 |
| B.Cu | copper | 0.035 | |
| B.Mask / B.Paste / B.Silkscreen | | 0.0305 | Er 3.8 |

Board thickness 1.6 mm, copper finish ENIG. Loss tangent is not published by JLCPCB (UNRESOLVED; leave the KiCad default). The sum of listed copper and dielectric is 1.538 mm; with mask about 1.60 mm.

### 4.3 Board Setup > Design Rules > Constraints (PROPOSED values, JLCPCB limit in brackets)

| Setting | Value | Basis |
|---|---|---|
| Minimum clearance | 0.10 mm (the Default netclass uses 0.15) | JLCPCB 0.09 outer/multilayer, 0.10 pad to track |
| Minimum track width | 0.10 mm | needed for 0.11 mm DIFF100 traces; JLCPCB 0.09 |
| Minimum connection width | 0.10 mm | |
| Minimum annular width | 0.15 mm | JLCPCB absolute minimum 0.15; recommended 0.20 for PTH pads (check the connector THT pads) |
| Minimum via diameter | 0.45 mm | smaller costs more (CAP); project via 0.45/0.25 on every net since 2026-10-22 (Daniel), several in parallel for power; custom rule "via annular" allows 0.10 mm on vias only |
| Minimum through hole | 0.20 mm (component PTH >= 0.5 mm recommended) | CAP preferred minimum 0.2 mm |
| Hole to hole clearance | 0.45 mm | CAP pad hole-to-hole 0.45 (via-to-via only 0.2) |
| Copper to hole clearance | 0.30 mm | CAP inner PTH 0.3, PTH to track 0.28 |
| Copper to edge clearance | 0.30 mm (CAP minimum 0.2; V-cut 0.4); HV items 1.0 mm via custom rule | |
| Solder mask expansion | 0.0 mm | CAP allows 1:1 |
| Minimum solder mask web | 0.10 mm (0.13 if black/white mask) | CAP |
| Solder mask to copper clearance | 0.09 mm | CAP |
| Minimum text height / thickness | 1.0 mm / 0.15 mm | CAP |
| Silk to pad clearance (Silkscreen clearance / "silk to solder mask") | 0.15 mm | CAP |
| Courtyard overlap | DRC "Overlapping courtyards" severity Error; also "Missing footprint courtyard" Warning | PROPOSED |
| Tenting | tent vias (global, Board Setup > Solder mask/paste) | PROPOSED |

DRC > Violation Severity: set "Tuning profile track geometries" to Warning or Error (KM, tuning profiles section; KiCad 10 feature).

### 4.4 Net classes and tuning profiles (Board Setup > Design Rules > Net Classes)

KiCad 10 supports tuning profiles with per-layer width/gap and a calculator based on the stackup, assigned to net classes (KM, "Tuning profiles"). Create profiles `Z90_diff` (90 ohm, differential, layers F.Cu with bottom reference In1.Cu and B.Cu with reference In4.Cu, width 0.145, gap 0.15) and `Z100_diff` (width 0.11, gap 0.15), and assign them to the classes below; the calculator will only match the table above if the stackup in 4.2 is entered correctly.

| Class | Track | Clearance | Via (dia/drill) | Diff pair width/gap | Priority | Nets (pattern, hierarchical names carry a sheet prefix, so use wildcards) |
|---|---|---|---|---|---|---|
| Default | 0.15 | 0.15 | 0.45 / 0.25 | - | lowest | everything else |
| HV | 0.30 | 1.0 (see below) | 0.45 / 0.25, avoid vias | - | 1 | `HV_*`, `*/HV_*`, `APD_BIAS`, plus HV_K, HV_OUT, HV_CLAMP, HV_V1, HV_RAW, HV_PUMP, HV_FILT (all match `HV_*`); `HV_MON` and `HV_DIS` are low-voltage monitor/control nets that the existing `HV_*` pattern also catches (UNRESOLVED: consider renaming or excluding them to avoid a 1.0 mm clearance on the ESP32 side) |
| DIFF90 | - | 0.15 | 0.45 / 0.25 | 0.145 / 0.15 | 3 | `*LVDS_OUT1_P`, `*LVDS_OUT1_N`, `*LVDS_OUT2_P`, `*LVDS_OUT2_N` (SSTX pairs), and the CAN pairs at the connector end |
| CAN90 | - | 0.15 | 0.45 / 0.25 | 0.145 / 0.15 | 3 | `*/CAN_P`, `*/CAN_N` |
| USB90 | - | 0.15 | 0.45 / 0.25 | 0.145 / 0.15 | 3 | `*/USB_DP`, `*/USB_DN`, `*/USB_ESD_DP`, `*/USB_ESD_DN`, `*/USB_E_DP`, `*/USB_E_DN` (the last four added 2026-10-22: U61 -> R193/R194 and R193/R194 -> ESP32, renamed so the names end in P/N) |
| DIFF100 | - | 0.15 | 0.45 / 0.25 | 0.11 / 0.15 | 3 | `LVDS_P`, `LVDS_N` (U20 to R180) |
| LVDS (existing) | 0.2 | 0.2 | | | | `LVDS_*` currently catches all LVDS nets; narrow it to avoid overriding the classes above, or give DIFF90/DIFF100 higher priority (lower number) than LVDS. `LVDS_DBG_P/N` (U50 3Y/3Z to J51 scope header) is not an impedance-controlled run in the spec: leave on LVDS/Default (PROPOSED) |

HV clearance: IPC-2221 Table 6-1 (secondary reproduction, IPC), band 171-250 V: B1 internal 0.2 mm; B2 external uncoated up to 3050 m 1.25 mm; B3 external uncoated above 3050 m 6.4 mm; B4 external with permanent polymer coating 0.4 mm; A5 conformal-coated assembly 0.4 mm; A6 uncoated component leads 0.8 mm; A7 0.4 mm. APD_BIAS at 220 V falls in this band. The project's 1.0 mm is above B4/A6 (solder-mask-covered traces, assembled leads) but BELOW B2 (1.25 mm) for exposed (unmasked) copper such as pads and test points. PROPOSED: keep the 1.0 mm netclass, and for HV pads and test points add the 1.25 mm rule in section 4.5 (or accept 1.0 mm with Daniel's explicit sign-off). This is a fabrication-spacing table, not a product-safety isolation standard (IEC 60664-1 would govern certified isolation); the creepage value for any user-accessible HV is UNRESOLVED. KiCad 10 also has a `creepage` DRC constraint (KM) if a creepage figure is later chosen.

KiCad diff-pair recognition (KM, `inDiffPair`): a pair is recognised only if the net names are an _P/_N (or +/-) pair. `LVDS_*_P/N` qualify. USB_DP/USB_DM and CAN_H/CAN_L did not; resolved 2026-10-16 by renaming the nets to USB_DP/USB_DN and CAN_P/CAN_N in the KiCad schematic (no electrical change; CAN_P is CANH, CAN_N is CANL). Netclass patterns are now `*/CAN_P`, `*/CAN_N`, `*/USB_DP`, `*/USB_DN`. That the interactive router offers the diff-pair tool on them has not been checked in the PCB editor (PROPOSED).

### 4.5 Custom rules (`receiver-module.kicad_dru`, syntax from KM "Custom rules"; PROPOSED values, all untested)

```
(version 1)

# 90 ohm pairs: gap window around the 0.15 mm target (width comes from the tuning profile)
(rule "diff90 gap"
  (condition "A.hasNetclass('DIFF90')")
  (constraint diff_pair_gap (min 0.13mm) (opt 0.15mm) (max 0.20mm)))

(rule "diff100 gap"
  (condition "A.hasNetclass('DIFF100')")
  (constraint diff_pair_gap (min 0.13mm) (opt 0.15mm) (max 0.20mm)))

# 2026-10-22: CAN90/USB90 (125 kbit/s, 12 Mbps) have no maximum gap (router target only). This also stops KiCad from
# counting their pin-pitch fan-outs as uncoupled, so their uncoupled-length check is effectively off (accepted: slow buses).
(rule "slow pair gap"
  (condition "A.hasNetclass('CAN90') || A.hasNetclass('USB90')")
  (constraint diff_pair_gap (min 0.13mm) (opt 0.15mm)))

# 2026-10-22: pin fan-out. Inside the courtyard of J50, U50, U51, U52 or U20 the pad pitch sets the gap (max 1.2 mm).
# intersectsCourtyard is evaluated per segment, so a long segment that only touches a courtyard is exempt as a whole;
# R180 is left out for that reason. Full condition in hardware/pcb/receiver-module/receiver-module.kicad_dru.
(rule "pair gap at pins"
  (condition "(A.hasNetclass('DIFF90') || A.hasNetclass('DIFF100')) && (A.intersectsCourtyard('J50') || A.intersectsCourtyard('U50') || A.intersectsCourtyard('U51') || A.intersectsCourtyard('U52') || A.intersectsCourtyard('U20'))")
  (constraint diff_pair_gap (min 0.13mm) (opt 0.15mm) (max 1.2mm)))

# uncoupled length (connector fan-out): PROPOSED 10 mm for the SuperSpeed/USB/CAN pairs, 5 mm for the short LVDS run
(rule "diff90 uncoupled"
  (condition "A.hasNetclass('DIFF90') || A.hasNetclass('CAN90') || A.hasNetclass('USB90')")
  (constraint diff_pair_uncoupled (max 10mm)))
(rule "diff100 uncoupled"
  (condition "A.hasNetclass('DIFF100')")
  (constraint diff_pair_uncoupled (max 5mm)))

# intra-pair length match: 1 mm until 2026-10-22, now 2.5 mm (about 15 ps against a 20 ns UI and edges of a few hundred ps, PROPOSED),
# DIFF90 only: CAN90/USB90 dropped (slow), DIFF100 LVDS_P/N excluded (KiCad counts the R87 hysteresis tap, about 4.3 mm,
# in LVDS_P's length; check its through-path skew by eye). No inter-pair matching. within_diff_pairs (added 2026-10-22) checks each _P/_N pair
# on its own; without it KiCad measures every matched net against the longest one in all four classes (KiCad 10 manual, skew constraint)
(rule "pair skew"
  (condition "A.hasNetclass('DIFF90')")
  (constraint skew (max 2.5mm) (within_diff_pairs)))

# keep other copper away from coupled pairs (2x gap rule of thumb, PROPOSED); the board file splits this into
# per-class rules. USB90 (USB full speed, 12 Mbps) is exempt since 2026-10-22 and uses the 0.15 mm netclass clearance.
(rule "pair keepout"
  (condition "A.inDiffPair('*') && !A.hasNetclass('USB90') && !AB.isCoupledDiffPair()")
  (constraint clearance (min 0.3mm)))

# HV to board edge
(rule "hv edge"
  (condition "A.hasNetclass('HV')")
  (constraint edge_clearance (min 1.0mm)))

# exposed HV pads / test points: IPC-2221B B2 171-250 V uncoated = 1.25 mm (secondary source)
(rule "hv pad clearance"
  (condition "A.hasNetclass('HV') && A.Type == 'Pad' && B.Net != A.Net && B.Type != 'Zone'")
  (constraint clearance (min 1.25mm)))
```

Caveats: whether the same-footprint pad gap of the HV parts (R50 1206, C50 1210) satisfies 1.25 mm must be checked in DRC; `skew` for a coupled pair is computed as the length difference of the two tracks (KM, DRC "Skew between tracks"); `A.inDiffPair('*')` only matches names KiCad pairs (see 4.4).

### 4.6 Plot / Gerber settings (KC9 and KM; KiCad 9 article, same dialog in KiCad 10)

- Format Gerber, RS-274X with Protel filename extensions (VERIFIED, KC9); use extended X2 format and include netlist attributes ticked (KC9); coordinate format 4.6, mm; Plot mode Filled; scaling 1:1; drill marks None (KC9).
- Layers: F.Cu, In1.Cu, In2.Cu, In3.Cu, In4.Cu, B.Cu, F.Mask, B.Mask, F.Silkscreen, B.Silkscreen, F.Paste, B.Paste (paste needed for assembly/stencil), Edge.Cuts as one closed contour. Plot every inner layer in stackup order (the .G1..G4 numbering reconstructs the stackup, a skipped layer stops the job; KC9).
- Check zone fills before plotting: ticked (KC9, KM). Plot drawing sheet off (KM).
- Subtract soldermask from silkscreen: KM describes it (removes silk where there is no mask); KC9 does not list it. PROPOSED: tick it; JLCPCB's silk-to-pad rule is 0.15 mm.
- Drill: Excellon, millimetres, Zeros decimal, Origin absolute (KC9; match the Gerber origin: leave "Use drill/place file origin" unticked, PROPOSED), alternate drill mode for oval holes ticked, PTH and NPTH in a single file UNTICKED, so `-PTH.drl` and `-NPTH.drl` are written (KC9). Also generate the drill map (JLCPCB "Suggested Naming Patterns" says it highly recommends a drill map/drawing). Optional: Gerber job file (KM).
- Upload as one .zip, English file names (KC9). Run DRC to 0 errors first (KC9).

### 4.7 Assembly files (pointer only; BOM)

BOM columns: Comment, Designator, Footprint, JLCPCB/LCSC Part # (csv/xls/xlsx). CPL columns: Designator, Mid X, Mid Y, Rotation, Layer, mm; KiCad's built-in .pos gives Ref, PosX, PosY, Rot, Side and needs the header rename; JLCPCB recommends the Fabrication Toolkit plugin (BOM page). Rotation corrections against the JLCPCB library per part are not checked here (UNRESOLVED; verify in JLCPCB's placement preview).

## 5. Not verified / limits

- JLCPCB calculator results (JavaScript), prices (impedance, ENIG, filled vias), per-stackup finished thickness, and the KiCad 10-specific Gerber article.
- All widths/gaps above are my own FD calculation, not JLCPCB output, and are not tied to a measurement.
- IPC-2221 values are from a secondary web reproduction, not the standard.
