// Oppsett → setup-hjelperen (spec 8.4, HS-5/HS-6): ti steg fra tomt studio til «Klar for
// produksjon». Hvert steg: hva og hvorfor, slik gjør du, «Fiks for meg» der det er trygt,
// sjekk (helsesjekkene, forventet og faktisk side om side) og godkjenning med navn og tid.
// Stegene kommer fra config/defaults/setup/*.yaml, de samme filene som den trykte guiden.
import { errorMessage, useStudio } from "@cutcut/client";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import type { Ctx } from "../lib";

type StepState = "not_checked" | "red" | "yellow" | "green" | "approved";

interface Result {
  id: string;
  status: "green" | "yellow" | "red";
  value: string;
  expected: string | null;
  message: string;
}

export interface StepView {
  step: {
    number: number;
    id: string;
    title: string;
    why: string;
    how: string[];
    checks: string[];
    fix: { action: string; label: string; confirm: string } | null;
    panel: "devices" | "atem" | "mics" | "multiview" | null;
  };
  state: StepState;
  results: Result[];
  approved: { by: string; at: string; note: string | null } | null;
  fix_available: boolean;
  fix_blocked: string | null;
}

const STATE_TEXT: Record<StepState, string> = {
  not_checked: "ikke sjekket",
  red: "feil",
  yellow: "avvik",
  green: "klar til godkjenning",
  approved: "godkjent",
};
const PILL: Record<StepState, string> = {
  not_checked: "off",
  red: "err",
  yellow: "warn",
  green: "",
  approved: "",
};

/** «Slik gjør du» marks the expected value in **bold** and commands in `code`. */
function Rich({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("**") ? (
          <b key={i}>{p.slice(2, -2)}</b>
        ) : p.startsWith("`") ? (
          <span key={i} className="mono">
            {p.slice(1, -1)}
          </span>
        ) : (
          p
        ),
      )}
    </>
  );
}

export function Wizard({
  ctx,
  panels,
}: {
  ctx: Ctx;
  panels: Partial<Record<NonNullable<StepView["step"]["panel"]>, ReactNode>>;
}) {
  const { transport } = useStudio();
  const [steps, setSteps] = useState<StepView[] | null>(null);
  const [current, setCurrent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    transport
      .get<StepView[]>("/api/setup/steps")
      .then((s) => {
        setSteps(s);
        setCurrent(
          (c) => c ?? s.find((x) => x.state !== "approved")?.step.id ?? s[0]?.step.id ?? null,
        );
      })
      .catch(() => setSteps(null));
  }, [transport]);
  useEffect(load, [load]);

  if (!steps) return null;
  const view = steps.find((s) => s.step.id === current) ?? steps[0];
  if (!view) return null;
  const s = view.step;
  const replace = (v: StepView) =>
    setSteps((all) => all?.map((x) => (x.step.id === v.step.id ? v : x)) ?? null);
  const run = (path: string, ok: string) => {
    setBusy(true);
    setMsg(null);
    transport
      .post<StepView>(`/api/setup/steps/${s.id}/${path}`, {})
      .then((v) => {
        replace(v);
        setMsg({ ok: true, text: ok });
      })
      .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }))
      .finally(() => {
        setBusy(false);
        setConfirming(false);
      });
  };
  const choose = (id: string) => {
    setCurrent(id);
    setMsg(null);
    setConfirming(false);
  };
  const done = steps.filter((x) => x.state === "approved").length;

  return (
    <div className="grid2 wizard">
      <div className="panel">
        <div className="ph">
          <span className="lbl">Setup-hjelperen</span>
          <span className="muted small">
            {done} av {steps.length} godkjent
          </span>
        </div>
        <ol className="steps">
          {steps.map((x) => (
            <li key={x.step.id}>
              <button
                type="button"
                className={`pill ${PILL[x.state]}${x.step.id === s.id ? " on" : ""}`}
                aria-current={x.step.id === s.id ? "step" : undefined}
                onClick={() => choose(x.step.id)}
              >
                <span className="d" />
                {x.step.number} {x.step.title}
                <span className="muted small">{STATE_TEXT[x.state]}</span>
              </button>
            </li>
          ))}
        </ol>
        {done === steps.length && <p className="ok-text">Klar for produksjon.</p>}
      </div>

      <div className="panel">
        <div className="ph">
          <span className="lbl">
            Steg {s.number}: {s.title}
          </span>
          <span className={`pill ${PILL[view.state]}`}>
            <span className="d" />
            {STATE_TEXT[view.state]}
          </span>
        </div>
        <p>{s.why}</p>
        <span className="lbl">Slik gjør du</span>
        <ol>
          {s.how.map((h, i) => (
            <li key={i}>
              <Rich text={h} />
            </li>
          ))}
        </ol>

        {s.checks.length > 0 && (
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Sjekk</th>
                  <th>Forventet</th>
                  <th>Faktisk</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {view.results.length === 0 && (
                  <tr>
                    <td colSpan={4} className="muted">
                      Ingen svar ennå. Trykk «Sjekk steget».
                    </td>
                  </tr>
                )}
                {view.results.map((r) => (
                  <tr key={r.id} title={r.message}>
                    <td className="mono">{r.id}</td>
                    <td className="muted">{r.expected ?? "–"}</td>
                    <td
                      className={
                        r.status === "red" ? "err-text" : r.status === "yellow" ? "warn-text" : ""
                      }
                    >
                      {r.value}
                    </td>
                    <td className="small muted">{r.status === "green" ? "" : r.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {view.approved && (
          <p className="small muted">
            Godkjent av {view.approved.by} {view.approved.at.slice(0, 16).replace("T", " ")}
            {view.approved.note ? ` · ${view.approved.note}` : ""}
          </p>
        )}
        {msg && (
          <p className={msg.ok ? "muted" : "err-text"} role={msg.ok ? "status" : "alert"}>
            {msg.text}
          </p>
        )}
        {confirming && s.fix && (
          <p className="warn-text" role="alert">
            {s.fix.confirm}
          </p>
        )}
        <div className="row">
          {s.checks.length > 0 && (
            <button
              className="btn"
              type="button"
              disabled={busy}
              onClick={() => run("check", "Sjekket.")}
            >
              Sjekk steget
            </button>
          )}
          {s.fix && ctx.role === "admin" && !confirming && (
            <button
              className="btn"
              type="button"
              disabled={busy || !view.fix_available}
              title={view.fix_blocked ?? undefined}
              onClick={() => setConfirming(true)}
            >
              Fiks for meg: {s.fix.label}
            </button>
          )}
          {confirming && (
            <>
              <button
                className="btn warn"
                type="button"
                disabled={busy}
                onClick={() => run("fix", "Rettet. Sjekk på nytt.")}
              >
                Ja, gjør det
              </button>
              <button className="btn" type="button" onClick={() => setConfirming(false)}>
                Avbryt
              </button>
            </>
          )}
          {ctx.role === "admin" && (
            <button
              className="btn primary"
              type="button"
              disabled={
                busy ||
                view.state === "red" ||
                (s.checks.length > 0 && view.state === "not_checked")
              }
              onClick={() => run("approve", "Godkjent.")}
            >
              Godkjenn steget
            </button>
          )}
        </div>
        {view.fix_blocked && s.fix && <p className="small muted">{view.fix_blocked}</p>}
      </div>

      {s.panel && panels[s.panel] && <div className="span">{panels[s.panel]}</div>}
    </div>
  );
}
