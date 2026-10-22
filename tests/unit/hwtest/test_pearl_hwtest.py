"""The Pearl machine test (SE-3) against the fake Pearl over real HTTP, and the P5 step
(an unasked stop is alarmed within 5 s) against a fake CutCut API."""

from __future__ import annotations

from typing import Any

from cutcut.devices.pearl.client import PearlHttp
from cutcut.hwtest.pearl import PearlTest
from cutcut.sim.fake_pearl import FakePearlState, fake_pearl


class Yes:
    def __init__(self, answer: bool = True, on_wait: Any = None) -> None:
        self.answer, self.on_wait = answer, on_wait
        self.said: list[str] = []

    def say(self, text: str) -> None:
        self.said.append(text)

    def wait(self, text: str) -> bool:
        if self.on_wait is not None:
            self.on_wait(text)
        return self.answer


def run(state: FakePearlState, op: Yes, api: Any = None) -> Any:
    with fake_pearl(state) as (url, _):
        pearl = PearlHttp(url, state.username, state.password)
        try:
            return PearlTest(pearl, "1", op, api, sleep=lambda s: None).run()
        finally:
            pearl.close()


def by_id(report: Any) -> dict[str, Any]:
    return {s.id: s for s in report.steps}


def test_a_healthy_pearl_passes_and_records_5_s() -> None:
    state = FakePearlState(start_delay_s=0.0)
    steps = by_id(run(state, Yes()))
    assert steps["P1"].result == "ok"
    assert "4.24.1" in steps["P1"].summary
    assert steps["P2"].result == "ok"
    assert steps["P3"].result == "ok"
    assert steps["P4"].result == "ok"
    assert state.commands  # started and stopped
    assert steps["P5"].result == "hoppet over"  # no --user
    assert state.recorders["1"] == "stopped"


def test_a_running_recording_is_never_touched() -> None:
    state = FakePearlState(recorders={"1": "started"}, started_at={"1": 0.0})
    steps = by_id(run(state, Yes()))
    assert steps["P4"].result == "hoppet over"
    assert "I7" in steps["P4"].summary
    assert state.recorders["1"] == "started"
    assert not state.commands


def test_wrong_password_is_a_clear_error() -> None:
    state = FakePearlState()
    with fake_pearl(state) as (url, _):
        pearl = PearlHttp(url, state.username, "feil")
        report = PearlTest(pearl, "1", Yes(), sleep=lambda s: None).run()
        pearl.close()
    assert report.result == "feil"
    assert "passord" in report.steps[0].summary


def test_a_full_disk_warns() -> None:
    state = FakePearlState(free_bytes=10_000_000_000)
    assert by_id(run(state, Yes(answer=False)))["P3"].result == "advarsel"


class Api:
    """CutCut as P5 sees it: start a session and a recording, and alarm when Pearl stops."""

    class Res:
        def __init__(self, body: Any) -> None:
            self.status_code, self.body = 200, body

        def json(self) -> Any:
            return self.body

    def __init__(self, pearl: FakePearlState, alarm: bool) -> None:
        self.pearl, self.alarm = pearl, alarm
        self.calls: list[tuple[str, str]] = []

    def post(self, url: str, *, json: Any = None) -> Any:
        self.calls.append(("POST", url))
        if url == "/api/recording":
            self.pearl.recorders["1"] = "started"
        return self.Res({"ok": True})

    def delete(self, url: str) -> Any:
        self.calls.append(("DELETE", url))
        return self.Res({"ok": True})

    def get(self, url: str) -> Any:
        stopped = self.pearl.recorders["1"] == "stopped"
        alerts = [{"id": 1, "code": "SESSION"}]
        if stopped and self.alarm:
            alerts.append({"id": 2, "code": "H-PRL-2"})
        return self.Res({"alerts": alerts})


def test_P5_an_unasked_stop_is_alarmed_in_time() -> None:
    state = FakePearlState(start_delay_s=0.0)
    api = Api(state, alarm=True)

    def person(text: str) -> None:
        if "nå" in text:
            state.stop_by_itself()

    steps = by_id(run(state, Yes(on_wait=person), api))
    assert steps["P5"].result == "ok"
    assert ("DELETE", "/api/session") in api.calls


def test_P5_no_alarm_fails() -> None:
    state = FakePearlState(start_delay_s=0.0)

    def person(text: str) -> None:
        if "nå" in text:
            state.stop_by_itself()

    clock = iter(range(0, 10_000))
    with fake_pearl(state) as (url, _):
        pearl = PearlHttp(url, state.username, state.password)
        test = PearlTest(
            pearl,
            "1",
            Yes(on_wait=person),
            Api(state, alarm=False),
            clock=lambda: float(next(clock)),
            sleep=lambda s: None,
        )
        report = test.run()
        pearl.close()
    assert by_id(report)["P5"].result == "feil"
