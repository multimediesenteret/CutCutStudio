// Front page of the web simulator: both screens side by side, one replay, and a small panel
// to pick a story, pause, change speed and jump (ADR-0013, U-9).
import type { ReplayStatus } from "@cutcut/client";
import "@cutcut/design/tokens.css";
import { Logo, clock } from "@cutcut/design";
import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./simulator.css";
import { loadStories, startSim, type Sim, type StoryInfo } from "./shared";

const SPEEDS = [1, 2, 4] as const;

function Screen({ src, title }: { src: string; title: string }) {
  const box = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      const w = e?.contentRect.width ?? 0;
      if (frame.current) frame.current.style.transform = `scale(${w / 1920})`;
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div className="screen" ref={box}>
      <iframe ref={frame} src={src} title={title} />
    </div>
  );
}

function Panel({ sim, onStory }: { sim: Sim; onStory: (id: string) => void }) {
  const [st, setSt] = useState<ReplayStatus>(() => sim.transport.status());
  useEffect(() => sim.transport.onStatus(setSt), [sim]);
  const t = sim.transport;
  return (
    <div className="panel" role="group" aria-label="Avspilling">
      <label>
        Forløp{" "}
        <select value={sim.story.id} onChange={(e) => onStory(e.target.value)}>
          {sim.stories.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="tbtn" onClick={() => t.setPlaying(!st.playing)}>
        {st.playing ? "Pause" : "Spill av"}
      </button>
      <div className="seg" role="group" aria-label="Fart">
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            className={st.speed === s ? "sel" : ""}
            aria-pressed={st.speed === s}
            onClick={() => t.setSpeed(s)}
          >
            {s}×
          </button>
        ))}
      </div>
      <input
        className="seek"
        type="range"
        min={0}
        max={st.duration_ms}
        step={1000}
        value={st.t_ms}
        aria-label="Hopp i forløpet"
        onChange={(e) => t.seek(Number(e.target.value))}
      />
      <span className="time">
        {clock(st.t_ms / 1000)} / {clock(st.duration_ms / 1000)}
      </span>
    </div>
  );
}

function Page() {
  const [sim, setSim] = useState<Sim | null>(null);
  const [stories, setStories] = useState<StoryInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [gen, setGen] = useState(0);

  const open = (list: StoryInfo[], id?: string) => {
    startSim(list, id)
      .then((s) => {
        window.cutcutSim?.transport.stop();
        window.cutcutSim = s;
        setSim(s);
        setGen((g) => g + 1); // reload the screens so they pick up the new replay
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  };
  useEffect(() => {
    loadStories()
      .then((list) => {
        setStories(list);
        open(list);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="wrap">
      <div className="simbanner" role="note">
        <b>SIMULATOR – ingen ekte utstyr.</b> Du ser et forløp kjørt med den ekte regimotoren og
        spilt av i de ekte skjermene. Knappene virker i studio, ikke her.
      </div>
      <header>
        <div className="brand">
          <Logo />
          <div>
            <h1>CutCut Studio · simulator</h1>
            <p>Teknikervindu og touch-skjerm i studio, med samme forløp.</p>
          </div>
        </div>
        {sim && <Panel sim={sim} onStory={(id) => open(stories, id)} />}
      </header>
      {error && <p className="error">Kunne ikke laste forløpet: {error}</p>}
      {sim && (
        <div className="mons" key={gen}>
          <div className="mon">
            <div className="hd">
              <h2>Teknikervindu</h2>
              <a href={`tech.html?story=${sim.story.id}`} target="_blank" rel="noopener">
                Åpne i full størrelse
              </a>
            </div>
            <Screen src="tech.html" title="Teknikervindu" />
          </div>
          <div className="mon">
            <div className="hd">
              <h2>Touch-skjerm i studio</h2>
              <a href={`touch.html?story=${sim.story.id}`} target="_blank" rel="noopener">
                Åpne i full størrelse
              </a>
            </div>
            <Screen src="touch.html" title="Touch-skjerm" />
          </div>
        </div>
      )}
      <div className="notes">
        <div className="note">
          <b>Hva du ser</b>
          Kortskanning, valg av personer, lydsjekk, opptak med automatisk klipping og ferdig-skjerm.
          Hvert kutt har regel-ID i teknikervinduet.
        </div>
        <div className="note">
          <b>Samme kode som i studio</b>
          Forløpet er laget med <code>uv run cutcut trace</code>, som kjører motoren på falsk
          klokke. Skjermene er de samme appene som motoren serverer i studio.
        </div>
        <div className="note">
          <b>Prøv selv</b>
          Lokalt kan du styre alt: <code>uv run cutcut sim</code> gir begge skjermene med simulert
          tale, slides og feil.
        </div>
      </div>
    </div>
  );
}

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <Page />
    </StrictMode>,
  );
}
