import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Store } from "./store";
import { WsTransport } from "./transport";

class FakeSocket {
  static all: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  readonly url: string;
  constructor(url: string) {
    this.url = url;
    FakeSocket.all.push(this);
  }
  close() {
    if (this.closed) return;
    this.closed = true;
    this.onclose?.();
  }
  open() {
    this.onopen?.();
  }
  receive(msg: unknown) {
    this.onmessage?.({ data: typeof msg === "string" ? msg : JSON.stringify(msg) });
  }
}

const last = () => FakeSocket.all.at(-1) as FakeSocket;

describe("WsTransport", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeSocket.all = [];
    vi.stubGlobal("WebSocket", FakeSocket);
    vi.stubGlobal("location", { protocol: "http:", host: "127.0.0.1:8080" });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("connects with the topics and applies messages", () => {
    const store = new Store();
    new WsTransport(["state", "touch"]).start(store);
    expect(last().url).toBe("ws://127.0.0.1:8080/ws?topics=state,touch");
    last().open();
    last().receive({ type: "state", seq: 0, full: true, data: { touch: { step: "ready" } } });
    expect(store.getSnapshot().connection).toBe("connected");
    expect(store.getSnapshot().state?.touch.step).toBe("ready");
  });

  it("keeps the last state and reconnects forever with backoff up to 5 s", () => {
    const store = new Store();
    new WsTransport(["state"]).start(store);
    last().open();
    last().receive({ type: "state", seq: 0, full: true, data: { touch: { step: "rec" } } });
    const delays: number[] = [];
    for (let i = 0; i < 8; i++) {
      const before = FakeSocket.all.length;
      last().close();
      expect(store.getSnapshot().connection).toBe("reconnecting");
      expect(store.getSnapshot().state?.touch.step).toBe("rec"); // never blank (12.5)
      let waited = 0;
      while (FakeSocket.all.length === before) {
        vi.advanceTimersByTime(50);
        waited += 50;
      }
      delays.push(waited);
    }
    expect(delays.slice(0, 4)).toEqual([250, 500, 1000, 2000]);
    expect(Math.max(...delays)).toBe(5000);
    last().open();
    expect(store.getSnapshot().connection).toBe("connected");
  });

  it("resets the backoff after a successful connection", () => {
    const store = new Store();
    new WsTransport(["state"]).start(store);
    for (let i = 0; i < 4; i++) {
      last().close();
      vi.advanceTimersByTime(5000);
    }
    last().open();
    const before = FakeSocket.all.length;
    last().close();
    vi.advanceTimersByTime(250);
    expect(FakeSocket.all.length).toBe(before + 1);
  });

  it("skips a broken message without dropping the connection", () => {
    const store = new Store();
    new WsTransport(["state"]).start(store);
    last().open();
    last().receive("{not json");
    expect(last().closed).toBe(false);
    expect(store.getSnapshot().connection).toBe("connected");
  });

  it("stops reconnecting when stopped", () => {
    const store = new Store();
    const t = new WsTransport(["state"]);
    t.start(store);
    t.stop();
    const n = FakeSocket.all.length;
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.all.length).toBe(n);
  });
});
