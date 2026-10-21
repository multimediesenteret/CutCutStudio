import { describe, expect, it } from "vitest";
import { clock, seconds } from "./time";

describe("time formatting", () => {
  it("formats durations like the touch screen", () => {
    expect(clock(0)).toBe("00:00");
    expect(clock(65)).toBe("01:05");
    expect(clock(3723)).toBe("1:02:03");
  });
  it("uses a decimal comma", () => {
    expect(seconds(2500)).toBe("2,5 s");
  });
});
