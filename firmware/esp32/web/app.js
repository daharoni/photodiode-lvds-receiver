"use strict";
// Console, self-test and telemetry for the receiver module. Protocol:
// docs/firmware/can-and-console-protocol.md s.4, s.4.1, s.6. Lines starting with "{"
// are machine lines; everything else goes to the log only.
const $ = (id) => document.getElementById(id);
const logEl = $("log"), stateEl = $("state");
let port = null, writer = null, reader = null, keepReading = false;

function log(text, cls) {
  const near = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 20;
  const span = document.createElement("span");
  if (cls) span.className = cls;
  span.textContent = text + "\n";
  logEl.appendChild(span);
  while (logEl.childNodes.length > 2000) logEl.removeChild(logEl.firstChild);
  if (near) logEl.scrollTop = logEl.scrollHeight;
}

function setConnected(on) {
  $("connect").disabled = on;
  $("disconnect").disabled = !on;
  document.querySelectorAll(".cmd,#sendform button,#line").forEach((e) => (e.disabled = !on));
  stateEl.textContent = on ? "connected (115200)" : "disconnected";
}

async function openPort() {
  if (!("serial" in navigator)) { log("Web Serial is not available; use Chrome or Edge.", "fail"); return; }
  try {
    // Espressif USB Serial/JTAG: VID 0x303a, PID 0x1001 (docs/research/esp32-usb-tooling.md s.2).
    port = await navigator.serial.requestPort({ filters: [{ usbVendorId: 0x303a }] });
    await port.open({ baudRate: 115200 });
  } catch (e) { log("open failed: " + e.message, "fail"); port = null; return; }
  $("reconnect").hidden = true;
  writer = port.writable.getWriter();
  setConnected(true);
  keepReading = true;
  readLoop();
}

async function readLoop() {
  const dec = new TextDecoder();
  let buf = "";
  try {
    while (keepReading && port.readable) {
      reader = port.readable.getReader();
      try {
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          let i;
          while ((i = buf.search(/\r?\n/)) >= 0) {
            handleLine(buf.slice(0, i));
            buf = buf.slice(buf.indexOf("\n", i) + 1);
          }
        }
      } finally { reader.releaseLock(); reader = null; }
    }
  } catch (e) { log("read error: " + e.message, "fail"); }
  await closePort(true);
}

async function closePort(lost) {
  keepReading = false;
  try { if (reader) await reader.cancel(); } catch (_) {}
  try { if (writer) { writer.releaseLock(); } } catch (_) {}
  try { if (port) await port.close(); } catch (_) {}
  writer = null; port = null;
  setConnected(false);
  if (lost) {
    log("[port closed or device disappeared (a reset re-enumerates USB); reconnect]", "skip");
    $("reconnect").hidden = false;
  }
}

async function send(line) {
  if (!writer) return;
  log("> " + line, "tx");
  try { await writer.write(new TextEncoder().encode(line + "\n")); }
  catch (e) { log("write failed: " + e.message, "fail"); }
}

function handleLine(line) {
  line = line.replace(/\r$/, "");
  if (!line) return;
  const isStream = line.startsWith('{"t":');
  if (!isStream) log(line);       // telemetry lines would flood the log
  const m = line.match(/BOOT OK fw=(\S+)/);
  if (m) $("boot").textContent = "Firmware reports version " + m[1] + " (BOOT OK banner).";
  if (!line.startsWith("{")) return;
  let obj;
  try { obj = JSON.parse(line); } catch (_) { if (isStream) log(line); return; }
  if (obj.selftest) renderSelftest(obj.selftest);
  else if (isStream || "t" in obj) renderTelemetry(obj);
  else log(line);
}

function renderSelftest(st) {
  const box = $("selftest");
  box.className = ""; box.textContent = "";
  const head = document.createElement("p");
  const verdict = document.createElement("span");
  verdict.className = st.pass ? "pass" : "fail";
  verdict.textContent = st.pass ? "PASS" : "FAIL";
  head.append("mode " + (st.mode ?? "?") + ": ", verdict);
  box.appendChild(head);
  const table = document.createElement("table");
  for (const s of st.steps || []) {
    const tr = table.insertRow();
    tr.insertCell().textContent = s.id;
    const c = tr.insertCell();
    c.textContent = s.r;
    c.className = ["pass", "fail", "skip", "info"].includes(s.r) ? s.r : "";
  }
  box.appendChild(table);
  const extra = document.createElement("p");
  const bits = [];
  for (const k of ["hv_peak_v", "hv_floor_v", "usb_ma_est", "sn", "ver"])
    if (st[k] !== undefined && st[k] !== null) bits.push(k + " = " + st[k]);
  extra.textContent = bits.join(", ");
  box.appendChild(extra);
}

function renderTelemetry(obj) {
  const box = $("telemetry");
  let table = box.querySelector("table");
  if (!table) { box.className = ""; box.textContent = ""; table = document.createElement("table"); box.appendChild(table); }
  for (const [k, v] of Object.entries(obj)) {
    let row = table.querySelector('tr[data-k="' + CSS.escape(k) + '"]');
    if (!row) {
      row = table.insertRow(); row.dataset.k = k;
      row.insertCell().textContent = k; row.insertCell();
    }
    row.cells[1].textContent = v === null ? "null" : String(v);
  }
}

$("connect").onclick = openPort;
$("reconnect").onclick = openPort;
$("disconnect").onclick = () => closePort(false);
$("clear").onclick = () => (logEl.textContent = "");
document.querySelectorAll(".cmd[data-cmd]").forEach((b) => (b.onclick = () => send(b.dataset.cmd)));
$("full").onclick = () => {
  if (confirm("selftest full raises the APD bias supply to about 100 V. Make sure nothing touches the HV area and the optics are covered as required. Continue?"))
    send("selftest full");
};
$("sendform").onsubmit = (e) => {
  e.preventDefault();
  const v = $("line").value.trim();
  if (v) { send(v); $("line").value = ""; }
};
if ("serial" in navigator) {
  navigator.serial.addEventListener("disconnect", (e) => { if (e.target === port) closePort(true); });
} else {
  log("Web Serial is not available in this browser; use Chrome or Edge.", "skip");
}
