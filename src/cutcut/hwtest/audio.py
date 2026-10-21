"""Machine test for the RØDECaster (AU-6, docs/research/lyd-fra-rodecaster.md, steps 1–7).

``cutcut hwtest audio --site site/ntnu-studio`` – the technician follows the prompts (talk in
mic N, pull the USB cable …); the report answers Q21 (ASIO stable with 20 channels), Q24 (is a
muted mic on its pre-fader track?) and ADR-0014. No raw audio is kept unless ``--save-wav``.

| Step | What |
| --- | --- |
| A1 | The RØDECaster is found, on ASIO and/or WASAPI, with enough channels |
| A2 | Channel map: each person talks; their own channel must be the loudest |
| A3 | Sync: the mic and the main mix line up (lag in ms) |
| A4 | Stability for N minutes: over/underflows, stalls, frames lost |
| A5 | Recovery after the USB cable is pulled and put back |
| A6 | Q24: a muted mic – is it still on the multitrack? Is it gone from the main mix? |
| A7 | The WASAPI reserve delivers sound |
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol

import numpy as np

from cutcut.audio.backend import write_wav
from cutcut.audio.channels import MAIN_MIX, SAMPLE_RATE, mic_channel
from cutcut.audio.device import HOSTAPI, DeviceBackend, NoDeviceError, find_device, load_sounddevice
from cutcut.audio.dsp import rms_db
from cutcut.common.ids import MicId
from cutcut.common.models.site import AudioDevice
from cutcut.hwtest.report import Report, Result, Step

TALK_S: Final = 5.0
SPEECH_DB: Final = -45.0
MAX_LAG_MS: Final = 20.0
RECOVER_S: Final = 15.0


class Operator(Protocol):
    def say(self, text: str) -> None: ...

    def wait(self, text: str) -> bool:
        """Show an instruction, wait for Enter. False: the technician skips this step."""
        ...


class ConsoleOperator:
    def say(self, text: str) -> None:
        print(text, flush=True)

    def wait(self, text: str) -> bool:
        answer = input(f"\n» {text}\n  Enter = start, h = hopp over: ").strip().lower()
        return answer not in ("h", "hopp", "skip")


@dataclass
class AudioTest:
    cfg: AudioDevice
    mics: list[MicId]
    op: Operator
    minutes: float = 60.0
    sd: Any = None
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    save_wav: Path | None = None
    report: Report = field(init=False)

    def __post_init__(self) -> None:
        self.report = Report("lyd", datetime.now().astimezone())

    # -- helpers --------------------------------------------------------------------------------

    def _backend(self, backend: str) -> DeviceBackend:
        cfg = self.cfg.model_copy(update={"backend": backend})
        return DeviceBackend(cfg, sd=self.sd, clock=self.clock, fallback=False)

    def _capture(self, b: DeviceBackend, seconds: float) -> np.ndarray:
        blocks = []
        t0 = self.clock()
        while self.clock() - t0 < seconds:
            block = b.read()
            if block is None:
                self.sleep(0.002)
            else:
                blocks.append(block)
        if not blocks:
            return np.zeros((0, self.cfg.channels), dtype=np.float32)
        return np.concatenate(blocks)

    def _skip(self, id_: str, title: str, why: str) -> None:
        self.report.add(Step(id_, title, "hoppet over", why))

    # -- the steps ------------------------------------------------------------------------------

    def run(self) -> Report:
        self.sd = self.sd or load_sounddevice()
        backend = self.step_devices()
        if backend is None:
            for id_, title in (
                ("A2", "Kanalkart"),
                ("A3", "Synkronitet"),
                ("A4", "Stabilitet"),
                ("A5", "USB ut og inn"),
                ("A6", "Dempet mic (Q24)"),
                ("A7", "WASAPI-reserve"),
            ):
                self._skip(id_, title, "Fant ikke lydkortet (A1).")
            return self.report
        b = self._backend(backend)
        try:
            first = self.step_channels(b)
            self.step_sync(first)
            self.step_stability(b)
            self.step_usb(b)
            self.step_muted(b)
        finally:
            b.close()
        self.step_wasapi()
        return self.report

    def step_devices(self) -> str | None:
        apis = self.sd.query_hostapis()
        found = []
        for dev in self.sd.query_devices():
            if self.cfg.device.lower() in str(dev["name"]).lower():
                found.append(
                    {
                        "name": dev["name"],
                        "hostapi": apis[dev["hostapi"]]["name"],
                        "inputs": dev["max_input_channels"],
                    }
                )
        ok = {}
        for key in ("asio", "wasapi"):
            with contextlib.suppress(NoDeviceError):
                ok[key] = find_device(self.sd, self.cfg, key)
        details = {"devices": found, "wanted_channels": self.cfg.channels}
        if "asio" in ok:
            self.report.add(
                Step(
                    "A1",
                    "Lydkort",
                    "ok",
                    f"RØDECaster på ASIO med {self.cfg.channels} kanaler"
                    + (", og på WASAPI" if "wasapi" in ok else ""),
                    details,
                )
            )
            return "asio"
        if "wasapi" in ok:
            self.report.add(
                Step(
                    "A1",
                    "Lydkort",
                    "advarsel",
                    "Bare på WASAPI: ASIO-driveren fra RØDE mangler eller viser for "
                    "få kanaler. CutCut virker, men med mer forsinkelse.",
                    details,
                    answers="Q21",
                )
            )
            return "wasapi"
        self.report.add(
            Step(
                "A1",
                "Lydkort",
                "feil",
                f"Fant ikke «{self.cfg.device}» med {self.cfg.channels} kanaler. "
                "Sjekk USB-kabelen og at RØDECaster står i multitrack-modus.",
                details,
            )
        )
        return None

    def step_channels(self, b: DeviceBackend) -> np.ndarray | None:
        rows: dict[str, Any] = {}
        wrong = []
        first: np.ndarray | None = None
        for mic in self.mics:
            fader = mic.value[1:]
            if not self.op.wait(
                f"Be personen ved {mic.value} (fader {fader}) snakke vanlig i "
                f"{TALK_S:.0f} sekunder, ingen andre snakker."
            ):
                rows[mic.value] = "hoppet over"
                continue
            audio = self._capture(b, TALK_S)
            if first is None:
                first = audio
                if self.save_wav is not None:
                    write_wav(self.save_wav, audio)
            levels = [round(rms_db(audio[:, ch]), 1) for ch in range(audio.shape[1])]
            loudest = int(np.argmax(levels)) if levels else -1
            want = mic_channel(mic)
            rows[mic.value] = {
                "expected_channel": want + 1,
                "loudest_channel": loudest + 1,
                "level_db": levels[want] if levels else None,
                "levels_db": levels,
            }
            if loudest != want or (levels and levels[want] < SPEECH_DB):
                wrong.append(f"{mic.value} sterkest på kanal {loudest + 1} (ventet {want + 1})")
        if wrong:
            self.report.add(
                Step(
                    "A2",
                    "Kanalkart",
                    "feil",
                    "; ".join(wrong) + ". Sjekk faderne mot "
                    "docs/studio/rodecaster-standardoppsett.md.",
                    rows,
                )
            )
        else:
            done = [m for m, r in rows.items() if r != "hoppet over"]
            self.report.add(
                Step(
                    "A2",
                    "Kanalkart",
                    "ok" if done else "hoppet over",
                    f"Riktig kanal for {', '.join(done)} (mic N på kanal 2N+1)"
                    if done
                    else "Ingen mic ble målt.",
                    rows,
                )
            )
        return first

    def step_sync(self, audio: np.ndarray | None) -> None:
        mic = self.mics[0]
        ch = mic_channel(mic)
        if audio is None or len(audio) < SAMPLE_RATE or audio.shape[1] <= max(MAIN_MIX):
            self._skip("A3", "Synkronitet", "Trenger opptaket fra A2.")
            return
        x = audio[: 2 * SAMPLE_RATE, ch].astype(np.float64)
        y = audio[: 2 * SAMPLE_RATE, MAIN_MIX[0]].astype(np.float64)
        if rms_db(y.astype(np.float32)) < SPEECH_DB:
            self.report.add(
                Step(
                    "A3",
                    "Synkronitet",
                    "advarsel",
                    "Ingen lyd i hovedmiksen under A2 (fader nede eller hovedmiks "
                    "ikke på USB-kanal 1–2?). S6 kan ikke sammenligne.",
                    {},
                )
            )
            return
        n = 1 << (2 * len(x) - 1).bit_length()
        corr = np.fft.irfft(np.fft.rfft(y, n) * np.conj(np.fft.rfft(x, n)), n)
        max_lag = int(MAX_LAG_MS * SAMPLE_RATE / 1000)
        window = np.concatenate([corr[-max_lag:], corr[: max_lag + 1]])
        lag = int(np.argmax(window)) - max_lag
        lag_ms = round(lag * 1000 / SAMPLE_RATE, 2)
        result: Result = "ok" if abs(lag_ms) <= 5 else "advarsel"
        self.report.add(
            Step(
                "A3",
                "Synkronitet",
                result,
                f"Hovedmiksen ligger {lag_ms} ms etter {mic.value} "
                "(samme strøm; S6 sammenligner nivåkurver, tåler opptil 10 ms)",
                {"lag_samples": lag, "lag_ms": lag_ms},
            )
        )

    def step_stability(self, b: DeviceBackend) -> None:
        if self.minutes <= 0:
            self._skip("A4", "Stabilitet", "Valgt bort (--minutes 0).")
            return
        self.op.say(f"A4: lytter i {self.minutes:g} minutter. Ikke rør lydkortet.")
        before = b.status()
        t0 = self.clock()
        frames = 0
        while self.clock() - t0 < self.minutes * 60:
            block = b.read()
            if block is None:
                self.sleep(0.002)
            else:
                frames += len(block)
        after = b.status()
        seconds = self.clock() - t0
        xruns = (after["overflows"] - before["overflows"]) + (
            after["underflows"] - before["underflows"]
        )
        stalls = after["reopened"] - before["reopened"] + (0 if after["running"] else 1)
        lost = max(0, int(seconds * SAMPLE_RATE) - frames)
        per_min = xruns / max(seconds / 60, 1e-9)
        details = {
            "minutes": round(seconds / 60, 1),
            "xruns": xruns,
            "xruns_per_min": round(per_min, 2),
            "stalls": stalls,
            "frames_lost": lost,
            "buffer": self.cfg.buffer,
        }
        result: Result
        if stalls:
            result, text = "feil", f"Strømmen stoppet {stalls} gang(er)"
        elif per_min > 5:
            result, text = "feil", f"{per_min:.1f} over-/underflyt per minutt: øk buffer"
        elif xruns:
            result, text = "advarsel", f"{xruns} over-/underflyt på {seconds / 60:.0f} min"
        else:
            result, text = "ok", f"Ingen avbrudd på {seconds / 60:.0f} min"
        self.report.add(
            Step(
                "A4",
                "Stabilitet",
                result,
                f"{text} (buffer {self.cfg.buffer}).",
                details,
                answers="Q21",
            )
        )

    def step_usb(self, b: DeviceBackend) -> None:
        if not self.op.wait("Trekk USB-kabelen ut av RØDECaster nå. Trykk Enter når den er ute."):
            self._skip("A5", "USB ut og inn", "Valgt bort.")
            return
        t0 = self.clock()
        while b.running and self.clock() - t0 < 30:
            b.read()
            self.sleep(0.05)
        noticed = round(self.clock() - t0, 1)
        if b.running:
            self.report.add(
                Step(
                    "A5",
                    "USB ut og inn",
                    "feil",
                    "CutCut merket ikke at lydkortet forsvant (30 s).",
                    {},
                )
            )
            return
        if not self.op.wait("Sett kabelen inn igjen. Trykk Enter når den er i."):
            self._skip("A5", "USB ut og inn", "Kabelen ble ikke satt inn igjen.")
            return
        t1 = self.clock()
        block = None
        while block is None and self.clock() - t1 < 60:
            block = b.read()
            if block is None:
                self.sleep(0.05)
        back = round(self.clock() - t1, 1)
        details = {"noticed_s": noticed, "back_s": back}
        if block is None:
            self.report.add(
                Step("A5", "USB ut og inn", "feil", "Lyden kom ikke tilbake innen 60 s.", details)
            )
        else:
            result: Result = "ok" if back <= RECOVER_S else "advarsel"
            self.report.add(
                Step(
                    "A5",
                    "USB ut og inn",
                    result,
                    f"Merket bortfall etter {noticed} s, lyd igjen {back} s etter "
                    "at kabelen var inne.",
                    details,
                )
            )

    def step_muted(self, b: DeviceBackend) -> None:
        mic = self.mics[0]
        if not self.op.wait(
            f"Trykk MUTE på {mic.value} (fader {mic.value[1:]}) på RØDECaster, "
            f"og la personen snakke i {TALK_S:.0f} sekunder."
        ):
            self._skip("A6", "Dempet mic (Q24)", "Valgt bort.")
            return
        audio = self._capture(b, TALK_S)
        self.op.say("Takk. Skru av MUTE igjen.")
        if len(audio) == 0:
            self._skip("A6", "Dempet mic (Q24)", "Ingen lyd ble tatt opp.")
            return
        track = round(rms_db(audio[:, mic_channel(mic)]), 1)
        main = round(max(rms_db(audio[:, ch]) for ch in MAIN_MIX), 1)
        details = {"track_db": track, "main_mix_db": main}
        if track >= SPEECH_DB:
            text = (
                f"Ja: den dempede stemmen er på multitrack-sporet ({track} dB), "
                f"hovedmiksen {main} dB. CutCut trenger S6 og bruker den."
            )
        else:
            text = (
                f"Nei: sporet er stille når mic-en er dempet ({track} dB). "
                "S6 skader ikke, men trengs ikke."
            )
        self.report.add(Step("A6", "Dempet mic (Q24)", "ok", text, details, answers="Q24"))

    def step_wasapi(self) -> None:
        b = self._backend("wasapi")
        try:
            audio = self._capture(b, 10.0)
            details = b.status()
        finally:
            b.close()
        frames = len(audio)
        share = frames / (8.0 * SAMPLE_RATE)  # 10 s minus up to 2 s to open
        if frames == 0:
            self.report.add(
                Step(
                    "A7",
                    "WASAPI-reserve",
                    "advarsel",
                    f"WASAPI eksklusiv ga ingen lyd ({details.get('last_error')}).",
                    details,
                )
            )
        else:
            self.report.add(
                Step(
                    "A7",
                    "WASAPI-reserve",
                    "ok" if share > 0.9 else "advarsel",
                    f"WASAPI eksklusiv leverer lyd ({frames / SAMPLE_RATE:.1f} s på 10 s)",
                    details,
                )
            )


def main(site_dir: Path | None, minutes: float, out: Path, save_wav: bool) -> int:
    from cutcut.common.config import load_site

    cfg, mics = AudioDevice(), list(MicId)
    if site_dir is not None:
        site = load_site(site_dir)
        cfg = site.devices.audio
        mics = sorted(
            {p.mic for s in site.shows.values() for p in s.participants}, key=lambda m: m.value
        )
    wav = out / "a2-mic1.wav" if save_wav else None
    print(f"Maskintest lyd · «{cfg.device}» · {cfg.channels} kanaler · buffer {cfg.buffer}")
    test = AudioTest(cfg, mics, ConsoleOperator(), minutes=minutes, save_wav=wav)
    report = test.run()
    js, md = report.write(out)
    print("\n" + report.to_markdown())
    print(f"Rapport: {md} (lim inn i GitHub-issue AU-6) og {js}")
    return 0 if report.result != "feil" else 1


__all__ = ["HOSTAPI", "AudioTest", "ConsoleOperator", "Operator", "main"]
