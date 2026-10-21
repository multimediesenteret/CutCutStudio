"""The real sound card: RØDECaster multitrack through PortAudio (AU-5, ADR-0014).

* **ASIO first** (RØDE's driver, low and stable latency), **WASAPI exclusive** as the reserve
  when ASIO is missing or will not open. Through ``sounddevice`` (MIT), which ships PortAudio
  with ASIO for Windows; ``SD_ENABLE_ASIO=1`` turns that on before the import.
* PortAudio calls back from its own thread with ``buffer`` samples; the callback only copies
  into a queue. :meth:`read` hands out 10 ms blocks (480 frames) to the analyzer loop.
* **Never gives up (spec 9.1):** a stream that stops (USB pulled, driver hang, no callbacks for
  1 s) is closed and opened again every 5 s, forever. Meanwhile :meth:`read` returns None,
  ``audio.frame`` stops, and core falls back to ``S4`` until the sound is back.
* Overflows and underflows are counted for ``audio.status`` (more than 5 a minute: raise the
  buffer, docs/plans/audio.md).

Everything in PortAudio sits behind ``sd`` (the module), so tests use a fake.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any, Final

import numpy as np

from cutcut.audio.analyzer import FRAME
from cutcut.audio.channels import SAMPLE_RATE
from cutcut.audio.dsp import Array
from cutcut.common.models.site import AudioDevice

log = logging.getLogger(__name__)

REOPEN_S: Final = 5.0
STALL_S: Final = 1.0
MAX_QUEUE_S: Final = 0.5  # more than this behind: drop the oldest (the engine wants now)
HOSTAPI: Final = {"asio": "ASIO", "wasapi": "Windows WASAPI"}


class NoDeviceError(RuntimeError):
    """The RØDECaster is not there (or not with enough channels)."""


def load_sounddevice() -> Any:
    os.environ.setdefault("SD_ENABLE_ASIO", "1")
    import sounddevice  # type: ignore[import-not-found,unused-ignore]

    return sounddevice


def find_device(sd: Any, cfg: AudioDevice, backend: str) -> int:
    """Index of the input device whose name contains ``cfg.device`` on the wanted host API."""
    want = HOSTAPI[backend]
    apis = sd.query_hostapis()
    for idx, dev in enumerate(sd.query_devices()):
        api = apis[dev["hostapi"]]["name"]
        if (
            api == want
            and cfg.device.lower() in str(dev["name"]).lower()
            and dev["max_input_channels"] >= cfg.channels
        ):
            return idx
    raise NoDeviceError(f"fant ikke «{cfg.device}» med {cfg.channels} kanaler på {want}")


class DeviceBackend:
    """``Backend`` for the studio: the sound card, reopened when it fails."""

    def __init__(
        self,
        cfg: AudioDevice,
        *,
        sd: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
        fallback: bool = True,
    ) -> None:
        self.cfg = cfg
        self.fallback = fallback  # False: only cfg.backend (the machine test tries each)
        self._sd = sd
        self.clock = clock
        self.name: str = cfg.backend
        self._stream: Any = None
        self._lock = threading.Lock()
        self._chunks: deque[Array] = deque()
        self._queued = 0
        self._buf = np.zeros((0, cfg.channels), dtype=np.float32)
        self._last_callback = 0.0
        self._next_open = 0.0
        self.overflows = 0
        self.underflows = 0
        self.dropped_frames = 0
        self.opened = 0
        self.last_error: str | None = None
        self.device_name: str | None = None

    # -- status for audio.status --------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._stream is not None

    def status(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "device": self.device_name,
            "running": self.running,
            "buffer": self.cfg.buffer,
            "overflows": self.overflows,
            "underflows": self.underflows,
            "dropped_frames": self.dropped_frames,
            "reopened": max(0, self.opened - 1),
            "last_error": self.last_error,
        }

    # -- PortAudio side -----------------------------------------------------------------------

    def _callback(self, indata: Any, frames: int, _time: Any, status: Any) -> None:
        """PortAudio's thread: copy and go. No allocation beyond the copy, no logging."""
        if status:
            if getattr(status, "input_overflow", False):
                self.overflows += 1
            if getattr(status, "input_underflow", False):
                self.underflows += 1
        block = np.array(indata[:, : self.cfg.channels], dtype=np.float32, copy=True)
        with self._lock:
            self._chunks.append(block)
            self._queued += len(block)
            limit = int(MAX_QUEUE_S * SAMPLE_RATE)
            while self._queued > limit and self._chunks:
                old = self._chunks.popleft()
                self._queued -= len(old)
                self.dropped_frames += len(old)
            self._last_callback = self.clock()

    def _open(self) -> None:
        sd = self._sd or load_sounddevice()
        self._sd = sd
        errors = []
        order = [self.cfg.backend]
        if self.fallback:
            order += [b for b in ("asio", "wasapi") if b != self.cfg.backend]
        for backend in order:
            try:
                idx = find_device(sd, self.cfg, backend)
                extra = sd.WasapiSettings(exclusive=True) if backend == "wasapi" else None
                stream = sd.InputStream(
                    device=idx,
                    channels=self.cfg.channels,
                    samplerate=SAMPLE_RATE,
                    blocksize=self.cfg.buffer,
                    dtype="float32",
                    latency="low",
                    extra_settings=extra,
                    callback=self._callback,
                )
                stream.start()
            except Exception as exc:
                errors.append(f"{HOSTAPI[backend]}: {exc}")
                continue
            self._stream = stream
            self.name = backend
            self.device_name = str(sd.query_devices(idx)["name"])
            self._last_callback = self.clock()
            self.opened += 1
            self.last_error = None
            if backend != self.cfg.backend:
                log.warning("Lyd: %s virket ikke, bruker reserven %s", self.cfg.backend, backend)
            log.info(
                "Lyd: %s via %s, buffer %d", self.device_name, HOSTAPI[backend], self.cfg.buffer
            )
            return
        raise NoDeviceError("; ".join(errors))

    def _close(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.abort()
                stream.close()
            except Exception as exc:  # a dead driver may throw on close too
                log.debug("lukking feilet: %s", exc)
        with self._lock:
            self._chunks.clear()
            self._queued = 0
        self._buf = self._buf[:0]

    # -- Backend --------------------------------------------------------------------------------

    def read(self) -> Array | None:
        now = self.clock()
        if self._stream is None:
            if now < self._next_open:
                return None
            try:
                self._open()
            except Exception as exc:
                self.last_error = str(exc)
                self._next_open = now + REOPEN_S
                log.warning("Lyd: kan ikke åpne (%s); prøver igjen om %g s", exc, REOPEN_S)
                return None
        stream = self._stream
        if (not getattr(stream, "active", True)) or now - self._last_callback > STALL_S:
            self.last_error = "lydstrømmen stoppet"
            log.error("Lyd: strømmen stoppet; åpner på nytt om %g s", REOPEN_S)
            self._close()
            self._next_open = now + REOPEN_S
            return None
        if len(self._buf) < FRAME:
            with self._lock:
                chunks = list(self._chunks)
                self._chunks.clear()
                self._queued = 0
            if chunks:
                self._buf = np.concatenate([self._buf, *chunks])
        if len(self._buf) < FRAME:
            return None
        block, self._buf = self._buf[:FRAME], self._buf[FRAME:]
        return block

    def close(self) -> None:
        self._close()
