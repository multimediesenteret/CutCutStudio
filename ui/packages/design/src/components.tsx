// Shared building blocks for touch and technician screens (U-2). Behaviour lives here; sizes
// live in each app's CSS, because touch needs ≥ 120 px targets and the technician does not.
import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  type ReactElement,
  type ReactNode,
} from "react";
import { participantColor } from "./drawings";

type Level = "ok" | "warn" | "err" | "off";

/** Small round status light. Colour carries meaning (docs/design/farger.md). */
export function StatusDot({ level = "ok" }: { level?: Level }): ReactElement {
  return <span className={`cc-dot ${level}`} aria-hidden="true" />;
}

/** A rounded label, optionally with a status light. */
export function Chip({
  level,
  children,
  className = "",
}: {
  level?: Level;
  children: ReactNode;
  className?: string;
}): ReactElement {
  return (
    <span className={`cc-chip ${className}`.trim()}>
      {level && <StatusDot level={level} />}
      {children}
    </span>
  );
}

/** A row of chips (statusrad). */
export function StatusRow({ children }: { children: ReactNode }): ReactElement {
  return <div className="cc-status">{children}</div>;
}

/** Microphone level 0–1 drawn with transform only, so a meter never causes layout (12.5). */
export function LevelBar({ level, color }: { level: number; color?: string }): ReactElement {
  const v = Math.max(0, Math.min(1, Math.round(level * 50) / 50));
  const style = { "--lv": String(v), "--pc": color } as CSSProperties;
  return (
    <span className="cc-level" style={style} aria-hidden="true">
      <i />
    </span>
  );
}

/** Map a level in dBFS to 0–1 for the bars (−50 dB is empty, −12 dB is full). */
export function levelFromDb(db: number): number {
  return Math.max(0, Math.min(1, (db + 50) / 38));
}

export const HOLD_MS = 2000;

/**
 * Press and hold for `ms` to confirm (spec 8.3: stopping a recording needs a 2 s hold).
 * Works with touch, mouse and keyboard; letting go early cancels with no side effect.
 */
export function HoldButton({
  ms = HOLD_MS,
  onComplete,
  className = "",
  label,
  children,
  disabled = false,
}: {
  ms?: number;
  onComplete: () => void;
  className?: string;
  label: string;
  children: ReactNode;
  disabled?: boolean;
}): ReactElement {
  const [holding, setHolding] = useState(false);
  const fill = useRef<HTMLSpanElement>(null);
  const frame = useRef<number | null>(null);
  const started = useRef(0);
  const done = useRef(onComplete);
  done.current = onComplete;

  const draw = (p: number) => {
    if (fill.current) fill.current.style.transform = `scaleX(${p})`;
  };
  const cancel = () => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
    setHolding(false);
    draw(0);
  };
  const tick = () => {
    const p = Math.min(1, (performance.now() - started.current) / ms);
    draw(p);
    if (p >= 1) {
      cancel();
      done.current();
    } else {
      frame.current = requestAnimationFrame(tick);
    }
  };
  const begin = () => {
    if (disabled || frame.current !== null) return;
    started.current = performance.now();
    setHolding(true);
    frame.current = requestAnimationFrame(tick);
  };
  useEffect(
    () => () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    },
    [],
  );

  return (
    <button
      type="button"
      className={`cc-hold ${holding ? "hold" : ""} ${className}`.trim()}
      aria-label={label}
      disabled={disabled}
      onPointerDown={(e: PointerEvent<HTMLButtonElement>) => {
        e.preventDefault();
        e.currentTarget.setPointerCapture?.(e.pointerId);
        begin();
      }}
      onPointerUp={cancel}
      onPointerCancel={cancel}
      onLostPointerCapture={() => frame.current !== null && cancel()}
      onKeyDown={(e: KeyboardEvent) => {
        if ((e.key === " " || e.key === "Enter") && !e.repeat) begin();
      }}
      onKeyUp={cancel}
      onContextMenu={(e) => e.preventDefault()}
    >
      <span className="cc-hold-fill" ref={fill} />
      <span className="cc-hold-label">{children}</span>
    </button>
  );
}

/** A seat on the ready screen (setebrikke): number in the participant colour when chosen. */
export function SeatButton({
  index,
  title,
  subtitle,
  on,
  lead = false,
  onPress,
}: {
  index: number;
  title: string;
  subtitle: string;
  on: boolean;
  lead?: boolean;
  onPress?: () => void;
}): ReactElement {
  const style = { "--pc": participantColor(`P${index + 1}`) } as CSSProperties;
  return (
    <button
      type="button"
      className={`cc-seat ${on ? "on" : ""} ${lead ? "lead" : ""}`.trim()}
      style={style}
      aria-pressed={on}
      onClick={lead ? undefined : onPress}
    >
      <span className="num">{index + 1}</span>
      <span>
        <b>{title}</b>
        <span>{subtitle}</span>
      </span>
    </button>
  );
}

/** One microphone (mic-stripe): who, what is happening, and a level bar. */
export function MicRow({
  index,
  title,
  subtitle,
  level,
  talking,
  muted,
  lead = false,
}: {
  index: number;
  title: string;
  subtitle: string;
  level: number;
  talking: boolean;
  muted: boolean;
  lead?: boolean;
}): ReactElement {
  const color = participantColor(`P${index + 1}`);
  const style = { "--pc": color } as CSSProperties;
  const cls = ["cc-mic", talking && "talk", muted && "muted", lead && "lead"].filter(Boolean);
  return (
    <div className={cls.join(" ")} style={style}>
      <span className="num">{index + 1}</span>
      <span className="nm">
        <b>{title}</b>
        <span>{subtitle}</span>
      </span>
      <LevelBar level={level} color={color} />
    </div>
  );
}
