// Helse → Feilsøkingsmodus: record everything that reaches the engine for a while (admin), so a
// problem in the studio can be looked at afterwards, and the acceptance numbers measured.
import { errorMessage, useStudio } from "@cutcut/client";
import { useCallback, useEffect, useState } from "react";
import { type Ctx } from "../lib";

interface DebugInfo {
  on: boolean;
  until: string | null;
  folder: string;
  files: number;
  mb: number;
  dropped: number;
}

const CHOICES = [
  [0, "Av"],
  [1, "1 time"],
  [8, "8 timer"],
  [24, "24 timer"],
] as const;

export function DebugPanel({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [info, setInfo] = useState<DebugInfo | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const admin = ctx.role === "admin";

  const load = useCallback(() => {
    transport
      .get<DebugInfo>("/api/debug")
      .then(setInfo)
      .catch(() => setInfo(null));
  }, [transport]);
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  if (!info) return null;
  const set = (hours: number) => {
    setMsg(null);
    transport
      .send("PUT", "/api/debug", { hours })
      .then(load)
      .catch((x: unknown) => setMsg(errorMessage(x)));
  };
  const until = info.until ? new Date(info.until) : null;
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Feilsøkingsmodus</span>
        <span className={`hst ${info.on ? "warn" : ""}`}>
          <i />
          {info.on && until
            ? `på til ${until.toLocaleString("nb-NO", { weekday: "short", hour: "2-digit", minute: "2-digit" })}`
            : "av"}
        </span>
      </div>
      <p className="muted small">
        Tar opp alt som kommer inn til motoren (lyd- og videomålinger, ATEM, kameraer), hver
        beslutning og hvor lang tid hvert kall til Companion tok, og logger mer. Slår seg av selv.
        Brukes i studioperioden og når noe skal feilsøkes; «Feilsøkingspakke» under Logg tar med
        siste time.
      </p>
      <div className="seg" role="group" aria-label="Feilsøkingsmodus">
        {CHOICES.map(([hours, label]) => (
          <button
            key={label}
            type="button"
            className={hours === 0 && !info.on ? "sel" : ""}
            aria-pressed={hours === 0 && !info.on}
            disabled={!admin}
            onClick={() => set(hours)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="kv" style={{ marginTop: 10 }}>
        <span>Opptak</span>
        <span>
          {info.files} filer · {info.mb} MB
        </span>
        <span>Mappe</span>
        <span className="mono small">{info.folder}</span>
        {info.dropped > 0 && (
          <>
            <span>Tapt</span>
            <span className="err-text">{info.dropped} meldinger (disken henger ikke med)</span>
          </>
        )}
      </div>
      {!admin && <p className="muted small">Bare admin kan slå den av og på.</p>}
      {msg && <p className="err-text small">{msg}</p>}
    </div>
  );
}
