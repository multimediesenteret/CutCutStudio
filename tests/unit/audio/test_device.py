"""AU-5: the sound card backend – ASIO first, WASAPI reserve, reopen forever – against a fake
PortAudio, plus a real PortAudio smoke test on the Windows CI runner (no sound card there)."""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from cutcut.audio.analyzer import FRAME, Analyzer
from cutcut.audio.device import REOPEN_S, DeviceBackend, NoDeviceError, find_device
from cutcut.audio.process import run
from cutcut.common.models.site import AudioDevice

CFG = AudioDevice()


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


class FakeStream:
    def __init__(self, sd: FakeSd, **kw: Any) -> None:
        self.sd, self.kw = sd, kw
        self.active = False
        self.closed = False

    def start(self) -> None:
        if self.sd.fail_open.get(self.sd.apis[self.sd.devices[self.kw["device"]]["hostapi"]]):
            raise RuntimeError("Error opening InputStream: Unanticipated host error")
        self.active = True
        self.sd.streams.append(self)

    def abort(self) -> None:
        self.active = False

    def close(self) -> None:
        self.closed = True

    def push(self, frames: int, value: float = 0.1, **status: bool) -> None:
        data = np.full((frames, 20), value, dtype=np.float32)
        self.kw["callback"](data, frames, None, SimpleNamespace(**status) if status else None)


class FakeSd:
    """Enough of the sounddevice module: host APIs, devices, InputStream, WasapiSettings."""

    def __init__(self, *, asio: bool = True, wasapi: bool = True) -> None:
        self.apis = ["MME", "ASIO", "Windows WASAPI"]
        self.devices = [{"name": "Microphone (Realtek)", "hostapi": 0, "max_input_channels": 2}]
        if asio:
            self.devices.append(
                {"name": "RODECaster Pro II ASIO", "hostapi": 1, "max_input_channels": 20}
            )
        if wasapi:
            self.devices.append(
                {
                    "name": "RØDECaster Pro II Multitrack (RODECaster Pro II)",
                    "hostapi": 2,
                    "max_input_channels": 20,
                }
            )
        self.fail_open: dict[str, bool] = {}
        self.streams: list[FakeStream] = []

    def query_hostapis(self) -> list[dict[str, str]]:
        return [{"name": n} for n in self.apis]

    def query_devices(self, idx: int | None = None) -> Any:
        return self.devices if idx is None else self.devices[idx]

    def InputStream(self, **kw: Any) -> FakeStream:
        return FakeStream(self, **kw)

    def WasapiSettings(self, exclusive: bool = False) -> dict[str, bool]:
        return {"exclusive": exclusive}


def backend(sd: FakeSd, clock: Clock | None = None, **cfg: Any) -> DeviceBackend:
    return DeviceBackend(AudioDevice(**cfg), sd=sd, clock=clock or Clock())


def test_finds_the_rodecaster_on_asio() -> None:
    sd = FakeSd()
    assert find_device(sd, CFG, "asio") == 1
    assert find_device(sd, CFG, "wasapi") == 2
    with pytest.raises(NoDeviceError, match="20 kanaler"):
        find_device(sd, AudioDevice(device="Realtek"), "asio")


def test_opens_asio_and_hands_out_10_ms_blocks() -> None:
    sd = FakeSd()
    b = backend(sd)
    assert b.read() is None  # opened; nothing recorded yet
    (stream,) = sd.streams
    assert stream.kw["blocksize"] == 256
    assert stream.kw["samplerate"] == 48_000
    assert stream.kw["channels"] == 20
    assert stream.kw["extra_settings"] is None
    for _ in range(4):  # 4 × 256 = 1024 frames = two 10 ms blocks and a bit
        stream.push(256)
    blocks = [b.read(), b.read(), b.read()]
    assert [None if x is None else x.shape for x in blocks] == [(FRAME, 20), (FRAME, 20), None]
    assert b.status()["backend"] == "asio"
    assert b.status()["device"] == "RODECaster Pro II ASIO"


def test_wasapi_exclusive_is_the_reserve() -> None:
    sd = FakeSd()
    sd.fail_open["ASIO"] = True
    b = backend(sd)
    b.read()
    (stream,) = sd.streams
    assert stream.kw["extra_settings"] == {"exclusive": True}
    assert b.name == "wasapi"
    assert b.status()["running"] is True


def test_no_sound_card_is_retried_every_5_s_forever() -> None:
    clock = Clock()
    sd = FakeSd(asio=False, wasapi=False)
    b = backend(sd, clock)
    assert b.read() is None
    assert "fant ikke" in (b.last_error or "")
    sd.devices.append({"name": "RODECaster Pro II ASIO", "hostapi": 1, "max_input_channels": 20})
    clock.t += REOPEN_S - 0.1
    b.read()
    assert not sd.streams  # waits out the pause
    clock.t += 0.2
    b.read()
    assert len(sd.streams) == 1  # USB plugged back in: found


def test_a_stream_that_stops_is_closed_and_opened_again() -> None:
    clock = Clock()
    sd = FakeSd()
    b = backend(sd, clock)
    b.read()
    first = sd.streams[0]
    first.push(512)
    assert b.read() is not None
    clock.t += 1.5  # no callbacks for 1.5 s: driver hang or cable out
    assert b.read() is None
    assert first.closed
    assert b.status()["last_error"] == "lydstrømmen stoppet"
    clock.t += REOPEN_S
    b.read()
    assert len(sd.streams) == 2
    assert b.status()["reopened"] == 1


def test_overflows_are_counted_and_a_backlog_is_dropped() -> None:
    sd = FakeSd()
    b = backend(sd)
    b.read()
    s = sd.streams[0]
    s.push(256, input_overflow=True)
    for _ in range(200):  # ~1 s that nobody read: keep the newest 0.5 s
        s.push(256)
    st = b.status()
    assert st["overflows"] == 1
    assert st["dropped_frames"] > 0
    assert b._queued <= 24_000


def test_audio_status_is_sent_while_the_card_is_missing() -> None:
    sd = FakeSd(asio=False, wasapi=False)
    b = backend(sd)
    sent: list[tuple[str, dict[str, Any]]] = []

    async def publish(topic: str, payload: dict[str, Any]) -> None:
        sent.append((topic, payload))

    async def go() -> None:
        task = asyncio.create_task(run(b, Analyzer(), publish))
        await asyncio.sleep(0.05)
        task.cancel()

    asyncio.run(go())
    statuses = [p for t, p in sent if t == "audio.status"]
    assert statuses
    assert statuses[0]["ok"] is False
    assert "fant ikke" in statuses[0]["last_error"]
    assert not any(t == "audio.frame" for t, _ in sent)


@pytest.mark.skipif(sys.platform != "win32", reason="PortAudio with ASIO ships for Windows")
def test_real_portaudio_on_windows_without_a_rodecaster() -> None:
    """CI's Windows runner has no RØDECaster: the real stack loads and says so, no crash."""
    b = DeviceBackend(AudioDevice())
    assert b.read() is None
    assert b.last_error
    b.close()
