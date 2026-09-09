import { chromium } from "playwright";
import { readFile, mkdir } from "node:fs/promises";
import assert from "node:assert/strict";

const browser = await chromium.launch({ headless: true });
const credentials = JSON.parse(
  await readFile("artifacts/browser-secret", "utf8"),
);
const password = credentials.password;
await mkdir("artifacts/screenshots", { recursive: true });
try {
  for (const [name, width, height] of [
    ["desktop", 1366, 900],
    ["mobile", 390, 844],
    ["tablet", 820, 1180],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("http://localhost:8080/login");
    await page.getByLabel("Username", { exact: true }).fill("admin");
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL("http://localhost:8080/");
    await page.locator("#updated").filter({ hasText: "Measured" }).waitFor();
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      `${name} page overflow`,
    );
    assert.equal(
      await page
        .locator(".brand img")
        .evaluate((image) => image.complete && image.naturalWidth > 0),
      true,
      "Logo must render",
    );
    assert.equal(
      await page
        .locator("body")
        .innerText()
        .then((text) => text.includes(password)),
      false,
      "No visible password",
    );
    await page.screenshot({
      path: `artifacts/screenshots/dashboard-${name}.png`,
      fullPage: true,
    });
    for (const view of ["Services", "Backups", "Activity", "Websites"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      assert.equal(await page.locator("#heading").innerText(), view);
    }
    await page
      .getByRole("button", { name: "New website", exact: true })
      .click();
    await page
      .getByLabel("Application", { exact: true })
      .selectOption("wordpress");
    assert.equal(await page.locator("#cms-fields").isVisible(), true);
    await page
      .locator("#site-dialog")
      .getByRole("button", { name: "Close", exact: true })
      .click();
    if (name === "desktop") {
      await page.goto("http://localhost:8080/phpmyadmin/");
      assert.equal(
        await page.locator('input[name="pma_username"]').count(),
        1,
        "phpMyAdmin login unavailable: " +
          (await page.locator("body").innerText()).slice(0, 4000),
      );
      await page
        .locator('input[name="pma_username"]')
        .fill(credentials.database.username);
      await page
        .locator('input[name="pma_password"]')
        .fill(credentials.database.password);
      await page
        .locator('input[type="submit"], button[type="submit"]')
        .first()
        .click();
      await page
        .getByText(credentials.database.database, { exact: true })
        .first()
        .waitFor();
      await page.goto("http://localhost:8080/filebrowser/");
      await page.getByText("Websites", { exact: true }).first().waitFor();
    }
    assert.deepEqual(errors, [], `${name} browser errors`);
    await page.close();
  }
} catch (error) {
  const message = String(error)
    .replaceAll(password, "[redacted]")
    .replaceAll(credentials.database.password, "[redacted]");
  throw new Error(message);
} finally {
  await browser.close();
}
