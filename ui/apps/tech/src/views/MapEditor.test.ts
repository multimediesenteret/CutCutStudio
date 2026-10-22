import { describe, expect, it } from "vitest";
import { dragCorner } from "./MapEditor";

describe("dragCorner (VI-5)", () => {
  it("moves one corner and keeps the opposite one", () => {
    expect(dragCorner([0, 0.5, 0.25, 0.25], "nw", 0.02, 0.52)).toEqual([0.02, 0.52, 0.23, 0.23]);
    expect(dragCorner([0, 0.5, 0.25, 0.25], "se", 0.24, 0.74)).toEqual([0, 0.5, 0.24, 0.24]);
  });
  it("stays inside the picture and never collapses a window", () => {
    expect(dragCorner([0, 0.5, 0.25, 0.25], "nw", -0.3, 0.9)).toEqual([0, 0.71, 0.25, 0.04]);
    expect(dragCorner([0.75, 0.75, 0.25, 0.25], "se", 1.4, 1.2)).toEqual([0.75, 0.75, 0.25, 0.25]);
  });
});
