// Oppsett → steg 6 (VI-5): rutekartet tegnet på bildet av multiviewen. «Foreslå fra bildet»
// finner rutene i bildet og kildene i ATEM; hjørnene kan dras før rutekartet lagres. Lagret
// rutekart ligger i appen og brukes av videolaget med en gang.
import { errorMessage, useStudio } from "@cutcut/client";
import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { LivePicture } from "../live";

type Rect = [number, number, number, number];

export interface EditTile {
  id: string;
  label: string;
  rect: Rect;
  source: string;
  camera: string | null;
}

export interface EditMap {
  tiles: EditTile[];
  layout: string;
  [key: string]: unknown;
}

type Corner = "nw" | "ne" | "sw" | "se";
const CORNERS: Corner[] = ["nw", "ne", "sw", "se"];
const MIN = 0.04; // smallest window, share of the picture
const r4 = (v: number) => Math.round(v * 10000) / 10000;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Move one corner of a window to (px, py), keeping the opposite corner where it is. */
export function dragCorner(rect: Rect, corner: Corner, px: number, py: number): Rect {
  let [x, y, w, h] = rect;
  let x1 = x + w;
  let y1 = y + h;
  const cx = clamp(px, 0, 1);
  const cy = clamp(py, 0, 1);
  if (corner === "nw" || corner === "sw") x = Math.min(cx, x1 - MIN);
  else x1 = Math.max(cx, x + MIN);
  if (corner === "nw" || corner === "ne") y = Math.min(cy, y1 - MIN);
  else y1 = Math.max(cy, y + MIN);
  w = x1 - x;
  h = y1 - y;
  return [r4(x), r4(y), r4(w), r4(h)];
}

function name(t: EditTile): string {
  if (t.id === "PVW") return "Preview";
  if (t.id === "PGM") return "Program";
  return t.camera ? `${t.id} · ${t.camera}` : `${t.id} · ${t.label || t.source}`;
}

export function MapEditor({
  current,
  inApp,
  onSaved,
}: {
  current: EditMap | null;
  inApp: boolean;
  onSaved: () => void;
}) {
  const { transport } = useStudio();
  const [draft, setDraft] = useState<EditMap | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const drag = useRef<{ tile: number; corner: Corner } | null>(null);

  const shown = draft ?? current;

  const suggest = () => {
    setBusy(true);
    setMsg(null);
    transport
      .get<{ map: EditMap; found: boolean; notes: string[] }>("/api/setup/multiview/suggest")
      .then((s) => {
        setDraft(s.map);
        setNotes(s.notes);
      })
      .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }))
      .finally(() => setBusy(false));
  };
  const edit = () => {
    if (current) setDraft(structuredClone(current));
    setNotes([]);
    setMsg(null);
  };
  const done = (text: string) => {
    setDraft(null);
    setNotes([]);
    setMsg({ ok: true, text });
    onSaved();
  };
  const save = () => {
    if (!draft) return;
    setBusy(true);
    transport
      .send("PUT", "/api/setup/multiview", draft)
      .then(() => done("Rutekartet er lagret og brukes nå."))
      .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }))
      .finally(() => setBusy(false));
  };
  const reset = () => {
    setBusy(true);
    transport
      .send("DELETE", "/api/setup/multiview")
      .then(() => done("Tilbake til rutekartet i filen."))
      .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }))
      .finally(() => setBusy(false));
  };

  const where = (e: ReactPointerEvent) => {
    const b = box.current?.getBoundingClientRect();
    if (!b) return null;
    return [(e.clientX - b.left) / b.width, (e.clientY - b.top) / b.height] as const;
  };
  const onMove = (e: ReactPointerEvent) => {
    const d = drag.current;
    const p = where(e);
    if (!d || !p || !draft) return;
    setDraft({
      ...draft,
      tiles: draft.tiles.map((t, i) =>
        i === d.tile ? { ...t, rect: dragCorner(t.rect, d.corner, p[0], p[1]) } : t,
      ),
    });
  };
  const stop = () => {
    drag.current = null;
  };

  return (
    <div className="mapedit">
      <div
        className={`mapbox ${draft ? "editing" : ""}`}
        ref={box}
        onPointerMove={onMove}
        onPointerUp={stop}
        onPointerLeave={stop}
      >
        <LivePicture
          source="MV"
          live
          fallback={<div className="mapph">Ikke noe bilde fra videolaget</div>}
        />
        {shown?.tiles.map((t, i) => (
          <div
            key={t.id}
            className={`maptile ${t.camera ? "cam" : ""}`}
            style={{
              left: `${t.rect[0] * 100}%`,
              top: `${t.rect[1] * 100}%`,
              width: `${t.rect[2] * 100}%`,
              height: `${t.rect[3] * 100}%`,
            }}
          >
            <span>{name(t)}</span>
            {draft &&
              CORNERS.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`corner ${c}`}
                  aria-label={`Dra hjørnet av ${name(t)}`}
                  onPointerDown={(e) => {
                    e.preventDefault();
                    (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
                    drag.current = { tile: i, corner: c };
                  }}
                />
              ))}
          </div>
        ))}
      </div>
      {notes.length > 0 && (
        <ul className="small muted">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {msg && (
        <p className={msg.ok ? "muted" : "err-text"} role={msg.ok ? "status" : "alert"}>
          {msg.text}
        </p>
      )}
      <div className="row">
        {!draft && (
          <>
            <button className="btn" type="button" disabled={busy} onClick={suggest}>
              Foreslå fra bildet
            </button>
            <button className="btn" type="button" disabled={busy || !current} onClick={edit}>
              Juster hjørnene
            </button>
            {inApp && (
              <button className="btn" type="button" disabled={busy} onClick={reset}>
                Tilbake til filen
              </button>
            )}
          </>
        )}
        {draft && (
          <>
            <button className="btn primary" type="button" disabled={busy} onClick={save}>
              Lagre rutekart
            </button>
            <button className="btn" type="button" disabled={busy} onClick={() => setDraft(null)}>
              Avbryt
            </button>
          </>
        )}
      </div>
    </div>
  );
}
