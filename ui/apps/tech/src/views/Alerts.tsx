// Innstillinger → Varsling (HS-3, Q29): who gets an email when something is red for over a
// minute or a recording fails, the mail relay, and «Send testvarsel».
import { useStudio } from "@cutcut/client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { hms, type Ctx } from "../lib";

interface AlertsInfo {
  on: boolean;
  email: string[];
  smtp_host: string;
  red_after_s: number;
  enabled: boolean;
  sent: number;
  last_sent: string | null;
  last_error: string | null;
}

export function Alerts({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [info, setInfo] = useState<AlertsInfo | null>(null);
  const [email, setEmail] = useState("");
  const [host, setHost] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const admin = ctx.role === "admin";

  const load = useCallback(() => {
    transport
      .get<AlertsInfo>("/api/settings/alerts")
      .then((i) => {
        setInfo(i);
        setEmail(i.email.join(", "));
        setHost(i.smtp_host);
      })
      .catch(() => setInfo(null));
  }, [transport]);
  useEffect(load, [load]);

  if (!info) return null;
  const changed = email.trim() !== info.email.join(", ") || host.trim() !== info.smtp_host;

  const toggle = (on: boolean) => {
    setMsg(null);
    transport
      .send("PUT", "/api/settings/devices", { "alerts.enabled": on ? "true" : null })
      .then(load)
      .catch(fail);
  };

  const fail = (x: unknown) =>
    setMsg({ ok: false, text: (x as { message?: string }).message ?? "Noe gikk galt." });

  const save = (e: FormEvent) => {
    e.preventDefault();
    setMsg(null);
    transport
      .send("PUT", "/api/settings/devices", {
        "alerts.email": email.trim() || null,
        "alerts.smtp.host": host.trim() || null,
      })
      .then(() => {
        setMsg({ ok: true, text: "Lagret." });
        load();
      })
      .catch(fail);
  };

  const test = () => {
    setMsg(null);
    setBusy(true);
    transport
      .send("POST", "/api/settings/alerts/test", {})
      .then(() => setMsg({ ok: true, text: `Testvarsel sendt til ${info.email.join(", ")}.` }))
      .catch(fail)
      .finally(() => {
        setBusy(false);
        load();
      });
  };

  return (
    <form className="panel" onSubmit={save}>
      <div className="ph">
        <span className="lbl">Varsling</span>
        <span className={`small ${info.on && !info.enabled ? "err-text" : "muted"}`}>
          {!info.on ? "av" : info.enabled ? "på" : "på, men ikke satt opp"}
        </span>
      </div>
      <div className="seg" role="group" aria-label="Varsel på e-post">
        {(
          [
            [false, "Av"],
            [true, "På"],
          ] as const
        ).map(([on, label]) => (
          <button
            key={label}
            type="button"
            className={info.on === on ? "sel" : ""}
            aria-pressed={info.on === on}
            disabled={!admin}
            onClick={() => toggle(on)}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="muted">
        E-post når noe har vært rødt i over {Math.round(info.red_after_s)} s, og med en gang når et
        opptak ikke starter eller stopper av seg selv. Høyst ti i timen. «Send testvarsel» virker
        også når varsling er av.
      </p>
      <label className="field">
        <span className="small muted">Mottakere</span>
        <input
          className="addr"
          aria-label="E-postadresser for varsler"
          value={email}
          placeholder="navn@ntnu.no"
          inputMode="email"
          disabled={!admin}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      <label className="field">
        <span className="small muted">SMTP-server</span>
        <input
          className="addr"
          aria-label="SMTP-server"
          value={host}
          placeholder="fra NTNU-IT"
          disabled={!admin}
          onChange={(e) => setHost(e.target.value)}
        />
      </label>
      <div className="kv">
        <span>Sendt</span>
        <span>
          {info.sent}
          {info.last_sent ? ` · sist ${hms(info.last_sent)}` : ""}
        </span>
        {info.last_error && (
          <>
            <span>Siste feil</span>
            <span className="err-text">{info.last_error}</span>
          </>
        )}
      </div>
      {msg && (
        <p className={msg.ok ? "muted" : "err-text"} role={msg.ok ? "status" : "alert"}>
          {msg.text}
        </p>
      )}
      {admin && (
        <div className="row">
          <button className="btn primary" type="submit" disabled={!changed}>
            Lagre
          </button>
          <button
            className="btn"
            type="button"
            disabled={busy || changed || info.email.length === 0}
            onClick={test}
          >
            {busy ? "Sender …" : "Send testvarsel"}
          </button>
        </div>
      )}
    </form>
  );
}
