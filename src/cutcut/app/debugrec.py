"""Feilsøkingsmodus: record everything that reaches the engine, for a limited time.

Turned on from the technician window (Helse, admin) for 1, 8 or 24 hours, for example for the
studio period. While it is on:

* every bus message to ``core`` (audio measurements, ATEM state, video measurements, camera
  movement, …) is written with its time, except the picture data (``vision.thumbs``,
  ``vision.frame``);
* every decision, every intent sent to the equipment, and every Companion press with how long
  it took from the decision (``press``, ``ms``) are written alongside;
* ``core`` logs at DEBUG level.

Files: ``data\\debug\\<YYYY-MM-DD>T<HH>.jsonl.gz``, one per hour, one JSON object per line
(``t`` wall clock, ``mono`` engine ms, ``kind``, …). Kept 7 days; recording stops by itself if
the folder grows past ``MAX_BYTES``. The writing happens in its own thread, so the engine is
never held up (12.5). Nothing here holds a password, a PIN or a card number: those never
reach the bus.

Used by ``cutcut hwtest akseptanse`` (10.4 from real sessions) and, later, replay (SIM-8).
"""

from __future__ import annotations

import gzip
import json
import logging
import queue
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

log = logging.getLogger(__name__)

SKIP_TOPICS: Final = frozenset({"vision.thumbs", "vision.frame"})
KEEP_DAYS: Final = 7
MAX_BYTES: Final = 5_000_000_000
QUEUE_MAX: Final = 50_000
FLUSH_S: Final = 5.0


class DebugRecorder:
    def __init__(
        self,
        folder: Path,
        now: Callable[[], datetime],
        mono_ms: Callable[[], int],
        *,
        thread: bool = True,
    ) -> None:
        self.folder = folder
        self.now = now
        self.mono_ms = mono_ms
        self.until: datetime | None = None
        self.dropped = 0
        self._q: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=QUEUE_MAX)
        self._file: gzip.GzipFile | None = None
        self._file_hour: str | None = None
        self._written = 0
        self._flushed_at = 0.0
        self._thread: threading.Thread | None = None
        self._use_thread = thread

    # -- on and off (engine thread) --------------------------------------------------------

    @property
    def active(self) -> bool:
        return self.until is not None

    def start(self, until: datetime) -> None:
        self.until = until
        self.folder.mkdir(parents=True, exist_ok=True)
        self._prune()
        if self._use_thread and (self._thread is None or not self._thread.is_alive()):
            self._thread = threading.Thread(target=self._run, name="debugrec", daemon=True)
            self._thread.start()
        log.info("Feilsøkingsmodus på til %s", until.isoformat(timespec="minutes"))

    def stop(self) -> None:
        if self.until is None:
            return
        self.until = None
        self._q.put(None)  # close the file
        if not self._use_thread:
            self.drain()
        log.info("Feilsøkingsmodus av")

    def expire(self) -> bool:
        """Turn off when the time is up. True when it just turned off."""
        if self.until is not None and self.now() >= self.until:
            self.stop()
            return True
        return False

    # -- recording (engine thread: only a queue put) ---------------------------------------

    def bus(self, topic: str, payload: dict[str, Any]) -> None:
        if self.until is not None and topic not in SKIP_TOPICS:
            self._put({"kind": "bus", "topic": topic, "data": payload})

    def event(self, kind: str, data: dict[str, Any]) -> None:
        if self.until is not None:
            self._put({"kind": kind, **data})

    def _put(self, item: dict[str, Any]) -> None:
        item = {"t": self.now().isoformat(timespec="milliseconds"), "mono": self.mono_ms(), **item}
        try:
            self._q.put_nowait(item)
        except queue.Full:
            self.dropped += 1

    # -- writing (own thread) ---------------------------------------------------------------

    def _run(self) -> None:
        while True:
            item = self._q.get()
            self._write(item)

    def drain(self) -> None:
        """Write what is queued (tests, and when there is no thread)."""
        while True:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                return
            self._write(item)

    def _write(self, item: dict[str, Any] | None) -> None:
        try:
            if item is None:
                self._close()
                return
            hour = str(item["t"])[:13]
            if hour != self._file_hour:
                self._close()
                # kept open across writes on purpose; closed on the next hour or at stop
                self._file = gzip.open(self.folder / f"{hour}.jsonl.gz", "ab")  # noqa: SIM115
                self._file_hour = hour
            if self._file is None:
                return
            line = (json.dumps(item, ensure_ascii=False, default=str) + "\n").encode("utf-8")
            self._file.write(line)
            self._written += len(line)
            if time.monotonic() - self._flushed_at >= FLUSH_S:
                # so `hwtest akseptanse` can read the hour that is still being written
                self._flushed_at = time.monotonic()
                self._file.flush()
            if self._written > 1_000_000:
                self._written = 0
                if self.size() > MAX_BYTES:
                    log.error("Feilsøkingsopptaket er over %d GB; stopper", MAX_BYTES // 10**9)
                    self.until = None
                    self._close()
        except OSError:
            log.exception("kunne ikke skrive feilsøkingsopptaket")

    def _close(self) -> None:
        if self._file is not None:
            self._file.close()
        self._file, self._file_hour = None, None

    # -- housekeeping -----------------------------------------------------------------------

    def files(self) -> list[Path]:
        return sorted(self.folder.glob("*.jsonl.gz")) if self.folder.exists() else []

    def size(self) -> int:
        return sum(f.stat().st_size for f in self.files())

    def _prune(self) -> None:
        cutoff = (self.now() - timedelta(days=KEEP_DAYS)).isoformat()[:13]
        for f in self.files():
            if f.name[:13] < cutoff:
                f.unlink(missing_ok=True)

    def info(self) -> dict[str, Any]:
        files = self.files()
        return {
            "on": self.active,
            "until": self.until.isoformat(timespec="minutes") if self.until else None,
            "folder": str(self.folder),
            "files": len(files),
            "mb": round(sum(f.stat().st_size for f in files) / 1e6, 1),
            "dropped": self.dropped,
        }


def read(paths: list[Path]) -> list[dict[str, Any]]:
    """All records from the given files, in order (``cutcut hwtest akseptanse``)."""
    out: list[dict[str, Any]] = []
    for p in sorted(paths):
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            out.append(json.loads(line))
                        except ValueError:
                            continue  # a line cut off by a power loss
        except (EOFError, OSError):
            continue  # the file of the current hour, or one cut off: keep what was read
    return out
