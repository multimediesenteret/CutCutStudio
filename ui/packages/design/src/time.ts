/** 00:00 or 1:02:03 for durations in seconds. */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${String(m).padStart(2, "0")}:${ss}`;
}

/** 2,5 s – Norwegian decimal comma. */
export function seconds(ms: number, digits = 1): string {
  return `${(ms / 1000).toFixed(digits).replace(".", ",")} s`;
}
