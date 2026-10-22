// Oppsett → ATEM (HS-7): what CutCut reads from the ATEM, against the approved fasit, and
// «Lagre ATEM som fasit». H-ATEM-2 says when someone changes format, input names or AUX later.
import { errorMessage, useStudio } from "@cutcut/client";
import { useCallback, useEffect, useState } from "react";
import type { Ctx } from "../lib";

interface AtemInfo {
  connected: boolean;
  model: string | null;
  video_mode: string | null;
  inputs: Record<string, string>;
  aux: string[];
  iso: { disk: string | null; time_available_s: number | null; state: string | null } | null;
  fasit: {
    video_mode: string;
    input_names: Record<string, string>;
    aux: string[];
    approved_by: string | null;
    approved_at: string | null;
  } | null;
}

export function AtemSetup({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [info, setInfo] = useState<AtemInfo | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    transport
      .get<AtemInfo>("/api/setup/atem")
      .then(setInfo)
      .catch(() => setInfo(null));
  }, [transport]);
  useEffect(load, [load]);
  if (!info) return null;

  const save = () => {
    setMsg(null);
    transport
      .post<AtemInfo>("/api/setup/atem/fasit", {})
      .then((i) => {
        setInfo(i);
        setMsg({ ok: true, text: "Lagret som fasit." });
      })
      .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }));
  };

  const f = info.fasit;
  const numbers = Array.from(
    new Set([...Object.keys(info.inputs), ...Object.keys(f?.input_names ?? {})]),
  ).sort((a, b) => Number(a) - Number(b));
  const differs = (now: string | undefined, want: string | undefined) =>
    f !== null && now !== want ? "err-text" : "";

  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">ATEM</span>
        <span className="muted small">
          {info.connected ? `${info.model ?? ""} · ${info.video_mode ?? ""}` : "ikke tilkoblet"}
        </span>
      </div>
      <p className="muted">
        {f
          ? `Fasit lagret av ${f.approved_by ?? "–"}${f.approved_at ? ` ${f.approved_at.slice(0, 10)}` : ""}. Rødt = endret siden da (H-ATEM-2).`
          : "Ingen fasit ennå. Når ATEM er satt opp riktig, lagrer du den som fasit, så varsler CutCut hvis noen endrer den."}
      </p>
      {info.connected && (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Inngang</th>
                <th>Navn i ATEM</th>
                <th>Fasit</th>
              </tr>
            </thead>
            <tbody>
              {numbers.map((n) => (
                <tr key={n}>
                  <td className="mono">{n}</td>
                  <td className={differs(info.inputs[n], f?.input_names[n])}>
                    {info.inputs[n] ?? "–"}
                  </td>
                  <td className="muted">{f?.input_names[n] ?? "–"}</td>
                </tr>
              ))}
              {info.aux.map((a, i) => (
                <tr key={`aux${i}`}>
                  <td className="mono">AUX {i + 1}</td>
                  <td className={differs(a, f?.aux[i])}>{a}</td>
                  <td className="muted">{f?.aux[i] ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {info.iso && (
        <p className="small muted">
          ISO-disk: {info.iso.disk ?? "mangler"}
          {info.iso.time_available_s !== null
            ? ` · ${Math.round(info.iso.time_available_s / 60)} min ledig`
            : ""}
        </p>
      )}
      {msg && (
        <p className={msg.ok ? "muted" : "err-text"} role={msg.ok ? "status" : "alert"}>
          {msg.text}
        </p>
      )}
      {ctx.role === "admin" && (
        <div className="row">
          <button className="btn" type="button" disabled={!info.connected} onClick={save}>
            Lagre ATEM som fasit
          </button>
        </div>
      )}
    </div>
  );
}
