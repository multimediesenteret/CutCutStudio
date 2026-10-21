// The five touch steps from concept/touch.html: idle → ready → countdown → rec → done.
import { useSnapshot, type StudioState } from "@cutcut/client";
import {
  Chip,
  HoldButton,
  Icon,
  MicRow,
  SeatButton,
  SeatMap,
  ShotPicture,
  StatusDot,
  StatusRow,
  clock,
  levelFromDb,
  participantColor,
} from "@cutcut/design";
import type { CSSProperties } from "react";
import type { Act } from "./App";

export const SEATS = [
  { title: "Programleder", subtitle: "ved mikseren" },
  { title: "Gjest 1", subtitle: "Cyan mikrofon" },
  { title: "Gjest 2", subtitle: "Lilla mikrofon" },
  { title: "Gjest 3", subtitle: "Oransje mikrofon" },
] as const;

const COLOR_NAME: Record<string, string> = {
  magenta: "Magenta",
  cyan: "Cyan",
  lilla: "Lilla",
  oransje: "Oransje",
};

/** Simulated test card (fictional, src/cutcut/sim/fakes.py). Only shown in the simulator. */
export const DEMO_CARD = "04A1B2C3";

function firstName(state: StudioState): string {
  return state.session?.user.display_name.split(" ")[0] ?? "";
}

/** What the user is told when something blocks recording: one sentence, no technique. */
function blocking(state: StudioState): string | null {
  const a = state.alerts.find((x) => x.for_user && x.level === "error" && !x.acknowledged);
  // Health checks marked for the user (Pearl, ATEM) block only while they are red right now.
  const red = state.health?.checks.some((c) => c.for_user && c.status === "red");
  if (a || red) return "Noe er galt i studio. Teknikeren er varslet.";
  if (!state.engine.audio_ok) return "Noe er galt med lyden. Teknikeren er varslet.";
  return null;
}

function participantsOf(state: StudioState): number {
  const show = state.session?.show ?? state.touch.default_show;
  return show.guests + 1;
}

function useLevels(state: StudioState): { level: number; speaking: boolean; muted: boolean }[] {
  const meters = useSnapshot((s) => s.meters);
  return state.participants.map((p) => {
    const m = meters[p.mic];
    return {
      level: m ? levelFromDb(m.level_db) : 0,
      speaking: m?.speaking ?? false,
      muted: m?.muted ?? false,
    };
  });
}

/** The start-up and morning check as a small dot (spec 8.5): green, or yellow when the
 * technician has something to look at. Never details: the user cannot act on them. */
function MorningDot({ state }: { state: StudioState }) {
  const m = state.health?.morning;
  if (!m) return <Chip>Kamera, lyd og opptak er sjekket</Chip>;
  const at = m.ts.slice(11, 16);
  return (
    <Chip level={m.status === "green" ? "ok" : "warn"}>
      <span title={m.status === "green" ? "Alt grønt" : "Teknikeren ser på noe"}>
        Sjekket kl. {at}
      </span>
    </Chip>
  );
}

export function Idle({ state, act }: { state: StudioState; act: Act }) {
  const problem = blocking(state);
  return (
    <section className="scr" id="idle">
      <div className="txt">
        <h1>Hold NTNU-kortet ditt mot leseren</h1>
        <p className="intro">Så er studioet klart. Opptaket havner i din egen Panopto-konto.</p>
        <StatusRow>
          {problem ? (
            <Chip level="err">Teknikeren er varslet om en feil</Chip>
          ) : (
            <>
              <Chip level="ok">Studio klart</Chip>
              <MorningDot state={state} />
            </>
          )}
        </StatusRow>
      </div>
      <div className="art">
        <div className="reader">
          <div className="ncard">
            <b>NTNU</b>
            <span>Studentkort / ansattkort</span>
          </div>
          <div className="pad" />
        </div>
      </div>
      {state.studio.simulator && (
        <button type="button" className="demo" onClick={() => act.run(act.cmd.simCard(DEMO_CARD))}>
          <Icon name="card" />
          Demo: simuler kortskanning
        </button>
      )}
    </section>
  );
}

export function Ready({ state, act }: { state: StudioState; act: Act }) {
  const show = state.session?.show ?? state.touch.default_show;
  const n = show.guests + 1;
  const problem = blocking(state);
  const choose = (guests: number, video: boolean) =>
    act.run(act.cmd.setShow(guests, video, show.laptop));
  const pressSeat = (i: number) => {
    // Pressing a chosen guest removes it and everyone after; pressing an empty seat fills up to it.
    const next = i < n ? i : i + 1;
    choose(Math.max(0, Math.min(3, next - 1)), show.video);
  };
  return (
    <section className="scr" id="ready">
      <div className="left">
        <div>
          <h1>Hei, {firstName(state)}!</h1>
          <p className="intro" style={{ marginTop: 14 }}>
            Velg hvem som er med, og trykk Start.
          </p>
        </div>
        <div className="group">
          <h2>Hvem er med?</h2>
          <div className="seats">
            {SEATS.map((s, i) => (
              <SeatButton
                key={i}
                index={i}
                title={s.title}
                subtitle={s.subtitle}
                on={i < n}
                lead={i === 0}
                onPress={() => pressSeat(i)}
              />
            ))}
          </div>
        </div>
        <div className="group">
          <h2>Opptak</h2>
          <div className="modes">
            <button
              type="button"
              className={`mode ${show.video ? "on" : ""}`}
              aria-pressed={show.video}
              onClick={() => choose(show.guests, true)}
            >
              <Icon name="cam" />
              <span>
                <b>Video og lyd</b>
                <span>Kameraene klipper automatisk</span>
              </span>
            </button>
            <button
              type="button"
              className={`mode ${show.video ? "" : "on"}`}
              aria-pressed={!show.video}
              onClick={() => choose(show.guests, false)}
            >
              <Icon name="mic" />
              <span>
                <b>Kun lyd</b>
                <span>Ingen kamera i opptaket</span>
              </span>
            </button>
          </div>
        </div>
      </div>
      <div className="right">
        <h2>Sett dere slik</h2>
        <div className="map">
          <SeatMap participants={n} names={SEATS.map((s) => s.title)} />
        </div>
        {problem && (
          <div className="warnbox" role="alert">
            <StatusDot level="err" />
            <span>{problem}</span>
          </div>
        )}
        <button
          type="button"
          className="start"
          disabled={problem !== null}
          onClick={() => act.run(act.cmd.startRecording())}
        >
          <i />
          Start opptak
        </button>
        <button type="button" className="link" onClick={() => act.run(act.cmd.logout())}>
          Ikke deg? Logg ut
        </button>
      </div>
    </section>
  );
}

export function Countdown({ state }: { state: StudioState }) {
  const levels = useLevels(state).map((l) => Math.round(l.level * 4) / 4);
  const left = Math.max(1, Math.ceil(state.touch.countdown_ms / 1000));
  const starting = state.touch.countdown_ms === 0;
  return (
    <section className="scr" id="countdown">
      <h2>{starting ? "Starter opptaket …" : "Snakk litt, så sjekker vi lyden"}</h2>
      <div className="big" aria-live="polite">
        {starting ? "…" : left}
      </div>
      <div className="map">
        <SeatMap
          participants={participantsOf(state)}
          names={SEATS.map((s) => s.title)}
          levels={levels}
        />
      </div>
    </section>
  );
}

function shotLabel(state: StudioState, shot: string | null | undefined): [string, string] {
  if (!shot || shot === "BIRD" || shot === "WIDE") return ["Fugleperspektiv", "var(--bleed)"];
  if (shot.includes("CONTENT")) return ["Laptop", "var(--bleed)"];
  if (shot === "AUDIO_ONLY") return ["Kun lyd", "var(--bleed)"];
  const id = shot.startsWith("CU:") ? shot.slice(3) : shot;
  const p = state.participants.find((x) => x.id === id);
  return [p?.name ?? id, participantColor(id)];
}

export function Rec({ state, act }: { state: StudioState; act: Act }) {
  const levels = useLevels(state);
  const program = state.engine.program;
  const [label, color] = shotLabel(state, program);
  const talking = state.participants.filter((_, i) => levels[i]?.speaking).map((p) => p.id);
  const video = state.session?.show.video ?? true;
  return (
    <section className="scr" id="rec">
      <div className="left">
        <h2>Nå i bildet</h2>
        <div className="onair">
          <ShotPicture
            shot={video ? program : "AUDIO_ONLY"}
            participants={state.participants.length}
            talking={talking}
            faces={false}
          />
          <div className="tag" style={{ "--pc": color } as CSSProperties}>
            <i />
            <span>{video ? label : "Kun lyd"}</span>
          </div>
        </div>
        <StatusRow>
          <Chip>{video ? "Video og lyd" : "Kun lyd"}</Chip>
          <Chip>Lagres i Panopto: {state.session?.user.username ?? ""}</Chip>
          <Chip>{state.engine.auto ? "Klipper automatisk" : "Tekniker klipper"}</Chip>
        </StatusRow>
      </div>
      <div className="right">
        <h2>Mikrofoner</h2>
        <div className="mics">
          {state.participants.map((p, i) => {
            const l = levels[i] ?? { level: 0, speaking: false, muted: false };
            const sub = l.muted
              ? "dempet på mikseren"
              : l.speaking
                ? "snakker"
                : `${COLOR_NAME[p.color] ?? p.color} mikrofon`;
            return (
              <MicRow
                key={p.id}
                index={i}
                title={p.name}
                subtitle={sub}
                level={l.level}
                talking={l.speaking}
                muted={l.muted}
                lead={i === 0}
              />
            );
          })}
        </div>
        <div className="spacer" />
        <button
          type="button"
          className={`help ${state.touch.help ? "sent" : ""}`}
          onClick={() => {
            if (state.touch.help) return;
            act.run(act.cmd.help());
            act.toast("Teknikeren er varslet. Opptaket fortsetter.");
          }}
        >
          <Icon name="help" />
          <span>{state.touch.help ? "Teknikeren er varslet" : "Trenger du hjelp?"}</span>
        </button>
        <HoldButton
          className="stop"
          label="Hold inne for å avslutte opptaket"
          onComplete={() => act.run(act.cmd.stopRecording())}
        >
          Avslutt opptak
          <small>Hold inne i 2 sekunder</small>
        </HoldButton>
      </div>
    </section>
  );
}

export function Done({ state, act }: { state: StudioState; act: Act }) {
  const session = state.session;
  const n = participantsOf(state);
  const video = session?.show.video ?? true;
  const left = Math.ceil(state.touch.done_logout_ms / 1000);
  return (
    <section className="scr" id="done">
      <div className="okmark">
        <Icon name="check" />
      </div>
      <h1>Takk, {firstName(state)}! Opptaket er lagret.</h1>
      <StatusRow>
        <span className="facts cc-status">
          <Chip className="tnum">{clock(session?.recording.duration_s ?? 0)}</Chip>
          <Chip>{video ? "Video og lyd" : "Kun lyd"}</Chip>
          <Chip>
            {n} {n === 1 ? "person" : "personer"}
          </Chip>
        </span>
      </StatusRow>
      <p className="intro">
        Opptaket kommer i Panopto-kontoen din ({session?.user.username ?? ""}) innen omtrent en
        time. Du logges ut om {left} s.
      </p>
      <button type="button" className="primary" onClick={() => act.run(act.cmd.logout())}>
        Ferdig, logg ut
      </button>
      <button type="button" className="link" onClick={() => act.run(act.cmd.again())}>
        Ta et nytt opptak
      </button>
    </section>
  );
}
