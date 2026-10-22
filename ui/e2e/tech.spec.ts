import { expect, test } from "@playwright/test";

// U-6–U-8: the technician window against the simulator. Locally the simulator treats the
// browser as admin (dev_admin), so every page is reachable.

test.afterEach(async ({ page }) => {
  await page.request.post("/api/rules/overrides", { data: { T2_confirm_ms: null } });
  await page.request.post("/api/auto", { data: { on: true } });
  await page.request.post("/api/recording", { data: { action: "stop" } });
  await page.waitForTimeout(300);
  await page.request.delete("/api/session");
});

test("overview: manual cut from the multiview, AUTO, decisions", async ({ page }) => {
  await page.request.post("/api/sim/card", { data: { card: "04A1B2C3" } });
  await page.goto("/tech/");
  await expect(page.getByRole("heading", { name: "Oversikt" })).toBeVisible();
  await expect(page.getByText("SIMULATOR")).toBeVisible();
  await expect(page.getByText("Testkort A")).toBeVisible();

  await page.getByRole("button", { name: "Klipp til Camera 2 · Gjest 1" }).click();
  await expect(page.locator(".shot")).toHaveText("Camera 2 · Gjest 1");
  await expect(page.locator(".log")).toContainText("manuell");

  await page.getByRole("button", { name: "Auto på" }).click();
  await expect(page.getByRole("button", { name: "Auto av" })).toBeVisible();
});

test("regi: fine tuning applies live and resets", async ({ page }) => {
  await page.goto("/tech/#regi");
  await expect(page.getByRole("heading", { name: "Regi og brytere" })).toBeVisible();
  const slider = page.getByLabel("Bekreftelse før kutt");
  await slider.fill("1200");
  await expect(page.locator("output.changed")).toHaveText("1200 ms", { timeout: 5000 });
  const rules = (await (await page.request.get("/api/rules")).json()) as {
    values: Record<string, number>;
  };
  expect(rules.values["T2_confirm_ms"]).toBe(1200);
  await page.getByRole("button", { name: "Nullstill" }).first().click();
  await expect(page.locator("output.changed")).toHaveCount(0);
});

test("pages render and the log can be filtered", async ({ page }) => {
  for (const [hash, heading] of [
    ["kameraer", "Kameraer"],
    ["opptak", "Opptak"],
    ["helse", "Helse"],
    ["logg", "Beslutningslogg"],
    ["innstillinger", "Innstillinger"],
    ["oppsett", "Oppsett-veiviser"],
  ]) {
    await page.goto(`/tech/#${hash}`);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
  await page.goto("/tech/#opptak");
  await expect(page.getByText("Opptak siste døgn")).toBeVisible();
  await page.goto("/tech/#logg");
  const pkg = page.waitForEvent("download");
  await page.getByRole("link", { name: "Feilsøkingspakke" }).click();
  expect((await pkg).suggestedFilename()).toMatch(/^cutcut-feilsok-.*\.zip$/);
  await page.getByRole("button", { name: "Kutt" }).click();
  await expect(page.getByRole("button", { name: "Kutt" })).toHaveAttribute("aria-pressed", "true");
});

test("overview stays under 50 ms of main-thread work per second (12.5)", async ({ page }) => {
  await page.request.post("/api/sim/card", { data: { card: "04A1B2C3" } });
  await page.request.post("/api/recording", { data: { action: "start" } });
  await page.request.post("/api/sim/conversation", { data: { on: true } });
  await page.goto("/tech/");
  await page.waitForTimeout(4000);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Performance.enable");
  const metric = async () => {
    const { metrics } = await cdp.send("Performance.getMetrics");
    return metrics.find((m) => m.name === "TaskDuration")?.value ?? 0;
  };
  const before = await metric();
  await page.waitForTimeout(10_000);
  const perSecondMs = ((await metric()) - before) * 100; // s over 10 s → ms per s
  await page.request.post("/api/sim/conversation", { data: { on: false } });
  console.log(`tech overview main thread: ${perSecondMs.toFixed(1)} ms/s`);
  expect(perSecondMs).toBeLessThan(50);
});

test("oppsett: equipment addresses are saved and the multiview is checked (D-055)", async ({
  page,
}) => {
  await page.goto("/tech/#oppsett");
  await expect(page.getByRole("heading", { name: "Oppsett-veiviser" })).toBeVisible();
  const cam2 = page.getByLabel(/Adresse for Camera 2/);
  await cam2.fill("10.10.10.299");
  await expect(page.getByText("Skriv fire tall")).toBeVisible();
  await expect(page.getByRole("button", { name: "Lagre endringer" })).toBeDisabled();
  await cam2.fill("10.10.10.42");
  await page.getByRole("button", { name: "Lagre endringer" }).click();
  await expect(page.getByText("I filen: 10.10.10.22")).toBeVisible();
  const yml = await (await page.request.get("/api/settings/devices.yaml")).text();
  expect(yml).toContain("10.10.10.42");
  await page.getByRole("button", { name: "Nullstill" }).click();
  await expect(page.getByText("I filen: 10.10.10.22")).toHaveCount(0);

  // the multiview panel belongs to step 6 of the setup helper (HS-5)
  await page.getByRole("button", { name: /^6 Multiview/ }).click();
  await expect(page.getByText("Stemmer", { exact: true })).toBeVisible();
  await page.request.post("/api/sim/fault", { data: { kind: "multiview_wrong", on: true } });
  try {
    await page.getByRole("button", { name: "Sjekk nå" }).click();
    await expect(page.getByText("Stemmer ikke")).toBeVisible();
    await expect(page.getByText(/CutCut ville lest feil kamera/).first()).toBeVisible();
  } finally {
    await page.request.post("/api/sim/fault", { data: { kind: "multiview_wrong", on: false } });
  }
});
