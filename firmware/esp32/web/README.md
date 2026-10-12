# Flash-and-verify web page

Static page (no build step, no framework) for the ESP32-C6 module controller. PROPOSED; nothing here has been tested on hardware or in a browser against a board.

## Files

- `index.html`, `app.js`, `style.css`: ESP Web Tools install button, Web Serial console (115200), self-test result panel, live telemetry panel. Console protocol: `docs/firmware/can-and-console-protocol.md` s.4, s.4.1, s.6.
- `manifest.template.json`: ESP Web Tools manifest with a `__VERSION__` placeholder and the merged image `receiver-esp32c6-merged.bin` at offset 0 (ESP32-C6 bootloader is at 0x0; `docs/research/esp32-usb-tooling.md` s.4).

## Sources

- ESP Web Tools manifest schema and button usage: https://esphome.github.io/esp-web-tools/ (read 2026-10-12). Fields used: `name`, `version`, `new_install_prompt_erase`, `new_install_improv_wait_time` (0 disables Improv detection), `builds[].chipFamily` = `ESP32-C6`, `parts[].path/offset`. The site must be served over https://; cross-origin manifests/firmware need CORS.
- The page loads ESP Web Tools from `vendor/esp-web-tools/` (the unmodified `dist/web` bundle of the npm package `esp-web-tools@10.2.1`, Apache-2.0, LICENSE included), not from a CDN: no third-party script at run time and no network needed beyond the manifest and image. To update: `npm pack esp-web-tools@<ver>` and copy `package/dist/web/*.js` over the directory. 10.2.1 was not run here.

## How CI fills it

The `build` job in `.github/workflows/esp32-firmware.yml` copies this directory to `firmware/esp32/build/web/`, copies the merged image next to it and writes `manifest.json` from the template with the version from `firmware/esp32/version.txt`. The folder is part of the `esp32-firmware` artifact. There is deliberately no Pages deploy job; Daniel decides on hosting.

## Serve locally

```
cd firmware/esp32/web
sed "s/__VERSION__/$(cat ../version.txt)/" manifest.template.json > manifest.json
cp ../build/receiver-esp32c6-merged.bin .
python3 -m http.server 8000
```

Open http://localhost:8000 in Chrome or Edge. (`manifest.json` and the `.bin` are generated files; do not commit them.)

## UNRESOLVED

From `docs/research/esp32-usb-tooling.md` s.7, all untested:

1. Clean-machine runs on Windows 10/11, macOS, Ubuntu with Chrome and Edge.
2. Whether the browser flasher resets a C6 running USB-CDC firmware into download mode (BOOT + RESET is the recovery).
3. Coexistence of ESP Web Tools' own console and this page's console (assumed: ours opens after the flasher closes the port; the page's Connect button asks for the port again).
4. Firefox Web Serial support (unchecked).

Also untested: the JavaScript has only been syntax-checked, not exercised against a board or a mock port.
