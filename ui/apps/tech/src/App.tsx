// Technician window (spec 8.4, D-037, D-045). Reads the live state from the engine and sends
// commands; every change is audited on the server with who did it.
import { commands, useSnapshot, useStudio, type Role } from "@cutcut/client";
import {
  Icon,
  Logo,
  applyTheme,
  clock,
  isDark,
  loadTheme,
  saveTheme,
  type Theme,
} from "@cutcut/design";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { NAV, allowed, errorText, type Ctx, type View } from "./lib";
import { Overview } from "./views/Overview";
import { Cameras, Health, LogView, Recording, Regi, Settings } from "./views/Pages";
import { Setup } from "./views/Setup";

function viewFromHash(): View {
  const h = location.hash.slice(1);
  return (NAV.find((n) => n.view === h)?.view ?? "oversikt") as View;
}

export function App() {
  const { transport } = useStudio();
  const cmd = useMemo(() => commands(transport), [transport]);
  const [role, setRole] = useState<Role | "unknown">("unknown");

  const checkMe = useCallback(() => {
    if (transport.role) {
      setRole(transport.role);
      return;
    }
    cmd
      .me()
      .then((me) => setRole(me.role))
      .catch((e: unknown) => {
        // 401: not signed in from another machine. Anything else: try again shortly.
        const status = (e as { status?: unknown } | null)?.status;
        if (status === 401 || status === 403) setRole("touch");
        else setTimeout(checkMe, 3000);
      });
  }, [cmd, transport]);
  useEffect(checkMe, [checkMe]);

  if (role === "unknown") return null;
  if (role === "touch") return <Login onDone={checkMe} />;
  return <Shell role={role} />;
}

function Login({ onDone }: { onDone: () => void }) {
  const { transport } = useStudio();
  const [user, setUser] = useState("");
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    commands(transport)
      .login(user.trim(), pin)
      .then(onDone)
      .catch((x: unknown) => setErr(errorText(x)));
  };
  return (
    <div className="login">
      <form className="panel" onSubmit={submit}>
        <Logo />
        <h1 style={{ margin: 0, fontFamily: "var(--f-display)" }}>Teknikertilgang</h1>
        <label>
          Brukernavn
          <input value={user} onChange={(e) => setUser(e.target.value)} autoComplete="username" />
        </label>
        <label>
          PIN
          <input
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
          />
        </label>
        {err && <p className="err">{err}</p>}
        <button className="btn primary" type="submit" disabled={!user || pin.length < 4}>
          Logg inn
        </button>
      </form>
    </div>
  );
}

function Shell({ role }: { role: Role }) {
  const { transport } = useStudio();
  const state = useSnapshot((s) => s.state);
  const connection = useSnapshot((s) => s.connection);
  const [view, setView] = useState<View>(() => {
    const v = viewFromHash();
    return allowed(v, role) ? v : "oversikt";
  });
  const go = useCallback(
    (v: View) => {
      if (!allowed(v, role)) return;
      setView(v);
      try {
        history.replaceState(null, "", `#${v}`);
      } catch {
        /* sandboxed preview */
      }
    },
    [role],
  );
  useEffect(() => {
    const on = () => go(viewFromHash());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, [go]);

  const [theme, setTheme] = useState<Theme>(() => {
    const t = loadTheme("tech", "system");
    applyTheme(t);
    return t;
  });
  const chooseTheme = (t: Theme) => {
    applyTheme(t);
    saveTheme("tech", t);
    setTheme(t);
  };

  const [toastText, setToast] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toast = useCallback((text: string) => {
    setToast(text);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 4000);
  }, []);

  const cmd = useMemo(() => commands(transport), [transport]);
  const run = useCallback(
    (p: Promise<unknown>) => {
      p.catch((e: unknown) => toast(errorText(e)));
    },
    [toast],
  );

  if (!state) {
    return (
      <div className="login">
        <p className="muted">Kobler til motoren …</p>
      </div>
    );
  }
  const ctx: Ctx = { state, cmd, role, run, toast, go };
  const errors = state.alerts.filter((a) => a.level === "error").length;
  const warns = state.alerts.filter((a) => a.level === "warn").length;
  const title = NAV.find((n) => n.view === view)?.title ?? "";

  return (
    <div className={`app ${connection === "connected" ? "" : "offline"}`}>
      <nav className="rail" aria-label="Meny">
        <Logo />
        {NAV.filter((n) => allowed(n.view, role)).map((n) => (
          <button
            key={n.view}
            type="button"
            className={`nav ${view === n.view ? "on" : ""}`}
            aria-label={n.title}
            aria-current={view === n.view ? "page" : undefined}
            onClick={() => go(n.view)}
          >
            <Icon name={n.icon} />
            <span>{n.label}</span>
            {n.view === "helse" && (errors || warns) > 0 && (
              <span className={`badge ${errors ? "" : "warn"}`}>{errors || warns}</span>
            )}
          </button>
        ))}
        <span className="grow" />
        <button
          type="button"
          className="nav"
          aria-label="Bytt tema"
          onClick={() => chooseTheme(isDark() ? "light" : "dark")}
        >
          <Icon name={isDark() ? "sun" : "moon"} />
          <span>Tema</span>
        </button>
      </nav>
      <div className="col">
        <TopBar ctx={ctx} title={title} errors={errors} warns={warns} />
        {connection !== "connected" && (
          <div className="banner err" role="status">
            Mistet forbindelsen med motoren. Viser siste kjente tilstand og kobler til igjen …
          </div>
        )}
        <HelpBanner ctx={ctx} />
        <main>
          {view === "oversikt" && <Overview ctx={ctx} />}
          {view === "regi" && <Regi ctx={ctx} />}
          {view === "kameraer" && <Cameras ctx={ctx} />}
          {view === "opptak" && <Recording ctx={ctx} />}
          {view === "helse" && <Health ctx={ctx} />}
          {view === "oppsett" && <Setup ctx={ctx} />}
          {view === "logg" && <LogView ctx={ctx} />}
          {view === "innstillinger" && <Settings ctx={ctx} theme={theme} onTheme={chooseTheme} />}
        </main>
      </div>
      {toastText && (
        <div className="toast" role="status">
          {toastText}
        </div>
      )}
    </div>
  );
}

const STEP_TEXT: Record<string, string> = {
  idle: "",
  ready: "velger oppsett",
  countdown: "starter",
  rec: "tar opp",
  done: "ferdig",
};

function TopBar({
  ctx,
  title,
  errors,
  warns,
}: {
  ctx: Ctx;
  title: string;
  errors: number;
  warns: number;
}) {
  const { state, cmd, run, go } = ctx;
  const session = state.session;
  const rec = state.touch.step === "rec" || state.touch.step === "countdown";
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    if (!confirm) return;
    const t = setTimeout(() => setConfirm(false), 3000);
    return () => clearTimeout(t);
  }, [confirm]);
  const n = (session?.show.guests ?? 0) + 1;
  return (
    <header className="top">
      <h1>{title}</h1>
      <span className="room">{state.studio.name}</span>
      {state.studio.simulator && (
        <span className="pill sim" title="Alt utstyr er simulert">
          SIMULATOR
        </span>
      )}
      <span className="grow" />
      <div className="user">
        {session ? (
          <>
            <span className="av">{session.user.display_name.slice(0, 1)}</span>
            <span>
              {session.user.display_name}
              <small>
                {n} {n === 1 ? "person" : "personer"} · {session.show.video ? "video" : "kun lyd"}
                {STEP_TEXT[state.touch.step] ? ` · ${STEP_TEXT[state.touch.step]}` : ""}
              </small>
            </span>
          </>
        ) : (
          <span className="muted">Ingen innlogget</span>
        )}
      </div>
      {state.touch.step === "rec" ? (
        <span className="pill rec">
          <span className="d" />
          OPPTAK <span className="tnum">{clock(state.recording.duration_s)}</span> · Pearl
        </span>
      ) : (
        <span className="pill off">
          <span className="d" />
          Ikke opptak
        </span>
      )}
      {rec ? (
        <button
          type="button"
          className={`btn ${confirm ? "red" : ""}`}
          onClick={() => {
            if (!confirm) return setConfirm(true);
            setConfirm(false);
            run(cmd.stopRecording());
          }}
        >
          {confirm ? "Bekreft stopp" : "Stopp opptak"}
        </button>
      ) : (
        <button
          type="button"
          className="btn red"
          disabled={!session}
          title={session ? "" : "Ingen er logget inn på touch-skjermen"}
          onClick={() => run(cmd.startRecording())}
        >
          Start opptak
        </button>
      )}
      <button
        type="button"
        className={`pill ${errors ? "err" : warns ? "warn" : ""}`}
        onClick={() => go("helse")}
      >
        <span className="d" />
        {errors ? `${errors} feil` : warns ? `${warns} advarsel` : "Alt OK"}
      </button>
    </header>
  );
}

function HelpBanner({ ctx }: { ctx: Ctx }) {
  const { state, cmd, run } = ctx;
  const help = state.alerts.find((a) => a.code === "HELP" && !a.acknowledged);
  if (!help) return null;
  return (
    <div className="banner" role="alert">
      <span>⚑</span>
      <span>
        {help.message} (kl. {new Date(help.ts).toTimeString().slice(0, 5)})
      </span>
      <span className="grow" />
      <button type="button" className="btn" onClick={() => run(cmd.ack(help.id))}>
        Kvitter
      </button>
    </div>
  );
}
