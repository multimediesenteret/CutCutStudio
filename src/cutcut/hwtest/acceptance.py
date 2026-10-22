"""The acceptance criteria in spec 10.4 that can be measured from what CutCut wrote down.

``cutcut hwtest akseptanse --since "2026-11-04 09:00" [--until …] [--data C:\\CutCut\\data]``
reads the decisions in the database (kept 30 days) and, when feilsøkingsmodus was on, the
recording in ``data\\debug`` (the time of each Companion press). Nothing is sent anywhere, and
CutCut may run while it reads.

| Step | Criterion (10.4) | From |
| --- | --- | --- |
| A1 | A cut reaches Companion within 150 ms of the decision (95 %, and the slowest) | recording |
| A2 | At least 90 % of the speaker cuts on cut point ``K1`` or ``K2``, not ``K3`` | decisions |
| A3 | Preview shows the next picture 300 ms or more before it is taken, in 95 % | decisions |
| A4 | No cut back to the previous picture within 4 s (``H2``) | decisions |
| A5 | Cuts per 10 minutes and manual overrides, for the operator's judgement (Q2) | decisions |

Run it after each test broadcast in the studio period (``docs/studio/testdag.md`` 4 and 7).
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

from cutcut.app.debugrec import read
from cutcut.hwtest.report import Report, Step

SPEAKER_RULES: Final = frozenset({"T2", "T4", "H1"})
CUT_MAX_MS: Final = 150.0
CUT_POINT_SHARE: Final = 0.90
PREVIEW_MIN_MS: Final = 300.0
PREVIEW_SHARE: Final = 0.95
BACK_MIN_MS: Final = 4000
MARGIN: Final = timedelta(days=1)


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f} %" if whole else "–"


def analyze(
    decisions: Sequence[dict[str, Any]],
    presses: Sequence[dict[str, Any]],
    since: datetime,
    until: datetime,
) -> Report:
    report = Report("akseptanse", datetime.now().astimezone())
    report.env["periode"] = f"{since:%Y-%m-%d %H:%M} – {until:%Y-%m-%d %H:%M}"
    live = [d for d in decisions if not d.get("shadow")]
    cuts = [d for d in live if d.get("action") == "cut"]
    speaker = [d for d in cuts if d.get("rule") in SPEAKER_RULES]

    # A1 – the time from the engine's decision until Companion had answered
    takes = [
        float(p["ms"]) for p in presses if str(p.get("label", "")).startswith(("take", "direkte"))
    ]
    if not takes:
        report.add(
            Step(
                "A1",
                "Kutt innen 150 ms",
                "hoppet over",
                "Ingen målinger: slå på feilsøkingsmodus (Helse) før testsendingen.",
            )
        )
    else:
        q95 = statistics.quantiles(takes, n=20)[-1] if len(takes) >= 2 else takes[0]
        ok = q95 <= CUT_MAX_MS
        report.add(
            Step(
                "A1",
                "Kutt innen 150 ms",
                "ok" if ok else "feil",
                f"{len(takes)} kutt: 95 % innen {q95:.0f} ms, tregeste {max(takes):.0f} ms",
                {"antall": len(takes), "p95_ms": round(q95, 1), "maks_ms": round(max(takes), 1)},
            )
        )

    # A2 – cut point K1 or K2
    if not speaker:
        report.add(Step("A2", "Kuttpunkt K1/K2", "hoppet over", "Ingen taler-kutt i perioden."))
    else:
        good = [d for d in speaker if (d.get("measures") or {}).get("cut_point") in (1, 2)]
        share = len(good) / len(speaker)
        report.add(
            Step(
                "A2",
                "Kuttpunkt K1/K2",
                "ok" if share >= CUT_POINT_SHARE else "feil",
                f"{len(good)} av {len(speaker)} taler-kutt ({_pct(len(good), len(speaker))}) på "
                "K1 eller K2 (krav 90 %)",
                {"andel": round(share, 3), "antall": len(speaker)},
            )
        )

    # A3 – preview before take
    if not speaker:
        report.add(Step("A3", "Preview før TAKE", "hoppet over", "Ingen taler-kutt i perioden."))
    else:
        good = [
            d for d in speaker if (d.get("measures") or {}).get("preview_ms", 0) >= PREVIEW_MIN_MS
        ]
        share = len(good) / len(speaker)
        report.add(
            Step(
                "A3",
                "Preview før TAKE",
                "ok" if share >= PREVIEW_SHARE else "feil",
                f"{_pct(len(good), len(speaker))} av taler-kuttene hadde preview i minst 300 ms "
                "(krav 95 %)",
                {"andel": round(share, 3)},
            )
        )

    # A4 – no cut back to the previous picture within 4 s
    auto = [d for d in cuts if d.get("rule") != "MANUAL"]
    backs = []
    for a, b, c in zip(auto, auto[1:], auto[2:], strict=False):
        if c.get("shot") == a.get("shot") and int(c["mono_ms"]) - int(b["mono_ms"]) < BACK_MIN_MS:
            backs.append(f"{c.get('ts', '')[11:19]} {c.get('shot')}")
    report.add(
        Step(
            "A4",
            "Ingen kutt tilbake innen 4 s",
            "ok" if not backs else "feil",
            "Ingen" if not backs else f"{len(backs)}: " + ", ".join(backs[:5]),
            {"tilbake": backs},
        )
    )

    # A5 – for the operator: how much it cut, and how often a person took over
    minutes = max((until - since).total_seconds() / 60, 1.0)
    manual = [d for d in live if d.get("rule") == "MANUAL"]
    report.add(
        Step(
            "A5",
            "Kutt og overstyringer",
            "ok",
            f"{len(cuts)} kutt ({10 * len(cuts) / minutes:.1f} per 10 min), "
            f"{len(manual)} overstyringer av en person",
            {
                "kutt": len(cuts),
                "per_10_min": round(10 * len(cuts) / minutes, 1),
                "overstyringer": len(manual),
            },
        )
    )
    return report


def load_decisions(db: Path, since: datetime, until: datetime) -> list[dict[str, Any]]:
    # ts is stored with the PC's UTC offset, which changes with summer time: read a day
    # around the period as text, then compare real times
    con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT data FROM decisions WHERE ts >= ? AND ts <= ? ORDER BY id",
            ((since - MARGIN).isoformat(), (until + MARGIN).isoformat()),
        ).fetchall()
    finally:
        con.close()
    out = [json.loads(r[0]) for r in rows]
    return [d for d in out if since <= datetime.fromisoformat(d["ts"]) <= until]


def load_presses(folder: Path, since: datetime, until: datetime) -> list[dict[str, Any]]:
    lo, hi = (since - MARGIN).isoformat()[:13], (until + MARGIN).isoformat()[:13]
    files = [f for f in sorted(folder.glob("*.jsonl.gz")) if lo <= f.name[:13] <= hi]
    out = []
    for r in read(files):
        if r.get("kind") == "press":
            t = datetime.fromisoformat(str(r["t"]))
            if since <= t <= until:
                out.append(r)
    return out


def _when(text: str | None, default: datetime) -> datetime:
    if not text:
        return default
    t = datetime.fromisoformat(text)
    return t if t.tzinfo else t.astimezone()


def main(data: Path | None, since: str | None, until: str | None, out: Path) -> int:
    from cutcut.app.core import default_data_dir

    if data is None:
        studio_pc = Path(r"C:\CutCut\data")
        data = studio_pc if studio_pc.exists() else default_data_dir()
    db = data / "cutcut.db"
    if not db.exists():
        print(f"Fant ikke databasen {db}. Oppgi mappen med --data.")
        return 2
    now = datetime.now().astimezone()
    t_until = _when(until, now)
    t_since = _when(since, t_until.replace(hour=0, minute=0, second=0, microsecond=0))
    report = analyze(
        load_decisions(db, t_since, t_until),
        load_presses(data / "debug", t_since, t_until),
        t_since,
        t_until,
    )
    js, md = report.write(out)
    print("\n" + report.to_markdown())
    print(f"Rapport: {md} (lim inn i GitHub-issue T-M3) og {js}")
    return 0 if report.result != "feil" else 1
