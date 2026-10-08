# ULX3S LVDS input from the TLV3605 pair

Labels: VERIFIED (cited page), PROPOSED (recommendation), UNRESOLVED (documents do not settle it).
Sources: Lattice FPGA-TN-02032 v1.4 ("TN"); ULX3S schematics v3.1.7 ("ULX3S", PDF page = sheet); TI SNOSDA2F Rev F, June 2024 ("TLV3605 DS").
Nothing here was measured or simulated. Checked on 2026-10-08.

## 1. Answer

Yes. The ECP5 can receive the TLV3605 pair directly as a true differential LVDS input on ULX3S header pins gp/gn[8..13] (bank 7) or gp/gn[14..21] (banks 2/3), even though those banks run at 3.3 V (bank 7: 2.5 V or 3.3 V, see below). Differential input buffers are powered from VCCAUX (2.5 V), not VCCIO, and are supported independent of VCCIO. On-die 100 ohm differential termination (DIFFRESISTOR="100") is available on every pair of the left and right banks, which includes banks 7 (left) and 2/3 (right), so no external termination or LVDS-to-LVCMOS receiver IC is needed. Do not use gp/gn[0..7] or [22..27]: those are on top banks 0/1, which have no differential input and no on-die termination. The remaining unknowns are the ECP5 LVDS input common-mode range (not in the TN; expected to be met by the TLV3605 1.2 V output common mode) and open-source toolchain support for DIFFRESISTOR.

## 2. Findings

| # | Finding | Label | Citation |
|---|---|---|---|
| 1 | Differential inputs (LVDS, SUBLVDS, MLVDS25, BLVDS, SLVS) are supported on A/B and C/D pair PIOs "on left and right sides only". | VERIFIED | TN p.14, s.4.11.6 |
| 2 | "Left and right banks can support LVDS input buffers." Top banks 0/1 are not listed. | VERIFIED | TN p.26, bank-rules list |
| 3 | LVDS input is "Yes" in the differential standards table; LVDS output only on A/B pairs. Table 3.2 lists no VCCIO column for differential standards. | VERIFIED | TN p.7, Table 3.2 |
| 4 | "All differential and referenced inputs are supported independent of VCCIO." | VERIFIED | TN p.13, s.4.10 |
| 5 | Bank VCCAUX (2.5 V) powers the differential and referenced input buffers. | VERIFIED | TN p.9, s.4.3 |
| 6 | On-chip 100 ohm differential input termination exists "between all pairs of all banks on left and right sides"; 100 ohm is the only value, on/off programmable. | VERIFIED | TN p.15, s.4.11.8 and Fig. 4.5 |
| 7 | DIFFRESISTOR values OFF/100, default OFF, "available only for differential IO_TYPES". Syntax example: `IO_TYPE="LVDS" DIFFRESISTOR="100"`. | VERIFIED | TN p.20, s.5.6; p.24 attribute example |
| 8 | "DIFFRESISTOR termination is available on all sysI/O pairs of left and right banks." | VERIFIED | TN p.26 |
| 9 | The differential IO_TYPE attribute is assigned only to the TRUE pad (gp); the tool assigns the complement (gn). | VERIFIED | TN p.26 |
| 10 | Bank placement: banks 0/1 top, 7/6 left, 2/3 right, 8 config (lower left). | VERIFIED | TN p.8, banking figure |
| 11 | ULX3S gp/gn[0..7] on bank 0; gp/gn[8..13] "differential bidirectional" on bank 7; gp/gn[14..21] on banks 2/3 (via "ram" sheet); gp/gn[22..27] on bank 1 ("gpdi" sheet). Note: "BANK0,1 are single-ended (non-differential)". Only A/B pairs are routed to the GPIO headers. Project notes confirmed. | VERIFIED | ULX3S p.2 (gpio sheet notes) |
| 12 | VCCIO wiring on U1 (LFE5U-85F-6BG381C): banks 1, 2, 3, 6, 8 on fixed +3V3. Banks 0 and 7 on net 2V5_3V3, a selectable rail (jumper VJ1/J5 choosing +3V3 or +2V5, plus 0 ohm options RV2/RV3). No bank is fixed at 2.5 V. | VERIFIED (net wiring); default jumper position UNRESOLVED | ULX3S p.3 (power sheet, U1I and VJ1) |
| 13 | TLV3605 output is LVDS: VOD 250/350/450 mV (min/typ/max), VOCM 1.125/1.2/1.375 V, specified with RLOAD = 100 ohm, VCCI=VCCO = 2.5 to 5 V. | VERIFIED | TLV3605 DS p.7, electrical characteristics |
| 14 | "When the input of the downstream device is terminated with a 100 ohm resistor, it provides a +/-350 mV LVDS swing"; output designed to drive a standard LVDS input such as high-speed FPGAs. | VERIFIED | TLV3605 DS p.13, s.6.4.2; p.1 |
| 15 | Layout guidance: "Use a 100 ohm termination resistor across the device's LVDS outputs" (see Section 3 on where). | VERIFIED | TLV3605 DS p.19, layout list item 6 |
| 16 | ECP5 LVDS input common-mode range, differential threshold and input swing limits. The TN has no "common mode" entry. The family data sheet FPGA-DS-02012 is not in docs/datasheets/; a direct fetch returned an HTML page, not the PDF. | UNRESOLVED | TN searched; DS-02012 not obtained |
| 17 | Open-source flow (nextpnr-ecp5/Trellis) support for DIFFRESISTOR and LVDS input is not covered by any local document. | UNRESOLVED | none |
| 18 | The ULX3S bank-7 pair pads GP12/GN12 are labelled PCLKT7_1/PCLKC7_1 on the schematic (pins G3/F3). Pad-level pair labels for the other header pins were not extracted. | VERIFIED (GP12 only) | ULX3S p.2 |

## 3. Recommended receive arrangement (PROPOSED)

Terminate with the on-die DIFFRESISTOR="100" at the ECP5, using one true pair on bank 7 or banks 2/3.
Reasoning: (a) findings 1-8 show the receiver is legal and terminable on these banks regardless of the 3.3 V VCCIO; (b) the TLV3605 is specified into 100 ohm (finding 13) and the termination belongs at the receiving end of the line, so on-die termination puts it at the FPGA pins with the shortest stub; (c) an LVDS-to-LVCMOS IC adds delay, jitter and a part on a board we do not own, for no benefit.

Pin choice (PROPOSED):
- First choice: a gp/gn pair in 8..13 (bank 7, left). Caveat: bank 7 VCCIO is switchable 2.5/3.3 V on the ULX3S (finding 12). That does not matter for the LVDS input (finding 4) but matters for any single-ended lines sharing the bank. Check the jumper position on the physical board.
- Second choice: gp/gn[14..21] (banks 2/3, fixed 3.3 V, shared with SDRAM and buttons on the "ram" sheet, so check for loading on the header net).
- Constrain the true pad (gp) only; the gn pin is the complement (finding 9). Use the even/odd assignment that the board's pad-to-header map gives; do not guess polarity. Polarity can be swapped in gateware if reversed.

Receiver-board connector sheet (PROPOSED):
- Nets: LVDS_P and LVDS_N as a 100 ohm differential pair to a connector, with ground returns beside them (each GND pin interleaved, not shared with HV or TIA ground paths).
- No termination resistor fitted as default. Place a 100 ohm 0.1 % 0603 footprint across LVDS_P/LVDS_N at the connector, marked DNP, for bench use (scope or a test load with no FPGA attached). Never populate it when the ULX3S DIFFRESISTOR is enabled: two 100 ohm loads make about 50 ohm and cut VOD by about half (arithmetic, not measured).
- If a fallback to external termination at the FPGA is needed (toolchain without DIFFRESISTOR, finding 17), put a 100 ohm resistor on a ULX3S-side adapter or header breakout across the pair, not on the receiver board.
- Keep the AC-coupling and DC bias out of this path: the TLV3605 output already sits at about 1.2 V common mode (finding 13) and the ECP5 input is DC-coupled by the datasheet LVDS scheme. No series capacitors.
- Keep the TLV3605 on 3.3 V (inside the 2.5-5 V range, finding 13). Place no 3.3 V pull-ups or ESD parts that load the pair.

## 4. Open items

1. Obtain FPGA-DS-02012 and record the LVDS input common-mode range and minimum differential input swing; check them against VOCM 1.125-1.375 V and VOD 250-450 mV (UNRESOLVED).
2. Confirm that the open-source flow (if the project uses it) honours DIFFRESISTOR; otherwise use Diamond or the external-termination fallback (UNRESOLVED).
3. Read VJ1 default and RV2/RV3 on the physical ULX3S; the schematic does not say which is populated (UNRESOLVED).
4. Confirm the exact gp/gn header-pin to ECP5 ball map for the chosen pair on p.2 (pin-by-pin extraction not done).
5. Bench: verify the received eye and VOD on the header with the termination enabled; no measurement exists yet.

## 5. architecture.md "Signal chain" item 10: contradictions

Quoted: "ULX3S true pairs: gp/gn[8..13] (bank 7), gp/gn[14..21] (banks 2/3); VCCIO 3.3 V; use DIFFRESISTOR for termination. LVDS input on a 3.3 V bank is UNVERIFIED. Label: UNRESOLVED (pending that check)."

- "gp/gn[8..13] (bank 7), gp/gn[14..21] (banks 2/3)": confirmed (ULX3S p.2).
- "VCCIO 3.3 V": partly wrong. Banks 2/3 are fixed 3.3 V, but bank 7 is on the switchable 2V5_3V3 rail (ULX3S p.3).
- "LVDS input on a 3.3 V bank is UNVERIFIED": now VERIFIED as supported (TN p.13 s.4.10, p.14 s.4.11.6, p.26). Differential inputs do not depend on VCCIO. The residual unknown is the input common-mode range, not the VCCIO.
- "use DIFFRESISTOR for termination": consistent with TN p.15 and p.26, valid on banks 7 and 2/3 only (left and right banks), not on banks 0/1 (gp/gn[0..7] and [22..27]).
- The "Label: UNRESOLVED" can become PROPOSED (arrangement) with open items 1-2 kept UNRESOLVED.
