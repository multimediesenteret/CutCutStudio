import { describe, expect, it } from "vitest";
import { NAV, allowed, shotName, tileOf } from "./lib";
import type { StudioState } from "@cutcut/client";

describe("menu per role (D-045)", () => {
  it("operator sees Oversikt, Kameraer, Opptak, Helse, Logg", () => {
    const seen = NAV.filter((n) => allowed(n.view, "operator")).map((n) => n.view);
    expect(seen).toEqual(["oversikt", "kameraer", "opptak", "helse", "logg"]);
  });
  it("admin sees everything", () => {
    expect(NAV.every((n) => allowed(n.view, "admin"))).toBe(true);
  });
  it("touch sees nothing", () => {
    expect(NAV.some((n) => allowed(n.view, "touch"))).toBe(false);
  });
});

describe("shot names", () => {
  const studio = {
    participants: [{ id: "P2", name: "Gjest 1" }],
    studio: { inputs: { P1: 1, P2: 2, P3: 3, P4: 4, BIRD: 6, CONTENT: 7 } },
  } as unknown as StudioState;
  it("uses the ATEM names from the studio's input map (D-054)", () => {
    expect(shotName(studio, "CU:P2")).toBe("Camera 2 · Gjest 1");
    expect(shotName(studio, "BIRD")).toBe("Camera 6 · Fugleperspektiv");
    expect(shotName(studio, "CONTENT")).toBe("Camera 7 · Laptop");
    expect(shotName(studio, null)).toBe("–");
  });
  it("falls back to the default inputs without a map", () => {
    const old = { participants: [], studio: {} } as unknown as StudioState;
    expect(shotName(old, "BIRD")).toBe("Camera 5 · Fugleperspektiv");
  });
  it("maps shots to multiview tiles", () => {
    expect(tileOf("CU:P3")).toBe("P3");
    expect(tileOf("PIP:P1+CONTENT")).toBeNull();
  });
});
