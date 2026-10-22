"""How well faces and mouths are found on studio footage (P6, VI-6).

``cutcut hwtest faces --site C:\\CutCut\\site --file multiview.mp4`` runs the face analysis on a
recording of the multiview (from the capture card, or a test session) with the same code as the
video layer, and writes the usual report:

| Step | What |
| --- | --- |
| F1 | Each camera window: share of rounds with a face, and with a usable face (V2) |
| F2 | Mouth: how often it counts as moving (above 0.3) per window, to compare with who talked |
| F3 | Time per round for all windows; must stay under 1/5 s so 5 rounds a second fit (12.5) |

The numbers are for tuning: thresholds in ``vision/faces.py`` and ``V1``/``V2`` in the engine.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Final

from cutcut.common.config import load_site
from cutcut.hwtest.report import Report, Step
from cutcut.vision.capture import OpenCvSource, Source
from cutcut.vision.faces import FACES_HZ, FaceAnalyzer
from cutcut.vision.faces import load as load_faces
from cutcut.vision.process import Vision

MODELS: Final = Path(__file__).resolve().parents[3] / "models"
MOUTH_ON: Final = 0.3


def measure(
    vision: Vision, source: Source, analyzer: FaceAnalyzer, rounds: int, fps: float = 50.0
) -> Report:
    report = Report("ansikt", datetime.now().astimezone())
    found: dict[str, int] = defaultdict(int)
    usable: dict[str, int] = defaultdict(int)
    talking: dict[str, int] = defaultdict(int)
    times: list[float] = []
    every = max(1, round(fps / FACES_HZ))
    done = frames = 0
    while done < rounds:
        frame = source.read()
        if frame is None:
            break
        frames += 1
        if frames % every:
            continue
        vision.measure(frame)
        out = analyzer.analyze(frames / fps, vision.camera_windows(frame))
        times.append(analyzer.last_ms or 0.0)
        for src, r in out.items():
            found[src] += r.found
            usable[src] += r.found and r.size_ok
            talking[src] += r.mouth >= MOUTH_ON
        done += 1
    if done == 0:
        report.add(Step("F1", "Ansikt per rute", "feil", "Fikk ingen bilder fra kilden."))
        return report
    share = {s: round(100 * found[s] / done) for s in sorted(found)}
    ok = {s: round(100 * usable[s] / done) for s in sorted(found)}
    worst = min(ok.values(), default=0)
    report.add(
        Step(
            "F1",
            "Ansikt per rute",
            "ok" if worst >= 90 else "advarsel",
            ", ".join(f"{s}: {share[s]} % funnet, {ok[s]} % brukbart" for s in share),
            {"runder": done, "funnet_pct": share, "brukbart_pct": ok},
        )
    )
    talk = {s: round(100 * talking[s] / done) for s in sorted(talking)}
    report.add(
        Step(
            "F2",
            "Munn i bevegelse",
            "ok",
            ", ".join(f"{s}: {talk[s]} %" for s in talk) + " av rundene",
            {"munn_pct": talk, "grense": MOUTH_ON},
        )
    )
    mean, top = statistics.fmean(times), max(times)
    budget = 1000 / FACES_HZ
    report.add(
        Step(
            "F3",
            "Tid per runde",
            "ok" if top < budget else "advarsel",
            f"snitt {mean:.1f} ms, høyest {top:.1f} ms (grense {budget:.0f} ms)",
            {"snitt_ms": round(mean, 1), "maks_ms": round(top, 1)},
        )
    )
    return report


def main(site_dir: Path, file: Path, rounds: int, out: Path) -> int:
    site = load_site(site_dir)
    if site.multiview is None:
        print("Studioet har ikke noe rutekart (equipment/multiview_map.yaml).")
        return 2
    analyzer = load_faces(MODELS)
    if analyzer is None:
        print("Ansiktsmodellen mangler: kjør tools/fetch_models.py, og installer «vision».")
        return 2
    source = OpenCvSource(str(file), loop=False)
    try:
        report = measure(Vision(site.multiview), source, analyzer, rounds)
    finally:
        source.close()
    js, md = report.write(out)
    print("\n" + report.to_markdown())
    print(f"Rapport: {md} (lim inn i GitHub-issue P6) og {js}")
    return 0 if report.result != "feil" else 1
