"""Machine test for the Epiphan Pearl (SE-2, SE-3, spec 7.4 and 10.4).

``cutcut hwtest pearl --site C:\\CutCut\\site`` talks to the Pearl with the same client as
CutCut, with the password from Credential Manager (``pearl_password``):

| Step | What | Passed when |
| --- | --- | --- |
| P1 | Pearl answers, firmware, how fast | answers within 1 s |
| P2 | The recorder in ``devices.yaml`` exists, and its state | not in error |
| P3 | Storage: free space | over 10 % free |
| P4 | A 5 s test recording: start, wait, stop (asks first) | starts within 10 s, stops |
| P5 | With ``--user``: CutCut records, a person stops it on the Pearl | alarm within 5 s |

P4 and P5 are never done while the recorder is already recording: CutCut never stops a
recording someone else started (I7).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol

from cutcut.common.config import load_site
from cutcut.common.models.session import RecordingStatus
from cutcut.devices.pearl.client import PearlError, RecorderInfo, StorageInfo
from cutcut.hwtest.audio import ConsoleOperator, Operator
from cutcut.hwtest.report import Report, Step

ANSWER_MAX_S: Final = 1.0
START_MAX_S: Final = 10.0
TEST_RECORDING_S: Final = 5.0
ALARM_MAX_S: Final = 5.0
FREE_MIN: Final = 0.10
BUSY: Final = (RecordingStatus.STARTING, RecordingStatus.STARTED)


class Pearl(Protocol):
    def firmware(self) -> str: ...
    def recorder_status(self, rid: str) -> RecorderInfo: ...
    def storages(self) -> list[StorageInfo]: ...
    def start(self, rid: str) -> None: ...
    def stop(self, rid: str) -> None: ...


class CutCutApi(Protocol):
    """The parts of CutCut's API the P5 step uses (an ``httpx.Client`` signed in)."""

    def get(self, url: str) -> Any: ...
    def post(self, url: str, *, json: Any = None) -> Any: ...
    def delete(self, url: str) -> Any: ...


@dataclass
class PearlTest:
    pearl: Pearl
    recorder: str
    op: Operator
    api: CutCutApi | None = None
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    report: Report = field(default_factory=lambda: Report("pearl", datetime.now().astimezone()))

    def run(self) -> Report:
        if not self.step_answer():
            return self.report
        state = self.step_recorder()
        self.step_storage()
        if state in BUSY:
            why = "Opptakeren tar opp nå; CutCut rører aldri et opptak noen andre har startet (I7)."
            self.report.add(Step("P4", "Testopptak", "hoppet over", why))
            self.report.add(Step("P5", "Stopp uten trykk", "hoppet over", why))
            return self.report
        self.step_test_recording()
        self.step_unasked_stop()
        return self.report

    def _wait_for(self, want: set[RecordingStatus], within_s: float) -> float | None:
        t0 = self.clock()
        while self.clock() - t0 <= within_s:
            if self.pearl.recorder_status(self.recorder).state in want:
                return self.clock() - t0
            self.sleep(0.2)
        return None

    def step_answer(self) -> bool:
        t0 = self.clock()
        try:
            fw = self.pearl.firmware()
        except PearlError as exc:
            self.report.add(Step("P1", "Pearl svarer", "feil", str(exc)))
            return False
        dt = self.clock() - t0
        ok = dt <= ANSWER_MAX_S
        self.report.add(
            Step(
                "P1",
                "Pearl svarer",
                "ok" if ok else "advarsel",
                f"Fastvare {fw}, svar på {dt * 1000:.0f} ms",
                {"firmware": fw, "svar_ms": round(dt * 1000)},
            )
        )
        return True

    def step_recorder(self) -> RecordingStatus | None:
        try:
            info = self.pearl.recorder_status(self.recorder)
        except PearlError as exc:
            self.report.add(Step("P2", "Opptaker", "feil", f"Opptaker {self.recorder}: {exc}"))
            return None
        bad = info.state is RecordingStatus.ERROR
        text = f"Opptaker {self.recorder}: {info.state.value}"
        if info.description:
            text += f" ({info.description})"
        self.report.add(Step("P2", "Opptaker", "feil" if bad else "ok", text))
        return info.state

    def step_storage(self) -> None:
        try:
            disks = self.pearl.storages()
        except PearlError as exc:
            self.report.add(Step("P3", "Lagring", "feil", str(exc)))
            return
        if not disks:
            self.report.add(Step("P3", "Lagring", "feil", "Pearl melder ingen lagring."))
            return
        best = max(disks, key=lambda d: d.free_share)
        gb = best.free_bytes / 1e9
        ok = best.free_share >= FREE_MIN
        self.report.add(
            Step(
                "P3",
                "Lagring",
                "ok" if ok else "advarsel",
                f"{best.id}: {gb:.0f} GB ledig ({best.free_share * 100:.0f} %)",
                {
                    "lagring": best.id,
                    "ledig_gb": round(gb),
                    "ledig_andel": round(best.free_share, 3),
                },
            )
        )

    def step_test_recording(self) -> None:
        if not self.op.wait("P4: et testopptak på 5 s startes og stoppes på Pearl. Klart?"):
            self.report.add(Step("P4", "Testopptak", "hoppet over", "Valgt bort."))
            return
        try:
            self.pearl.start(self.recorder)
            started = self._wait_for({RecordingStatus.STARTED}, START_MAX_S)
            if started is None:
                self.report.add(
                    Step("P4", "Testopptak", "feil", f"Startet ikke innen {START_MAX_S:.0f} s.")
                )
                return
            self.sleep(TEST_RECORDING_S)
            self.pearl.stop(self.recorder)
            stopped = self._wait_for({RecordingStatus.STOPPED}, START_MAX_S)
        except PearlError as exc:
            self.report.add(Step("P4", "Testopptak", "feil", str(exc)))
            return
        if stopped is None:
            self.report.add(Step("P4", "Testopptak", "feil", "Stoppet ikke; sjekk Pearl."))
            return
        self.report.add(
            Step(
                "P4",
                "Testopptak",
                "ok",
                f"Startet på {started:.1f} s, stoppet på {stopped:.1f} s. Sjekk at filen på "
                "5 s finnes i Pearls opptaksliste.",
                {"start_s": round(started, 2), "stopp_s": round(stopped, 2)},
            )
        )

    def step_unasked_stop(self) -> None:
        api = self.api
        if api is None:
            why = "Kjør med --user for å teste at CutCut varsler (10.4)."
            self.report.add(Step("P5", "Stopp uten trykk", "hoppet over", why))
            return
        if not self.op.wait(
            "P5: CutCut starter et opptak for «maskintest». Når det går, stopper du det på "
            "Pearl selv (nettsiden eller frontpanelet) og trykker Enter med en gang. Klart?"
        ):
            self.report.add(Step("P5", "Stopp uten trykk", "hoppet over", "Valgt bort."))
            return
        api.post("/api/session", json={"username": "maskintest", "display_name": "Maskintest"})
        try:
            api.post("/api/recording", json={"action": "start"})
            if self._wait_for({RecordingStatus.STARTED}, START_MAX_S) is None:
                self.report.add(
                    Step("P5", "Stopp uten trykk", "feil", "Opptaket startet ikke fra CutCut.")
                )
                return
            seen = {a.get("id") for a in _alerts(api)}
            self.op.wait("Stopp opptaket på Pearl nå, og trykk Enter med en gang.")
            t0 = self.clock()
            while self.clock() - t0 <= ALARM_MAX_S + 5:
                new = [a for a in _alerts(api) if a.get("id") not in seen]
                if any(a.get("code") == "H-PRL-2" for a in new):
                    dt = self.clock() - t0
                    self.report.add(
                        Step(
                            "P5",
                            "Stopp uten trykk",
                            "ok" if dt <= ALARM_MAX_S else "feil",
                            f"CutCut varslet etter {dt:.1f} s (krav {ALARM_MAX_S:.0f} s)",
                            {"varsel_s": round(dt, 1)},
                        )
                    )
                    return
                self.sleep(0.25)
            self.report.add(
                Step("P5", "Stopp uten trykk", "feil", "CutCut varslet ikke innen 10 s.")
            )
        finally:
            api.delete("/api/session")


def _alerts(api: CutCutApi) -> list[dict[str, Any]]:
    res = api.get("/api/health")
    alerts = res.json().get("alerts") if getattr(res, "status_code", 200) == 200 else None
    return [a for a in alerts or [] if isinstance(a, dict)]


def main(site_dir: Path, api_url: str | None, user: str | None, out: Path) -> int:
    from cutcut.app.core import pearl_api
    from cutcut.common.platform import get_platform
    from cutcut.hwtest.atem import cutcut_session

    site = load_site(site_dir)
    api = cutcut_session(site, api_url, user) if user else None
    if user and api is None:
        return 2
    devices = site.devices
    if api is not None:  # the addresses set in the technician window win over devices.yaml
        res = api.get("/api/settings/devices")
        if res.status_code == 200:
            for row in res.json().get("rows", []):
                if row.get("key") == "pearl.ip" and row.get("value"):
                    pearl_dev = devices.pearl.model_copy(update={"ip": row["value"]})
                    devices = devices.model_copy(update={"pearl": pearl_dev})
    pearl = pearl_api(devices, get_platform().secrets)
    print(f"Maskintest Pearl · {devices.pearl.ip} · opptaker {devices.pearl.recorder_id}")
    try:
        report = PearlTest(pearl, devices.pearl.recorder_id, ConsoleOperator(), api).run()
    finally:
        pearl.close()
    js, md = report.write(out)
    print("\n" + report.to_markdown())
    print(f"Rapport: {md} (lim inn i GitHub-issue SE-3) og {js}")
    return 0 if report.result != "feil" else 1
