# drv_ads1115

Status: PROPOSED; compiled (ESP-IDF v5.5.5, 2026-10-12); not host-tested; not run on hardware.

ADS1115 on I2C 0x48. Datasheet SBAS444E (Dec 2024), read from `docs/datasheets/ads1115.pdf`; registers: Table 8-1 p.24, Config Table 8-3 p.25-26, FSR Table 7-1 p.15, single-shot s.7.4.2.1 p.18, address Table 7-2 p.21.

Single-shot, AINx vs GND, PGA +-4.096 V (125 uV/LSB), 128 SPS, OS-bit poll with 30 ms timeout, 4-sample average by default. About 31 ms per `ads1115_read_mv` call, so a sense round of three channels is about 100 ms. This conflicts with the README s.3 table ("about 30 ms per round"); the README number looks like a per-channel figure. UNRESOLVED.

Waits shorter than 10 ms use `ticks_at_least_1()` (board_time.h). Failures set FAULT_I2C_ADC. Takes `board_i2c_mutex()` per transaction.
