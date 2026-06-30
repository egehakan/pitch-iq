// Live headless-browser E2E: register → dashboard → companion → grounded chat →
// bracket pick → HITL submit/confirm → locked. Captures screenshots at each step.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOTS = "/tmp/pitchiq-shots";
mkdirSync(SHOTS, { recursive: true });

const email = `e2e.${Date.now()}@pitchiq.app`;
const log = (s) => console.log(`• ${s}`);
let step = 0;
const shot = async (page, name) => {
  step += 1;
  const p = `${SHOTS}/${String(step).padStart(2, "0")}-${name}.png`;
  await page.screenshot({ path: p, fullPage: false });
  log(`screenshot → ${p}`);
};

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(45000);

try {
  log("open app (expect redirect to /login)");
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForURL(/\/login/, { timeout: 15000 });
  await shot(page, "login");

  log("go to register");
  await page.getByRole("link", { name: /create one/i }).click();
  await page.waitForURL(/\/register/);
  const inputs = page.locator("form input");
  await inputs.nth(0).fill("E2E Fan");
  await inputs.nth(1).fill(email);
  await inputs.nth(2).fill("secret123");
  await shot(page, "register-filled");
  await page.getByRole("button", { name: /create account/i }).click();

  log("land on dashboard");
  await page.waitForURL(BASE + "/", { timeout: 20000 });
  await page.getByText(/your tournament companion/i).waitFor();
  await shot(page, "dashboard");

  log("open the companion (3-pane)");
  await page.getByText(/open the companion/i).click();
  await page.waitForURL(/\/tournament\//);
  await page.getByPlaceholder(/ask about a match/i).waitFor();
  await page.getByRole("heading", { name: "Bracket" }).waitFor();
  await page.waitForTimeout(1200);
  await shot(page, "companion-3pane");

  log("send a grounded chat question");
  await page.getByRole("button", { name: /what's happening in the netherlands match/i }).click();
  // the assistant bubble uses .prose-chat (only present on assistant messages in this view)
  await page.locator(".prose-chat", { hasText: /netherlands|japan|gakpo|score/i }).first().waitFor({ timeout: 60000 });
  await page.waitForTimeout(2500);
  await shot(page, "chat-grounded-answer");

  log("pick Netherlands in the bracket");
  await page.getByRole("button", { name: /Netherlands/ }).first().click();
  await page.waitForTimeout(800);
  await shot(page, "bracket-pick");

  log("submit → HITL confirm dialog");
  await page.getByRole("button", { name: /^Submit & lock$/ }).first().click();
  await page.getByText(/confirm submission/i).waitFor({ timeout: 20000 });
  await shot(page, "hitl-confirm-dialog");

  log("approve → bracket locks");
  await page.getByRole("button", { name: /^Submit & lock$/ }).last().click();
  await page.getByText("locked", { exact: true }).waitFor({ timeout: 20000 });
  await page.waitForTimeout(1000);
  await shot(page, "bracket-locked");

  // also exercise a prediction in chat
  log("ask for a prediction (gen→critic loop)");
  const composer = page.getByPlaceholder(/ask about a match/i);
  await composer.fill("Predict Spain vs Brazil");
  await composer.press("Enter");
  await page.locator(".prose-chat", { hasText: /probabilit/i }).first().waitFor({ timeout: 90000 });
  await page.waitForTimeout(2000);
  await shot(page, "chat-prediction");

  log("✅ E2E PASSED — all steps completed");
} catch (err) {
  log(`❌ E2E FAILED: ${err.message}`);
  await shot(page, "failure");
  process.exitCode = 1;
} finally {
  await browser.close();
}
