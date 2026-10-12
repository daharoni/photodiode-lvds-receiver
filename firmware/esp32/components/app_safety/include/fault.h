/* Latched fault word. Bits: docs/firmware/can-and-console-protocol.md s.5
 * (PROPOSED). Thread safe (atomic). */
#pragma once
#include <stdint.h>

typedef uint16_t fault_word_t;

#define FAULT_I2C_DAC      (1u << 0)   /* MCP4728 NACK or readback mismatch; HV off */
#define FAULT_I2C_ADC      (1u << 1)   /* ADS1115 NACK or conversion timeout; HV off */
#define FAULT_DAC_EEPROM   (1u << 2)   /* EEPROM defaults not as expected; no enable accepted */
#define FAULT_HV_OVER      (1u << 3)   /* bias above hv_max + 5 V; HV off */
#define FAULT_HV_UNDER     (1u << 4)   /* ramp timeout or collapse below 70 % of set; HV off */
#define FAULT_HV_STUCK     (1u << 5)   /* bias above 20 V 30 s after HV_DIS high; report only */
#define FAULT_CAN_BUSOFF   (1u << 6)   /* TWAI bus-off; HV off. Set by can_link. */
#define FAULT_CAN_TIMEOUT  (1u << 7)   /* no LINK_ALL for bus_timeout (bus mode); HV off */
#define FAULT_BROWNOUT     (1u << 8)   /* last reset was brown-out */
#define FAULT_WDT          (1u << 9)   /* last reset was a watchdog */
#define FAULT_RSSI_RAIL    (1u << 10)  /* telemetry only */
#define FAULT_TIA_5K_SAT   (1u << 11)  /* telemetry only */
#define FAULT_SELFTEST     (1u << 12)  /* last self-test failed */
#define FAULT_LOOP_LIMIT   (1u << 13)  /* bias pinned at a limit for > 10 s */
/* Bit 14 is reserved in protocol s.5. PROPOSED use here: parameter NVS
 * corrupt or erased (README s.4 step 2 asks for "a fault flag"). Needs adding
 * to the protocol table if kept. Not HV-blocking. */
#define FAULT_NVS          (1u << 14)

/** Faults that block an HV enable request and force HV_DIS high when latched. */
#define FAULT_HV_BLOCKING_MASK (FAULT_I2C_DAC | FAULT_I2C_ADC | FAULT_DAC_EEPROM | \
                                FAULT_HV_OVER | FAULT_HV_UNDER | FAULT_HV_STUCK | \
                                FAULT_CAN_BUSOFF | FAULT_CAN_TIMEOUT)

/** Latch the given bits (OR). */
void fault_set(fault_word_t bits);
/** Clear the given bits unconditionally (the caller decides whether the cause
 *  is gone; see app_safety_faults_clear). */
void fault_clear(fault_word_t bits);
/** Current word. */
fault_word_t fault_get(void);
/** Short name of bit n (0..15), "?" if out of range. */
const char *fault_name(int bit);
