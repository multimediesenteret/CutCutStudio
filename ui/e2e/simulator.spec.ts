import { expect, test } from "@playwright/test";

// U-9: the web simulator as Vercel serves it — both real screens, fed by a recorded trace.
const SIM = "http://127.0.0.1:8092/sim/";

test("both screens play the same recorded session", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(SIM);
  await expect(page.getByText("SIMULATOR – ingen ekte utstyr.")).toBeVisible();
  const touch = page.frameLocator('iframe[title="Touch-skjerm"]');
  const tech = page.frameLocator('iframe[title="Teknikervindu"]');
  await expect(
    touch.getByRole("heading", { name: "Hold NTNU-kortet ditt mot leseren" }),
  ).toBeVisible();
  await expect(tech.getByRole("heading", { name: "Oversikt" })).toBeVisible();

  await page.getByLabel("Hopp i forløpet").fill("40000");
  await expect(touch.getByRole("heading", { name: "Nå i bildet" })).toBeVisible();
  await expect(tech.locator(".pill.rec")).toBeVisible();
  await expect(tech.locator(".log li").first()).toBeVisible();

  // Buttons explain that this is a recording instead of doing nothing.
  await touch.getByRole("button", { name: "Trenger du hjelp?" }).click();
  await expect(touch.getByText("Dette er et opptak – knappene virker i studio.")).toBeVisible();

  await page.locator("select").selectOption("panel-laptop");
  await page.getByLabel("Hopp i forløpet").fill("50000");
  await expect(touch.locator(".cc-mic")).toHaveCount(3);
  expect(errors).toEqual([]);
});

test("a screen opened on its own plays by itself", async ({ page }) => {
  await page.goto(`${SIM}tech.html#logg`);
  await expect(page.getByRole("heading", { name: "Beslutningslogg" })).toBeVisible();
});
