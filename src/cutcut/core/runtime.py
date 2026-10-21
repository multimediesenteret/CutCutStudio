"""The thin shell around the pure engine (docs/plans/core.md K-9).

* Collects the newest measurements (from the bus or the simulator) between ticks.
* Calls ``Engine.step`` every 30 ms on a monotonic schedule. A slow tick is logged; if the
  loop falls behind, ticks are skipped rather than piling up.
* Writes every decision to the JSON log and SQLite, and passes intents to an ``Executor``
  without waiting for the devices (the executor queues per device, ADR-0005).
* Saves the engine settings every second and restores them after a restart, so ``core`` is
  back within 5 s with the same AUTO/LOCK/content/shadow state (10.4).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from cutcut.common.clock import Clock
from cutcut.common.ids import CameraId, MicId, SourceId
from cutcut.common.logging import correlation
from cutcut.common.models.decision import Decision
from cutcut.common.store import Store
from cutcut.core import messages
from cutcut.core.engine import Engine, StepResult
from cutcut.core.inputs import AtemReadback, Command, ContentState, Inputs, MicFrame, TileFrame
from cutcut.core.intents import Intent

log = logging.getLogger(__name__)

TICK_MS: Final = 30
SLOW_STEP_MS: Final = 10
SETTINGS_KEY: Final = "engine_settings"
SNAPSHOT_EVERY_MS: Final = 1000
VISION_STALE_MS: Final = 1000  # spec 6.6


class Executor(Protocol):
    """Turns intents into device commands. Must return quickly (queue, don't wait)."""

    def submit(self, intent: Intent) -> None: ...


@dataclass
class RecordingExecutor:
    """Keeps intents in memory (tests, simulator, shadow mode)."""

    intents: list[Intent] = field(default_factory=list)

    def submit(self, intent: Intent) -> None:
        self.intents.append(intent)


@dataclass
class RuntimeStats:
    ticks: int = 0
    skipped_ticks: int = 0
    slow_steps: int = 0
    max_step_ms: float = 0.0
    decisions: int = 0
    invalid_messages: int = 0


class CoreRuntime:
    def __init__(
        self,
        engine: Engine,
        clock: Clock,
        executor: Executor,
        store: Store | None = None,
        on_decision: Callable[[Decision], None] | None = None,
        on_step: Callable[[StepResult], None] | None = None,
    ) -> None:
        self.engine = engine
        self.clock = clock
        self.executor = executor
        self.store = store
        self.on_decision = on_decision
        self.on_step = on_step
        self.stats = RuntimeStats()
        self._mics: dict[MicId, MicFrame] = {}
        self._last_audio_ms: int | None = None
        self.audio_status: dict[str, Any] = {}
        self.vision_frame: dict[str, Any] = {}
        self.vision_frame_ms: int | None = None
        self.vision_status: dict[str, Any] = {}
        self.vision_status_ms: int | None = None
        self.on_audio: Callable[[dict[MicId, MicFrame]], None] | None = None
        self._content: ContentState | None = None
        self._vision: dict[SourceId, TileFrame] = {}
        self._last_vision_ms: int | None = None
        self._atem: AtemReadback | None = None
        self._moving: frozenset[CameraId] = frozenset()
        self._commands: list[Command] = []
        self._last_snapshot_ms = -SNAPSHOT_EVERY_MS
        self._stop = asyncio.Event()
        self._started_ms = clock.mono_ms()
        self._restore()

    @property
    def latest_mics(self) -> dict[MicId, MicFrame]:
        """The newest mic measurements (read-only use: meters for the screens)."""
        return self._mics

    @property
    def atem(self) -> AtemReadback | None:
        """What the ATEM shows now (None: not connected). For ``H-ATEM-1``."""
        return self._atem

    def audio_age_ms(self) -> int | None:
        """How long since the last audio measurement, or since start if none came yet (the
        same grace as S4). For ``H-AUD-1``."""
        last = self._last_audio_ms if self._last_audio_ms is not None else self._started_ms
        return self.clock.mono_ms() - last

    # -- feeding --------------------------------------------------------------------------

    def feed_audio(self, mics: dict[MicId, MicFrame]) -> None:
        self._mics = mics
        self._last_audio_ms = self.clock.mono_ms()
        if self.on_audio is not None:  # the setup mic check listens along (AU-7)
            self.on_audio(mics)

    def feed_content(self, state: ContentState | None) -> None:
        self._content = state

    def feed_tile(self, source: SourceId, frame: TileFrame) -> None:
        self._vision[source] = frame
        self._last_vision_ms = self.clock.mono_ms()

    def feed_atem(self, readback: AtemReadback | None) -> None:
        self._atem = readback

    def feed_cameras_moving(self, moving: frozenset[CameraId]) -> None:
        self._moving = moving

    def command(self, cmd: Command) -> None:
        self._commands.append(cmd)

    def feed_bus(self, topic: str, payload: dict[str, Any]) -> None:
        """Route one bus message. Invalid payloads are counted and dropped, never raised."""
        try:
            if topic == "audio.frame":
                self.feed_audio(messages.mic_frames(payload))
            elif topic == "vision.content":
                self.feed_content(messages.content_state(payload))
            elif topic == "vision.tile":
                self.feed_tile(*messages.tile(payload))
            elif topic == "atem.state":
                self.feed_atem(messages.atem_readback(payload))
            elif topic == "vision.frame":
                self.vision_frame = dict(payload)  # VI-1: the screens and H-VID-1, not rules
                self.vision_frame_ms = self.clock.mono_ms()
            elif topic == "vision.status":
                self.vision_status = dict(payload)
                self.vision_status_ms = self.clock.mono_ms()
            elif topic == "audio.status":
                self.audio_status = dict(payload)  # for H-AUD-1's message, not for decisions
            elif topic == "cameras.moving":
                self.feed_cameras_moving(messages.cameras_moving(payload))
        except ValueError as exc:
            self.stats.invalid_messages += 1
            log.warning("invalid %s payload: %s", topic, exc)

    # -- ticking --------------------------------------------------------------------------

    def _inputs(self, now: int) -> Inputs:
        # No audio yet since start counts as lost audio after the S4 limit (5.7).
        last_audio = self._last_audio_ms if self._last_audio_ms is not None else self._started_ms
        vision_ok = (
            self._last_vision_ms is not None and now - self._last_vision_ms <= VISION_STALE_MS
        )
        commands, self._commands = tuple(self._commands), []
        return Inputs(
            now_ms=now,
            mics=self._mics,
            audio_age_ms=max(0, now - last_audio),
            vision=dict(self._vision) if vision_ok else None,
            content=self._content,
            atem=self._atem,
            cameras_moving=self._moving,
            commands=commands,
        )

    def tick(self) -> StepResult:
        now = self.clock.mono_ms()
        t0 = time.perf_counter()
        result = self.engine.step(self._inputs(now))
        step_ms = (time.perf_counter() - t0) * 1000
        self.stats.ticks += 1
        self.stats.max_step_ms = max(self.stats.max_step_ms, step_ms)
        if step_ms > SLOW_STEP_MS:
            self.stats.slow_steps += 1
            log.warning("slow engine step: %.1f ms", step_ms)
        for decision in result.decisions:
            self._handle_decision(decision)
        for intent in result.intents:
            try:
                self.executor.submit(intent)
            except Exception:  # an executor bug must never stop the loop
                log.exception("executor failed for %r", intent)
        if self.on_step is not None:
            self.on_step(result)
        if now - self._last_snapshot_ms >= SNAPSHOT_EVERY_MS:
            self._snapshot(now)
        return result

    def _handle_decision(self, decision: Decision) -> None:
        self.stats.decisions += 1
        with correlation(decision.correlation_id):
            log.info(
                decision.reason,
                extra={
                    "rule": decision.rule.value,
                    "action": decision.action,
                    "shot": decision.shot,
                    "mode": decision.mode.value,
                    "blocked_by": decision.blocked_by.value if decision.blocked_by else None,
                    "shadow": decision.shadow,
                },
            )
        if self.store is not None:
            self.store.add_decision(decision)
        if self.on_decision is not None:
            self.on_decision(decision)

    async def run(self) -> None:
        """Tick every 30 ms until ``stop()``. Missed ticks are skipped, never queued."""
        next_tick = self.clock.mono_ms()
        while not self._stop.is_set():
            self.tick()
            next_tick += TICK_MS
            now = self.clock.mono_ms()
            if now > next_tick + TICK_MS:  # fell behind: skip, don't catch up in a burst
                missed = (now - next_tick) // TICK_MS
                self.stats.skipped_ticks += missed
                next_tick += missed * TICK_MS
            delay = max(0, next_tick - now) / 1000
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=delay)

    def stop(self) -> None:
        self._stop.set()

    # -- persistence ----------------------------------------------------------------------

    def _snapshot(self, now: int) -> None:
        self._last_snapshot_ms = now
        if self.store is not None:
            self.store.put_kv(SETTINGS_KEY, self.engine.settings(), self.clock.now())

    def _restore(self) -> None:
        if self.store is None:
            return
        settings = self.store.get_kv(SETTINGS_KEY)
        if isinstance(settings, dict):
            self.engine.restore(settings, self.clock.mono_ms())
            log.info("restored engine settings after restart", extra={"settings": settings})
