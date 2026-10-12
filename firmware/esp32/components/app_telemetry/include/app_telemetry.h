/* CAN telemetry frames, `stream on` JSON lines, event ring and LED patterns.
 * Protocol: docs/firmware/can-and-console-protocol.md s.1.4, s.4.1. PROPOSED. */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

/** Create the telemetry task (prio 5, 20 ms tick) and the LED task (prio 2,
 *  50 ms tick). */
void app_telemetry_start(void);

/** Start or stop NDJSON streaming on the console. period_ms is clamped to
 *  the `tlm_ms` minimum of 50 ms (protocol s.4); 0 keeps the current period.
 *  The same period drives TLM_ANALOG on CAN. */
void app_telemetry_stream(bool on, uint32_t period_ms);
bool app_telemetry_streaming(void);

/** Queue one event line (a complete JSON object) into the 64-entry RAM ring
 *  (README s.6.6); if streaming, it is also queued for printing. Copies the string
 *  (truncated to 159 chars). Thread safe. */
void app_telemetry_event(const char *json_line);

/** Queue one line (no newline) for the printer task, which writes it only
 *  while a USB host is connected and drops it otherwise. Never blocks. Returns
 *  false if the line was dropped (queue full or not started). */
bool app_telemetry_print_line(const char *line);
/** Lines dropped so far (no host, queue full); shown by `status`. */
uint32_t app_telemetry_print_drops(void);

/** Print the ring (oldest first), used by `status`. */
void app_telemetry_events_print(void);

/** Write the `status -j` / stream line (protocol s.4.1 keys, plus "rev" and
 *  "mac") into buf; returns the length (truncated to len-1). Unknown values
 *  are `null`. */
int app_telemetry_status_json(char *buf, size_t len);

/** Record what the boot step learned about the source (README s.4 step 7):
 *  src "system"|"host"|"unknown", cc_class "default"|"1.5A"|"3.0A"|"none",
 *  cc_orient "cc1"|"cc2"|"none". Strings must be static. */
void app_telemetry_set_source(const char *src, const char *cc_class, const char *cc_orient);

/** IDENTIFY: blink the STATUS LED in the identify pattern for `seconds`. */
void app_telemetry_identify(uint8_t seconds);
