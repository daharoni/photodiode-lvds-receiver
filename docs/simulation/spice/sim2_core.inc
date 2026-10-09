* Sim 2 core: OPA857 TIA with APD source capacitance, as on the Front End sheet (docs/schematic/frontend.md)
* Pins of the TI model: CTRL GND IN OUT OUTN VS. CTRL = 3.3 V -> 20k mode, 0 V -> 5k mode (model: CTRL high selects the
* 20k feedback path; board: R57 pull-up = 20k). OUTN (TP12) unloaded.
* APD = current source (photocurrent INTO the IN pin) in parallel with CD; cathode node HVK is AC ground through
* C50 10n and the bias supply (R50 10k to an ideal, AC-quiet bias). DC bias not modelled (AC-coupled signal only).
* Load on OUT: C51 100n into R51 1k (OPA855 input return); R58 1k tap to the high-impedance RSSI diode is open here.
.include sim2_iph.inc
VS 3V3 0 3.3
VCTRL CTRL 0 {CTRLV}
XU10 CTRL 0 IN OUT OUTN 3V3 OPA857
CAPD IN HVK {CD}
C50 HVK 0 10n
R50 HVK 0 10k
C51 OUT PA_IN 100n
R51 PA_IN 0 1k
