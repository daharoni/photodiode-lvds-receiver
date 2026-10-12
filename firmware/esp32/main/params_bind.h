/* Wiring of live getters and action hooks into the parameter registry, so
 * CAN SET and console set run the same code. */
#pragma once
#include <stdint.h>

/** Register getters/actions and start the self-test worker. Call after
 *  params_init() and before can_link_start() / console_start(). */
void params_bind_init(void);

/** DAC_TH code for a threshold offset in 0.1 mV (CAN unit of `th`):
 *  code = 0x800 + th x 10.1 / 0.80566 (offset = (DAC - VCM_REF) / 101 with a
 *  3.3 V reference, README s.1; PROPOSED, calculated). Clamped to 0..4095. */
uint16_t params_th_to_code(int32_t th_dmv);
