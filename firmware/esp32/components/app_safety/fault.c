#include "fault.h"
#include <stdatomic.h>

static _Atomic fault_word_t s_faults;

static const char *const k_names[16] = {
    "I2C_DAC", "I2C_ADC", "DAC_EEPROM", "HV_OVER", "HV_UNDER", "HV_STUCK", "CAN_BUSOFF",
    "CAN_TIMEOUT", "BROWNOUT", "WDT", "RSSI_RAIL", "TIA_5K_SAT", "SELFTEST", "LOOP_LIMIT",
    "NVS", "?"};

void fault_set(fault_word_t bits) { atomic_fetch_or(&s_faults, bits); }
void fault_clear(fault_word_t bits) { atomic_fetch_and(&s_faults, (fault_word_t)~bits); }
fault_word_t fault_get(void) { return atomic_load(&s_faults); }
const char *fault_name(int bit) { return (bit >= 0 && bit < 16) ? k_names[bit] : "?"; }
