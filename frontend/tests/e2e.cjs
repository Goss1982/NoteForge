const { chromium } = require("playwright");
const assert = require("assert");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.BROWSER_EXECUTABLE_PATH || undefined,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    headless: true,
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:3000");
  await page.getByLabel("Workspace password").fill("browser-test-password");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page
    .getByRole("heading", { name: "Notebooks.", exact: true })
    .waitFor();
  if (process.env.E2E_SCREENSHOTS)
    await page.screenshot({
      path: process.env.E2E_SCREENSHOTS + "/empty-desktop.png",
      fullPage: true,
    });
  await page
    .getByRole("button", { name: "Import notebook", exact: true })
    .click();
  await page
    .getByLabel("Choose notebook file")
    .setInputFiles(process.env.E2E_PDF);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Import notebook", exact: true })
    .click();
  await page.getByRole("heading", { name: "Meeting", exact: true }).waitFor();
  await page
    .getByText("Alex to send the proposal on Friday. Budget: GBP 2500.", {
      exact: true,
    })
    .waitFor({ timeout: 60000 });
  if (process.env.E2E_SCREENSHOTS)
    await page.screenshot({
      path: process.env.E2E_SCREENSHOTS + "/notebook-desktop.png",
      fullPage: true,
    });
  await page.getByRole("button", { name: "review", exact: true }).click();
  await page.getByLabel("Review notes").fill("Checked against original.");
  await page.getByRole("button", { name: "Mark verified" }).click();
  await page.getByText("Page review saved.", { exact: true }).waitFor();
  await page
    .getByRole("button", { name: /Documents/ })
    .first()
    .click();
  await page
    .getByRole("button", { name: /Meeting follow-up/ })
    .click({ timeout: 60000 });
  await page
    .getByRole("heading", { name: "Meeting follow-up", exact: true })
    .first()
    .waitFor();
  await page
    .getByRole("button", { name: "Source 1", exact: false })
    .first()
    .click();
  await page
    .getByRole("dialog")
    .getByRole("heading", { name: "Original source page" })
    .waitFor();
  await page.getByRole("button", { name: "Close source preview" }).click();
  await page.getByRole("button", { name: "Review & edit" }).click();
  await page
    .getByRole("textbox", { name: "Paragraph 1 of Actions" })
    .fill("Alex is to send the proposal on Friday, as recorded in the notes.");
  await page
    .getByRole("checkbox", {
      name: "I have checked this document against the original notes.",
    })
    .check();
  await page.getByRole("button", { name: "Save version 2" }).click();
  await page.getByText("Version 2", { exact: false }).first().waitFor();
  await page.getByRole("button", { name: "History", exact: true }).click();
  await page.getByRole("heading", { name: "Version history" }).waitFor();
  if (process.env.E2E_SCREENSHOTS)
    await page.screenshot({
      path: process.env.E2E_SCREENSHOTS + "/document-desktop.png",
      fullPage: true,
    });
  await page
    .getByRole("textbox", { name: "Search all notes" })
    .fill("proposal");
  await page.getByRole("textbox", { name: "Search all notes" }).press("Enter");
  await page.getByRole("button", { name: /Meeting Page 1/ }).waitFor();
  await page
    .getByRole("button", { name: "Notebooks", exact: false })
    .first()
    .click();
  await page.getByRole("button", { name: "Use dark theme" }).click();
  if (process.env.E2E_SCREENSHOTS)
    await page.screenshot({
      path: process.env.E2E_SCREENSHOTS + "/dark-desktop.png",
      fullPage: true,
    });
  await page.setViewportSize({ width: 390, height: 844 });
  if (process.env.E2E_SCREENSHOTS)
    await page.screenshot({
      path: process.env.E2E_SCREENSHOTS + "/mobile.png",
      fullPage: true,
    });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
    "Mobile layout overflows",
  );
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("heading", { name: "Connections & settings." })
    .waitFor();
  await page.waitForFunction(
    () => document.querySelector(".sidebar").getBoundingClientRect().right <= 1,
  );
  if (process.env.E2E_SCREENSHOTS)
    await page.screenshot({
      path: process.env.E2E_SCREENSHOTS + "/settings-mobile.png",
      fullPage: true,
    });
  assert.deepStrictEqual(errors, [], "Browser runtime errors");
  console.log(
    "PASS: login, import, live worker extraction, auto-generation, source preview, page review, document editing, review history, search, dark theme, mobile navigation and overflow.",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
