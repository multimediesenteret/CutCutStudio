import { expect, test, type Page } from "@playwright/test";

// U-5: the whole touch flow against the simulator (spec 11 step 3).

async function logIn(page: Page) {
  await page.goto("/touch/");
  await expect(
    page.getByRole("heading", { name: "Hold adgangskortet ditt mot leseren" }),
  ).toBeVisible();
  await expect(page.getByText("Studio klart")).toBeVisible();
  await page.getByRole("button", { name: "Demo: simuler kortskanning" }).click();
  await expect(page.getByRole("heading", { name: "Hei, Testkort!" })).toBeVisible();
}

async function hold(page: Page, ms: number) {
  const box = await page.getByRole("button", { name: /Hold inne for å avslutte/ }).boundingBox();
  if (!box) throw new Error("stop button missing");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(ms);
  await page.mouse.up();
}

test.afterEach(async ({ page }) => {
  // Leave the studio idle for the next test, whatever happened.
  await page.request.post("/api/recording", { data: { action: "stop" } });
  await page.waitForTimeout(300);
  await page.request.delete("/api/session");
});

test("card → choose → countdown → recording → hold to stop → done → log out", async ({ page }) => {
  await logIn(page);

  await page.getByRole("button", { name: /Gjest 2/ }).click();
  await expect(page.getByRole("button", { name: /Gjest 2/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByRole("button", { name: /Gjest 1/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: /Kun lyd/ }).click();
  await expect(page.getByRole("button", { name: /Kun lyd/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: /Video og lyd/ }).click();

  await page.getByRole("button", { name: "Start opptak" }).click();
  await expect(page.getByText("Snakk litt, så sjekker vi lyden")).toBeVisible();

  await expect(page.getByRole("heading", { name: "Nå i bildet" })).toBeVisible({ timeout: 8000 });
  await expect(page.locator(".recpill")).toBeVisible();
  await expect(page.getByText("Lagres i studioet")).toBeVisible(); // Panopto is prepared, not on (SE-7)

  // A speaker gets the picture (real engine, simulated voice).
  await page.request.post("/api/sim/talk", { data: { participant: "P2", on: true } });
  await expect(page.locator(".onair .tag")).toHaveText("Gjest 1", { timeout: 10_000 });
  await expect(page.locator(".cc-mic.talk")).toContainText("Gjest 1");
  await page.request.post("/api/sim/talk", { data: { participant: "P2", on: false } });

  // Letting go early does nothing (spec 8.3).
  await hold(page, 800);
  await page.waitForTimeout(500);
  await expect(page.getByRole("heading", { name: "Nå i bildet" })).toBeVisible();

  await hold(page, 2400);
  await expect(page.getByRole("heading", { name: /Opptaket er lagret/ })).toBeVisible();
  await expect(page.getByText("3 personer")).toBeVisible();

  await page.getByRole("button", { name: "Ta et nytt opptak" }).click();
  await expect(page.getByRole("heading", { name: "Hei, Testkort!" })).toBeVisible();
  await page.getByRole("button", { name: "Ikke deg? Logg ut" }).click();
  await expect(
    page.getByRole("heading", { name: "Hold adgangskortet ditt mot leseren" }),
  ).toBeVisible();
});

test("help reaches the technician and the recording continues", async ({ page }) => {
  await logIn(page);
  await page.getByRole("button", { name: "Start opptak" }).click();
  await expect(page.getByRole("heading", { name: "Nå i bildet" })).toBeVisible({ timeout: 8000 });
  await page.getByRole("button", { name: "Trenger du hjelp?" }).click();
  await expect(page.getByText("Teknikeren er varslet. Opptaket fortsetter.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Teknikeren er varslet" })).toBeVisible();
  const state = (await (await page.request.get("/api/state")).json()) as {
    alerts: { code: string }[];
  };
  expect(state.alerts.some((a) => a.code === "HELP")).toBe(true);
});

test("a problem the user cannot fix blocks start with one plain sentence", async ({ page }) => {
  await logIn(page);
  await page.request.post("/api/sim/fault", { data: { kind: "audio_lost", on: true } });
  try {
    await expect(page.getByRole("alert")).toHaveText(
      "Noe er galt med lyden. Teknikeren er varslet.",
      { timeout: 8000 },
    );
    await expect(page.getByRole("button", { name: "Start opptak" })).toBeDisabled();
  } finally {
    await page.request.post("/api/sim/fault", { data: { kind: "audio_lost", on: false } });
  }
  await expect(page.getByRole("button", { name: "Start opptak" })).toBeEnabled({ timeout: 8000 });
});

test("light and dark theme", async ({ page }) => {
  await page.goto("/touch/");
  const toggle = page.getByRole("button", { name: "Bytt mellom lyst og mørkt tema" });
  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByText("Studio klart")).toBeVisible();
  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("without card reader: Start logs in a guest (D-057)", async ({ page }) => {
  await page.request.put("/api/settings/login", { data: { mode: "open" } });
  try {
    await page.goto("/touch/");
    await expect(
      page.getByRole("heading", { name: "Velkommen til podkaststudioet" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Start", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Hei!" })).toBeVisible();
    await page.request.delete("/api/session");
  } finally {
    await page.request.put("/api/settings/login", { data: { mode: "card" } });
  }
});
