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
  const state = { participants: [{ id: "P2", name: "Gjest 1" }] } as unknown as StudioState;
  it("uses display names from D-041", () => {
    expect(shotName(state, "CU:P2")).toBe("CAM 2 · Gjest 1");
    expect(shotName(state, "BIRD")).toBe("CAM 5 · Fugleperspektiv");
    expect(shotName(state, "CONTENT")).toBe("IN 6 · Laptop");
    expect(shotName(state, null)).toBe("–");
  });
  it("maps shots to multiview tiles", () => {
    expect(tileOf("CU:P3")).toBe("P3");
    expect(tileOf("PIP:P1+CONTENT")).toBeNull();
  });
});
