"""AU-6: the audio machine test, run against a simulated RØDECaster with a scripted technician."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from cutcut.audio.channels import MAIN_MIX, SAMPLE_RATE, mic_channel
from cutcut.common.ids import MicId
from cutcut.common.models.site import AudioDevice
from cutcut.hwtest.audio import AudioTest
from tests.unit.audio.test_device import FakeSd, FakeStream

M1, M2 = MicId.M1, MicId.M2


class Rodecaster:
    """A RØDECaster on a timeline: who talks, which mic is muted, whether USB is in."""

    def __init__(self, *, wasapi_ok: bool = True, swapped: bool = False, pre_fader: bool = True):
        self.sd = FakeSd()
        self.sd.fail_open["Windows WASAPI"] = not wasapi_ok
        self.t = 0.0
        self.talking: MicId | None = None
        self.muted: set[MicId] = set()
        self.unplugged = False
        self.swapped = swapped  # M1 and M2 faders swapped: wrong channel map
        self.pre_fader = pre_fader
        self.rng = np.random.default_rng(4)
        self.xrun_at: float | None = None

    def clock(self) -> float:
        return self.t

    def sleep(self, dt: float) -> None:
        end = self.t + dt
        while self.t < end:
            self.t += 256 / SAMPLE_RATE
            if self.unplugged:
                continue
            for s in self.sd.streams:
                if s.active:
                    self._push(s)

    def _push(self, s: FakeStream) -> None:
        n = 256
        data = (self.rng.standard_normal((n, 20)) * 10 ** (-70 / 20)).astype(np.float32)
        if self.talking is not None:
            ph = 2 * np.pi * 150 * (self.t + np.arange(n) / SAMPLE_RATE)
            voice = (0.1 * np.sin(ph)).astype(np.float32)
            mic = self.talking
            if self.swapped and mic in (M1, M2):
                mic = M2 if mic is M1 else M1
            ch = mic_channel(mic)
            if mic not in self.muted or self.pre_fader:
                data[:, ch] += voice
            for other in MicId:
                if mic_channel(other) != ch:
                    data[:, mic_channel(other)] += voice * 0.05
            if mic not in self.muted:
                for m in MAIN_MIX:
                    data[:, m] += voice * 0.7
        status: dict[str, bool] = {}
        if self.xrun_at is not None and self.t >= self.xrun_at:
            status["input_overflow"], self.xrun_at = True, None
        s.kw["callback"](data, n, None, type("S", (), status)() if status else None)


class Technician:
    """Answers the prompts and does what they say to the simulated studio."""

    def __init__(self, rode: Rodecaster, skip: tuple[str, ...] = ()) -> None:
        self.rode = rode
        self.skip = skip
        self.said: list[str] = []

    def say(self, text: str) -> None:
        self.said.append(text)
        if "Skru av MUTE" in text:
            self.rode.muted.clear()
            self.rode.talking = None

    def wait(self, text: str) -> bool:
        self.said.append(text)
        if any(s in text for s in self.skip):
            return False
        r = self.rode
        if "Be personen ved" in text:
            r.talking = MicId(text.split("ved ")[1][:2])
        elif "Trekk USB" in text:
            r.talking, r.unplugged = None, True
        elif "Sett kabelen inn" in text:
            r.unplugged = False
        elif "Trykk MUTE" in text:
            r.muted.add(M1)
            r.talking = M1
        return True


def run(rode: Rodecaster, minutes: float = 0.5, **kw: Any) -> AudioTest:
    test = AudioTest(
        AudioDevice(),
        [M1, M2],
        Technician(rode, **kw),
        minutes=minutes,
        sd=rode.sd,
        clock=rode.clock,
        sleep=rode.sleep,
    )
    test.run()
    return test


def steps(test: AudioTest) -> dict[str, Any]:
    return {s.id: s for s in test.report.steps}


def test_a_healthy_rodecaster_passes_everything(tmp_path: Path) -> None:
    rode = Rodecaster()
    rode.xrun_at = 30.0
    test = run(rode)
    got = steps(test)
    assert {k: v.result for k, v in got.items()} == {
        "A1": "ok",
        "A2": "ok",
        "A3": "ok",
        "A4": "advarsel",
        "A5": "ok",
        "A6": "ok",
        "A7": "ok",
    }
    assert got["A2"].details["M2"]["loudest_channel"] == 5  # 1-based, like the RØDECaster
    assert got["A3"].details["lag_ms"] == 0.0
    assert got["A4"].details["xruns"] == 1
    assert got["A5"].details["back_s"] <= 6
    assert got["A6"].summary.startswith("Ja:")  # pre-fader carries the muted voice
    assert got["A6"].answers == "Q24"
    js, md = test.report.write(tmp_path)
    assert json.loads(js.read_text())["result"] == "advarsel"
    text = md.read_text()
    assert "| A6 Dempet mic (Q24) | ✅ ok |" in text
    assert "**Svar på Q24.**" in text


def test_swapped_faders_are_found() -> None:
    got = steps(run(Rodecaster(swapped=True), minutes=0))
    assert got["A2"].result == "feil"
    assert "M1 sterkest på kanal 5 (ventet 3)" in got["A2"].summary
    assert got["A4"].result == "hoppet over"


def test_post_fader_answers_q24_no() -> None:
    got = steps(run(Rodecaster(pre_fader=False), minutes=0))
    assert got["A6"].summary.startswith("Nei:")


def test_no_rodecaster_skips_the_rest() -> None:
    rode = Rodecaster()
    rode.sd.devices = rode.sd.devices[:1]
    test = run(rode)
    assert [(s.id, s.result) for s in test.report.steps][:2] == [
        ("A1", "feil"),
        ("A2", "hoppet over"),
    ]
    assert test.report.result == "feil"


def test_wasapi_only_is_a_warning_and_steps_can_be_skipped() -> None:
    rode = Rodecaster()
    rode.sd.devices = [d for d in rode.sd.devices if d["hostapi"] != 1]  # no ASIO driver
    got = steps(run(rode, minutes=0, skip=("Trekk USB", "Trykk MUTE")))
    assert got["A1"].result == "advarsel"
    assert got["A1"].answers == "Q21"
    assert got["A2"].result == "ok"
    assert got["A5"].result == "hoppet over"
    assert got["A6"].result == "hoppet over"
