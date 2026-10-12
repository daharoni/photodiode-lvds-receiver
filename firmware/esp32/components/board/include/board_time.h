/* Tick helpers. FreeRTOS tick rate is 1 kHz (sdkconfig.defaults,
 * CONFIG_FREERTOS_HZ=1000), but pdMS_TO_TICKS(x) with x < 1000/HZ is 0 ticks,
 * which turns a timed wait into a busy loop. Use ticks_at_least_1() for any
 * delay or queue wait that may be shorter than 10 ms (review finding 1). */
#pragma once
#include <stdint.h>
#include "freertos/FreeRTOS.h"

static inline TickType_t ticks_at_least_1(uint32_t ms)
{
    TickType_t t = pdMS_TO_TICKS(ms);
    return t ? t : (TickType_t)1;
}
