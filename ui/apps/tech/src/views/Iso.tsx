// Opptak → ISO-opptak i ATEM (spes. 7.7, DA-8): hver kamerainngang som egen fil på ATEM-disken,
// i tillegg til Pearl. Startes her eller sammen med Pearl når show-typen tar opp ISO. Stoppes
// bare av en person (I7), med bekreftelse.
import { clock } from "@cutcut/design";
import { useStudio } from "@cutcut/client";
import { useState } from "react";
import type { Ctx } from "../lib";

const STATE: Record<string, [string, string]> = {
  idle: ["Klar", ""],
  recording: ["Tar opp", "err"],
  stopping: ["Stopper", "warn"],
  unknown: ["Ukjent", "warn"],
};

export function IsoPanel({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [confirm, setConfirm] = useState(false);
  const iso = ctx.state.recording.iso;
  if (!iso) return null;
  const [label, cls] = iso.available
    ? (STATE[iso.state] ?? ["–", "todo"])
    : ["Ikke tilkoblet", "err"];
  const recording = iso.state === "recording" || iso.state === "stopping";
  const minutes = iso.time_available_s != null ? Math.round(iso.time_available_s / 60) : null;
  const send = (action: "start" | "stop") =>
    ctx.run(transport.send("POST", "/api/recording/iso", { action }));
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">ISO-opptak i ATEM</span>
        <span className={`hst ${cls}`}>
          <i />
          {label}
        </span>
      </div>
      <div className="kv">
        <span>Disk</span>
        <span className={iso.available && !iso.disk ? "err-text" : ""}>
          {iso.disk ?? "mangler"}
        </span>
        <span>Ledig</span>
        <span className={minutes != null && minutes < 60 ? "warn-text" : ""}>
          {minutes != null ? `${minutes} min` : "–"}
        </span>
        {recording && (
          <>
            <span>Lengde</span>
            <span className="tnum">{clock(iso.duration_s)}</span>
          </>
        )}
        {iso.filename && (
          <>
            <span>Filnavn</span>
            <span className="mono small">{iso.filename}</span>
          </>
        )}
        {iso.started_by && (
          <>
            <span>Startet av</span>
            <span>{iso.started_by}</span>
          </>
        )}
        <span>Med Pearl</span>
        <span>{iso.wanted ? "Ja, show-typen tar opp ISO" : "Nei, startes her ved behov"}</span>
        {iso.error && (
          <>
            <span>Feil</span>
            <span className="err-text">{iso.error}</span>
          </>
        )}
      </div>
      <div className="row">
        {recording ? (
          <button
            type="button"
            className={`btn ${confirm ? "red" : ""}`}
            onClick={() => {
              if (!confirm) return setConfirm(true);
              setConfirm(false);
              send("stop");
            }}
          >
            {confirm ? "Bekreft stopp av ISO" : "Stopp ISO-opptak"}
          </button>
        ) : (
          <button
            type="button"
            className="btn"
            disabled={!iso.available || !iso.disk}
            onClick={() => send("start")}
          >
            Start ISO-opptak
          </button>
        )}
      </div>
      <p className="small muted">
        Pearl er hovedopptaket. ISO-filene er reserve og for etterarbeid; de ligger på disken i ATEM
        under filnavnet over.
      </p>
    </div>
  );
}
