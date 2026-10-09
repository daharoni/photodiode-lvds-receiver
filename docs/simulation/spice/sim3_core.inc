* Sim 3: Monitor sheet VCM_REF buffer (docs/schematic/control.md, gen/control.py): U30A OPA2320 unity follower
* R100/R101 10k/10k from 3V3 to GND, C100 100n at the midpoint -> IN+. Feedback from the op-amp OUT pin (before R102).
* OUT -> R102 10 ohm -> VCM_REF node with C101 1u to GND. Loads: three 1k returns (LOADMODE 0: to ground, DC 1.65 mA
* each = spec case; LOADMODE 1: each in series with 10 uF, AC load only). RD 1k = the disturbance source resistor.
* TI OPAx320 model (SBOM438; single-core OPA320 = one channel of the OPA2320). Pins IN+ IN- VCC VEE OUT.
VDD 3V3 0 3.3
R100 3V3 MID 10k
R101 MID 0 10k
C100 MID 0 100n
* VT: AC stimulus at IN+. VT2: 10 mV step at IN+ (at 400 us, 400 us wide, 100 ns edges) for the small-signal step test.
VT2 M2 MID PWL(0 0 400u 0 400.1u 0.01 800u 0.01 800.1u 0)
VT INP M2 DC 0 AC 1
XU30 INP INM 3V3 0 OPOUT OPAx320
R102 OPOUT VCM_REF {R102}
C101 VCM_REF 0 1u
* LOADMODE 0: three 1k to ground (DC); 1: three 1k each in series with 10 uF (AC load only)
RL1 VCM_REF L1 1k
RL2 VCM_REF L2 1k
RL3 VCM_REF L3 1k
.if (LOADMODE == 0)
RS1 L1 0 0.001
RS2 L2 0 0.001
RS3 L3 0 0.001
.else
CS1 L1 0 10u
CS2 L2 0 10u
CS3 L3 0 10u
.endif
* disturbance (source idles at 1.65 V so it draws no DC): 100 mV step injected at the C101 node through 1k (a signal-return event)
VD D 0 PWL(0 1.65 1m 1.65 1.00002m 1.75 1.5m 1.75 1.50002m 1.65)
RD D VCM_REF 1k
