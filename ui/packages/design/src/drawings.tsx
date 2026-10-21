// Drawn "camera pictures" and the seating map from the GUI concept (concept/assets/views.js).
// In the studio, the technician sees real multiview thumbnails (vision, M3); these drawings are
// used on touch, in the simulator and whenever no picture is available.
import { useId, type ReactElement } from "react";

export type ParticipantKey = "P1" | "P2" | "P3" | "P4";
export const PARTICIPANT_VAR: Record<ParticipantKey, string> = {
  P1: "var(--p1)",
  P2: "var(--p2)",
  P3: "var(--p3)",
  P4: "var(--p4)",
};

export function participantColor(id: string | null | undefined): string {
  return id && id in PARTICIPANT_VAR ? PARTICIPANT_VAR[id as ParticipantKey] : "var(--bleed)";
}

export function PersonPicture({
  id,
  talking = false,
  faces = true,
}: {
  id: string;
  talking?: boolean;
  faces?: boolean;
}): ReactElement {
  const gid = useId();
  const color = participantColor(id);
  return (
    <svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--cam-bg1)" />
          <stop offset="1" stopColor="var(--cam-bg2)" />
        </linearGradient>
      </defs>
      <rect width="160" height="90" fill={`url(#${gid})`} />
      <rect x="0" y="66" width="160" height="24" fill="var(--cam-table)" opacity=".7" />
      <ellipse cx="80" cy="92" rx="38" ry="26" fill="var(--cam-skin)" />
      <circle cx="80" cy="44" r="15" fill="var(--cam-skin)" />
      <rect
        x="61"
        y="25"
        width="38"
        height="40"
        rx="3"
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        opacity={faces ? 1 : 0}
      />
      <rect
        className="mouth"
        x="74"
        y="51"
        width="12"
        height="3"
        rx="1.5"
        fill={color}
        opacity={talking ? 1 : 0}
      />
    </svg>
  );
}

const SEATS: [number, number][] = [
  [80, 24],
  [124, 50],
  [80, 74],
  [36, 50],
];

export function BirdPicture({ participants }: { participants: number }): ReactElement {
  return (
    <svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="160" height="90" fill="var(--cam-bg2)" />
      <ellipse cx="80" cy="49" rx="40" ry="20" fill="var(--cam-table)" />
      <rect x="66" y="31" width="28" height="7" rx="1.5" fill="var(--cam-skin)" opacity=".9" />
      {SEATS.map(([x, y], i) => (
        <circle
          key={i}
          cx={x}
          cy={y}
          r="7.5"
          fill={i < participants ? participantColor(`P${i + 1}`) : "var(--cam-skin)"}
          opacity={i < participants ? 1 : 0.35}
        />
      ))}
    </svg>
  );
}

export function SlidePicture({ label = "Laptop" }: { label?: string }): ReactElement {
  return (
    <svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="160" height="90" fill="#F4F6F9" />
      <rect x="14" y="12" width="84" height="8" rx="2" fill="#1F3B66" />
      <rect x="14" y="28" width="60" height="4" rx="2" fill="#8A97A8" />
      <rect x="14" y="37" width="70" height="4" rx="2" fill="#8A97A8" />
      <rect x="14" y="46" width="52" height="4" rx="2" fill="#8A97A8" />
      <rect x="100" y="28" width="46" height="40" rx="3" fill="#C9D6EA" />
      <text
        x="146"
        y="83"
        fontSize="7"
        textAnchor="end"
        fill="#59636F"
        fontFamily="Segoe UI,system-ui,sans-serif"
      >
        {label}
      </text>
    </svg>
  );
}

export function AudioOnlyPicture(): ReactElement {
  return (
    <svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="160" height="90" fill="var(--cam-bg2)" />
      {Array.from({ length: 28 }, (_, i) => {
        const h = 8 + Math.abs(Math.sin(i * 1.7)) * 26 + ((i * 37) % 11);
        return (
          <rect
            key={i}
            x={24 + i * 4}
            y={45 - h / 2}
            width="2.4"
            height={h}
            rx="1.2"
            fill="var(--eye)"
            opacity=".85"
          />
        );
      })}
      <text
        x="80"
        y="82"
        fontSize="8"
        textAnchor="middle"
        fill="var(--muted)"
        fontFamily="Segoe UI,system-ui,sans-serif"
      >
        KUN LYD
      </text>
    </svg>
  );
}

export function NoSignalPicture(): ReactElement {
  return (
    <svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="160" height="90" fill="var(--cam-bg2)" />
      <text
        x="80"
        y="49"
        fontSize="9"
        textAnchor="middle"
        fill="var(--muted)"
        fontFamily="Segoe UI,system-ui,sans-serif"
      >
        Ingen signal
      </text>
    </svg>
  );
}

/** The picture for a shot as the engine names it: CU:P2, BIRD, WIDE, CONTENT, AUDIO_ONLY … */
export function ShotPicture({
  shot,
  participants,
  talking = [],
  faces = true,
}: {
  shot: string | null | undefined;
  participants: number;
  talking?: string[];
  faces?: boolean;
}): ReactElement {
  if (!shot || shot === "BIRD" || shot === "WIDE")
    return <BirdPicture participants={participants} />;
  if (shot === "CONTENT" || shot.endsWith("+CONTENT")) return <SlidePicture />;
  if (shot === "AUDIO_ONLY") return <AudioOnlyPicture />;
  const id = shot.startsWith("CU:") ? shot.slice(3) : shot;
  return <PersonPicture id={id} talking={talking.includes(id)} faces={faces} />;
}

const MAP_POS: [number, number][] = [
  [300, 330],
  [470, 200],
  [300, 82],
  [130, 200],
];

/** Top-down seating map: presenter at the mixer, guests clockwise (rodecaster-standardoppsett). */
export type SeatCheck = "heard" | "muted" | null;

export function SeatMap({
  participants,
  names,
  levels = [],
  checks = [],
}: {
  participants: number;
  names: string[];
  levels?: number[];
  /** The audio check (AU-7): a green tick when heard, a red mark when muted on the mixer. */
  checks?: SeatCheck[];
}): ReactElement {
  return (
    <svg viewBox="0 0 600 420" role="img" aria-label={`Bordplan med ${participants} plasser`}>
      <ellipse
        cx="300"
        cy="205"
        rx="170"
        ry="96"
        fill="var(--surface-2)"
        stroke="var(--line)"
        strokeWidth="2"
      />
      <rect
        x="246"
        y="250"
        width="108"
        height="34"
        rx="6"
        fill="var(--surface)"
        stroke="var(--line)"
        strokeWidth="2"
      />
      <text
        x="300"
        y="272"
        textAnchor="middle"
        fontSize="15"
        fill="var(--muted)"
        fontFamily="var(--f-ui)"
        letterSpacing="1"
      >
        RØDECASTER
      </text>
      {MAP_POS.map(([x, y], i) => {
        const on = i < participants;
        const c = participantColor(`P${i + 1}`);
        const lvl = levels[i] ?? 0;
        return (
          <g key={i} opacity={on ? 1 : 0.32}>
            {on && lvl > 0 && (
              <circle cx={x} cy={y} r={34 + Math.min(16, lvl * 16)} fill={c} opacity=".22" />
            )}
            <circle
              cx={x}
              cy={y}
              r="34"
              fill={on ? c : "var(--surface)"}
              stroke={on ? c : "var(--line)"}
              strokeWidth="3"
              strokeDasharray={on ? undefined : "6 6"}
            />
            <text
              x={x}
              y={y + 11}
              textAnchor="middle"
              fontSize="32"
              fontWeight="700"
              fill={on ? "#fff" : "var(--faint)"}
              fontFamily="var(--f-display)"
            >
              {i + 1}
            </text>
            {on && checks[i] && (
              <g aria-label={checks[i] === "heard" ? "Hørt" : "Dempet på mikseren"}>
                <circle
                  cx={x + 27}
                  cy={y - 27}
                  r="16"
                  fill={checks[i] === "heard" ? "var(--pvw)" : "var(--pgm)"}
                  stroke="var(--bg)"
                  strokeWidth="3"
                />
                {checks[i] === "heard" ? (
                  <path
                    d={`M${x + 20} ${y - 27} l5 5 l9 -10`}
                    fill="none"
                    stroke="#fff"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                ) : (
                  <path
                    d={`M${x + 27} ${y - 35} v9 M${x + 27} ${y - 20} v0.5`}
                    stroke="#fff"
                    strokeWidth="3.4"
                    strokeLinecap="round"
                  />
                )}
              </g>
            )}
            <text
              x={x}
              y={y + (i === 2 ? -48 : 62)}
              textAnchor="middle"
              fontSize="19"
              fontWeight="600"
              fill="var(--ink)"
              fontFamily="var(--f-ui)"
            >
              {names[i] ?? ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
