import { describe, expect, it } from "vitest";
import { Store, type StudioState } from "./store";

const state = { touch: { step: "idle" }, engine: { program: "BIRD" } } as unknown as StudioState;

describe("Store", () => {
  it("takes a full state, then merges changed top-level keys", () => {
    const s = new Store();
    s.apply({ type: "state", seq: 0, full: true, data: state });
    s.apply({ type: "state", seq: 1, data: { engine: { program: "CU:P2" } } });
    const snap = s.getSnapshot();
    expect(snap.state?.engine.program).toBe("CU:P2");
    expect(snap.state?.touch.step).toBe("idle");
  });

  it("keeps the newest decisions first and bounded", () => {
    const s = new Store();
    for (let i = 0; i < 250; i++) s.apply({ type: "decision", seq: i, data: { mono_ms: i } });
    const d = s.getSnapshot().decisions;
    expect(d.length).toBe(200);
    expect(d[0]?.mono_ms).toBe(249);
  });

  it("notifies subscribers and reports connection changes once", () => {
    const s = new Store();
    let calls = 0;
    s.subscribe(() => calls++);
    s.setConnection("connected");
    s.setConnection("connected");
    expect(calls).toBe(1);
  });
});
