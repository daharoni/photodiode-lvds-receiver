# PCB review: stackup/planes, power integrity, diff pairs, DRC triage, DFM (Rev A, 2026-10-22)

Scope: planes/pours/stitching, rail distribution and decoupling, USB/CAN/LVDS_OUT pairs, DRC triage, DFM/assembly/testability.
Coordinates are doc coordinates (file minus 50,50), mm. Method: pcbnew Python on a copy of the board (zones refilled in the copy; fill areas identical to the saved file, so the saved fills are not stale), plus drc.rpt/drc.json, SVG/own renders, ESP32 datasheet and hardware design guideline PDFs. Scripts are in `.../scratchpad/work-pi/` (a1..a28.py). Nothing in the repo was edited. Nothing here is a measurement or simulation; "VERIFIED" means read from the board file, a report or a cited document.

## Executive summary
1. No BLOCKER found in my scope. Planes are solid (no tracks on In1/In3/In4; voids only from holes, edge pullback, the two rule areas and the J50 B-row). All three rail pours are connected (0 unconnected items after refill). The USB, CAN and LVDS_OUT pairs are cleanly built: no splits, matched, no stubs.
2. MAJOR: 155 of 209 vias (74 %) sit inside SMD pads (0402/0603, TSSOP, QFN EPs, ESP32 thermal pad with 9 vias). The board file says "vias tented", which cannot apply inside a pad. The fab-doc lists "epoxy filled and capped" as available but no document selects it or prices it. Order spec must say via-in-pad filled+capped or assembly will wick solder.
3. MAJOR: the J50 shell posts (decision 16 says "several vias each") have no dedicated vias and 4 of 8 shell pads plus the TLV3605 GND pad U20.9 are the "starved_thermal" items; fix with solid connection plus stitch vias.
4. MAJOR (cheap): several high-speed/ESD ground pins are far from any GND via: U50 (SN65LVDS104) GND pins 5/8 are 3.0/4.7 mm from the nearest GND via and its decoupling caps C184/C185 return 3.0-3.2 mm away; U51 pin 5 2.3 mm; U4 output caps C30/C31 4.5-5.2 mm.
5. ESP32 antenna question closed: Espressif's keepout figure was read (Fig. 25, p.25 of the guideline); the 1.0 mm side margin matches it, but the module is mid-edge and not at a corner and the base board is not cut away, which Fig. 24 does not endorse. Radio is disabled by design, so this is documentation, not a layout defect. All DRC items are triaged below; none blocks, five items are real cleanups.

---

## MAJOR

### M1. Via-in-pad on 155 of 209 vias, fill/tenting not specified
- Where: everywhere. Examples: U60 pad 49 (9 sub-pads, 1 via each, paste 100 % of each sub-pad), U10 EP (2 vias, paste 100 %), U3 EP (2 vias, paste 54 %), U20 EP (1 via, 55 %), U11 EP, U5 EP, U50 pin 1, 12 of the 0402 caps (C80, C82, C194, C195, C206... both pads have a 0.45 mm via in a 0.56 x 0.62 mm pad), every 0603 GND/3V3 pad with a via, 8 TPs. Count VERIFIED by hit-testing all 209 vias against SMD pad polygons (script a8/a9). 54 vias are not in a pad (16 GND, rest signal/rail layer changes).
- Why it matters: an open 0.25 mm drill in a pad draws solder paste/solder down the barrel (starved joint, tombstoning on 0402, voided thermal pads). `README.md` Board Setup says "vias tented"; tenting only covers vias outside pad openings. `docs/pcb/jlcpcb-fab-settings.md` section 1 row "Via-in-pad / filled vias" records JLCPCB "epoxy filled & capped" or "copper paste filled & capped", via 0.15-0.55 mm, "default for 6-layer and above (CAP wording)", cost UNRESOLVED. No document makes it an order requirement and no G4 item checks it (grep of docs/pcb and gates.md for plug/epoxy/fill finds only that row).
- Fix (PROPOSED): add to the order checklist/G4: "Via covering = epoxy filled and capped (or copper paste filled)" for ALL vias, confirm price and that JLCPCB DFM accepts 0.25 mm drill / 0.45 pad with it (0.25/0.45 are inside the stated 0.15-0.55 mm filled-via range). Alternatively keep the via-in-pad only where needed (ESP32 EP, U10, U3 EP) and move signal/cap vias off pads by 0.6-0.8 mm; a 0.45 mm via leaves almost no solderable area on a 0.56 mm 0402 pad even when filled. Confidence HIGH on the issue, MED on the exact JLC option wording (live page not re-read).

### M2. J50 shell posts: decision 16 layout rule not implemented, thermal relief starves the connection
- Where: J50 S1 pads at (66.82,20.73), (71.55,20.73), (66.82,29.27), (71.55,29.27) [pad 1.0 x 1.6, slot 0.6 x 1.2], (69.0,25.0), (72.1,25.0) [pad 0.5 x 1.3, slot 0.2 x 1.0], (65.67,23.0), (65.67,27.0) [0.65 pad, 0.4 drill, between B-row signal holes]. DRC: starved_thermal (1 spoke, 2 required) on (71.55,29.27) PWR, (72.1,25.0) PWR, (65.67,27.0) F.Cu, (65.67,23.0) F.Cu. Zone connection on every S1 pad is "inherit" (thermal). GND vias within 2.5 mm of any S1 pad: 0 (script a14).
- Why: `docs/decision-log.md` entry 16: "every shell post to the GND planes with several vias each". The only bond is the plated barrel plus thermal spokes (0.4 mm wide), so a 6.63 MHz field/ESD return through the cable braid sees spokes instead of copper. Cable shield bonding is the purpose of decision 16.
- Fix: set the 8 S1 pads' local zone connection to Solid on all layers, add 2-3 GND vias beside each large post (spots exist: GND1/GND2 void map shows the J50 B-row void is 2 x 6 mm at (65-67, 22-28) so keep vias outside it) and one on the right side of (69,25)/(72.1,25). This also clears the 4 starved items. Confidence HIGH.

### M3. High-speed/ESD ground pins and caps far from a GND via
Measured pad-to-nearest-GND-via (centre to centre, script a19/a7). The outer GND pours connect to GND1/GND2 only through vias, so this distance is the extra loop length.
| Part | Item | Distance |
|---|---|---|
| U50 SN65LVDS104 | GND pin 5 / pin 8 | 3.0 / 4.7 mm |
| U50 | C184 100n (pins 1-4 at 2.1-2.9 mm) GND pad / C185 1u GND pad | 3.2 / 3.0 mm |
| U51 | GND pin 5 / pin 10 | 2.3 / 0.95 mm |
| U52 | GND pin 5 / pin 10 | 1.5 / 1.8 mm |
| U10 OPA857 | C57 / C56 100n GND pads (pin-to-cap 1.2-1.3 mm) | 2.3 / 1.3 mm |
| U11 OPA855 | C52 100n GND pad | 1.55 mm |
| U64 | C196 100n | 2.2 mm |
| U5 eFuse | C1 10u (output) | 2.0 mm |
| U4 LDO | C30 10u / C31 1u (out caps) ; GND pin 2 | 5.2 / 4.5 mm ; 2.0 mm |
| U62 | GND pin 10 | 2.75 mm |
Good ones: C80, C82, C81 (TLV3605), C58, C59, C29, C2, C33, U60 pad 49 (9 vias), C194/C195 all have a via in or within 0.2 mm of the GND pad.
- Why: SN65LVDS104 drives two 90 ohm pairs with 50 Mbps data (edges of a few hundred ps, not datasheet-checked here: PROPOSED); the return/supply loop is the thing that couples switching into 3V3 and into the TLV3605 front end, and TPD6E05U06 clamps need a short ground path to be effective (TPD6E05U06 datasheet is not in docs/datasheets; the usual practice is a via adjacent to the GND pin: PROPOSED, not verified against the datasheet).
- Fix (PROPOSED): one via beside U50 pins 5 and 8 (the pour is there), move/add a GND via at C184/C185 GND pads, a via at U51 pin 5 and U52 pins 5/10, and a via on the GND pad of C57/C56/C52/C196/C1/C30/C31. Confidence MED-HIGH (distances measured; effect not simulated).

---

## MINOR

### m1. Single vias carry the whole VBUS and +5V trunks; VBUS necks are 0.15 mm (README says "several in parallel for power")
- VBUS: J50 pads A4/A9 on F.Cu 0.15 mm x 1.2 mm each, B-row side joins on In2 0.5 mm, then ONE via at (71.35,18.58) to B.Cu (0.15 mm, 6.1 mm total) into U5 pin 4. +5V from the eFuse output: ONE via at (61.05,19.03), 28.8 mm of 0.5 mm In2, ONE via at L2 (37.61,11.35) feeding the whole LT8365 input (budget 0.19-0.24 A, `docs/schematic/power.md`; eFuse ILIM 0.68/0.76/0.84 A). VERIFIED from the file; budget numbers cited from power.md (estimates).
- Own arithmetic (PROPOSED, IPC-2221 style): 0.5 mm x 15 um inner copper is about 0.055 ohm for 24 mm, ok at 0.24 A (13 mV) and still ok at the 0.84 A trip current (46 mV) but runs warm (tens of K) if the fuse sits at its limit; one 0.25 mm via is about 1 A class. 0.15 mm F.Cu necks at the J50 pins: about 3.3 mohm/mm.
- Fix: add a second via at each of those three points and widen the 0.15 mm VBUS stubs to 0.3 mm where there is room. Confidence MED.

### m2. Mounting-hole via rings violate the 0.45 mm pad hole-to-hole rule (32 DRC items)
- H1 (3.5,3.5), H2 (71.5,3.5), H3 (3.5,46.5), H4 (71.5,46.5): 2.2 mm PTH with 4.4 mm pad and 8 x 0.4/0.7 mm ring pads at radius 1.65 mm: wall-to-wall 0.35 mm (DRC min 0.4495, JLCPCB "Pad Hole-to-Hole Spacing 0.45mm" per `docs/pcb/j50-receptacle-dfm.md` section 1). How JLCPCB classifies the 0.4 mm ring holes (via 0.2 mm rule vs pad 0.45 mm rule) is UNRESOLVED.
- Fix: move the ring to radius 1.8 mm (wall-to-wall 0.5 mm; the 0.7 pad still ends at 2.15 mm inside the 2.2 mm pad radius) or use the plain `_Pad` footprint (the 4.4 mm barrel already bonds all planes). Footprint is in lab-library PR #62. Class (i), trivial, but do it before the order.

### m3. Stitching/pour density and board-edge fence
- GND-via spacing map (script a10, includes GND PTH pads): regions more than 8 mm from any GND via: left edge x 0-2, y 16-34 (optical end; clearance 8-19 mm), bottom-left x 12-22, y 38-50; 5-8 mm: top-left x 10-18, y 0-14, bottom-centre x 18-30, y 40-50, front-right x 56-70, y 38-50. Edge band counts: left edge (x<3.5) 0 GND vias, top (y<3.5) 2 vias (11.8 mm gap), right (x>71.5) 4 (13.9 mm gap), bottom 5 (6.5 mm gap).
- Why: unstitched outer GND pours act as patch radiators and let return current wander; with edges of a few hundred ps keep pour-to-plane via spacing <= 5 mm (rule of thumb, PROPOSED). The top edge cannot be fenced where HV_OUT runs at y 1.15 (1.0 mm HV clearance, `hv edge` rule).
- Fix: add GND stitch vias along the left, bottom and right edges at about 4-5 mm and in the 8 mm holes above. Cheap; vias are 0.25/0.45 (filled, see M1). Confidence MED.

### m4. ESP32 antenna keep-out: Espressif figure read, README question resolved (documentation fix)
- Read: `docs/datasheets/esp32-c6-hw-design-guidelines.pdf`, section 1.4.7 "Positioning a Module on a Base Board", PDF p.27 text / p.28 figures, Fig. 24 and Fig. 25 (Fig. 25 dimensions: clearance area 6.00 mm deep over the antenna, "Max 2" beside it on the feed side, "Max 1" above, and the base board cut away "Min 15" along the side). Text: place the antenna outside the base board with the feed close to the edge; if the antenna cannot extend beyond the edge, cut the base board away on both sides and below; do not place the module in the middle of a board; dense ground vias near the antenna; keep >= 15 mm clearance in the housing. Fig. 24: positions 1 and 5 (corners) are marked as strongly recommended, mid-edge positions are not. VERIFIED (read from the PDF).
- Board: U60 body (Fab) x 36.35-49.65, y 33.05-49.75, so the antenna end is 0.25 mm from the board edge; `ANT_KEEPOUT` x 35.35-50.65, y 44.2-50 covers the 5.4 mm antenna area (y 44.35-49.75) with a 1.0 mm margin each side. That matches the figure's <= 1-2 mm margin. VERIFIED from the file.
- Deviations from Espressif: module at mid-edge (x centre 43 of 75), antenna not outside the board, no board cut-out beside it, and the nearest copper outside the rule area is within 1 mm laterally (top/bottom pours) plus J51 at 2.9 mm. The housing is a shielded aluminium box (`docs/requirements.md` row 4). Since the radio must stay disabled (power.md: Wi-Fi TX 251-382 mA exceeds the 300 mA U4) the antenna is unused: no performance consequence, only EMI/keep-out hygiene.
- Fix: update README text to say "read, matches Fig. 25 margin, deviates from Fig. 24 corner placement; unused radio". Optionally drop the keep-out (it blocks 88 mm2 of both planes) if the radio is never used. Confidence HIGH on the reading.

### m5. Layer changes of slow pairs without return vias; USB_DN asymmetric layer path
- USB_DN has its only via at (63.28,25.01): 2.55 mm on In2 while USB_DP stays on F/B (total J50-to-U61 length 8.00 vs 4.95 mm). Nearest GND via to that via is 1.9 mm; CAN vias are 1.9-4.5 mm from a GND via. Espressif guideline p.24: "add a pair of ground return vias at each transition point" (USB). 12 Mbps and 125 kbit/s make this electrically harmless; PROPOSED fix: put the layer transition on both lines at the same spot with a GND via beside, or keep USB on one layer. Segment totals are balanced end to end (below).

### m6. DRC cleanups that are real but cosmetic
- Duplicate GND via at (52.65,11.7) on C22 pad 2 (holes_co_located): delete one. Real (a duplicate drill hit in the Excellon file may be flagged by DFM).
- via_dangling at (23.725,27.81) (VCM_REF, in R102 pad 2 on B.Cu; no copper on F.Cu) and (16.475,30.775) (TIA_CTRL, in R57 pad 2; F.Cu track passes through, nothing on B.Cu): both are connected on their net through other copper (0 unconnected) so they are stubs, not breaks; delete both, or finish the intended B.Cu route if one was planned. A filled via-in-pad on an otherwise unused layer is harmless but pointless and VCM_REF/TIA_CTRL are analog.
- track_dangling at (70.675,34.7) (EN, 0.05 mm copper nub next to a via at (71.12,34.7)): delete the nub; the EN net is connected (pads TP60, SW60 x2, R190, C190, U60.8).

### m7. DFM extras (none blocks)
- No fiducials, no panel/tooling/mouse-bite definition (grep of docs/pcb and README: none; footprint list has no FID). JLCPCB adds process rails for assembly; the J50 mouth overhangs 0.95 mm at the right edge (silk at x 75.95), so tell JLCPCB which edges get rails (long edges, not the J50 edge) or panel with the J50 end free. ESP32 module body is 0.25 mm from the bottom edge, so a bottom rail would butt against it: UNRESOLVED, ask JLCPCB. Add two 1.0 mm fiducials (2.0 mm mask opening) for the 0.4 mm pitch ESP32 and 0.5 mm TPD6E05U06/QFN parts if JLCPCB wants them (requirement UNRESOLVED).
- J50 S1 slots at (69.0,25.0) and (72.1,25.0) are 0.2 x 1.0 mm plated slots; `docs/pcb/jlcpcb-fab-settings.md` section 1 lists "multilayer plated slot >= 0.35 mm". The test board `hardware/pcb/j50-dfm-test` passed JLCPCB DFM (Daniel, 2026-10-09, user-reported); whether that test used this slot is not stated: UNRESOLVED, confirm at the real upload.
- J50 B-row: 14 holes 0.4 mm drill / 0.65 pad, ring 0.125 mm (below the 0.15 absolute minimum), waived by rules j50 annular / j50 hole to hole / j50 hole clearance and accepted by the test board at the 0.25 mm tier: documented, nothing to add.
- Min feature use VERIFIED from the file: tracks 0.11 (14 segments, LVDS_P/N only), 0.145 (228), 0.15 (903), 0.2, 0.3, 0.5; JLC multilayer minimum 0.09/0.09. One via type everywhere 0.45/0.25 (all 209). Smallest passives: 12 x 0402, 83+40 0603, no 0201. Closest copper to the board edge outside J50: 0.8 mm (C200 pads at y 49.2), HV tracks 0.88-1.0 mm; Board Setup min 0.30, JLC routed-edge 0.2. Courtyard overlaps: none (DRC clean). No component sits under the J50 overhang or body (bbox overlap scan: none).
- LED D60 at (72.38,40.85) F.Cu; switches SW60/SW61 at (71.28,33.62)/(71.28,37.62); both on the right edge, reachable if the housing has openings (enclosure TBD, not checkable). J51 at the front edge (54.3-67.0, 47.6), pad edge 1.55 mm from the board edge.

### m8. Test points
- 27 TPs, on both sides (F: TP2, 10-12, 20, 21, 50-55, 60-63; B: TP3, 4, 30-32, 64-69). Rails: 3V3 (TP50), 3V3_D (TP51), GND (TP54/55). No TP for VBUS, +5V (eFuse output), APD_BIAS (probably intentional, HV), 5V_HVIN, CAN_P/CAN_N, USB_DP/DN, DAC_TH, LPF_OUT; CAN_P/N are on J51 pins 4/5, so bench access exists. Whether the TP names are visible on Fab: refdes only are on Fab (README); values are not placed. Suggest adding VBUS and +5V TPs (G1 supply bring-up needs them). Confidence MED.

### m9. Handoff to the HV/analog reviewer (plane/pour effects only)
- U3 (LT8365) exposed pad 1.65 x 2.85 mm has only 2 GND vias (0.95 mm from centre each); thermal path and the "power ground" connection per LT8365 Rev. A Fig. 5 are theirs, but 2 vias is light for the switch return.
- GND1/GND2 under the HV island are unbroken; HV on F.Cu lies 0.0994 mm (prepreg 3313, Er 4.1) above GND1: 200-220 V across it is about 2.2 kV/mm, not checked against JLCPCB's dielectric spec (PROPOSED fine, put to the HV reviewer).
- TIA_IN_WINDOW is a real void in GND1/GND2 at x 7.5-16, y 23.2-26.7 (8.5 x 3.5 mm incl. APD can antipads) as intended; LVDS_P/N DRC items are at (44.4-46.2, 25.4-26.0), see triage table.

---

## DRC triage (evidence/drc.rpt, 52 items; doc coordinates)
Rules are live: rule names "diff100 gap" and "diff100 uncoupled" appear in the report. KiCad ignores the whole .kicad_dru on a syntax error, so every rule parsed (VERIFIED). Rules that produced no item (pair skew, pair keepout, hv ..., j50 ...) cannot be shown live individually but are in the same file. No exclusions are set. Severities in .kicad_pro: only hole_to_hole, holes_co_located, silk, dangling are downgraded to warning; four checks are ignored (track_not_centered_on_via, tuning_profile_track_geometries, footprint_filters_mismatch, footprint_type_mismatch): harmless.

| Class (count) | Where | Class | Fix |
|---|---|---|---|
| hole_to_hole (32), actual 0.35 vs 0.4495 | H1 (3.5,3.5), H2 (71.5,3.5), H3 (3.5,46.5), H4 (71.5,46.5): 8 ring-via pairs each | (i) real vs JLC pad rule, low risk | ring radius 1.8 mm or `_Pad` variant (m2) |
| starved_thermal (5) | J50 S1 (71.55,29.27) PWR, (72.1,25.0) PWR, (65.67,27.0) F.Cu, (65.67,23.0) F.Cu; U20 pad 9 (40.35,26.47) F.Cu | (i) real | S1: solid connection + vias (M2). U20.9 (TLV3605 GND pin): set pad zone connection Solid (pin sits between pad 8 and pad 10, only 1 spoke fits); add the via next to it (nearest GND via 1.56 mm). Other regulator/ESP32 GND pads are not flagged: their EPs have via-in-pad and thermal relief; U10 EP is already solid. U5 EP: 1 via, relief inherited, no flag. |
| diff_pair_gap_out_of_range (4 = 2 distinct, reported twice) | LVDS_P/N between (44.4,25.8)-(46.2,26.0): actual 1.0567 mm; (45.7,25.4)/(42.6,25.8): 0.24 mm; max 0.20 | (ii) acceptable as location only | fast-path reviewer to analyse; I only note location. R180 pads are 1.66 mm apart so the pair necessarily opens there |
| diff_pair_uncoupled (1) | LVDS_P, 11.69 mm vs 5 mm | (iii) tooling artifact in part: LVDS_P net length 11.69 mm includes the 4.34 mm R87 hysteresis tap; only 17 % of P/N run within 0.25 mm gap, through-path P 7.35 mm vs N 7.58 mm to U50 pins 6/7 | handled by the fast-path reviewer; rule already notes it |
| via_dangling (2) | (23.725,27.81) VCM_REF; (16.475,30.775) TIA_CTRL | (i) stubs, not breaks | delete or finish route (m6) |
| track_dangling (1) | (70.675,34.7) EN, 0.05 mm | (i) cosmetic nub, not a break | delete (m6) |
| holes_co_located (1) | (52.65,11.7) two GND vias | (i) real duplicate | delete one (m6) |
| silk_edge_clearance (5) | J50 silk at x 75.95 (y 20.51 and 29.49), 0 clearance: silk lies on the 0.95 mm overhang outside the board; U60 B.SilkS at (36.25,49.85) and (49.75,49.85), 0.09 mm vs 0.15 | (ii) acceptable | J50 silk is outside the outline and is clipped; delete U60 silk edge segments or accept; document as exclusion |
| silk_overlap (1) | U51/U52 silk at (60.8,25.2)/(62.26,24.85), 0.085 mm | (ii) acceptable cosmetic | move/trim silk or exclude |

DRC items that are NOT there but I checked: 0 clearance, courtyard, edge, annular, unconnected, isolated_copper, mask web, silk-over-pad. ERC 0/0.

## Diff-pair table (lengths are the sum of all segments of the net, all layers; vias counted on the net; script a2/a5/a21)
| Pair (netclass) | Path | Len P mm | Len N mm | Mismatch | Vias P/N | Layer(s) | Reference | Coupled share* |
|---|---|---|---|---|---|---|---|---|
| LVDS_OUT1 (DIFF90, 0.145/0.15) | U50.16/15 -> U52 pins 1,14 / 2,13 -> J50 B3/B2 | 20.98 | 19.78 | 1.20 | 0/0 | F.Cu | In1 (solid) | 77 % |
| LVDS_OUT2 (DIFF90) | U50.14/13 -> U51 pins 3,12 / 4,11 -> J50 A3/A2 | 11.84 | 11.90 | 0.06 | 0/0 | F.Cu | In1 | 69 % |
| CAN_P/N (CAN90), both branches summed | U64.7/6 -> U51 -> J50 B11/B10 (B.Cu) and -> U52 -> J50 A11/A10 (F.Cu/In2) + J51 pins 4/5 stub | 62.95 | 62.28 | 0.67 | 3/3 | F 34.9/33.9, B 21.0/22.0, In2 7.1/6.4 | In1/In4/In3 | 78 % |
| USB_DP/DN, J50 to U61 | J50 A6,B6 / A7,B7 -> U61.1/3 | 4.95 | 8.00 | 3.05 | 0/1 | F 1.5/1.5, B 3.4/4.0, In2 0/2.55 | In1/In4/In3 | 36 % |
| USB_ESD_DP/DN, U61 to 22R | U61.6/4 -> R193/R194 | 18.58 | 14.38 | 4.20 | 0/0 | B.Cu | In4 | 73 % |
| USB_E_DP/DN, 22R to ESP32 | R193/194.2 -> U60.18/17 (+C206/C207 taps) | 5.95 | 6.76 | 0.81 | 0/0 | B.Cu | In4 | 61 % |
| USB end to end (J50 pad to U60 pin) | sum of the three rows | 29.5 | 29.1 | 0.4 | 0/1 | | | |
| LVDS_P/N (DIFF100, 0.11/0.15), U20 to U50 | through-path U20.12/10 -> U50.6/7 | 7.35 | 7.58 | 0.23 | 0/0 | F.Cu | In1 | 17 % (see above) |
*share of P segment length within 0.25 mm edge gap of N on the same layer; gap median 0.15 mm in all pairs (matches DIFF90 target); uncoupled stretches are the pin fan-outs. All DIFF90 uncoupled lengths are below the 10 mm rule (no DRC hit). Intra-pair skew rule is 2.5 mm: OUT1 1.20 mm passes.

Findings on the pairs (all VERIFIED from the file unless marked):
- Reference continuity: every F.Cu sample along LVDS_OUT1/2 and LVDS_P/N lies over solid GND1; every B.Cu sample of USB_E/USB_ESD lies over GND2. The only voids under the pairs are via/PTH antipads: the J50 B-row (2 x 6 mm merged antipad at (65-67,22-28) in both GND1 and GND2 under the B-row holes), 3-5 samples at the J50 pads. CAN/USB runs on In2 reference In3, which is the 3V3_D pour under the CAN segments (slow signals, ignorable). No plane split under any controlled pair (script a4).
- Topology: no stubs. LVDS_OUT1/2 and the USB lines pass through (flow-through) the ESD arrays. CAN is a split trunk, the two J50 RX-pair branches are 25.07 (A11) and 24.97 (B11) mm from U64, 24.01/24.88 mm for CAN_N; no termination on the module (R182/R183/C180 DNP, docs/schematic/connector.md); the J51 debug tap is a 14.7 mm F.Cu stub per line; at 125 kbit/s with a slowed driver it is below the SLLA270 stub guidance the docs cite (arithmetic not repeated here, PROPOSED).
- LVDS_OUT1 takes a loop around the top of J50 (11.4 mm from U52 pins 14/13 to B3/B2 for a 6 mm straight distance), U52 sits 3 mm from J50 on OUT2 side: acceptable, no via, but the loop is dead length ahead of the connector; harmless at 50 Mbps, PROPOSED to shorten.
- 22 ohm USB resistors R193/R194 at (47.3,29.0)/(47.3,30.5) are 4.2-6 mm from U60 pins 17/18 (Espressif: "close to the chip side", p.24); 12 Mbps full speed, so acceptable. C206/C207 at (43.25,31.8)/(42.25,31.8) are right at the chip.
- Impedance (own arithmetic, IPC-2141 edge-coupled microstrip, PROPOSED, not a field solve and not JLCPCB calculator output): w 0.145, s 0.15, h 0.0994, Er 4.1, t 0.035 gives Z0 about 51 ohm and Zdiff about 90 ohm; w 0.11, s 0.15 gives about 104 ohm for DIFF100. Consistent with the README's solver values; mask not included. Stackup in the file matches README (0.0994/0.55/0.1088/0.55/0.0994, JLC06161H-3313). Confirm with the JLCPCB calculator (README already says so).
- Pair spacing to foreign copper: OUT1 0.35 mm to CAN_P (62.8,21.9), 0.51 mm to OUT2_P; OUT2 0.35 mm to GND/VBUS tracks (62.2,27.1), (63.7,26.8): all >= 2 x gap, rule "pair keepout" is satisfied.

## Planes, pours and stitching (VERIFIED, script a1/a3/a11/a25)
- Layer use: F.Cu 601 tracks, B.Cu 546, In2 (SIG_IN) 128, tracks on In1/In3/In4: 0. In1 (GND1) and In4 (GND2) fill area 3449.9 mm2 each, identical; voids are only through-hole/via antipads, the 0.3 mm edge pullback, ANT_KEEPOUT (touches the edge), TIA_IN_WINDOW, the J50 B-row merge and the 2.2 mm antipads of J51 and mounting holes. The 124 void components include no unexplained slot.
- Rail pours (In3): PWR_3V3 743 mm2 with 17 net vias into it, PWR_3V3_D 990 mm2 with 10 (+2 same-net vias outside the pour: (63.25,13.23), (37.85,7.05), i.e. the R33 and C30 pads linked by track), PWR_5V 163 mm2 with only 3 vias (+1 outside: L2 at (37.61,11.35)). 0 unconnected items after refill, 0 isolated_copper in the DRC. README's list of pads needing a trace (TP50, R33, R39, U4 group, C18/L2, C29) is all connected (by vias in the pad or track), TP50 via-in-pad.
- GND_In3 (In3 GND pour) refills into 78 separate polygons, each tied by vias (islands removed): not a problem, but its coupling to In2 is mostly 3V3/3V3_D/GND mixed, so In2 slow signals see several reference pours (slow signals only).
- Stitching: 100 GND vias in total, 84 of them in pads; see m3 for the uncovered regions.

## Decoupling (VERIFIED from the file, centre-to-centre distances)
| IC | Supply pin | Cap(s), pin to cap pad | GND via of cap |
|---|---|---|---|
| U10 OPA857 | 3V3 pins 9-11 | C57 100n 1.2-1.3 mm, C56 100n 2.5 mm, C59 1u 3.8 mm | 2.3 / 1.3 mm / in pad |
| U11 OPA855 | 3V3 pins 7,8 | C52 100n 1.2-1.4 mm, C58 1u 2.1-2.5 mm | 1.55 mm / in pad |
| U20 TLV3605 | VCC pin 2 | C80 100n 1.46 mm, C81 1u 4.3 mm | both in pad |
| U20 | VCCO pin 1 (net U20-VCCO) | C82 100n 1.6 mm, C83 1u 5.7 mm | C82 via 0.06 mm |
| U50 LVDS104 | 3V3 pins 1-4 | C184 100n 2.1-2.9 mm, C185 1u 2.4-2.6 mm | 3.2 / 3.0 mm (M3) |
| U30 OPA2320 | 3V3 pin 8 | C103 100n 1.9 mm | in pad |
| U5 eFuse | VBUS pin 4 / +5V pin 5 | C33 4.7u 4.4 mm; C1 10u 2.6 mm, C2 100n 2.75 mm | C33 via 0.12; C1 2.0; C2 0.19 mm |
| U1 LDO | in pins 1,3 / out pin 5 | C9 1u 1.7 mm; C11 4.7u 2.2 mm, C10 4.7u 3.6 mm, C12 1n | C9 1.0; C11 0.4; C10 1.7 mm |
| U4 LDO | in pins 1,3 / out pin 5 | C29 1u 2.5 mm; C31 1u 1.85 mm, C30 10u 2.7 mm | C29 0.12; C31 4.5; C30 5.2 mm |
| U60 ESP32 | 3V3_D pin 3 | C192 100n 1.8 mm, C191 10u 2.7 mm | 0.83 / 1.4 mm |
| U64 | 3V3_D pin 3 | C196 100n 2.2 mm | 2.2 mm |
| U62 MCP4728 | 3V3_D pin 1 | C194 100n 1.7 mm | via 0.04 mm |
| U63 ADS1115 | 3V3_D pin 8 | C195 100n 2.85 mm | in pad |
| U3 LT8365 | VIN pin 3 (5V_HVIN) | C20 4.7u 2.2 mm, C19 10u 3.9 mm | both in pad |
- LT8365 input: the pi filter C18 (10u, at L2, (35.95,11.65)) -> L2 0.47 uH -> C19/C20 at VIN does have local bulk at the pin (C19 10u and C20 4.7u, 3.9/2.2 mm); it is fed from the eFuse through 28.8 mm of 0.5 mm In2 and a single via at each end (5.7 nH estimated for 21 mm over In3 at 0.1088 mm: own arithmetic, PROPOSED). Acceptable; add a via (m1).
- ESP32 3V3_D feeding: 0.15 mm B.Cu net (48.5 mm of tracks on the whole rail) to pin 3, estimated load 60 mA (power.md); R is a few mohm per mm, a few mV drop (PROPOSED), C191/C192 are local.
- Not checked: the datasheet decoupling requirement of each IC (only placement distances).

## What I checked and found correct
Stackup in file equals README/JLC06161H-3313; vias 0.45/0.25 on all 209 (annular 0.10 per the rule, JLC needs pad >= drill + 0.1); track min 0.11 over JLC 0.09; solid In1/In4; no routing on planes; rails connected; pairs matched with no splits and no stubs; diff gap median 0.15 mm everywhere; DIFF90 spacing to other copper >= 0.35 mm; LVDS_OUT has 0 vias; USB pair ends balanced to 0.4 mm end to end; U61 and U52/U51 are flow-through; both CAN branches equal; U60 thermal pad 9 vias; courtyards clean; no part under the J50 overhang; copper-to-edge >= 0.8 mm (excluding J50); `.kicad_dru` parses; ERC clean.

## QUESTIONS / UNRESOLVED
1. Is the intent for JLCPCB to fill every via (M1)? Which option and price? Needed before the G4 pre-order checks pass.
2. Will JLCPCB treat the 0.4 mm ring holes of the mounting holes as vias (0.2 mm rule) or pad holes (0.45 mm)? Moot if the ring moves to r=1.8 mm.
3. Should the CAN bus end terminate on the module? docs say no (connector.md: "no termination on the module"; bus on both RX pairs is about 45 ohm in parallel, PROPOSED). Two parallel J50 branches are equal length, so the stub issue is only the J51 tap.
4. Does the 0.2 mm J50 shell slot at (69,25) and (72.1,25) pass JLCPCB DFM (doc minimum 0.35 mm plated slot)? Test board outcome does not state it.
5. SN65LVDS104 pin 1-4 are all on 3V3 in the netlist and pins 5/8 are GND; the datasheet is not in docs/datasheets so I did not verify the pinout or its layout guidance (the schematic reviewer should).
6. TPD6E05U06 layout guidance (GND via placement) is not in the repo; M3 uses general practice.
