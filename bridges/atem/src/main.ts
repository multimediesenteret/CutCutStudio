// atem-bridge: connects to the ATEM with atem-connection and to CutCut core over ZeroMQ.
// Started by the supervisor with the ATEM's address: `node src/main.ts --ip 10.10.10.10`.
// Restarts are cheap and safe: the ATEM keeps its picture, and core waits (I1).
import { Atem } from "atem-connection";
import { Publisher, Subscriber } from "zeromq";
import { EVENTS_IN, EVENTS_OUT, Envelope, parseCommand } from "./bus.ts";
import { statePayload } from "./translate.ts";

function arg(name: string, fallback?: string): string {
  const i = process.argv.indexOf(`--${name}`);
  const value = i >= 0 ? process.argv[i + 1] : process.env[`CUTCUT_ATEM_${name.toUpperCase()}`];
  if (value) return value;
  if (fallback !== undefined) return fallback;
  console.error(`atem-bridge: --${name} mangler`);
  process.exit(2);
}

const ip = arg("ip");
const env = new Envelope();
const pub = new Publisher();
const sub = new Subscriber();
const atem = new Atem();
let connected = false;
let pending: ReturnType<typeof setTimeout> | null = null;

async function send(topic: string, payload: object): Promise<void> {
  try {
    await pub.send([topic, JSON.stringify(env.wrap(topic, payload))]);
  } catch (err) {
    console.error("atem-bridge: kunne ikke sende", topic, err);
  }
}

function publishState(): void {
  if (!connected || !atem.state) return;
  void send("atem.state", statePayload(atem.state));
}

function publishSoon(): void {
  // Many fields change at once on a cut; send one message 30 ms later.
  if (pending) return;
  pending = setTimeout(() => {
    pending = null;
    publishState();
  }, 30);
}

async function status(error: string | null = null): Promise<void> {
  await send("atem.status", { connected, last_error: error, model: atem.state?.info.model ?? null });
}

atem.on("connected", () => {
  connected = true;
  console.log(`atem-bridge: koblet til ${ip}`);
  void status();
  publishState();
});
atem.on("disconnected", () => {
  connected = false;
  console.warn("atem-bridge: mistet forbindelsen, kobler til igjen");
  void status("frakoblet");
});
atem.on("stateChanged", publishSoon);
atem.on("error", (e) => console.error("atem-bridge:", e));

async function commands(): Promise<void> {
  for await (const [, frame] of sub) {
    let id = "?";
    try {
      const msg = JSON.parse(String(frame)) as { payload?: unknown };
      const cmd = parseCommand(msg.payload);
      if (!cmd) {
        await send("atem.ack", { id, ok: false, error: "ugyldig kommando" });
        continue;
      }
      id = cmd.id;
      if (!connected) throw new Error("ATEM er ikke tilkoblet");
      if (cmd.op === "cut") await atem.changeProgramInput(cmd.args.input ?? 0);
      else if (cmd.op === "preview") await atem.changePreviewInput(cmd.args.input ?? 0);
      else await atem.macroRun(cmd.args.macro ?? 0);
      await send("atem.ack", { id, ok: true });
    } catch (err) {
      await send("atem.ack", { id, ok: false, error: String(err) });
    }
  }
}

async function main(): Promise<void> {
  pub.connect(EVENTS_IN);
  sub.connect(EVENTS_OUT);
  sub.subscribe("atem.cmd");
  setInterval(() => {
    publishState(); // at least once a second, so core sees a stale bridge (S-rules)
    void status();
  }, 1000);
  await atem.connect(ip);
  await commands();
}

// SIGBREAK is how the supervisor asks politely on Windows (CTRL_BREAK_EVENT).
for (const sig of ["SIGINT", "SIGTERM", "SIGBREAK"] as const) {
  process.on(sig, () => {
    void atem.disconnect().finally(() => process.exit(0));
  });
}

main().catch((err) => {
  console.error("atem-bridge: stoppet", err);
  process.exit(1); // the supervisor starts it again
});
