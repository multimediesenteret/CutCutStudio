"""The 72-hour test (spec 10.4, SO-8): does CutCut run for days without growing or losing things?

``cutcut hwtest soak --site C:\\CutCut\\site --hours 72`` runs next to the CutCut service and
measures every 10 minutes, without signing in and without changing anything:

| Step | What | Passed when |
| --- | --- | --- |
| D1 | Memory per process (RSS, with its child processes) | under 5 % growth after the first hour |
| D2 | Handles per process (Windows; open files elsewhere) | under 5 % growth after the first hour |
| D3 | Restarts: a process with a new pid, or a shorter uptime | none |
| D4 | Connections: ATEM, Companion, Pearl, cameras and sound (``H-…`` checks) | none lost |
| D5 | Health: the overall status from ``/api/health`` | green or yellow in every sample |

Every sample is also written as a line of JSON as it is taken, so a test that is stopped half
way still has its numbers. The process list (with pids) comes from the supervisor through
``/api/health``; the numbers come from psutil on the same PC.
"""

from __future__ import annotations

import itertools
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol

from cutcut.hwtest.report import Report, Result, Step

GROWTH_MAX_PCT: Final = 5.0
RSS_SLACK_MB: Final = 10.0  # a small process may grow a few MB without it being a leak
HANDLE_SLACK: Final = 50
WARMUP_S: Final = 3600.0  # the first hour is not counted: caches and models are filling up
CONNECTIONS: Final = ("H-ATEM-1", "H-COMP-1", "H-PRL-1", "H-CAM-", "H-AUD-1")


@dataclass(frozen=True)
class ProcSample:
    pid: int
    rss_mb: float
    handles: int
    uptime_s: int = 0


@dataclass(frozen=True)
class Sample:
    t_s: float  # seconds since the test started
    procs: dict[str, ProcSample]
    status: str  # ok, warn, error, or «ingen svar» when CutCut did not answer
    down: tuple[str, ...] = ()  # connection checks that are not green

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class Probe(Protocol):
    def sample(self, t_s: float) -> Sample: ...


# -- the analysis (pure) -------------------------------------------------------------------


def _growth(values: Sequence[float]) -> tuple[float, float, float]:
    """Start (first sample after warm-up), end (mean of the last three), growth in %."""
    start = values[0]
    end = sum(values[-3:]) / len(values[-3:])
    pct = 100.0 * (end - start) / start if start > 0 else 0.0
    return start, end, pct


def _growth_step(
    sid: str, title: str, samples: Sequence[Sample], what: str, unit: str, slack: float
) -> Step:
    after = [s for s in samples if s.t_s >= WARMUP_S]
    if len(after) < 3:
        hours = samples[-1].t_s / 3600 if samples else 0.0
        return Step(
            sid,
            title,
            "advarsel",
            f"For kort til å vurdere vekst: {hours:.1f} t (trenger over 1 t)",
        )
    names = sorted({n for s in after for n in s.procs})
    parts: list[str] = []
    details: dict[str, Any] = {}
    result: Result = "ok"
    for name in names:
        values = [float(getattr(s.procs[name], what)) for s in after if name in s.procs]
        if len(values) < 3:
            continue
        start, end, pct = _growth(values)
        grew = pct >= GROWTH_MAX_PCT and end - start >= slack
        if grew:
            result = "feil"
        details[name] = {
            "start": round(start, 1),
            "slutt": round(end, 1),
            "vekst_pct": round(pct, 1),
        }
        mark = " ❌" if grew else ""
        parts.append(f"{name}: {start:.0f} → {end:.0f} {unit} ({pct:+.1f} %){mark}")
    details["grense_pct"] = GROWTH_MAX_PCT
    return Step(sid, title, result, "; ".join(parts) or "ingen prosesser målt", details)


def _restarts(samples: Sequence[Sample]) -> Step:
    events: list[str] = []
    for prev, cur in itertools.pairwise(samples):
        for name, p in cur.procs.items():
            q = prev.procs.get(name)
            if q is not None and (p.pid != q.pid or p.uptime_s < q.uptime_s):
                events.append(f"{name} etter {cur.t_s / 3600:.1f} t")
    if not events:
        return Step("D3", "Omstarter", "ok", "Ingen prosess startet på nytt")
    return Step("D3", "Omstarter", "feil", ", ".join(events), {"omstarter": events})


def _connections(samples: Sequence[Sample]) -> Step:
    lost: list[str] = []
    for prev, cur in itertools.pairwise(samples):
        for check in cur.down:
            if check not in prev.down:
                lost.append(f"{check} etter {cur.t_s / 3600:.1f} t")
    first = samples[0].down if samples else ()
    if first:
        lost = [f"{c} fra start" for c in first] + lost
    if not lost:
        return Step("D4", "Tilkoblinger", "ok", "Ingen tilkobling tapt")
    return Step("D4", "Tilkoblinger", "feil", ", ".join(lost), {"tapt": lost})


def _health(samples: Sequence[Sample]) -> Step:
    bad = [s for s in samples if s.status not in ("ok", "warn")]
    n = len(samples)
    if not bad:
        return Step("D5", "Helse", "ok", f"Grønn eller gul i alle {n} målinger")
    when = ", ".join(f"{s.status} etter {s.t_s / 3600:.1f} t" for s in bad[:5])
    more = f" (og {len(bad) - 5} til)" if len(bad) > 5 else ""
    return Step("D5", "Helse", "feil", f"{len(bad)} av {n} målinger: {when}{more}")


def analyze(samples: Sequence[Sample], started: datetime, hours: float) -> Report:
    report = Report("72-timer", started, env={"timer": f"{hours:g}"})
    if not samples:
        report.add(Step("D1", "Minne", "feil", "Ingen målinger: svarte CutCut på /api/health?"))
        return report
    report.add(_growth_step("D1", "Minne per prosess", samples, "rss_mb", "MB", RSS_SLACK_MB))
    report.add(_growth_step("D2", "Håndtak per prosess", samples, "handles", "", HANDLE_SLACK))
    report.add(_restarts(samples))
    report.add(_connections(samples))
    report.add(_health(samples))
    return report


# -- measuring (CutCut on this PC) ---------------------------------------------------------


def _is_connection(check_id: str) -> bool:
    return any(check_id == c or (c.endswith("-") and check_id.startswith(c)) for c in CONNECTIONS)


@dataclass
class CutCutProbe:
    """Reads ``/api/health`` and ``/api/health/checks`` (no sign-in), and psutil per pid."""

    get: Callable[[str], Any]  # GET a path, return the JSON (or raise)
    pids: Callable[[int], tuple[float, int] | None] = field(default=lambda pid: _ps(pid))

    def sample(self, t_s: float) -> Sample:
        try:
            health = self.get("/api/health")
            checks = self.get("/api/health/checks")
        except Exception:
            return Sample(t_s, {}, "ingen svar")
        procs: dict[str, ProcSample] = {}
        for p in (health.get("runtime") or {}).get("processes") or []:
            pid = p.get("pid")
            if not p.get("running") or not isinstance(pid, int):
                continue
            got = self.pids(pid)
            if got is not None:
                rss, handles = got
                procs[str(p["name"])] = ProcSample(pid, rss, handles, int(p.get("uptime_s") or 0))
        down = tuple(
            sorted(c["id"] for c in checks if _is_connection(c["id"]) and c["status"] != "green")
        )
        return Sample(t_s, procs, str(health.get("status", "?")), down)


def _ps(pid: int) -> tuple[float, int] | None:
    """RSS in MB and handles (open files outside Windows) for a process and its children."""
    import psutil

    try:
        root = psutil.Process(pid)
        rss = 0.0
        handles = 0
        for p in [root, *root.children(recursive=True)]:
            with p.oneshot():
                rss += p.memory_info().rss / 1e6
                if hasattr(p, "num_handles"):
                    handles += p.num_handles()
                else:
                    handles += p.num_fds()
        return round(rss, 1), handles
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def run(
    probe: Probe,
    hours: float,
    every_s: float,
    log: Path,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    say: Callable[[str], None] = print,
) -> list[Sample]:
    samples: list[Sample] = []
    t0 = clock()
    end = hours * 3600
    with log.open("a", encoding="utf-8") as f:
        while True:
            t = clock() - t0
            s = probe.sample(t)
            samples.append(s)
            f.write(s.to_json() + "\n")
            f.flush()
            mem = sum(p.rss_mb for p in s.procs.values())
            down = f", nede: {', '.join(s.down)}" if s.down else ""
            say(f"{t / 3600:6.2f} t · {s.status} · {len(s.procs)} prosesser · {mem:.0f} MB{down}")
            if t >= end:
                return samples
            sleep(min(every_s, max(end - t, 0.0)) or every_s)


def main(
    site_dir: Path | None, api_url: str | None, hours: float, every_min: float, out: Path
) -> int:
    import httpx

    from cutcut.common.config import load_site

    port = load_site(site_dir).devices.api_port if site_dir is not None else 8080
    api = httpx.Client(
        base_url=api_url or f"http://127.0.0.1:{port}", timeout=10.0, trust_env=False
    )

    def get(path: str) -> Any:
        r = api.get(path)
        r.raise_for_status()
        return r.json()

    started = datetime.now().astimezone()
    out.mkdir(parents=True, exist_ok=True)
    log = out / f"72-timer-{started:%Y%m%d-%H%M}.jsonl"
    print(f"72-timerstest i {hours:g} t, måling hvert {every_min:g}. min. Målingene: {log}")
    print("Avbryt med Ctrl+C: rapporten skrives likevel med det som er målt.")
    samples: list[Sample] = []
    try:
        samples = run(CutCutProbe(get), hours, every_min * 60, log)
    except KeyboardInterrupt:
        samples = [
            Sample(**_revive(json.loads(line))) for line in log.read_text("utf-8").splitlines()
        ]
        print("Avbrutt.")
    finally:
        api.close()
    report = analyze(samples, started, hours)
    js, md = report.write(out)
    print("\n" + report.to_markdown())
    print(f"Rapport: {md} (lim inn i GitHub-issue SO-8) og {js}")
    return 0 if report.result != "feil" else 1


def _revive(raw: dict[str, Any]) -> dict[str, Any]:
    raw["procs"] = {k: ProcSample(**v) for k, v in raw["procs"].items()}
    raw["down"] = tuple(raw.get("down") or ())
    return raw
