import { describe, expect, it } from "vitest";
import samtale from "../../../apps/simulator/public/traces/samtale.json";
import { ReplayTransport, type Trace } from "./replay";
import { Store } from "./store";

const trace = samtale as unknown as Trace;

function player(loop = false) {
  let clock = 0;
  const store = new Store();
  const replay = new ReplayTransport(trace, { loop, now: () => clock });
  replay.start(store);
  replay.stop(); // drive by hand, no timers
  const advance = (ms: number) => {
    for (let i = 0; i < ms; i += 50) {
      clock += 50;
      replay.step();
    }
  };
  return { store, replay, advance };
}

describe("ReplayTransport (SIM-7 trace)", () => {
  it("starts with a full state and is connected", () => {
    const { store } = player();
    const snap = store.getSnapshot();
    expect(snap.connection).toBe("connected");
    expect(snap.state?.touch.step).toBe("idle");
  });

  it("plays the whole touch flow from the real engine", () => {
    const { store, replay, advance } = player();
    replay.setSpeed(10);
    const steps: string[] = [];
    store.subscribe(() => {
      const step = store.getSnapshot().state?.touch.step;
      if (step && steps.at(-1) !== step) steps.push(step);
    });
    advance(trace.duration_ms / 10 + 100);
    expect(steps).toEqual(["idle", "ready", "countdown", "rec", "done", "idle"]);
    expect(store.getSnapshot().decisions.length).toBeGreaterThan(5);
    expect(replay.status().t_ms).toBe(trace.duration_ms);
  });

  it("seeks to the same state as playing there", () => {
    const a = player();
    a.advance(60_000);
    const b = player();
    b.replay.seek(a.replay.status().t_ms);
    expect(b.store.getSnapshot().state).toEqual(a.store.getSnapshot().state);
  });

  it("pauses", () => {
    const { replay, advance } = player();
    replay.setPlaying(false);
    advance(5000);
    expect(replay.status().t_ms).toBe(0);
  });

  it("loops after a short pause at the end", () => {
    const { replay, advance } = player(true);
    replay.seek(trace.duration_ms - 100);
    advance(200);
    expect(replay.status().t_ms).toBe(trace.duration_ms);
    advance(3100);
    expect(replay.status().t_ms).toBeLessThan(1000);
  });

  it("refuses commands with a Norwegian message", async () => {
    const { replay } = player();
    await expect(replay.send()).rejects.toThrow(/opptak/);
  });
});
