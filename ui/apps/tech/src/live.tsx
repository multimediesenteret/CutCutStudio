// Camera pictures as cut-outs of the multiview the video layer reads (D-056). One clock for all
// pictures, twice a second; a picture that fails falls back to the drawing
// until the video layer answers again.
import { useStudio } from "@cutcut/client";
import { useEffect, useState, type ReactNode } from "react";

let listeners = new Set<(n: number) => void>();
let timer: ReturnType<typeof setInterval> | null = null;
let tick = 0;

function useTick(on: boolean): number {
  const [n, setN] = useState(tick);
  useEffect(() => {
    if (!on) return;
    listeners.add(setN);
    if (!timer) {
      timer = setInterval(() => {
        tick += 1;
        listeners.forEach((l) => l(tick));
      }, 500);
    }
    return () => {
      listeners.delete(setN);
      if (listeners.size === 0 && timer) {
        clearInterval(timer);
        timer = null;
        listeners = new Set();
      }
    };
  }, [on]);
  return n;
}

/** The live cut-out of ``source`` (C1…, LAPTOP, PVW, PGM) when the video layer runs, else
 * ``fallback`` (the drawing). Never in the web simulator: it has no video layer. */
export function LivePicture({
  source,
  live,
  fallback,
}: {
  source: string | null | undefined;
  live: boolean;
  fallback: ReactNode;
}) {
  const { transport } = useStudio();
  const on = live && !!source && !transport.role;
  const n = useTick(on);
  // A picture that fails (the video layer is starting, or stopped) shows the drawing and is
  // probed again every two seconds by a hidden image, so the picture comes back by itself.
  const [failedAt, setFailedAt] = useState<number | null>(null);
  useEffect(() => setFailedAt(null), [source, live]);
  if (!on) return <>{fallback}</>;
  if (failedAt !== null) {
    const probe = n - failedAt >= 4;
    return (
      <>
        {fallback}
        {probe && (
          <img
            hidden
            alt=""
            src={`/api/vision/thumb/${source}?n=${n}`}
            onLoad={() => setFailedAt(null)}
            onError={() => setFailedAt(n)}
          />
        )}
      </>
    );
  }
  return (
    <img
      className="live"
      alt=""
      src={`/api/vision/thumb/${source}?n=${n}`}
      onError={() => setFailedAt(n)}
    />
  );
}
