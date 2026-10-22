// Innstillinger → Teknikere and Oppsett: what is entered in the app stays on the studio PC,
// never in the repository. «Lagre oppsett» downloads it as one file; «Hent oppsett» shows
// what a file would change, and uses it after a confirmation.
import { errorMessage, useStudio } from "@cutcut/client";
import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import type { Ctx } from "../lib";

interface StaffInfo {
  operators: string[];
  admins: string[];
  first_setup: boolean;
}

const names = (text: string) =>
  text
    .split(/[\s,;]+/)
    .map((x) => x.trim())
    .filter(Boolean);

export function Technicians({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [info, setInfo] = useState<StaffInfo | null>(null);
  const [ops, setOps] = useState("");
  const [admins, setAdmins] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    transport
      .get<StaffInfo>("/api/settings/staff")
      .then((i) => {
        setInfo(i);
        setOps(i.operators.join(", "));
        setAdmins(i.admins.join(", "));
      })
      .catch(() => setInfo(null));
  }, [transport]);
  useEffect(load, [load]);

  if (!info || ctx.role !== "admin") return null;
  const changed = ops !== info.operators.join(", ") || admins !== info.admins.join(", ");

  const save = (e: FormEvent) => {
    e.preventDefault();
    setMsg(null);
    transport
      .send("PUT", "/api/settings/staff", { operators: names(ops), admins: names(admins) })
      .then(() => {
        setMsg({ ok: true, text: "Lagret. Endringen gjelder fra neste innlogging." });
        load();
      })
      .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }));
  };

  return (
    <form className="panel" onSubmit={save}>
      <div className="ph">
        <span className="lbl">Teknikere</span>
        <span className="muted small">Lagres på denne PC-en</span>
      </div>
      {info.first_setup ? (
        <p className="err-text">
          Ingen står på listen ennå, så admin-PIN slipper hvem som helst inn. Legg inn teknikerne
          nå, og deg selv som admin.
        </p>
      ) : (
        <p className="muted">
          Brukernavn som kan logge inn i teknikervinduet. PIN ligger i Credential Manager.
        </p>
      )}
      <label className="field">
        <span className="small muted">Teknikere (operatør)</span>
        <input
          className="addr"
          aria-label="Teknikere"
          value={ops}
          placeholder="brukernavn, brukernavn"
          onChange={(e) => setOps(e.target.value)}
        />
      </label>
      <label className="field">
        <span className="small muted">Admin (kan endre oppsett)</span>
        <input
          className="addr"
          aria-label="Admin"
          value={admins}
          placeholder="brukernavn"
          onChange={(e) => setAdmins(e.target.value)}
        />
      </label>
      {msg && (
        <p className={msg.ok ? "muted" : "err-text"} role={msg.ok ? "status" : "alert"}>
          {msg.text}
        </p>
      )}
      <div className="row">
        <button className="btn primary" type="submit" disabled={!changed}>
          Lagre
        </button>
      </div>
    </form>
  );
}

export function SetupFile({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [text, setText] = useState<string | null>(null);
  const [file, setFile] = useState("");
  const [changes, setChanges] = useState<string[] | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  if (ctx.role !== "admin") return null;

  const pick = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    setMsg(null);
    setChanges(null);
    if (!f) return;
    setFile(f.name);
    f.text().then((t) => {
      setText(t);
      transport
        .post<{ changes: string[] }>("/api/settings/setup/check", { text: t })
        .then((r) => setChanges(r.changes))
        .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }));
    });
  };

  const use = () => {
    if (text === null) return;
    transport
      .post<{ changes: string[] }>("/api/settings/setup/import", { text })
      .then(() => {
        setMsg({ ok: true, text: `Oppsettet fra ${file} er tatt i bruk.` });
        setChanges(null);
        setText(null);
      })
      .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }));
  };

  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Oppsett</span>
        <a className="btn" href="/api/settings/setup.yaml" download>
          Lagre oppsett
        </a>
      </div>
      <p className="muted">
        Utstyrsadresser, teknikere, varsling, innlogging, regler og mikrofon-fasit, i én fil uten
        PIN eller passord. CutCut tar også en kopi selv ved hver endring, i{" "}
        <span className="mono">data\oppsett\</span> på denne PC-en.
      </p>
      <label className="field">
        <span className="small muted">Hent oppsett fra fil</span>
        <input type="file" accept=".yaml,.yml" aria-label="Hent oppsett" onChange={pick} />
      </label>
      {changes && (
        <>
          <p className="small">Dette endres:</p>
          <ul className="small">
            {changes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <div className="row">
            <button className="btn primary" type="button" onClick={use}>
              Bruk oppsettet
            </button>
            <button
              className="btn"
              type="button"
              onClick={() => {
                setChanges(null);
                setText(null);
              }}
            >
              Avbryt
            </button>
          </div>
        </>
      )}
      {msg && (
        <p className={msg.ok ? "muted" : "err-text"} role={msg.ok ? "status" : "alert"}>
          {msg.text}
        </p>
      )}
    </div>
  );
}
