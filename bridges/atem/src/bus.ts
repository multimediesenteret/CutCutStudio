// The CutCut bus envelope (src/cutcut/common/models/bus.py): frames are [topic, json] over
// ZeroMQ; core binds SUB on 5560 (events in) and PUB on 5561 (commands out).
export const EVENTS_IN = "tcp://127.0.0.1:5560";
export const EVENTS_OUT = "tcp://127.0.0.1:5561";
export const SOURCE = "atem-bridge";
const SCHEMA_VERSION = 1;

export interface BusMessage<P = Record<string, unknown>> {
  topic: string;
  source: string;
  ts: string;
  mono_ms: number;
  seq: number;
  schema_version: number;
  payload: P;
}

export class Envelope {
  private seq = new Map<string, number>();
  private readonly start = performance.now();

  wrap<P>(topic: string, payload: P): BusMessage<P> {
    const seq = this.seq.get(topic) ?? 0;
    this.seq.set(topic, seq + 1);
    return {
      topic,
      source: SOURCE,
      ts: new Date().toISOString(),
      mono_ms: Math.floor(performance.now() - this.start),
      seq,
      schema_version: SCHEMA_VERSION,
      payload,
    };
  }
}

export interface AtemCommand {
  id: string;
  op: "cut" | "preview" | "run_macro";
  args: { input?: number; macro?: number };
}

/** Parse an `atem.cmd` payload. Anything unexpected is refused, never guessed. */
export function parseCommand(payload: unknown): AtemCommand | null {
  if (typeof payload !== "object" || payload === null) return null;
  const p = payload as Record<string, unknown>;
  const args = (p.args ?? {}) as Record<string, unknown>;
  if (typeof p.id !== "string") return null;
  if (p.op === "cut" || p.op === "preview") {
    if (typeof args.input !== "number" || !Number.isInteger(args.input)) return null;
    return { id: p.id, op: p.op, args: { input: args.input } };
  }
  if (p.op === "run_macro") {
    if (typeof args.macro !== "number" || !Number.isInteger(args.macro)) return null;
    return { id: p.id, op: "run_macro", args: { macro: args.macro } };
  }
  return null;
}
