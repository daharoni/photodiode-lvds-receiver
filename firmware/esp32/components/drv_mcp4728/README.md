# drv_mcp4728

Status: PROPOSED; compiled (ESP-IDF v5.5.5, 2026-10-12); not host-tested (the parser `mcp4728_parse_read` and `mcp4728_eeprom_defaults_ok` are pure but live in the IDF source); not run on hardware.

MCP4728 quad DAC on I2C 0x60 (DAC_TH = channel B, DAC_HV = channel C). Datasheet DS22187E, read from `docs/datasheets/mcp4728.pdf`; each constant in `drv_mcp4728.c` cites its page.

- Read command (24 B, Fig 5-15 p.45), not the General Call Read. Framing check: the DAC1:DAC0 bits of every returned group must match the channel (PROPOSED check).
- Volatile write: Multi-Write, UDAC = 0, VREF = VDD, PD = 00 (p.35, Fig 5-8 p.39), with no LDAC pulse (changed 2026-10-12, finding 10): `drv_gpio_init()` holds LDAC (IO6) high, and with LDAC = 1 and UDAC = 0 the selected channel updates at the data ACK (DS22187E Table 4-5 p.26). `mcp4728_last_code(ch)` returns the last code written or read back (no I2C).
- EEPROM defaults: Sequential Write from channel A (p.36, Fig 5-9 p.40), wait for RDY/BSY pin and bit (TWRITE 25 ms typ, 50 ms max, p.6), 60 ms limit.
- Faults: any I2C error or readback mismatch sets FAULT_I2C_DAC.
- Takes `board_i2c_mutex()` around each transaction (not held while waiting for the EEPROM).
