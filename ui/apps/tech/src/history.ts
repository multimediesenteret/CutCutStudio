// The last 60 s of who talked and what was on air, for the overview timeline. Sampled from the
// store at 10 Hz; kept per store so switching views does not lose it.
import type { Store } from "@cutcut/client";

export const SAMPLE_MS = 100;
export const WINDOW = 600; // 60 s

export interface Sample {
  /** Per participant: 0 silent, 1 sound below speech (bleed), 2 speaking. */
  mics: number[];
  program: string | null;
}

export class History {
  readonly samples: Sample[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  private readonly store: Store;

  constructor(store: Store) {
    this.store = store;
  }

  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => this.sample(), SAMPLE_MS);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  sample(): void {
    const { state, meters } = this.store.getSnapshot();
    if (!state) return;
    const mics = state.participants.map((p) => {
      const m = meters[p.mic];
      if (!m) return 0;
      if (m.speaking) return 2;
      return m.level_db > -45 ? 1 : 0;
    });
    this.samples.push({ mics, program: state.engine.program ?? null });
    if (this.samples.length > WINDOW) this.samples.splice(0, this.samples.length - WINDOW);
  }
}

const histories = new WeakMap<Store, History>();

export function historyFor(store: Store): History {
  let h = histories.get(store);
  if (!h) {
    h = new History(store);
    histories.set(store, h);
    h.start();
  }
  return h;
}
