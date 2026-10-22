// Oppsett → steg 4 → farge (spes. 6.4, P8): et gråkort foran hvert kamera, så justerer CutCut
// hvitbalanse og gain mot referansekameraet i noen runder. Kameraer på lufta hoppes over (I2).
import { errorMessage, useStudio } from "@cutcut/client";
import { useCallback, useEffect, useState } from "react";
import type { Ctx } from "../lib";

interface CamRun {
  kelvin: number;
  gain_db: number;
  error_rb: number | null;
  error_luma: number | null;
  state: string;
  rounds: number;
}

interface ColorStatus {
  cameras: string[];
  saved: { reference: string; at: string; by: string } | null;
  run: {
    state: string;
    reference: string;
    round: number;
    rounds: number;
    message: string | null;
    cameras: Record<string, CamRun>;
  } | null;
}

const pct = (v: number | null) =>
  v === null ? "–" : `${(v * 100).toFixed(1).replace(".", ",")} %`;

export function ColorMatch({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [st, setSt] = useState<ColorStatus | null>(null);
  const [ref, setRef] = useState("C1");
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => {
    transport
      .get<ColorStatus>("/api/setup/color")
      .then(setSt)
      .catch(() => setSt(null));
  }, [transport]);
  useEffect(load, [load]);
  const running = st?.run?.state === "måler";
  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 1000);
    return () => clearInterval(t);
  }, [running, load]);
  if (!st) return null;
  const start = () => {
    setMsg(null);
    transport
      .post<ColorStatus>("/api/setup/color", { reference: ref })
      .then(setSt)
      .catch((x: unknown) => setMsg(errorMessage(x)));
  };
  const run = st.run;
  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Farge · gråkort</span>
        <span className="muted small">
          {run
            ? `${run.state} · runde ${run.round} av ${run.rounds}`
            : st.saved
              ? `sist ${st.saved.at.slice(0, 16).replace("T", " ")} (${st.saved.by})`
              : "ikke matchet ennå"}
        </span>
      </div>
      {st.cameras.length === 0 ? (
        <p className="muted">Kameraene styres ikke fra denne PC-en.</p>
      ) : (
        <>
          <p className="muted">
            Hold et gråkort midt i bildet foran hvert kamera, godt lyst. CutCut justerer hvitbalanse
            og gain mot referansen til forskjellen er under 3 %.
          </p>
          <div className="row">
            <label className="field">
              <span className="small muted">Referansekamera</span>
              <select value={ref} onChange={(e) => setRef(e.target.value)} disabled={running}>
                {st.cameras.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            {ctx.role === "admin" && (
              <button className="btn primary" type="button" disabled={running} onClick={start}>
                {running ? "Måler …" : "Start fargematching"}
              </button>
            )}
          </div>
          {run && (
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>Kamera</th>
                    <th>Farge</th>
                    <th>Lys</th>
                    <th>Hvitbalanse</th>
                    <th>Gain</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(run.cameras).map(([c, r]) => (
                    <tr key={c}>
                      <td className="mono">{c}</td>
                      <td>{pct(r.error_rb)}</td>
                      <td>{pct(r.error_luma)}</td>
                      <td>{r.kelvin} K</td>
                      <td>{r.gain_db.toFixed(1).replace(".", ",")} dB</td>
                      <td className={r.state === "ferdig" ? "" : "muted"}>{r.state}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {run?.message && (
            <p className={run.state === "feil" ? "err-text" : "muted"}>{run.message}</p>
          )}
          {msg && (
            <p className="err-text" role="alert">
              {msg}
            </p>
          )}
        </>
      )}
    </div>
  );
}
