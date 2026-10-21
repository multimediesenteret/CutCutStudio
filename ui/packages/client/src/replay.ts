// Plays back a trace recorded by `uv run cutcut trace` (SIM-7, ADR-0013 trinn 1). The screens
// get exactly the messages the real engine sent, at the same times – nothing is invented here.
import type { ServerMessage, Store } from "./store";
import { CommandError, type Transport } from "./transport";

export interface Trace {
  version: number;
  story: string;
  title: string;
  duration_ms: number;
  keyframe_ms: number;
  messages: [number, ServerMessage][];
}

export interface ReplayStatus {
  t_ms: number;
  duration_ms: number;
  playing: boolean;
  speed: number;
}

const STEP_MS = 50;
const LOOP_PAUSE_MS = 3000;

export class ReplayTransport implements Transport {
  private store: Store | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private index = 0;
  private t = 0;
  private wall = 0;
  private endedAt: number | null = null;
  private listeners = new Set<(s: ReplayStatus) => void>();
  playing = true;
  speed = 1;
  loop: boolean;
  private readonly trace: Trace;
  private readonly now: () => number;

  constructor(trace: Trace, opts: { loop?: boolean; now?: () => number } = {}) {
    if (trace.version !== 1) throw new Error(`Ukjent forløpsversjon ${trace.version}`);
    this.trace = trace;
    this.loop = opts.loop ?? true;
    this.now = opts.now ?? (() => performance.now());
  }

  get title(): string {
    return this.trace.title;
  }

  start(store: Store): void {
    this.store = store;
    store.setConnection("connected");
    this.seek(0);
    this.wall = this.now();
    this.timer = setInterval(() => this.step(), STEP_MS);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  /** Commands cannot change a recording. The simulator panel explains this to the viewer. */
  send(): Promise<void> {
    return Promise.reject(new CommandError("Dette er et opptak – knappene virker i studio.", 409));
  }

  get<T>(): Promise<T> {
    return Promise.reject(new CommandError("Ikke tilgjengelig i et opptak.", 409));
  }

  onStatus(fn: (s: ReplayStatus) => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  status(): ReplayStatus {
    return {
      t_ms: this.t,
      duration_ms: this.trace.duration_ms,
      playing: this.playing,
      speed: this.speed,
    };
  }

  setPlaying(on: boolean): void {
    this.playing = on;
    this.wall = this.now();
    this.emit();
  }

  setSpeed(speed: number): void {
    this.speed = speed;
    this.emit();
  }

  /** Jump: apply the last full state at or before t, then everything up to t. */
  seek(t_ms: number): void {
    const store = this.store;
    if (!store) return;
    const msgs = this.trace.messages;
    const t = Math.max(0, Math.min(t_ms, this.trace.duration_ms));
    let key = 0;
    for (let i = 0; i < msgs.length; i++) {
      const m = msgs[i];
      if (!m || m[0] > t) break;
      if (m[1].full) key = i;
    }
    store.reset();
    this.index = key;
    this.t = t;
    this.endedAt = null;
    this.applyUntil(t);
    this.emit();
  }

  /** Advance by wall time × speed. Public so tests can drive it without timers. */
  step(): void {
    const now = this.now();
    const elapsed = now - this.wall;
    this.wall = now;
    if (!this.playing) return;
    if (this.endedAt !== null) {
      if (this.loop && now - this.endedAt >= LOOP_PAUSE_MS) this.seek(0);
      return;
    }
    this.t = Math.min(this.trace.duration_ms, this.t + elapsed * this.speed);
    this.applyUntil(this.t);
    if (this.t >= this.trace.duration_ms) this.endedAt = now;
    this.emit();
  }

  private applyUntil(t: number): void {
    const store = this.store;
    if (!store) return;
    const msgs = this.trace.messages;
    while (this.index < msgs.length) {
      const m = msgs[this.index];
      if (!m || m[0] > t) break;
      store.apply(m[1]);
      this.index++;
    }
  }

  private emit(): void {
    const s = this.status();
    for (const fn of this.listeners) fn(s);
  }
}
