// Helse → «Sjekk dagens oppsett» (P14): health, multiview, a name round (mics and seats) and,
// with a grey card, colour, in about two minutes. Nothing new: the checks that exist, in one go.
import { errorMessage, useStudio } from "@cutcut/client";
import { useCallback, useEffect, useState } from "react";
import { type Ctx } from "../lib";

interface QuickStep {
  id: string;
  title: string;
  result: "ok" | "advarsel" | "feil" | "hoppet over" | null;
  summary: string;
}

interface QuickInfo {
  phase: "navnerunde" | "ferdig" | "ikke kjørt";
  result?: "ok" | "advarsel" | "feil" | null;
  steps: QuickStep[];
  waiting_for?: string[];
  at?: string;
}

const CLS: Record<string, string> = {
  ok: "",
  advarsel: "warn",
  feil: "err",
  "hoppet over": "info",
};

export function QuickCheckPanel({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [info, setInfo] = useState<QuickInfo | null>(null);
  const [color, setColor] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    transport
      .get<QuickInfo>("/api/quick-check")
      .then(setInfo)
      .catch(() => setInfo(null));
  }, [transport]);
  useEffect(() => {
    load();
    const t = setInterval(load, info?.phase === "navnerunde" ? 1000 : 10000);
    return () => clearInterval(t);
  }, [load, info?.phase]);

  if (!info) return null;
  const start = () => {
    setMsg(null);
    transport
      .send("POST", "/api/quick-check", { color })
      .then(load)
      .catch((x: unknown) => setMsg(errorMessage(x)));
  };
  const running = info.phase === "navnerunde";
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Sjekk dagens oppsett</span>
        {info.result && (
          <span className={`hst ${CLS[info.result] ?? ""}`}>
            <i />
            {info.result === "ok" ? "Alt i orden" : info.result === "feil" ? "Feil" : "Se over"}
          </span>
        )}
      </div>
      <p className="muted small">
        Helse, multiview og en navnerunde: alle setter seg på plass og sier navnet sitt, én om
        gangen. CutCut hører etter mikrofonene og ser at munnen beveger seg i riktig kamera. Tar
        rundt to minutter. Med gråkort foran alle kameraene måles fargen også.
      </p>
      {running ? (
        <p role="status">
          <b>Navnerunde:</b> vent på {info.waiting_for?.join(", ") || "…"}
        </p>
      ) : (
        <div className="row" style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button
            type="button"
            className="btn primary"
            disabled={ctx.role === "touch"}
            onClick={start}
          >
            Start sjekken
          </button>
          <label className="small">
            <input type="checkbox" checked={color} onChange={(e) => setColor(e.target.checked)} />{" "}
            Gråkort foran kameraene (farge)
          </label>
        </div>
      )}
      {info.steps.length > 0 && (
        <ul className="findings" style={{ marginTop: 10 }}>
          {info.steps.map((s) => (
            <li key={s.id}>
              <span className={`hst ${s.result ? (CLS[s.result] ?? "") : "info"}`}>
                <i />
                {s.result ?? "venter"}
              </span>
              <span>
                <b>{s.title}</b>
                <br />
                <span className="muted">{s.summary}</span>
              </span>
              <span className="tag">{s.id}</span>
            </li>
          ))}
        </ul>
      )}
      {info.at && !running && (
        <p className="muted small">
          Sist kjørt{" "}
          {new Date(info.at).toLocaleString("nb-NO", { dateStyle: "short", timeStyle: "short" })}
        </p>
      )}
      {msg && <p className="err-text small">{msg}</p>}
    </div>
  );
}
