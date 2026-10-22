// Oppsett (admin): equipment addresses and the multiview check (D-055). The full setup
// wizard with checks per device comes in M3 (docs/plans/setup-health.md).
import { useStudio } from "@cutcut/client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { inputName, type Ctx } from "../lib";
import { AtemSetup } from "./AtemSetup";
import { Wizard } from "./Wizard";

interface DeviceRow {
  key: string;
  kind: "ip" | "url";
  value: string | null;
  file_value: string | null;
  overridden: boolean;
  model: string | null;
}

interface DevicesInfo {
  studio: string;
  atem_model: string | null;
  rows: DeviceRow[];
}

interface Finding {
  check: string;
  level: "error" | "warn" | "info";
  where: string;
  message: string;
  fix: string;
}

interface TileJson {
  id: string;
  label: string;
  source: string;
  camera: string | null;
}

interface MapJson {
  tiles: TileJson[];
  layout: string;
}

interface MultiviewStatus {
  map: MapJson | null;
  recommended: MapJson;
  readback: { windows: string[]; preview_left: boolean; safe_area: boolean } | null;
  findings: Finding[];
  suggestions: Finding[];
  ok: boolean;
}

const CAMERA_ROLE: Record<string, string> = {
  C1: "Programleder",
  C2: "Gjest 1",
  C3: "Gjest 2",
  C4: "Gjest 3",
  C5: "Fugleperspektiv",
  C7: "Halvtotal",
};

function deviceLabel(ctx: Ctx, row: DeviceRow): string {
  if (row.key === "atem.ip") return "ATEM (bildemikser)";
  if (row.key === "pearl.ip") return "Pearl Nexus (opptak)";
  if (row.key === "companion.url") return "Companion";
  const cam = row.key.split(".")[1] ?? "";
  const seat = cam === "C5" ? "BIRD" : `P${cam.slice(1)}`;
  return `${inputName(ctx.state, seat)} · ${CAMERA_ROLE[cam] ?? cam}`;
}

const IPV4 = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

function localError(row: DeviceRow, value: string): string | null {
  if (!value.trim()) return null; // empty = back to the file value
  if (row.kind === "ip" && !IPV4.test(value.trim())) return "Skriv fire tall, f.eks. 10.10.10.21";
  if (row.kind === "url" && !/^https?:\/\/\S+$/.test(value.trim()))
    return "Skriv http://adresse:port";
  return null;
}

function Devices({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [info, setInfo] = useState<DevicesInfo | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(() => {
    transport
      .get<DevicesInfo>("/api/settings/devices")
      .then((i) => {
        setInfo(i);
        setDraft({});
      })
      .catch(() => setInfo(null));
  }, [transport]);
  useEffect(load, [load]);

  if (!info) {
    return (
      <div className="panel">
        <span className="lbl">Utstyr og nettverk</span>
        <p className="muted">Utstyrslisten er ikke tilgjengelig her.</p>
      </div>
    );
  }

  const changed = Object.entries(draft).filter(
    ([k, v]) => v.trim() !== (info.rows.find((r) => r.key === k)?.value ?? ""),
  );
  const invalid = changed.some(([k, v]) => {
    const row = info.rows.find((r) => r.key === k);
    return row ? localError(row, v) !== null : true;
  });

  const save = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const body = Object.fromEntries(changed.map(([k, v]) => [k, v.trim() || null]));
    transport
      .send("PUT", "/api/settings/devices", body)
      .then(() => {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        load();
      })
      .catch((x: unknown) => setError((x as { message?: string }).message ?? "Noe gikk galt."));
  };
  const reset = (key: string) => {
    ctx.run(transport.send("PUT", "/api/settings/devices", { [key]: null }).then(load));
  };

  return (
    <form className="panel" onSubmit={save}>
      <div className="ph">
        <span className="lbl">Utstyr og nettverk</span>
        <a className="btn" href="/api/settings/devices.yaml" download>
          Last ned devices.yaml
        </a>
      </div>
      <p className="muted">
        Adressene varierer fra studio til studio. Endringer lagres her, overlever omstart og gjelder
        fra neste tilkobling. Blå verdi = endret fra <span className="mono">devices.yaml</span>.
        Last ned filen og legg den i studio-repoet når oppsettet er ferdig.
      </p>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Enhet</th>
              <th>Modell</th>
              <th>Adresse</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {info.rows.map((row) => {
              const value = draft[row.key] ?? row.value ?? "";
              const err = localError(row, value);
              return (
                <tr key={row.key}>
                  <td>{deviceLabel(ctx, row)}</td>
                  <td className="muted">
                    {row.key === "atem.ip" ? (info.atem_model ?? "–") : (row.model ?? "–")}
                  </td>
                  <td>
                    <input
                      className={`addr ${row.overridden ? "changed" : ""} ${err ? "bad" : ""}`}
                      aria-label={`Adresse for ${deviceLabel(ctx, row)}`}
                      value={value}
                      placeholder={row.file_value ?? ""}
                      inputMode={row.kind === "ip" ? "decimal" : "url"}
                      onChange={(e) => setDraft({ ...draft, [row.key]: e.target.value })}
                    />
                    {err && <div className="small err-text">{err}</div>}
                    {row.overridden && (
                      <div className="small muted">I filen: {row.file_value ?? "–"}</div>
                    )}
                  </td>
                  <td>
                    {row.overridden && (
                      <button type="button" className="btn" onClick={() => reset(row.key)}>
                        Nullstill
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {error && (
        <p className="err-text" role="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button className="btn primary" type="submit" disabled={changed.length === 0 || invalid}>
          Lagre endringer
        </button>
        {changed.length > 0 && (
          <button type="button" className="btn" onClick={() => setDraft({})}>
            Angre
          </button>
        )}
        {saved && <span className="hst">Lagret</span>}
      </div>
    </form>
  );
}

const LEVEL = {
  error: ["err", "Feil"],
  warn: ["warn", "Advarsel"],
  info: ["info", "Forslag"],
} as const;

function sourceLabel(source: string): string {
  const m = /^input(\d)$/.exec(source);
  if (m) return `Camera ${m[1]}`;
  return (
    {
      preview: "Preview",
      program: "Program",
      mediaplayer1: "Media Player 1",
      mediaplayer2: "Media Player 2",
      supersource: "SuperSource",
      recording_status: "Opptaksstatus",
      streaming_status: "Strømmestatus",
      black: "Svart",
    }[source] ?? source
  );
}

function roleOf(camera: string | null): string {
  if (!camera) return "";
  if (camera === "LAPTOP") return "Laptop";
  if (camera === "SUPERSOURCE") return "Layouter";
  return CAMERA_ROLE[camera] ?? camera;
}

/** A 2 + 8 multiview drawn small, with the windows that differ marked. */
function Grid({
  title,
  windows,
  cameras,
  compare,
  previewLeft = true,
}: {
  title: string;
  windows: string[];
  cameras?: (string | null)[];
  compare?: string[];
  previewLeft?: boolean;
}) {
  return (
    <div className="mvgrid-wrap">
      <div className="lbl">{title}</div>
      <div className="mvgrid" role="img" aria-label={title}>
        <div className="big">{previewLeft ? "Preview" : "Program"}</div>
        <div className="big">{previewLeft ? "Program" : "Preview"}</div>
        {windows.map((w, i) => {
          const diff = compare !== undefined && compare[i] !== w;
          return (
            <div key={i} className={`small-w ${diff ? "diff" : ""}`}>
              <b>{sourceLabel(w)}</b>
              {cameras?.[i] && <span>{roleOf(cameras[i] ?? null)}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Multiview() {
  const { transport } = useStudio();
  const [st, setSt] = useState<MultiviewStatus | null>(null);
  const load = useCallback(() => {
    transport
      .get<MultiviewStatus>("/api/setup/multiview")
      .then(setSt)
      .catch(() => setSt(null));
  }, [transport]);
  useEffect(load, [load]);
  const [checking, setChecking] = useState(false);
  const checkNow = () => {
    setChecking(true);
    transport
      .send("POST", "/api/setup/multiview/check")
      .then(load)
      .catch(() => undefined)
      .finally(() => setChecking(false));
  };

  if (!st) {
    return (
      <div className="panel">
        <span className="lbl">Multiview</span>
        <p className="muted">Multiview-sjekken er ikke tilgjengelig her.</p>
      </div>
    );
  }
  const small = (m: MapJson | null) =>
    (m?.tiles ?? []).filter((t) => t.id.startsWith("W")).sort((a, b) => (a.id < b.id ? -1 : 1));
  const mapTiles = small(st.map);
  const recTiles = small(st.recommended);
  const issues = [...st.findings, ...st.suggestions];
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Multiview · ATEM mot rutekartet</span>
        <span className="row">
          <span className={`hst ${st.ok ? "" : "err"}`}>
            <i />
            {st.ok ? "Stemmer" : "Stemmer ikke"}
          </span>
          <button type="button" className="btn" onClick={checkNow} disabled={checking}>
            {checking ? "Sjekker …" : "Sjekk nå"}
          </button>
        </span>
      </div>
      <p className="muted">
        CutCut leser kameraene fra multiviewen etter posisjon. Står en rute feil, ville CutCut sett
        på feil kamera. Det sjekkes ved oppstart og varsles under Helse; trykk «Sjekk nå» hvis noen
        har endret ATEM-oppsettet.
      </p>
      <div className="mvgrids">
        {st.map && (
          <Grid
            title="Rutekartet (det CutCut leser)"
            windows={mapTiles.map((t) => t.source)}
            cameras={mapTiles.map((t) => t.camera)}
          />
        )}
        {st.readback && st.map && (
          <Grid
            title="ATEM viser nå"
            windows={st.readback.windows}
            compare={mapTiles.map((t) => t.source)}
            previewLeft={st.readback.preview_left}
          />
        )}
        <Grid
          title="Anbefalt"
          windows={recTiles.map((t) => t.source)}
          cameras={recTiles.map((t) => t.camera)}
          compare={st.map ? mapTiles.map((t) => t.source) : undefined}
        />
      </div>
      {issues.length === 0 ? (
        <p className="hst">
          <i />
          Multiviewen er satt opp som anbefalt.
        </p>
      ) : (
        <ul className="findings">
          {issues.map((f, i) => (
            <li key={i}>
              <span className={`hst ${LEVEL[f.level][0]}`}>
                <i />
                {LEVEL[f.level][1]}
              </span>
              <span>
                <b>{f.message}</b>
                <br />
                <span className="muted">{f.fix}</span>
              </span>
              <span className="tag">{f.check}</span>
            </li>
          ))}
        </ul>
      )}
      <details>
        <summary>Anbefalte multiview-innstillinger i ATEM Software Control</summary>
        <ul>
          <li>Layout med 2 store og 8 små ruter, preview til venstre og program til høyre.</li>
          <li>Rad 1: de fire nærbildekameraene i seterekkefølge (programleder, gjest 1–3).</li>
          <li>
            Rad 2: fugleperspektiv og laptop (CutCut leser begge), SuperSource (layouter) og Media
            Player 1 med «Kun lyd»-grafikken.
          </li>
          <li>Tally-rammer på, safe area av, lydmålere av, navneskilt på.</li>
          <li>Multiview ut på HDMI til opptakskortet i regi-PC-en, 1080p50.</li>
        </ul>
      </details>
    </div>
  );
}

interface MicResultJson {
  level_db: number;
  right_channel: boolean;
  loudest_other: string | null;
  leak_db: Record<string, number>;
  worst_leak_db: number | null;
}

interface MicStatus {
  mics: string[];
  running: { kind: "talk" | "noise"; mic: string | null; left_ms: number } | null;
  results: Record<string, MicResultJson>;
  noise_floor_db: Record<string, number>;
  message: string | null;
  done: boolean;
  simulator: boolean;
  saved: {
    leak_db: Record<string, Record<string, number>>;
    noise_floor_db: Record<string, number>;
  };
}

const MIC_WHO: Record<string, string> = {
  M1: "Programleder",
  M2: "Gjest 1",
  M3: "Gjest 2",
  M4: "Gjest 3",
  M5: "Laptop",
};

const db = (v: number | null | undefined) =>
  v === null || v === undefined ? "–" : `${v.toFixed(1).replace(".", ",")} dB`;

/** Setup step 5 (AU-7): right channel, leakage and noise floor, saved as fasit. */
function Mics({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [st, setSt] = useState<MicStatus | null>(null);
  const load = useCallback(() => {
    transport
      .get<MicStatus>("/api/setup/mics")
      .then(setSt)
      .catch(() => setSt(null));
  }, [transport]);
  useEffect(load, [load]);
  const running = st?.running;
  useEffect(() => {
    if (!running) return;
    const id = setInterval(load, 400);
    return () => clearInterval(id);
  }, [running, load]);
  if (!st) return null;
  const measure = (what: string) =>
    ctx.run(transport.send("POST", `/api/setup/mics/${what}`).then(load));
  const busy = running !== null;
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Mikrofoner · steg 5</span>
        <span className="muted small">Én og én snakker. Mikseren endres ikke</span>
      </div>
      <p className="muted">
        Be hver person si noen setninger i sin mikrofon mens CutCut lytter i 6 sekunder. CutCut
        sjekker at stemmen er sterkest på riktig kanal, og måler hvor mye den lekker til de andre
        mikrofonene. Mål også støyen i et stille rom. Lagret som fasit brukes målingene straks av
        lydanalysen.
      </p>
      {st.message && (
        <p role="status">
          <b>{st.message}</b>
          {running && ` (${Math.ceil(running.left_ms / 1000)} s)`}
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th>Mic</th>
            <th>Hvem</th>
            <th>Nivå</th>
            <th>Kanal</th>
            <th>Mest lekkasje til andre</th>
            <th>Støy</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {st.mics.map((m) => {
            const r = st.results[m];
            return (
              <tr key={m}>
                <td className="mono">{m}</td>
                <td>{MIC_WHO[m] ?? m}</td>
                <td className="tnum">{r ? db(r.level_db) : "–"}</td>
                <td>
                  {r ? (
                    <span className={`hst ${r.right_channel ? "" : "err"}`}>
                      <i />
                      {r.right_channel ? "Riktig" : `Sterkest på ${r.loudest_other}`}
                    </span>
                  ) : (
                    <span className="muted">ikke målt</span>
                  )}
                </td>
                <td className="tnum">{r ? db(r.worst_leak_db) : "–"}</td>
                <td className="tnum">{db(st.noise_floor_db[m])}</td>
                <td>
                  <button type="button" className="btn" disabled={busy} onClick={() => measure(m)}>
                    {r ? "Mål på nytt" : "Mål"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="row" style={{ display: "flex", gap: 10, marginTop: 12 }}>
        <button type="button" className="btn" disabled={busy} onClick={() => measure("noise")}>
          Mål støy (3 s stille)
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy || Object.keys(st.results).length === 0}
          onClick={() => measure("save")}
        >
          Lagre som fasit
        </button>
        {st.simulator && (
          <span className="muted small">Simulator: lagres bare i minnet, ikke i baseline.yaml</span>
        )}
      </div>
    </div>
  );
}

export function Setup({ ctx }: { ctx: Ctx }) {
  return (
    <Wizard
      ctx={ctx}
      panels={{
        devices: <Devices ctx={ctx} />,
        multiview: <Multiview />,
        atem: <AtemSetup ctx={ctx} />,
        mics: <Mics ctx={ctx} />,
      }}
    />
  );
}
