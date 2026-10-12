/* USB console (esp_console REPL over USB Serial/JTAG). Commands: protocol doc
 * s.4. Replies: `ok ...` or `err <reason>`; machine lines start with `{`. */
#pragma once

/** Register every command and start the REPL task (prio 3). */
void console_start(void);
