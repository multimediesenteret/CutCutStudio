// How a screen talks to the engine. The apps do not know which transport they use – that is the
// whole difference between the studio and the web simulator (ADR-0013, docs/plans/ui.md).
import type { ServerMessage, Store } from "./store";

export interface Transport {
  start(store: Store): void;
  stop(): void;
  /** Same commands as REST (spec 10.2). Throws CommandError with a Norwegian message. */
  send(method: "POST" | "PUT" | "DELETE", path: string, body?: unknown): Promise<void>;
  /** Read something that is not in the live state (rules, shows, log history). */
  get<T>(path: string): Promise<T>;
}

export class CommandError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function rest(base: string, method: string, path: string, body?: unknown): Promise<Response> {
  const res = await fetch(`${base}${path}`, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!res.ok) {
    let msg = "Noe gikk galt. Prøv igjen.";
    try {
      const detail = (await res.json()) as { detail?: unknown };
      if (typeof detail.detail === "string") msg = detail.detail;
    } catch {
      /* keep the generic message */
    }
    throw new CommandError(msg, res.status);
  }
  return res;
}

/** The real engine over WebSocket, reconnecting forever with backoff (the screen never goes
 * blank; it shows the last state greyed out with "Kobler til igjen", spec 12.5). */
export class WsTransport implements Transport {
  private ws: WebSocket | null = null;
  private store: Store | null = null;
  private retry = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;

  private readonly topics: string[];
  private readonly base: string;

  constructor(topics: string[], base = "") {
    this.topics = topics;
    this.base = base;
  }

  start(store: Store): void {
    this.store = store;
    this.stopped = false;
    this.connect();
  }

  private url(): string {
    const loc = globalThis.location;
    const proto = loc.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${loc.host}${this.base}/ws?topics=${this.topics.join(",")}`;
  }

  private connect(): void {
    if (this.stopped || !this.store) return;
    const store = this.store;
    const ws = new WebSocket(this.url());
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      store.setConnection("connected");
    };
    ws.onmessage = (ev) => {
      try {
        store.apply(JSON.parse(String(ev.data)) as ServerMessage);
      } catch {
        /* a bad message is skipped, never fatal */
      }
    };
    ws.onclose = () => {
      this.ws = null;
      if (this.stopped) return;
      store.setConnection("reconnecting");
      const delay = Math.min(5000, 250 * 2 ** this.retry++);
      this.timer = setTimeout(() => this.connect(), delay);
    };
    ws.onerror = () => ws.close();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    this.ws?.close();
  }

  async send(method: "POST" | "PUT" | "DELETE", path: string, body?: unknown): Promise<void> {
    await rest(this.base, method, path, body);
  }

  async get<T>(path: string): Promise<T> {
    const res = await rest(this.base, "GET", path);
    return (await res.json()) as T;
  }
}
