# J50 receptacle (Wuerth 632723300011) and JLCPCB hole rules

Status: research, 2026-10-09. Labels: VERIFIED = read on a cited page/drawing on 2026-10-09; PROPOSED = recommendation or own arithmetic; UNRESOLVED = not established. Nothing here was measured and JLCPCB was not asked.

Sources: CAP = https://jlcpcb.com/capabilities/pcb-capabilities (saved copy `docs/research/downloads/jlcpcb/cap.html`, read 2026-10-09). WE = `docs/research/downloads/usbc-connector/wurth-632723300011.pdf` (revision 003.000, 2025-09-04, page 1 Recommended Land Pattern). LCSC pages read 2026-10-09 through WebFetch (cited per row).

## 1. JLCPCB PTH rules (VERIFIED, CAP text, multilayer)

- "PTH annular ring ... Multilayer: 1 oz: Recommended 0.20 mm or above; absolute minimum 0.15 mm"
- "Pad Hole-to-Hole Spacing 0.45mm" (and "Via Hole-to-Hole Spacing 0.2mm")
- "PTH to Track 0.28mm / 0.35mm is recommended, minimum 0.28mm"
- "Inner layer PTH pad hole to copper clearance 0.3mm"
- "To avoid soldermask or tin stuck in the hole, recommended PTH size>=0.5mm." Hole tolerance "Through-holes: +0.13 / -0.08 mm".
- Exceptions: searching the saved CAP text for exception, connector, "flagged", "manufacturab" found nothing. CAP states no connector exception and no "flagged in DFM but manufacturable" wording. The only DFM mention is the "JLCDFM - DFM Check" navigation link. (VERIFIED absence in the saved page; the live page was not re-fetched.)

## 2. Footprint vs rules (PROPOSED arithmetic from the footprint and WE drawing)

WE page 1 land pattern (VERIFIED): B holes "O 0,65" pad, "O 0,4 +0.05/-0.0" drill, 0.8 mm pitch per row, rows 0.7 mm apart. Current footprint: ring (0.65-0.40)/2 = 0.125 (below 0.15 absolute minimum); same-row hole wall-to-wall 0.80-0.40 = 0.40 (below 0.45); hole to neighbour copper about 0.275 (below 0.28 minimum, 0.30 inner).

Options for the B row (all PROPOSED):
- 0.70 pad / 0.40 drill: ring 0.15 (JLC absolute minimum, not the 0.20 recommendation); hole-to-hole still 0.40; hole to neighbouring-row pad copper about 0.28 (marginal); same-row pad gap 0.10.
- 0.70 pad / 0.35 drill: ring 0.175, hole-to-hole 0.45 (equals the rule), hole to copper about 0.28. Not allowed without Wuerth data: WE's drawing gives 0.4 as the drill and I found no THT pin diameter in the drawing text (UNRESOLVED, the pin dimension is graphical and was not read). With +0.13/-0.08 tolerance a 0.35 drill can finish at 0.27 mm.

## 3. LCSC / JLCPCB availability

- Wuerth 632723300011: no LCSC or JLCPCB listing found (searches 2026-10-09 returned only distributor pages; lcsc.com search page returns no listing text, and the EasyEDA API and LCSC datasheet downloads were blocked). So there is NO evidence JLCPCB has fabricated this footprint. 632723300112: nothing found. (UNRESOLVED; check lcsc.com by hand.) Sibling 632723300021 appears on flux.ai and trace-tec.vn only.
- HCTL HC-TYPE-C-24P-MM-1.4-5A-12, C5307768: "Surface Mount, Right Angle", 738 in stock, $0.665 (1+). https://www.lcsc.com/product-detail/C5307768.html . Pad/drill not obtained; whether it has THT shell legs not stated.
- HCTL HC-TYPE-CF-24P-RAT-Z, C2894903: "Surface Mount, Right Angle", 878 in stock. https://www.lcsc.com/product-detail/C2894903.html . Dimensions not obtained.
- HCTL HC-TYPE-C-24P-DS10.0-CH2.75S-5A-04, C5342433: "Through Hole, Right Angle", 736 in stock. https://www.lcsc.com/product-detail/C5342433.html . Hybrid status not stated.
- SHOU HAN TYPE-C 24P-GTJB 040, C3151751: Extended, package SMD, no stock shown. https://jlcpcb.com/partdetail/SHOUHAN-TYPE_C_24P_GTJB040/C3151751
- HCTL 24P C5345936 / C5345940: Extended (search snippet), SMD. https://jlcpcb.com/partdetail/C5345936
- GCT USB4125-GF-A: DigiKey lists 6 active contacts ("24 (6+18 Dummy)", power only), so it is NOT a full-featured 24-pin part. The repo also has GCT USB4085/4110 drawings showing 16-contact parts.
- Amphenol 12401610E4#2A: DigiKey "Surface Mount, Right Angle; Through Hole"; no LCSC listing found. Molex 217175: not searched.
- Whether JLC's own footprints for these parts violate the same rules, and whether JLCPCB accepts 0.5 mm-pitch hybrid footprints regardless of the stated minima: UNRESOLVED (footprint dimensions could not be fetched).

## 4. Recommendation (PROPOSED)

Keep the Wuerth 632723300011 (approved by Daniel 2026-10-09). Change the B-row signal pads to 0.70 mm pad / 0.40 mm drill (ring 0.15, the JLCPCB absolute minimum) via a lab-library footprint PR; do not use a 0.35 mm drill. Waive the remaining two hole rules for J50 only with a custom DRC rule, and add a G4 pre-order item: upload the Gerbers to JLCPCB (order quote and JLCDFM) and get written confirmation, or a response from JLCPCB support, that the J50 B-row holes (0.40 drill, hole-to-hole 0.40) are manufacturable. If JLCPCB rejects them, fall back to an SMT-only 24-pin part (C5307768 or C2894903, needs a library PR, shell retention is weaker and cable-insertion force on a SMT-only part is the risk) or ask WE for an alternative drill.

Honest status: this is a waiver of JLCPCB's stated minimum, not evidence that JLCPCB builds it.

DRC rules (KiCad 10 syntax, UNTESTED; put after the general rules because later rules take priority):

```
(version 1)
(rule "J50 THT annular ring"
  (condition "A.memberOfFootprint('J50')")
  (constraint annular_width (min 0.15mm)))
(rule "J50 hole to hole"
  (condition "A.memberOfFootprint('J50') && B.memberOfFootprint('J50')")
  (constraint hole_to_hole (min 0.40mm)))
(rule "J50 hole to copper"
  (condition "A.memberOfFootprint('J50')")
  (constraint hole_clearance (min 0.27mm)))
```

## 5. Outcome (2026-10-09)

Daniel uploaded the test board `hardware/pcb/j50-dfm-test` to JLCPCB: the DFM check passed without error with the quote option "Min via hole size/diameter" = 0.25 mm/(0.35/0.4 mm) (the high-precision tier; JLCPCB then auto-selects "4-Wire Kelvin Test" and "FR4 Tg155", extra cost) (user-reported with a screenshot of the option; whether the standard 0.3 mm/(0.4/0.45 mm) tier also passes was not tested, UNRESOLVED). Decision: keep the Wuerth 632723300011 and its footprint as drawn by WE (no pad enlargement), order the receiver module with that option, and waive the three hole rules for J50 only in `receiver-module.kicad_dru`. The SMT-only fallback parts in section 4 are not needed.

## Not verified

LCSC/JLCPCB listing and footprint of the Wuerth part; pin diameter of the B-row legs; pad/drill of any LCSC alternative; JLCPCB's reaction to the waiver; the DRC rule syntax (not run).
