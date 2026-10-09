Notes: 
The OPA320S Spice model meets the following datasheet specs for 5.5V (+-2.75V) operation 
at a temperature of 27C with a load resistance of 10kohms:
- VOS, 
- IIB, 
- Input common-mode Voltage Range, 
- CMRR, 
- Noise, 
- Input Capacitance,
- Open-loop voltage gain, 
- GBW, 
- Slew Rate, 
- Output Voltage Swing, 
- Open-loop Output Resistance, 
- Quiescent Current
- Enable Time 
 
The model meets the following specs over the published operating temperature 
range:
- IIB

The model does not meet the following datahseet specs:
- Phase margin
- AOL at 2k load resistance, 
- Power-on time,
- Thresholds for enable & disable 
- Disable time is longer than the published spec.

The model will shut-down if the inputs exceed the maximum rated voltage.

The model enable/disable threshold is at the midpoint of the power supplies.

The settling time for the macromodel is less than the published device specs.