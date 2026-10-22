// The technician pages behind the rail (U-7, U-8): Regi, Kameraer, Opptak, Helse, Logg,
// Innstillinger and the Oppsett placeholder (the setup wizard comes in M3).
import {
  useStudio,
  type Decision,
  type SessionRow,
  type ShowDetail,
  type StudioState,
} from "@cutcut/client";
import { ShotPicture, clock, participantColor, type Theme } from "@cutcut/design";
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useDecisions, useRules } from "../hooks";
import { Alerts } from "./Alerts";
import { IsoPanel } from "./Iso";
import { CameraControls, useCameras } from "./CameraControls";
import { SetupFile, Technicians } from "./SetupFile";
import { LivePicture } from "../live";
import { hms, isCut, isError, ruleLabel, shotColor, shotName, tileOf, type Ctx } from "../lib";

const PRESETS = [
  ["rolig", "Rolig"],
  ["standard", "Standard"],
  ["energisk", "Energisk"],
] as const;

function Switch({
  on,
  label,
  onToggle,
  disabled = false,
}: {
  on: boolean;
  label: string;
  onToggle: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className="sw"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={onToggle}
    />
  );
}

// -- Regi (admin) ------------------------------------------------------------------------

const SLIDERS: {
  name: string;
  id: string;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  {
    name: "T2_confirm_ms",
    id: "T2",
    label: "Bekreftelse før kutt",
    min: 200,
    max: 2000,
    step: 50,
    unit: "ms",
  },
  {
    name: "T3_min_shot_s",
    id: "T3",
    label: "Minste bildelengde",
    min: 1,
    max: 8,
    step: 0.1,
    unit: "s",
  },
  {
    name: "T1_dominance_db",
    id: "T1",
    label: "Dominans over andre mic-er",
    min: 2,
    max: 15,
    step: 0.5,
    unit: "dB",
  },
  {
    name: "T5_crosstalk_s",
    id: "T5",
    label: "Krysstale før total",
    min: 0.4,
    max: 3,
    step: 0.1,
    unit: "s",
  },
  {
    name: "T8_silence_s",
    id: "T8",
    label: "Stillhet før total",
    min: 1,
    max: 8,
    step: 0.5,
    unit: "s",
  },
  {
    name: "T7_reaction_after_s",
    id: "T7",
    label: "Reaksjonsbilde etter",
    min: 5,
    max: 40,
    step: 1,
    unit: "s",
  },
];

const FEATURES: { key: string; name: string; ids: string; d: string; base?: boolean }[] = [
  {
    key: "bird",
    name: "Fugleperspektiv",
    ids: "B1–B5",
    d: "Åpning, krysstale, latter og stillhet",
    base: true,
  },
  {
    key: "content",
    name: "Laptop som content",
    ids: "CT1–CT6",
    d: "Ny slide vises; video holdes",
    base: true,
  },
  {
    key: "video_confirm",
    name: "Videolag bekrefter",
    ids: "V1 V2 V5",
    d: "Munnbevegelse bekrefter tale",
  },
  { key: "reactions", name: "Reaksjonsklipp", ids: "R1–R3", d: "Lytter som nikker eller ler" },
  { key: "framing_variety", name: "Vekslende utsnitt", ids: "F1–F3", d: "Nær og halvnær off air" },
  { key: "slow_zoom", name: "Langsom zoom", ids: "Z1–Z3", d: "Maks 10 % over 15 s" },
  { key: "layouts", name: "Layouter (PiP/quad)", ids: "L1–L4", d: "ATEM-makroer via Companion" },
  { key: "ai_tracking", name: "AI-tracking", ids: "AT1–AT6", d: "OBSBOT følger personen" },
];

const MODES = [
  ["off", "Av"],
  ["shadow", "Skygge"],
  ["on", "På"],
] as const;

function fmt(v: number, unit: string): string {
  const s =
    unit === "s"
      ? v.toFixed(1).replace(".", ",")
      : String(Math.round(v * 10) / 10).replace(".", ",");
  return `${s} ${unit}`;
}

function Slider({
  def,
  value,
  presetValue,
  overridden,
  onCommit,
  onReset,
}: {
  def: (typeof SLIDERS)[number];
  value: number;
  presetValue: number;
  overridden: boolean;
  onCommit: (v: number) => void;
  onReset: () => void;
}) {
  const [local, setLocal] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => setLocal(value), [value]);
  const change = (v: number) => {
    setLocal(v);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onCommit(v), 400);
  };
  const id = `sl-${def.name}`;
  return (
    <div className="slider">
      <span className="tag">{def.id}</span>
      <label htmlFor={id}>{def.label}</label>
      <output
        htmlFor={id}
        className={overridden ? "changed" : ""}
        title={`Forhåndsvalg: ${fmt(presetValue, def.unit)}`}
      >
        {fmt(local, def.unit)}
      </output>
      <button
        type="button"
        className="btn reset"
        disabled={!overridden}
        onClick={onReset}
        title="Tilbake til forhåndsvalget"
      >
        Nullstill
      </button>
      <input
        id={id}
        type="range"
        min={def.min}
        max={def.max}
        step={def.step}
        value={local}
        onChange={(e) => change(Number(e.target.value))}
      />
    </div>
  );
}

export function Regi({ ctx }: { ctx: Ctx }) {
  const { state, cmd, run } = ctx;
  const rules = useRules(cmd, `${state.rules.preset}|${JSON.stringify(state.rules.overrides)}`);
  return (
    <div className="grid2">
      <div className="panel">
        <div className="ph">
          <span className="lbl">Tuning</span>
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
        <p className="muted">
          Forhåndsvalg og finjustering gjelder fra neste tikk, overlever omstart og står i
          revisjonsloggen. Blå verdi = endret fra forhåndsvalget.
        </p>
        {rules ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {SLIDERS.map((def) => (
              <Slider
                key={def.name}
                def={def}
                value={Number(rules.values[def.name])}
                presetValue={Number(rules.preset_values[def.name])}
                overridden={def.name in state.rules.overrides}
                onCommit={(v) => run(cmd.overrides({ [def.name]: v }))}
                onReset={() => run(cmd.overrides({ [def.name]: null }))}
              />
            ))}
          </div>
        ) : (
          <p className="muted">Regelverdier er ikke tilgjengelige.</p>
        )}
      </div>
      <div className="panel">
        <div className="ph">
          <span className="lbl">Brytere · grunnmodus først</span>
        </div>
        <div>
          {FEATURES.map((f) => {
            const on = !!state.rules.features[f.key];
            const sw = state.rules.switches?.find((s) => s.key === f.key);
            return (
              <div className="feat" key={f.key}>
                <span>
                  <b>{f.name}</b> <span className="tag">{f.ids}</span>
                  {f.base && <span className="tag">grunnmodus</span>}
                  {sw?.mode === "shadow" && <span className="tag">skygge</span>}
                </span>
                <span className="fd">
                  {f.d}
                  {sw?.why && sw.mode === "off" && (
                    <>
                      <br />
                      <span className="small muted">{sw.why}</span>
                    </>
                  )}
                </span>
                {sw ? (
                  <div className="seg" role="group" aria-label={f.name}>
                    {MODES.map(([mode, label]) => (
                      <button
                        key={mode}
                        type="button"
                        className={sw.mode === mode ? "sel" : ""}
                        aria-pressed={sw.mode === mode}
                        disabled={
                          sw.mode !== mode &&
                          ((mode === "on" && !sw.can_on) || (mode === "shadow" && !sw.can_shadow))
                        }
                        title={
                          mode === "shadow"
                            ? "Reglene kjører og logges, men klipper ikke"
                            : undefined
                        }
                        onClick={() => run(cmd.features({ [f.key]: mode }))}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                ) : (
                  <Switch
                    on={on}
                    label={f.name}
                    onToggle={() => run(cmd.features({ [f.key]: !on }))}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="panel">
        <div className="ph">
          <span className="lbl">Laptop og content</span>
        </div>
        <div className="feat">
          <span>
            <b>Content på</b>
          </span>
          <span className="fd">Inngang 6, lest fra multiview. Av: laptopen klippes aldri inn.</span>
          <Switch
            on={state.engine.content_enabled}
            label="Content på"
            onToggle={() => run(cmd.content(!state.engine.content_enabled))}
          />
        </div>
        <p className="muted small">
          {state.engine.content_active ? "Laptopen viser noe nå." : "Ingen aktiv laptop-visning."}
        </p>
      </div>
    </div>
  );
}

// -- Kameraer (read only in M1; control comes with the camera drivers in M2) -------------

const DRIVER: Record<string, string> = {
  canon_xc: "Canon CR-N300 · XC over HTTP",
  obsbot: "OBSBOT Tail 2 · VISCA + OSC",
  none: "Fast kamera · ingen styring",
};

export function Cameras({ ctx }: { ctx: Ctx }) {
  const { state, cmd } = ctx;
  const [show, setShow] = useState<ShowDetail | null>(null);
  useEffect(() => {
    let alive = true;
    cmd
      .show(state.studio.show_id)
      .then((s) => alive && setShow(s))
      .catch(() => alive && setShow(null));
    return () => {
      alive = false;
    };
  }, [cmd, state.studio.show_id]);
  const pgm = tileOf(state.engine.program);
  const pvw = tileOf(state.engine.preview);
  const cams = show ? Object.entries(show.cameras) : [];
  const steered = useCameras();
  return (
    <>
      <p className="muted" style={{ marginBottom: 12 }}>
        Presets og utsnitt kan bare endres på kamera som ikke er på program eller preview (I2).
        {steered && steered.length === 0 && " Kameraene styres ikke fra denne PC-en."}
      </p>
      {!show && <p className="muted">Kameraoppsettet er ikke tilgjengelig.</p>}
      <div className="grid3">
        {cams.map(([id, c]) => {
          const p = show?.participants.find((x) => x.camera === id);
          const shot = p ? `CU:${p.id}` : c.role === "bird" ? "BIRD" : "WIDE";
          const key = p?.id ?? (c.role === "bird" ? "BIRD" : id);
          const live = pgm === key ? "På lufta" : pvw === key ? "På preview" : "Klar";
          return (
            <div
              className="panel camcard"
              key={id}
              style={{ "--pc": p ? participantColor(p.id) : undefined } as CSSProperties}
            >
              <div className="ph">
                <b>
                  Camera {c.atem_input} ·{" "}
                  {p?.name ?? (c.role === "bird" ? "Fugleperspektiv" : (c.role ?? ""))}
                </b>
                <span className={`hst ${live === "Klar" ? "" : "warn"}`}>
                  <i />
                  {live}
                </span>
              </div>
              <div className="pic">
                <LivePicture
                  live={!!state.runtime.vision}
                  source={id}
                  fallback={<ShotPicture shot={shot} participants={state.participants.length} />}
                />
              </div>
              <div className="kv">
                <span>Modell</span>
                <span>{DRIVER[c.driver] ?? c.driver}</span>
                <span>IP</span>
                <span className="mono">{c.ip ?? "–"}</span>
                <span>ATEM-inngang</span>
                <span>{c.atem_input}</span>
                <span>Hvitbalanse</span>
                <span>{c.driver === "none" ? "Fast" : "Manuell · 5600 K"}</span>
              </div>
              {(() => {
                const ci = steered?.find((s) => s.id === id);
                return ci ? <CameraControls ctx={ctx} cam={ci} /> : null;
              })()}
            </div>
          );
        })}
      </div>
    </>
  );
}

// -- Opptak --------------------------------------------------------------------------------

const PEARL: Record<string, [string, string]> = {
  idle: ["Klar", ""],
  starting: ["Starter …", "warn"],
  started: ["Tar opp", "err"],
  stopped: ["Klar", ""],
  error: ["Feil", "err"],
  disabled: ["Av", "todo"],
};

export function Recording({ ctx }: { ctx: Ctx }) {
  const { state } = ctx;
  const s = state.session;
  const [label, cls] = PEARL[state.recording.pearl] ?? ["–", "todo"];
  return (
    <div className="grid2">
      <div className="panel">
        <div className="ph">
          <span className="lbl">Epiphan Pearl Nexus</span>
          <span className={`hst ${cls}`}>
            <i />
            {label}
          </span>
        </div>
        <div className="kv">
          <span>Opptaker</span>
          <span>Podkast · kanal 1 (ATEM program)</span>
          <span>Lengde</span>
          <span className="tnum">{clock(state.recording.duration_s)}</span>
          <span>Startet fra</span>
          <span>{state.recording.started_by ?? "–"}</span>
          <span>Publisering</span>
          <span>Panopto: forberedt, ikke slått på (M4). Opptaket ligger på Pearl.</span>
          <span>Forbindelse</span>
          <span className={state.recording.online ? "" : "err-text"}>
            {state.recording.online ? "Svarer" : "Svarer ikke"}
          </span>
          {state.recording.storage_free_pct != null && (
            <>
              <span>Ledig lagring</span>
              <span>{state.recording.storage_free_pct} %</span>
            </>
          )}
          {state.recording.firmware && (
            <>
              <span>Fastvare</span>
              <span>{state.recording.firmware}</span>
            </>
          )}
          {state.recording.error && (
            <>
              <span>Siste feil</span>
              <span className="err-text">{state.recording.error}</span>
            </>
          )}
        </div>
      </div>
      <div className="panel">
        <div className="ph">
          <span className="lbl">Økt</span>
          <span className="muted small">{state.touch.step}</span>
        </div>
        {s ? (
          <div className="kv">
            <span>Bruker</span>
            <span>
              {s.user.display_name} ({s.user.username})
            </span>
            <span>Økt</span>
            <span className="mono small">{s.session_id}</span>
            <span>Oppsett</span>
            <span>
              {s.show.guests + 1} {s.show.guests === 0 ? "person" : "personer"} ·{" "}
              {s.show.video ? "video og lyd" : "kun lyd"}
              {s.show.laptop ? " · laptop" : ""}
            </span>
            <span>Modus</span>
            <span>{s.mode}</span>
            <span>Panopto</span>
            <span>
              {s.publish.state === "disabled"
                ? "forberedt, ikke slått på"
                : `${s.publish.folder} · ${s.publish.state}`}
            </span>
          </div>
        ) : (
          <p className="muted">Ingen er logget inn.</p>
        )}
      </div>
      <IsoPanel ctx={ctx} />
      <SessionTable ctx={ctx} />
    </div>
  );
}

function SessionTable({ ctx }: { ctx: Ctx }) {
  const { cmd, state } = ctx;
  const [rows, setRows] = useState<SessionRow[] | null>(null);
  // Refresh when a session starts, ends or changes step.
  const key = `${state.session?.session_id ?? ""}|${state.touch.step}`;
  useEffect(() => {
    let alive = true;
    cmd
      .sessions(1)
      .then((r) => alive && setRows(r))
      .catch(() => alive && setRows(null));
    return () => {
      alive = false;
    };
  }, [cmd, key]);
  return (
    <div className="panel span">
      <div className="ph">
        <span className="lbl">Opptak siste døgn</span>
        {rows && (
          <a className="btn" href="/api/sessions.csv?days=30" download>
            Last ned CSV (30 dager)
          </a>
        )}
      </div>
      {rows === null ? (
        <p className="muted">Økthistorikken er ikke tilgjengelig her.</p>
      ) : (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Start</th>
                <th>Bruker</th>
                <th>Lengde</th>
                <th>Type</th>
                <th>Personer</th>
                <th>Startet fra</th>
                <th>Panopto</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">
                    Ingen opptak ennå.
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.session_id}>
                  <td className="tnum">{hms(r.started_at).slice(0, 5)}</td>
                  <td>
                    {r.display_name} <span className="muted">({r.username})</span>
                  </td>
                  <td className="tnum">{clock(r.duration_s)}</td>
                  <td>{r.video ? "Video og lyd" : "Kun lyd"}</td>
                  <td>{r.participants}</td>
                  <td>{r.started_by ?? "–"}</td>
                  <td>{r.publish ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// -- Helse ---------------------------------------------------------------------------------

interface SimStatus {
  conversation: boolean;
  content: string | null;
  audio_lost: boolean;
  atem_online: boolean;
  companion_online: boolean;
  moving: string[];
  multiview_wrong?: boolean;
  pearl_online?: boolean;
  disk_full?: boolean;
}

const FAULTS: { kind: string; label: string; on: (s: SimStatus) => boolean; camera?: string }[] = [
  { kind: "audio_lost", label: "Lyd fra RØDECaster borte (S4)", on: (s) => s.audio_lost },
  { kind: "atem_down", label: "ATEM svarer ikke", on: (s) => !s.atem_online },
  { kind: "companion_down", label: "Companion nede (S5)", on: (s) => !s.companion_online },
  {
    kind: "camera_moving",
    label: "Gjest 1-kameraet beveger seg (S1)",
    on: (s) => s.moving.includes("C2"),
    camera: "C2",
  },
  {
    kind: "multiview_wrong",
    label: "Noen har endret ATEM-multiviewen (H-MV)",
    on: (s) => !!s.multiview_wrong,
  },
  {
    kind: "pearl_offline",
    label: "Pearl svarer ikke (H-PRL-1)",
    on: (s) => s.pearl_online === false,
  },
  { kind: "disk_full", label: "Disken på PC-en er full (H-PC-1)", on: (s) => !!s.disk_full },
];

function SimPanel({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const { cmd, run } = ctx;
  const [sim, setSim] = useState<SimStatus | null>(null);
  const refresh = useMemo(
    () => () => {
      transport
        .get<SimStatus>("/api/sim")
        .then(setSim)
        .catch(() => setSim(null));
    },
    [transport],
  );
  useEffect(refresh, [refresh]);
  if (!sim) return null;
  const after = (p: Promise<unknown>) => run(p.then(refresh));
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Simulator · bare i cutcut sim</span>
      </div>
      <div className="feat">
        <span>
          <b>Samtale</b>
        </span>
        <span className="fd">Syntetiske stemmer snakker etter tur</span>
        <Switch
          on={sim.conversation}
          label="Samtale"
          onToggle={() => after(cmd.simConversation(!sim.conversation))}
        />
      </div>
      <div className="row">
        <button
          type="button"
          className="btn"
          onClick={() => after(cmd.simContent("NEW_SLIDE").then(() => cmd.simContent("STATIC")))}
        >
          Ny slide
        </button>
        <button type="button" className="btn" onClick={() => after(cmd.simContent("VIDEO"))}>
          Video på laptop
        </button>
        <button type="button" className="btn" onClick={() => after(cmd.simContent(null))}>
          Laptop av
        </button>
      </div>
      {FAULTS.map((f) => (
        <div className="feat" key={f.kind}>
          <span>
            <b>{f.label}</b>
          </span>
          <span className="fd">Simulert feil</span>
          <Switch
            on={f.on(sim)}
            label={f.label}
            onToggle={() => after(cmd.simFault(f.kind, !f.on(sim), f.camera))}
          />
        </div>
      ))}
    </div>
  );
}

export function Health({ ctx }: { ctx: Ctx }) {
  const { state, cmd, run } = ctx;
  const levelText = { info: "Info", warn: "Advarsel", error: "Feil" } as const;
  const levelCls = { info: "", warn: "warn", error: "err" } as const;
  const rt = state.runtime;
  return (
    <div className="grid2">
      <div className="panel span">
        <div className="ph">
          <span className="lbl">Åpne varsler</span>
          <span className="muted small">
            Samme som <span className="mono">GET /api/health</span> for ekstern overvåkning
          </span>
        </div>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Tid</th>
                <th>Kode</th>
                <th>Status</th>
                <th>Melding</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {state.alerts.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    Ingen åpne varsler.
                  </td>
                </tr>
              )}
              {[...state.alerts].reverse().map((a) => (
                <tr key={a.id}>
                  <td className="mono">{hms(a.ts)}</td>
                  <td>
                    <span className="tag">{a.code}</span>
                  </td>
                  <td>
                    <span className={`hst ${levelCls[a.level]}`}>
                      <i />
                      {levelText[a.level]}
                    </span>
                  </td>
                  <td>{a.message}</td>
                  <td>
                    <button type="button" className="btn" onClick={() => run(cmd.ack(a.id))}>
                      Kvitter
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="panel">
        <div className="ph">
          <span className="lbl">Motor</span>
          <span className={`hst ${state.engine.audio_ok ? "" : "err"}`}>
            <i />
            {state.engine.audio_ok ? "Lyd OK" : "Ingen lyd"}
          </span>
        </div>
        <div className="kv">
          <span>Modus</span>
          <span>{state.engine.mode}</span>
          <span>AUTO / LÅS</span>
          <span>
            {state.engine.auto ? "på" : "av"} / {state.engine.lock ? "på" : "av"}
          </span>
          <span>Tikk</span>
          <span className="tnum">{rt.ticks}</span>
          <span>Lengste steg</span>
          <span className="tnum">{rt.max_step_ms.toFixed(2).replace(".", ",")} ms</span>
          <span>Hoppet over</span>
          <span className="tnum">{rt.skipped_ticks}</span>
          <span>Versjon</span>
          <span>{state.studio.version}</span>
        </div>
      </div>
      <Checks health={state.health} ctx={ctx} />
      <Processes processes={rt.processes ?? []} />
      {state.studio.simulator && <SimPanel ctx={ctx} />}
    </div>
  );
}

type Health = NonNullable<StudioState["health"]>;

const MORNING_REASON = {
  oppstart: "Oppstartssjekk",
  morgen: "Morgensjekk",
  manuell: "Full sjekk",
} as const;

const CHECK_TEXT = { green: "OK", yellow: "Avvik", red: "Feil" } as const;
const CHECK_CLS = { green: "", yellow: "warn", red: "err" } as const;

/** The health checks (spec 8.5): latest result of each, worst first. */
function Checks({ health, ctx }: { health: Health | undefined; ctx: Ctx }) {
  const rank = { red: 0, yellow: 1, green: 2 } as const;
  const checks = [...(health?.checks ?? [])].sort(
    (a, b) => rank[a.status] - rank[b.status] || a.id.localeCompare(b.id),
  );
  const status = health?.status ?? "green";
  return (
    <div className="panel span">
      <div className="ph">
        <span className="lbl">Sjekker</span>
        <span className={`hst ${CHECK_CLS[status]}`}>
          <i />
          {CHECK_TEXT[status]}
        </span>
        <span className="muted small">Et avvik lukkes etter 30 s grønt</span>
        {health?.morning && (
          <span className="muted small">
            {MORNING_REASON[health.morning.reason]} kl. {health.morning.ts.slice(11, 16)}:{" "}
            {health.morning.failed.length === 0 ? "alt grønt" : health.morning.failed.join(", ")}
          </span>
        )}
        <button type="button" className="btn" onClick={() => ctx.run(ctx.cmd.morningCheck())}>
          Kjør alle nå
        </button>
      </div>
      {checks.length === 0 ? (
        <p className="muted small">Sjekkene har ikke kjørt ennå.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Sjekk</th>
              <th>Status</th>
              <th>Verdi</th>
              <th>Forventet</th>
              <th>Melding</th>
            </tr>
          </thead>
          <tbody>
            {checks.map((c) => (
              <tr key={c.id}>
                <td>
                  <span className="tag">{c.id}</span>
                </td>
                <td>
                  <span className={`hst ${CHECK_CLS[c.status]}`}>
                    <i />
                    {CHECK_TEXT[c.status]}
                  </span>
                </td>
                <td className="mono">{c.value}</td>
                <td className="muted">{c.expected ?? "–"}</td>
                <td>
                  {c.message}
                  {c.since && <span className="muted small"> · siden {hms(c.since)}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

type Proc = NonNullable<StudioState["runtime"]["processes"]>[number];

function uptime(s: number): string {
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  const h = Math.floor(s / 3600);
  return h < 48 ? `${h} t` : `${Math.floor(h / 24)} d`;
}

/** What the supervisor reports (SO-1): each process, how long it has run, restarts. */
function Processes({ processes }: { processes: Proc[] }) {
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Prosesser</span>
        <span className="muted small">Supervisor starter dem på nytt selv</span>
      </div>
      {processes.length === 0 ? (
        <p className="muted small">Ingen status fra supervisor (kjører uten tjenesten).</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Prosess</th>
              <th>Status</th>
              <th>Oppe</th>
              <th title="Omstarter siste 10 minutter">Omstart</th>
            </tr>
          </thead>
          <tbody>
            {processes.map((p) => (
              <tr key={p.name}>
                <td className="mono">{p.name}</td>
                <td>
                  <span
                    className={`hst ${!p.running ? "err" : (p.restarts_10min ?? 0) > 5 ? "warn" : ""}`}
                    title={p.last_reason ?? undefined}
                  >
                    <i />
                    {p.running ? "Kjører" : "Startes"}
                  </span>
                </td>
                <td className="tnum">{p.running ? uptime(p.uptime_s ?? 0) : "–"}</td>
                <td className="tnum">{p.restarts_10min ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// -- Logg ----------------------------------------------------------------------------------

type Filter = "all" | "cut" | "set" | "err";

function csv(rows: Decision[]): string {
  const q = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const head = ["tid", "handling", "bilde", "regel", "hvorfor", "modus", "korrelasjon"];
  const lines = rows.map((d) =>
    [d.ts, d.action, d.shot, d.rule, d.reason, d.mode, d.correlation_id].map(q).join(";"),
  );
  return [head.join(";"), ...lines].join("\r\n");
}

export function LogView({ ctx }: { ctx: Ctx }) {
  const all = useDecisions(ctx.cmd);
  // The engine makes the files; in the web simulator (fixed role) the page makes the CSV.
  const live = !useStudio().transport.role;
  const [filter, setFilter] = useState<Filter>("all");
  const rows = all.filter((d) =>
    filter === "all"
      ? d.action !== "wait"
      : filter === "cut"
        ? isCut(d)
        : filter === "err"
          ? isError(d)
          : !isCut(d) && !isError(d) && d.action !== "wait",
  );
  const download = () => {
    const blob = new Blob(["﻿" + csv(rows)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `cutcut-logg-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  return (
    <div className="panel">
      <div className="ph">
        <div className="seg" role="group" aria-label="Filter">
          {(
            [
              ["all", "Alle"],
              ["cut", "Kutt"],
              ["set", "Preview og hold"],
              ["err", "Sikkerhet"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              className={filter === k ? "sel" : ""}
              aria-pressed={filter === k}
              onClick={() => setFilter(k)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="row">
          {live ? (
            <a className="btn" href="/api/log.csv" download>
              Last ned CSV
            </a>
          ) : (
            <button type="button" className="btn" onClick={download} disabled={rows.length === 0}>
              Last ned CSV
            </button>
          )}
          {live && ctx.role === "admin" && (
            <a className="btn" href="/api/debug-package" download>
              Feilsøkingspakke
            </a>
          )}
        </div>
      </div>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Tid</th>
              <th>Bilde</th>
              <th>Regel</th>
              <th>Hvorfor</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  Ingen hendelser ennå.
                </td>
              </tr>
            )}
            {rows.slice(0, 300).map((d) => (
              <tr key={`${d.mono_ms}|${d.correlation_id}`}>
                <td className="mono">{hms(d.ts)}</td>
                <td style={{ "--pc": shotColor(d.shot) } as CSSProperties}>
                  <span className="hst" style={{ color: "var(--ink)" }}>
                    <i style={{ background: "var(--pc)" }} />
                    {isCut(d) ? "" : `${d.action} · `}
                    {shotName(ctx.state, d.shot)}
                  </span>
                </td>
                <td>
                  {d.rule && <span className="tag">{ruleLabel(d.rule)}</span>}
                  {d.switch && <span className="tag">skygge · {d.switch}</span>}
                </td>
                <td>{d.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// -- Innstillinger (admin) -----------------------------------------------------------------

const COLORS = [
  ["P1", "Programleder", "magenta"],
  ["P2", "Gjest 1", "cyan"],
  ["P3", "Gjest 2", "lilla"],
  ["P4", "Gjest 3", "oransje"],
] as const;

/** The studio's show type (SE-6, D-036): chosen here, never by the user on touch. */
function ShowTypePanel({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const studio = ctx.state.studio as { show_types: Record<string, string>; show_type?: string };
  const current = studio.show_type ?? "podcast";
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Show-type</span>
        <span className="muted small">Gjelder nye økter</span>
      </div>
      <div className="seg" role="group" aria-label="Show-type">
        {Object.entries(studio.show_types).map(([k, label]) => (
          <button
            key={k}
            type="button"
            className={current === k ? "sel" : ""}
            aria-pressed={current === k}
            disabled={ctx.role !== "admin"}
            onClick={() => ctx.run(transport.send("PUT", "/api/settings/show-type", { type: k }))}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="muted">
        Typen gir regel-forhåndsvalget når en økt starter. «Kun lyd» tar bare opp lyd, med «Kun
        lyd»-grafikken på program. Brukeren velger bare antall personer.
      </p>
    </div>
  );
}

/** How users sign in (D-057). The card reader and card API come last; until then: Start. */
function Login({ ctx }: { ctx: Ctx }) {
  const mode = ctx.state.touch.login ?? "open";
  const options = [
    ["open", "Start-knapp (uten kort)"],
    ["card", "Adgangskort"],
  ] as const;
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Innlogging</span>
        <span className="muted small">Touch-skjermen</span>
      </div>
      <div className="seg" role="group" aria-label="Innlogging">
        {options.map(([k, label]) => (
          <button
            key={k}
            type="button"
            className={mode === k ? "sel" : ""}
            aria-pressed={mode === k}
            onClick={() => ctx.run(ctx.cmd.setLoginMode(k))}
          >
            {label}
          </button>
        ))}
      </div>
      {mode === "open" ? (
        <p className="muted">
          Brukeren trykker Start og tar opp som «Gjest». Opptaket havner på Pearl, ikke i noens
          Panopto-konto.
        </p>
      ) : (
        <p className="muted">
          Brukeren holder adgangskortet mot leseren. Krever kortleseren (TWN3) og kort-API-et med
          nøkkel i Credential Manager. Er de ikke satt opp, kommer ingen inn: bytt tilbake til
          Start-knapp.
        </p>
      )}
    </div>
  );
}

export function Settings({
  ctx,
  theme,
  onTheme,
}: {
  ctx: Ctx;
  theme: Theme;
  onTheme: (t: Theme) => void;
}) {
  const { state } = ctx;
  return (
    <div className="grid2">
      <div className="panel">
        <div className="ph">
          <span className="lbl">Tema</span>
        </div>
        <div className="seg" role="group" aria-label="Tema">
          {(
            [
              ["system", "System"],
              ["light", "Lyst"],
              ["dark", "Mørkt"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              className={theme === k ? "sel" : ""}
              aria-pressed={theme === k}
              onClick={() => onTheme(k)}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="muted">
          Touch-skjermen i studio har eget valg og starter i mørkt tema, så den ikke lyser opp
          rommet.
        </p>
      </div>
      <div className="panel">
        <div className="ph">
          <span className="lbl">Deltakerfarger</span>
          <span className="muted small">Samme på RØDECaster og mikrofonflagg</span>
        </div>
        <div className="colors">
          {COLORS.map(([id, name, color], i) => (
            <div key={id} style={{ "--pc": participantColor(id) } as CSSProperties}>
              <span className="seat">{i + 1}</span>
              <span>
                <b>{name}</b>
                <br />
                <span className="muted">{color}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
      <Login ctx={ctx} />
      <ShowTypePanel ctx={ctx} />
      <Technicians ctx={ctx} />
      <Alerts ctx={ctx} />
      <SetupFile ctx={ctx} />
      <div className="panel">
        <div className="ph">
          <span className="lbl">Utstyr og multiview</span>
        </div>
        <p className="muted">IP-adresser for utstyret og multiview-sjekken ligger under Oppsett.</p>
        <button type="button" className="btn" onClick={() => ctx.go("oppsett")}>
          Gå til Oppsett
        </button>
      </div>
      <div className="panel">
        <div className="ph">
          <span className="lbl">Om</span>
        </div>
        <div className="kv">
          <span>Versjon</span>
          <span>{state.studio.version}</span>
          <span>Studio</span>
          <span>
            {state.studio.name}
            {state.studio.simulator ? " · simulator" : ""}
          </span>
          <span>Show</span>
          <span>{state.studio.show_id}</span>
          <span>Språk</span>
          <span>Norsk (bokmål)</span>
        </div>
      </div>
    </div>
  );
}
