// Touch screen in the studio (spec 8.1–8.3, D-036). The engine decides which step is shown;
// this app only draws it and sends what the user presses.
import { commands, errorMessage, useSnapshot, useStudio, type StudioState } from "@cutcut/client";
import { Icon, Logo, applyTheme, clock, isDark, loadTheme, saveTheme } from "@cutcut/design";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Countdown, Done, Idle, Ready, Rec } from "./screens";

const TOAST_MS = 3500;
const TECH_HOLD_MS = 5000;

export interface Act {
  cmd: ReturnType<typeof commands>;
  /** Run a command; a refusal is shown as one plain sentence (spec 8.3). */
  run: (p: Promise<void>) => void;
  toast: (text: string) => void;
}

function useFit(ref: React.RefObject<HTMLDivElement | null>) {
  useLayoutEffect(() => {
    const fit = () => {
      const s = Math.min(innerWidth / 1920, innerHeight / 1080);
      if (ref.current) ref.current.style.transform = `translate(-50%,-50%) scale(${s})`;
    };
    fit();
    addEventListener("resize", fit);
    return () => removeEventListener("resize", fit);
  }, [ref]);
}

function useWallClock(): string {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now.toTimeString().slice(0, 5);
}

/** Reload once a night while nobody is logged in, so memory never grows over weeks (ui.md). */
function useNightlyReload(idle: boolean) {
  const loaded = useRef(Date.now());
  useEffect(() => {
    const t = setInterval(() => {
      const hour = new Date().getHours();
      if (idle && hour === 3 && Date.now() - loaded.current > 3_600_000) location.reload();
    }, 60_000);
    return () => clearInterval(t);
  }, [idle]);
}

export function App() {
  const { transport } = useStudio();
  const state = useSnapshot((s) => s.state);
  const connection = useSnapshot((s) => s.connection);
  const stage = useRef<HTMLDivElement>(null);
  useFit(stage);

  const [dark, setDark] = useState(() => {
    applyTheme(loadTheme("touch", "dark"));
    return isDark();
  });
  const toggleTheme = () => {
    const next = dark ? "light" : "dark";
    applyTheme(next);
    saveTheme("touch", next);
    setDark(!dark);
  };

  const [toastText, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toast = useCallback((text: string) => {
    setToast(text);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), TOAST_MS);
  }, []);

  const act = useMemo<Act>(() => {
    const cmd = commands(transport);
    return {
      cmd,
      toast,
      run: (p) => {
        p.catch((e: unknown) => toast(errorMessage(e)));
      },
    };
  }, [transport, toast]);

  const notice = state?.touch.notice ?? null;
  useEffect(() => {
    if (notice) toast(notice);
  }, [notice, toast]);

  const step = state?.touch.step ?? "idle";
  useNightlyReload(step === "idle" && connection === "connected");

  return (
    <div className="viewport" onPointerDown={() => state?.session && act.run(act.cmd.touched())}>
      <div className={`stage ${connection === "connected" ? "" : "offline"}`} ref={stage}>
        <Header state={state} dark={dark} onTheme={toggleTheme} toast={toast} />
        <main>
          {state && <Screen state={state} act={act} />}
          {toastText && <div className="toast">{toastText}</div>}
        </main>
        {connection !== "connected" && (
          <div className="reconnect" role="status">
            <i />
            Kobler til igjen …
          </div>
        )}
      </div>
    </div>
  );
}

function Screen({ state, act }: { state: StudioState; act: Act }) {
  switch (state.touch.step) {
    case "ready":
      return <Ready state={state} act={act} />;
    case "countdown":
      return <Countdown state={state} />;
    case "rec":
      return <Rec state={state} act={act} />;
    case "done":
      return <Done state={state} act={act} />;
    default:
      return <Idle state={state} act={act} />;
  }
}

function Header({
  state,
  dark,
  onTheme,
  toast,
}: {
  state: StudioState | null;
  dark: boolean;
  onTheme: () => void;
  toast: (t: string) => void;
}) {
  const time = useWallClock();
  const hold = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rec = state?.touch.step === "rec";
  // Hold the logo for 5 s to open technician access (spec 8.2).
  const down = () => {
    hold.current = setTimeout(() => {
      toast("Åpner teknikertilgang …");
      location.href = "/tech/";
    }, TECH_HOLD_MS);
  };
  const up = () => {
    if (hold.current) clearTimeout(hold.current);
  };
  return (
    <header>
      <div
        className="brand"
        onPointerDown={down}
        onPointerUp={up}
        onPointerLeave={up}
        onPointerCancel={up}
      >
        <Logo />
        <div>
          <b>CutCut Studio</b>
          <span>Podkaststudio · Multimediesenteret</span>
        </div>
      </div>
      <div className="hright">
        {rec && (
          <div className="recpill">
            <i />
            OPPTAK <span className="tnum">{clock(state?.recording.duration_s ?? 0)}</span>
          </div>
        )}
        <div className="clock">{time}</div>
        <button
          type="button"
          className="round"
          aria-label="Bytt mellom lyst og mørkt tema"
          onClick={onTheme}
        >
          <Icon name={dark ? "sun" : "moon"} />
        </button>
      </div>
    </header>
  );
}
