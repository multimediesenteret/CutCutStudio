// One source of truth on the screen side: the latest StudioState from the engine, plus meters,
// recent decisions and the connection status (spec 12.5). The screen never invents state.
import type { components } from "./api-types";

export type StudioState = components["schemas"]["StudioState"];
export type Meter = components["schemas"]["Meter"];
export type Decision = components["schemas"]["Decision"];
export type AlertInfo = components["schemas"]["AlertInfo"];
export type ParticipantInfo = components["schemas"]["ParticipantInfo"];
export type TouchStep = StudioState["touch"]["step"];

export type Connection = "connecting" | "connected" | "reconnecting";

export interface ServerMessage {
  type: "state" | "meters" | "decision" | "alert" | "touch" | "session" | "health" | "vision";
  seq: number;
  full?: boolean;
  data: unknown;
}

export interface Snapshot {
  state: StudioState | null;
  meters: Record<string, Meter>;
  decisions: Decision[];
  connection: Connection;
  /** Wall time of the last message, to show "Kobler til igjen" while greyed out. */
  lastMessageAt: number;
}

const MAX_DECISIONS = 200;

export class Store {
  private snap: Snapshot = {
    state: null,
    meters: {},
    decisions: [],
    connection: "connecting",
    lastMessageAt: 0,
  };
  private listeners = new Set<() => void>();

  getSnapshot = (): Snapshot => this.snap;

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  private set(patch: Partial<Snapshot>): void {
    this.snap = { ...this.snap, ...patch };
    for (const fn of this.listeners) fn();
  }

  setConnection(connection: Connection): void {
    if (connection !== this.snap.connection) this.set({ connection });
  }

  /** Apply one server message. Unknown or partial data never throws. */
  apply(msg: ServerMessage, now = Date.now()): void {
    switch (msg.type) {
      case "state": {
        const data = msg.data as Partial<StudioState>;
        if (msg.full || this.snap.state === null) {
          this.set({ state: data as StudioState, lastMessageAt: now });
        } else {
          this.set({ state: { ...this.snap.state, ...data }, lastMessageAt: now });
        }
        return;
      }
      case "meters":
        this.set({ meters: msg.data as Record<string, Meter>, lastMessageAt: now });
        return;
      case "decision": {
        const decisions = [msg.data as Decision, ...this.snap.decisions].slice(0, MAX_DECISIONS);
        this.set({ decisions, lastMessageAt: now });
        return;
      }
      default:
        this.set({ lastMessageAt: now });
    }
  }
}
