import { chromium } from "playwright";
const SHOTS = "/tmp/pitchiq-shots";
const DESK = { width: 1440, height: 900 };
const MOB = { width: 390, height: 844 };
const b = await chromium.launch({ headless: true });
const log = (s) => console.log("• " + s);
const email = `ui.${Date.now()}@pitchiq.app`;

// register → session
const c0 = await b.newContext({ viewport: DESK, deviceScaleFactor: 2 });
const p0 = await c0.newPage();
p0.setDefaultTimeout(90000);
await p0.goto("http://localhost:3000/register", { waitUntil: "domcontentloaded" });
await p0.locator("form input").nth(0).fill("Hako Mako");
await p0.locator("form input").nth(1).fill(email);
await p0.locator("form input").nth(2).fill("secret123");
await p0.screenshot({ path: `${SHOTS}/register-desktop.png` });
await p0.getByRole("button", { name: /create account/i }).click();
const dashReady = (p) => p.getByRole("link", { name: /open the companion/i }).waitFor();
await dashReady(p0);
await p0.waitForTimeout(2500);
await p0.screenshot({ path: `${SHOTS}/dashboard-desktop.png` });
log("dashboard");
const state = await c0.storageState();
await c0.close();

async function shoot(vp, fn) {
  const c = await b.newContext({ viewport: vp, deviceScaleFactor: 2, storageState: state });
  const p = await c.newPage();
  p.setDefaultTimeout(90000);
  try { await fn(p); } finally { await c.close(); }
}

// login logged-out
for (const [tag, vp] of [["desktop", DESK], ["mobile", MOB]]) {
  const c = await b.newContext({ viewport: vp, deviceScaleFactor: 2 });
  const p = await c.newPage();
  p.setDefaultTimeout(90000);
  await p.goto("http://localhost:3000/login", { waitUntil: "domcontentloaded" });
  await p.getByRole("button", { name: /^sign in$/i }).waitFor();
  await p.waitForTimeout(600);
  await p.screenshot({ path: `${SHOTS}/login-${tag}.png` });
  await c.close();
}
log("login");

await shoot(MOB, async (p) => {
  await p.goto("http://localhost:3000/", { waitUntil: "domcontentloaded" });
  await dashReady(p);
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${SHOTS}/dashboard-mobile.png`, fullPage: true });
});
log("dashboard mobile");

await shoot(DESK, async (p) => {
  await p.goto("http://localhost:3000/tournament/world-cup-2026", { waitUntil: "domcontentloaded" });
  await p.getByPlaceholder(/ask about a match/i).waitFor();
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${SHOTS}/companion-empty-desktop.png` });
  await p.getByRole("button", { name: /what happened in brazil vs japan/i }).click();
  await p.locator(".prose-chat").first().waitFor();
  await p.waitForTimeout(3500);
  await p.screenshot({ path: `${SHOTS}/companion-run-desktop.png` });
});
log("companion desktop");

await shoot(MOB, async (p) => {
  await p.goto("http://localhost:3000/tournament/world-cup-2026", { waitUntil: "domcontentloaded" });
  await p.getByPlaceholder(/ask about a match/i).waitFor();
  await p.waitForTimeout(2000);
  await p.screenshot({ path: `${SHOTS}/companion-mobile-chat.png` });
  await p.getByRole("button", { name: "Match" }).click();
  await p.waitForTimeout(1800);
  await p.screenshot({ path: `${SHOTS}/companion-mobile-match.png` });
});
log("companion mobile");

for (const [tag, vp] of [["desktop", DESK], ["mobile", MOB]]) {
  await shoot(vp, async (p) => {
    await p.goto("http://localhost:3000/", { waitUntil: "domcontentloaded" });
    await p.getByRole("link", { name: /edit my bracket/i }).click();
    await p.getByText("Round of 32").first().waitFor();
    await p.waitForTimeout(1800);
    await p.screenshot({ path: `${SHOTS}/bracket-${tag}.png` });
  });
}
log("bracket");

await b.close();
console.log("ALL SHOTS DONE");
