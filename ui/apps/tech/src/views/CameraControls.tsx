// Kameraer → styring av ett PTZ-kamera (spes. 7.3, AT1–AT6): presets «tett» og «vid», små steg,
// lagre preset (admin) og AI-tracking. Kameravakten i CutCut avviser alt som ville flyttet et
// kamera på program eller preview (I2), og svaret vises her.
import { errorMessage, useStudio } from "@cutcut/client";
import { useEffect, useState } from "react";
import type { Ctx } from "../lib";

export interface CameraInfo {
  id: string;
  model: string | null;
  online: boolean;
  tracking: boolean;
  can_track: boolean;
  presets: Record<string, number>;
  position: { pan: number; tilt: number; zoom: number } | null;
  last_refused: string | null;
  last_error: string | null;
}

/** All steered cameras, read every 2 s while the page is open. Empty in the simulator
 *  without fake cameras and on a PC that does not steer cameras. */
export function useCameras(): CameraInfo[] | null {
  const { transport } = useStudio();
  const [cams, setCams] = useState<CameraInfo[] | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      transport
        .get<CameraInfo[]>("/api/cameras")
        .then((c) => alive && setCams(c))
        .catch(() => alive && setCams(null));
    load();
    const t = setInterval(load, 2000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [transport]);
  return cams;
}

const NAME: Record<string, string> = { tight: "Tett", wide: "Vid" };

export function CameraControls({ ctx, cam }: { ctx: Ctx; cam: CameraInfo }) {
  const { transport } = useStudio();
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const admin = ctx.role === "admin";
  const send = (path: string, body: unknown, ok: string) => {
    setMsg(null);
    transport
      .send("POST", `/api/cameras/${cam.id}/${path}`, body)
      .then(() => setMsg({ ok: true, text: ok }))
      .catch((x: unknown) => setMsg({ ok: false, text: errorMessage(x) }));
  };
  const step = (pan: number, tilt: number, zoom: number) =>
    send("nudge", { pan, tilt, zoom }, "Sendt.");
  const presets = Object.entries(cam.presets).sort((a, b) => a[1] - b[1]);
  return (
    <div className="camctl">
      <div className="row">
        <span className={`hst ${cam.online ? "" : "err"}`}>
          <i />
          {cam.online ? "Svarer" : "Svarer ikke"}
        </span>
        {cam.position && (
          <span className="small muted mono">
            {cam.position.pan.toFixed(0)}° / {cam.position.tilt.toFixed(0)}° · zoom{" "}
            {Math.round(cam.position.zoom * 100)} %
          </span>
        )}
      </div>
      <div className="row">
        {presets.map(([name, n]) => (
          <button
            key={name}
            type="button"
            className="btn"
            disabled={cam.tracking}
            onClick={() => send("preset", { n }, `${NAME[name] ?? name} hentet.`)}
          >
            {NAME[name] ?? name}
          </button>
        ))}
        <span className="nudge" role="group" aria-label={`Små steg for ${cam.id}`}>
          <button
            type="button"
            className="btn"
            aria-label="Venstre"
            disabled={cam.tracking}
            onClick={() => step(-0.2, 0, 0)}
          >
            ◀
          </button>
          <button
            type="button"
            className="btn"
            aria-label="Opp"
            disabled={cam.tracking}
            onClick={() => step(0, 0.2, 0)}
          >
            ▲
          </button>
          <button
            type="button"
            className="btn"
            aria-label="Ned"
            disabled={cam.tracking}
            onClick={() => step(0, -0.2, 0)}
          >
            ▼
          </button>
          <button
            type="button"
            className="btn"
            aria-label="Høyre"
            disabled={cam.tracking}
            onClick={() => step(0.2, 0, 0)}
          >
            ▶
          </button>
          <button
            type="button"
            className="btn"
            aria-label="Zoom inn"
            disabled={cam.tracking}
            onClick={() => step(0, 0, 0.2)}
          >
            +
          </button>
          <button
            type="button"
            className="btn"
            aria-label="Zoom ut"
            disabled={cam.tracking}
            onClick={() => step(0, 0, -0.2)}
          >
            −
          </button>
        </span>
      </div>
      {admin && presets.length > 0 && (
        <div className="row">
          {presets.map(([name, n]) => (
            <button
              key={name}
              type="button"
              className="btn"
              onClick={() =>
                send("preset", { n, store: true }, `Lagret som ${NAME[name] ?? name}.`)
              }
            >
              Lagre som {(NAME[name] ?? name).toLowerCase()}
            </button>
          ))}
        </div>
      )}
      {cam.can_track && (
        <div className="row">
          <button
            type="button"
            className={`btn ${cam.tracking ? "on" : ""}`}
            aria-pressed={cam.tracking}
            onClick={() =>
              send(
                "tracking",
                { on: !cam.tracking },
                cam.tracking ? "AI-tracking av. Kameraet står der det er." : "AI-tracking på.",
              )
            }
          >
            AI-tracking {cam.tracking ? "på" : "av"}
          </button>
        </div>
      )}
      {msg && (
        <p className={`small ${msg.ok ? "muted" : "err-text"}`} role={msg.ok ? "status" : "alert"}>
          {msg.text}
        </p>
      )}
      {!msg && cam.last_refused && <p className="small muted">Sist avvist: {cam.last_refused}</p>}
    </div>
  );
}
