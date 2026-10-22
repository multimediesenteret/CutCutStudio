"""The 72-hour test (SO-8, spec 10.4): growth after the first hour, restarts, lost connections
and health, from samples; and the probe that reads CutCut and psutil."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from cutcut.hwtest.soak import CutCutProbe, ProcSample, Sample, analyze, run

T0 = datetime(2026, 11, 2, 9, 0).astimezone()
H = 3600.0


def series(
    hours: float = 72,
    every_min: float = 10,
    rss: dict[str, float] | None = None,
    leak_mb_per_h: dict[str, float] | None = None,
) -> list[Sample]:
    rss = rss or {"core": 300.0, "vision": 900.0, "audio-capture": 120.0}
    leak = leak_mb_per_h or {}
    out = []
    n = int(hours * 60 / every_min) + 1
    for i in range(n):
        t = i * every_min * 60
        procs = {
            name: ProcSample(
                pid=100 + k, rss_mb=base + leak.get(name, 0.0) * t / H, handles=400, uptime_s=int(t)
            )
            for k, (name, base) in enumerate(rss.items())
        }
        out.append(Sample(t, procs, "ok"))
    return out


def step(samples: list[Sample], sid: str) -> Any:
    report = analyze(samples, T0, 72)
    return next(s for s in report.steps if s.id == sid)


def test_a_steady_studio_passes() -> None:
    report = analyze(series(), T0, 72)
    assert report.result == "ok", report.to_markdown()


def test_a_slow_leak_is_found() -> None:
    d1 = step(series(leak_mb_per_h={"vision": 1.0}), "D1")  # 900 MB → ~970 MB
    assert d1.result == "feil"
    assert "vision" in d1.summary
    assert d1.details["vision"]["vekst_pct"] > 5


def test_a_small_process_may_wobble_a_few_mb() -> None:
    d1 = step(series(rss={"audio-capture": 40.0}, leak_mb_per_h={"audio-capture": 0.05}), "D1")
    assert d1.result == "ok"  # 40 → ~43 MB is over 5 %, but under the 10 MB slack


def test_the_first_hour_does_not_count() -> None:
    samples = series()
    for s in samples[:6]:  # models and caches load in the first hour
        s.procs["vision"] = ProcSample(101, 300.0, 400, int(s.t_s))
    assert step(samples, "D1").result == "ok"


def test_too_short_is_said_not_passed() -> None:
    d1 = step(series(hours=0.5), "D1")
    assert d1.result == "advarsel"
    assert "For kort" in d1.summary


def test_a_restart_is_found_by_a_new_pid() -> None:
    samples = series()
    for s in samples[200:]:
        p = s.procs["core"]
        s.procs["core"] = ProcSample(999, p.rss_mb, p.handles, int(s.t_s - samples[200].t_s))
    d3 = step(samples, "D3")
    assert d3.result == "feil"
    assert "core etter 33.3 t" in d3.summary


def test_a_lost_connection_is_reported_once() -> None:
    samples = series()
    for i in range(100, 103):
        samples[i] = Sample(samples[i].t_s, samples[i].procs, "error", ("H-ATEM-1",))
    d4 = step(samples, "D4")
    assert d4.result == "feil"
    assert d4.summary == "H-ATEM-1 etter 16.7 t"
    assert step(samples, "D5").result == "feil"


def test_no_samples_is_an_error() -> None:
    assert analyze([], T0, 72).result == "feil"


class Api:
    def __init__(self) -> None:
        self.answer = True

    def get(self, path: str) -> Any:
        if not self.answer:
            raise ConnectionError("nede")
        if path == "/api/health":
            procs = [
                {"name": "core", "running": True, "pid": os.getpid(), "uptime_s": 30},
                {"name": "vision", "running": False, "pid": None},
            ]
            return {"status": "warn", "runtime": {"processes": procs}}
        return [
            {"id": "H-ATEM-1", "status": "green"},
            {"id": "H-CAM-C2", "status": "red"},
            {"id": "H-PC-1", "status": "red"},  # not a connection
        ]


def test_the_probe_reads_cutcut_and_the_process() -> None:
    api = Api()
    s = CutCutProbe(api.get).sample(5.0)
    assert s.status == "warn"
    assert set(s.procs) == {"core"}
    assert s.procs["core"].pid == os.getpid()
    assert s.procs["core"].rss_mb > 10
    assert s.procs["core"].handles > 0
    assert s.down == ("H-CAM-C2",)
    api.answer = False
    assert CutCutProbe(api.get).sample(6.0).status == "ingen svar"


def test_run_samples_until_the_end_and_logs_each(tmp_path: Path) -> None:
    now = [0.0]
    api = Api()
    log = tmp_path / "soak.jsonl"

    def sleep(s: float) -> None:
        now[0] += s

    samples = run(
        CutCutProbe(api.get, pids=lambda pid: (100.0, 50)),
        hours=1,
        every_s=600,
        log=log,
        clock=lambda: now[0],
        sleep=sleep,
        say=lambda _: None,
    )
    assert [s.t_s for s in samples] == [i * 600.0 for i in range(7)]
    assert len(log.read_text("utf-8").splitlines()) == 7
