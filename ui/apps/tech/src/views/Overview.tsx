// Overview on one page (D-037): multiview, last 60 s, on air and preview, mics, decisions.
import { useSnapshot, useStudio, type Decision, type StudioState } from "@cutcut/client";
import { LevelBar, ShotPicture, levelFromDb, participantColor, seconds } from "@cutcut/design";
import { LivePicture } from "../live";
import { memo, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { historyFor, WINDOW, type History } from "../history";
import { useDecisions, useRules } from "../hooks";
import { hms, inputName, isCut, ruleLabel, shotColor, shotName, tileOf, type Ctx } from "../lib";

const TILES = [
  { key: "P1", shot: "CU:P1", seat: "Programleder" },
  { key: "P2", shot: "CU:P2", seat: "Gjest 1" },
  { key: "P3", shot: "CU:P3", seat: "Gjest 2" },
  { key: "P4", shot: "CU:P4", seat: "Gjest 3" },
  { key: "BIRD", shot: "BIRD", seat: "Fugleperspektiv" },
  { key: "CONTENT", shot: "CONTENT", seat: "Laptop" },
] as const;

const PRESETS = [
  ["rolig", "Rolig"],
  ["standard", "Standard"],
  ["energisk", "Energisk"],
] as const;

export function Overview({ ctx }: { ctx: Ctx }) {
  return (
    <div className="ov">
      <div className="c">
        <Multiview ctx={ctx} />
        <div className="panel grow-panel">
          <div className="ph">
            <span className="lbl">Siste 60 sekunder</span>
            <span className="legend">
              <span>
                <i
                  style={{
                    background:
                      "linear-gradient(90deg,var(--p1) 25%,var(--p2) 25% 50%,var(--p3) 50% 75%,var(--p4) 75%)",
                  }}
                />
                tale og nærbilde
              </span>
              <span>
                <i style={{ background: "var(--bleed)" }} />
                lyd under tale
              </span>
              <span>
                <i style={{ background: "var(--wait)" }} />
                fugleperspektiv
              </span>
              <span>
                <i style={{ background: "var(--eye)" }} />
                laptop
              </span>
            </span>
          </div>
          <Timeline state={ctx.state} />
        </div>
      </div>
      <div className="c">
        <OnAir ctx={ctx} />
        <Mics state={ctx.state} />
        <Decisions ctx={ctx} />
      </div>
    </div>
  );
}

/** The drawn picture only changes when the talker or the theme changes, not at 10 Hz. */
const TilePicture = memo(function TilePicture({
  shot,
  participants,
  talking,
}: {
  shot: string;
  participants: number;
  talking: boolean;
  dark: string;
}) {
  const id = shot.startsWith("CU:") ? shot.slice(3) : shot;
  return <ShotPicture shot={shot} participants={participants} talking={talking ? [id] : []} />;
});

function Multiview({ ctx }: { ctx: Ctx }) {
  const { state, cmd, run } = ctx;
  // A string, so the multiview re-renders only when who is talking changes (12.5 CPU budget).
  const talkingKey = useSnapshot((s) =>
    state.participants
      .filter((p) => s.meters[p.mic]?.speaking)
      .map((p) => p.id)
      .join(","),
  );
  const audioOnly = state.session ? !state.session.show.video : false;
  const ids = new Set(state.participants.map((p) => p.id));
  const pgm = tileOf(state.engine.program);
  const pvw = tileOf(state.engine.preview);
  const rec = state.touch.step === "rec";
  const isDarkKey = document.documentElement.getAttribute("data-theme") ?? "system";
  const note = audioOnly
    ? "Kun lyd: kameraene brukes ikke"
    : !rec
      ? "Ingen opptak: motoren står på total"
      : state.engine.auto
        ? "AUTO på"
        : "AUTO av";
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Multiview · klikk for å klippe manuelt</span>
        <span className="muted small">{note}</span>
      </div>
      <div className="mv">
        {TILES.map((t) => {
          const person = t.key.startsWith("P");
          const used = person
            ? ids.has(t.key)
            : t.key === "CONTENT"
              ? !!state.session?.show.laptop || state.engine.content_active
              : true;
          const off = !used || audioOnly;
          const p = state.participants.find((x) => x.id === t.key);
          const name = p?.name ?? t.seat;
          const cls = [
            "tile",
            off && "off",
            pgm === t.key && "pgm",
            pvw === t.key && pgm !== t.key && "pvw",
          ];
          return (
            <button
              key={t.key}
              type="button"
              className={cls.filter(Boolean).join(" ")}
              style={{ "--pc": person ? participantColor(t.key) : undefined } as CSSProperties}
              disabled={off}
              aria-label={`Klipp til ${inputName(state, t.key)} · ${name}`}
              onClick={() => run(cmd.cut(t.shot))}
            >
              <LivePicture
                live={!!state.runtime.vision}
                source={t.key === "BIRD" ? "C5" : t.key === "CONTENT" ? "LAPTOP" : p?.camera}
                fallback={
                  <TilePicture
                    shot={t.shot}
                    participants={state.participants.length}
                    talking={talkingKey.split(",").includes(t.key)}
                    dark={isDarkKey}
                  />
                }
              />
              {(pgm === t.key || pvw === t.key) && (
                <span className="st">{pgm === t.key ? "PGM" : "PVW"}</span>
              )}
              <span className="cap">
                <i />
                {inputName(state, t.key)} · {name}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function OnAir({ ctx }: { ctx: Ctx }) {
  const { state, cmd, run } = ctx;
  const e = state.engine;
  const rules = useRules(cmd, `${state.rules.preset}|${JSON.stringify(state.rules.overrides)}`);
  const minShot = Number(rules?.values["T3_min_shot_s"] ?? 2.5) * 1000;
  const age = e.program_ms;
  const decisions = useSnapshot((s) => s.decisions);
  // «Neste» is only what the engine is waiting for right now: the newest decision, if it waits.
  const newest = decisions[0];
  const waiting = newest && (newest.action === "wait" || newest.action === "hold") ? newest : null;
  return (
    <div className="panel">
      <div className="pgmcard">
        <div>
          <div className="row">
            <span className="onair">PÅ LUFTA</span>
            <span className="tag">{e.mode}</span>
            {/* Half-second steps: the bar shows the fine progress, and fewer text repaints keep
                the overview inside the CPU budget (12.5). */}
            <span className="tag live">{seconds(Math.floor(age / 500) * 500)}</span>
            {e.shadow && <span className="tag">skygge</span>}
          </div>
          <div className="shot" style={{ "--pc": shotColor(e.program) } as CSSProperties}>
            <i />
            <span>{shotName(state, e.program)}</span>
          </div>
        </div>
        <div className="seg" role="group" aria-label="Forhåndsvalg">
          {PRESETS.map(([k, label]) => (
            <button
              key={k}
              type="button"
              className={state.rules.preset === k ? "sel" : ""}
              aria-pressed={state.rules.preset === k}
              onClick={() => run(cmd.preset(k))}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className={`age ${age >= minShot ? "ok" : ""}`}>
        <i style={{ "--lv": String(Math.min(1, age / minShot)) } as CSSProperties} />
      </div>
      <div className="line pv">
        <b>Preview</b>
        <span>
          {e.preview ? `${shotName(state, e.preview)} · ${e.pv_state}` : "Ingen kandidat"}
        </span>
      </div>
      <div className="line nx">
        <b>Neste</b>
        <span>{waiting ? `${ruleLabel(waiting.rule)}: ${waiting.reason}` : "–"}</span>
      </div>
      <div className="ctrls">
        <button
          type="button"
          className={`btn ${e.auto ? "on" : ""}`}
          aria-pressed={e.auto}
          onClick={() => run(cmd.auto(!e.auto))}
        >
          {e.auto ? "Auto på" : "Auto av"}
        </button>
        <button
          type="button"
          className={`btn ${e.lock ? "warn" : ""}`}
          aria-pressed={e.lock}
          onClick={() => run(cmd.lock(!e.lock))}
        >
          {e.lock ? "Låst" : "Lås bildet"}
        </button>
        <button type="button" className="btn" onClick={() => run(cmd.cut("BIRD"))}>
          Bird nå
        </button>
      </div>
    </div>
  );
}

/** Meters at most 10 times a second: the eye does not see more, the CPU budget does. */
function useThrottledMeters() {
  const { store } = useStudio();
  const [meters, setMeters] = useState(() => store.getSnapshot().meters);
  useEffect(() => {
    const t = setInterval(() => setMeters(store.getSnapshot().meters), 100);
    return () => clearInterval(t);
  }, [store]);
  return meters;
}

function Mics({ state }: { state: StudioState }) {
  const meters = useThrottledMeters();
  const pgm = tileOf(state.engine.program);
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Mikrofoner · RØDECaster USB 1</span>
        <span className="muted small">fader = mic = kamera</span>
      </div>
      <div className="mics">
        {state.participants.map((p, i) => {
          const m = meters[p.mic];
          const label = !state.engine.audio_ok
            ? "ingen lyd"
            : m?.muted
              ? "dempet"
              : m?.speaking
                ? "snakker"
                : "stille";
          const stateCls = label === "snakker" ? "talk" : label === "stille" ? "" : "err";
          const cls = ["mic", i === 0 && "lead", pgm === p.id && "onpgm"].filter(Boolean);
          return (
            <div
              key={p.id}
              className={cls.join(" ")}
              style={{ "--pc": participantColor(p.id) } as CSSProperties}
            >
              <span className="seat">{i + 1}</span>
              <span className="nm">
                {p.name}
                <small>
                  fader {i + 1} · {p.mic} · {p.camera}
                </small>
              </span>
              <LevelBar
                level={m ? levelFromDb(m.level_db) : 0}
                color={participantColor(p.id)}
                steps={20}
              />
              <span className={`state ${stateCls}`}>{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Decisions({ ctx }: { ctx: Ctx }) {
  const all = useDecisions(ctx.cmd);
  const names = ctx.state.participants.map((p) => `${p.id}=${p.name}`).join("|");
  const { state, go } = ctx;
  return useMemo(
    () => <DecisionList decisions={all} state={state} go={go} />,
    // Re-render on new decisions or new names, not on every 10 Hz state message.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [all, names, go],
  );
}

function DecisionList({
  decisions: all,
  state,
  go,
}: {
  decisions: Decision[];
  state: StudioState;
  go: Ctx["go"];
}) {
  const decisions = all.filter((d) => d.action !== "wait");
  const ctx = { state, go };
  return (
    <div className="panel grow-panel">
      <div className="ph">
        <span className="lbl">Beslutninger · nyeste øverst</span>
        <button type="button" className="btn" onClick={() => ctx.go("logg")}>
          Hele loggen
        </button>
      </div>
      <ul className="log">
        {decisions.slice(0, 30).map((d) => (
          <li key={`${d.mono_ms}|${d.correlation_id}`}>
            <span className="t">{hms(d.ts)}</span>
            <span className="to" style={{ "--pc": shotColor(d.shot) } as CSSProperties}>
              <i />
              {isCut(d) ? "→ " : d.action === "preview" ? "PVW " : ""}
              {shotName(ctx.state, d.shot)}{" "}
              {d.rule && <span className="tag">{ruleLabel(d.rule)}</span>}
            </span>
            <span className="why">{d.reason}</span>
          </li>
        ))}
        {decisions.length === 0 && <li className="muted">Ingen beslutninger ennå.</li>}
      </ul>
    </div>
  );
}

function Timeline({ state }: { state: StudioState }) {
  const { store } = useStudio();
  const canvas = useRef<HTMLCanvasElement>(null);
  const names = state.participants.map((p) => p.name);
  const ids = state.participants.map((p) => p.id);
  const key = `${names.join("|")}`;
  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const history = historyFor(store);
    let size = { w: 0, h: 0 };
    const ro = new ResizeObserver((es) => {
      const r = es[0]?.contentRect;
      if (r) size = { w: r.width, h: r.height };
    });
    ro.observe(el);
    // Draw 4 times a second, only while the overview is on screen and visible (12.5 budget).
    const timer = setInterval(() => {
      if (!document.hidden) draw(el, size, history, ids, names);
    }, 250);
    return () => {
      clearInterval(timer);
      ro.disconnect();
    };
  }, [store, key]);
  return (
    <div className="tl">
      <canvas ref={canvas} aria-label="Tidslinje: hvem snakker og hva som var på lufta" />
    </div>
  );
}

let colorCache: { theme: string; get: (v: string) => string } | null = null;
function colors(): (v: string) => string {
  const theme = `${document.documentElement.getAttribute("data-theme")}|${matchMedia?.("(prefers-color-scheme: dark)").matches}`;
  if (colorCache?.theme === theme) return colorCache.get;
  const cs = getComputedStyle(document.documentElement);
  const cache = new Map<string, string>();
  const get = (v: string) => {
    let c = cache.get(v);
    if (c === undefined) {
      c = cs.getPropertyValue(v).trim() || "#888";
      cache.set(v, c);
    }
    return c;
  };
  colorCache = { theme, get };
  return get;
}

function draw(
  cv: HTMLCanvasElement,
  size: { w: number; h: number },
  history: History,
  ids: string[],
  names: string[],
) {
  const { w, h } = size;
  if (w < 10 || h < 10) return;
  const dpr = Math.min(2, devicePixelRatio || 1);
  const W = Math.round(w * dpr);
  const H = Math.round(h * dpr);
  if (cv.width !== W || cv.height !== H) {
    cv.width = W;
    cv.height = H;
  }
  const ctx = cv.getContext("2d");
  if (!ctx) return;
  const C = colors();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const n = ids.length;
  const left = 96;
  const rows = n + 1;
  const gap = 6;
  const axis = 18;
  const rh = Math.max(14, (h - axis - gap * (rows - 1)) / rows);
  ctx.font = `600 12px ${C("--f-ui")}`;
  ctx.textBaseline = "middle";
  for (let r = 0; r < rows; r++) {
    const y = r * (rh + gap);
    ctx.fillStyle = C("--surface-2");
    ctx.fillRect(left, y, w - left, rh);
    if (r < n) {
      ctx.fillStyle = C(`--${ids[r]?.toLowerCase()}`);
      ctx.fillRect(0, y + 3, 4, rh - 6);
      ctx.fillText(names[r] ?? "", 10, y + rh / 2);
    } else {
      ctx.fillStyle = C("--ink");
      ctx.fillText("Program", 10, y + rh / 2);
    }
  }
  const S = history.samples;
  const sw = (w - left) / WINDOW;
  const off = WINDOW - S.length;
  const X = (k: number) => left + (off + k) * sw;
  for (let i = 0; i < n; i++) {
    const y = i * (rh + gap);
    let k = 0;
    while (k < S.length) {
      const v = S[k]?.mics[i] ?? 0;
      let e = k + 1;
      while (e < S.length && (S[e]?.mics[i] ?? 0) === v) e++;
      if (v) {
        ctx.fillStyle = v === 2 ? C(`--${ids[i]?.toLowerCase()}`) : C("--bleed");
        ctx.fillRect(
          X(k),
          v === 2 ? y : y + rh * 0.62,
          X(e) - X(k) + 0.5,
          v === 2 ? rh : rh * 0.38,
        );
      }
      k = e;
    }
  }
  const py = (rows - 1) * (rh + gap);
  let k = 0;
  while (k < S.length) {
    const p = S[k]?.program ?? null;
    let e = k + 1;
    while (e < S.length && (S[e]?.program ?? null) === p) e++;
    const t = tileOf(p);
    ctx.fillStyle =
      t && t.startsWith("P")
        ? C(`--${t.toLowerCase()}`)
        : t === "CONTENT"
          ? C("--eye")
          : t === "BIRD"
            ? C("--wait")
            : C("--bleed");
    ctx.fillRect(X(k), py, X(e) - X(k) + 0.5, rh);
    if (k > 0) {
      ctx.fillStyle = C("--ink");
      ctx.fillRect(X(k) - 1, 0, 2, py + rh);
    }
    k = e;
  }
  ctx.fillStyle = C("--muted");
  ctx.font = `500 11px ${C("--f-ui")}`;
  ctx.textBaseline = "alphabetic";
  for (const sec of [60, 45, 30, 15, 0]) {
    const x = left + (w - left) * (1 - sec / 60);
    ctx.textAlign = sec === 0 ? "right" : sec === 60 ? "left" : "center";
    ctx.fillText(sec ? `−${sec} s` : "nå", x, h - 3);
  }
  ctx.textAlign = "left";
}
