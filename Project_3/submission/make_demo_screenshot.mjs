// Screenshot of the live demo judging one labelled case (original + edited reply), for slide 5.
// Drives headless Chrome over the DevTools protocol; Node >= 22 (built-in WebSocket), no npm packages.
//   node make_demo_screenshot.mjs [url] [case_id]
// Writes demo_screenshot.png next to this file. The site runs the real judge (claude-haiku-4.5), so this makes 2-6 calls.
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const URL_ = process.argv[2] || "https://divinecodes-judge-the-judge.vercel.app/";
const CASE = process.argv[3] || "J1D-0001";
const OUT = join(dirname(fileURLToPath(import.meta.url)), "demo_screenshot.png");
const PORT = 9333, W = 1440, H = 1000;
const sleep = ms => new Promise(r => setTimeout(r, ms));

const profile = mkdtempSync(join(tmpdir(), "demo-shot-"));
const chrome = spawn("google-chrome", ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  `--window-size=${W},${H}`, "--hide-scrollbars", "--force-color-profile=srgb", "--blink-settings=preferredColorScheme=1",
  "about:blank"], { stdio: "ignore" });

async function target() {
  for (let i = 0; i < 50; i++) {
    try { const t = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); const p = t.find(x => x.type === "page"); if (p) return p; }
    catch { /* chrome still starting */ }
    await sleep(200);
  }
  throw new Error("chrome did not start");
}

let ws, seq = 0; const waiting = new Map();
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = ++seq; waiting.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params }));
});
const evalJS = async expr => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.value;
async function until(expr, ms, what) {
  for (const t0 = Date.now(); Date.now() - t0 < ms; await sleep(300)) if (await evalJS(expr)) return;
  throw new Error(`timed out waiting for ${what}`);
}

try {
  ws = new WebSocket((await target()).webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = m => { const d = JSON.parse(m.data); const w = waiting.get(d.id);
    if (w) { waiting.delete(d.id); d.error ? w.rej(new Error(d.error.message)) : w.res(d.result); } };
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 2, mobile: false });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });
  await send("Page.enable");
  await send("Page.navigate", { url: URL_ });
  await until(`!!document.querySelector('#list button.case[data-id="${CASE}"]')`, 20000, "case list");
  await evalJS(`document.querySelector('#list button.case[data-id="${CASE}"]').click()`);
  await until(`!!document.querySelector('#go')`, 5000, "run button");
  await evalJS(`document.querySelector('#go').click()`);
  await until(`/Both replies are complete/.test(document.querySelector('#live-status')?.textContent || '')`, 120000, "verdicts");
  const err = await evalJS(`/Stopped:/.test(document.querySelector('#traces')?.textContent || '')`);
  if (err) throw new Error("the judge reported an error; not saving a screenshot of it");
  await sleep(500);
  const r = await evalJS(`(() => { window.scrollTo(0, 0); const b = document.querySelector('#stage').getBoundingClientRect();
    return { x: b.left, y: b.top + window.scrollY, w: b.width, h: Math.min(b.height, 1150) }; })()`);
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true,
    clip: { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 } });
  writeFileSync(OUT, Buffer.from(shot.data, "base64"));
  console.log(`wrote ${OUT} (${Math.round(r.w)}x${Math.round(r.h)} css px, case ${CASE})`);
} finally {
  try { ws?.close(); } catch {}
  chrome.kill();
  await sleep(300);
  rmSync(profile, { recursive: true, force: true });
}
