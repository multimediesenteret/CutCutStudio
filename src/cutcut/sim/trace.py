"""Record a whole simulated session as JSON for the web simulator on Vercel (SIM-7, ADR-0013).

The trace is exactly what the screens would have received over ``/ws``: the real engine, the
real studio service and the real hub run on a fake clock, and every hub message is stored
with its time. The browser plays it back with ``ReplayTransport`` – no engine on Vercel.

Format (version 1)::

    {"version": 1, "story": "...", "title": "...", "duration_ms": N, "keyframe_ms": K,
     "messages": [[t_ms, {"type": ..., "seq": ..., "data": ...}], ...],
     "rest": [[t_ms, "/api/...", <answer>], ...]}

A full state is stored every ``keyframe_ms`` (``"full": true``), so the player can jump.

The studio is recorded as it is set up in the studio, so the web simulator mirrors the app
there: Start button without a card (D-057), the PTZ cameras, and the health checks running.
``rest`` holds the answers of the GET endpoints the screens read (Oppsett, Kameraer, Helse …),
taken from the real API at each keyframe and stored when they change. The player gives the
newest answer for a path, so those pages are not empty.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from cutcut.common.clock import FakeClock
from cutcut.common.ids import ParticipantId
from cutcut.common.models.session import ShowChoice
from cutcut.core.inputs import ContentState
from cutcut.core.runtime import TICK_MS
from cutcut.sim.live import LiveSim, build_live_sim

TRACE_VERSION: Final = 1
KEYFRAME_MS: Final = 10_000
METERS_EVERY_MS: Final = 100  # 10 Hz is enough for playback and halves the size
HEALTH_EVERY_MS: Final = 1000
# What the screens fetch over REST (ui/packages/client and the technician pages).
REST_PATHS: Final = (
    "/api/me",
    "/api/rules",
    "/api/cameras",
    "/api/sessions?days=1",
    "/api/settings/alerts",
    "/api/settings/devices",
    "/api/settings/staff",
    "/api/setup/steps",
    "/api/setup/atem",
    "/api/setup/color",
    "/api/setup/mics",
    "/api/setup/multiview",
)

# Tick timings are measured in real time and would make the trace differ run to run (I3).
_RUNTIME: Final = {"ticks": 0, "max_step_ms": 0.0, "skipped_ticks": 0}

Action = Callable[[LiveSim], None]


@dataclass(frozen=True)
class Story:
    id: str
    title: str
    duration_s: int
    steps: tuple[tuple[float, Action], ...]


def _start_button(sim: LiveSim) -> None:
    """«Start» on the touch screen, as in the studio (D-057): a session for «Gjest»."""
    sim.studio.start_without_card("touch", "touch")


def _show(guests: int, laptop: bool = False) -> Action:
    def act(sim: LiveSim) -> None:
        sim.studio.set_show(ShowChoice(guests=guests, laptop=laptop), "touch", "touch")

    return act


def _start(sim: LiveSim) -> None:
    sim.studio.start_recording("touch", "touch", "touch")


def _stop(sim: LiveSim) -> None:
    sim.studio.stop_recording("touch", "touch", "touch")


def _conversation(on: bool) -> Action:
    def act(sim: LiveSim) -> None:
        sim.conversation_on = on
        if not on:
            for pid in list(sim.voices.voices):
                sim.voices.stop(pid, sim.studio.now)

    return act


def _talk(pid: ParticipantId, on: bool) -> Action:
    def act(sim: LiveSim) -> None:
        if on:
            sim.voices.talk(pid, sim.studio.now)
        else:
            sim.voices.stop(pid, sim.studio.now)

    return act


def _content(state: ContentState | None) -> Action:
    def act(sim: LiveSim) -> None:
        sim.content = state

    return act


STORIES: Final[dict[str, Story]] = {
    s.id: s
    for s in (
        Story(
            id="samtale",
            title="Samtale med to personer",
            duration_s=150,
            steps=(
                (3, _start_button),
                (7, _show(1)),
                (10, _start),
                (14, _talk(ParticipantId.P1, True)),
                (19, _talk(ParticipantId.P1, False)),
                (19.4, _conversation(True)),
                (110, _conversation(False)),
                (111, _talk(ParticipantId.P1, True)),
                (116, _talk(ParticipantId.P1, False)),
                (118, _stop),
            ),
        ),
        Story(
            id="panel-laptop",
            title="Panel med tre personer og slides",
            duration_s=150,
            steps=(
                (3, _start_button),
                (7, _show(2, laptop=True)),
                (10, _start),
                (14, _talk(ParticipantId.P1, True)),
                (19, _talk(ParticipantId.P1, False)),
                (19.4, _conversation(True)),
                (45, _content(ContentState.NEW_SLIDE)),
                (46, _content(ContentState.STATIC)),
                (75, _content(ContentState.NEW_SLIDE)),
                (76, _content(ContentState.STATIC)),
                (95, _content(None)),
                (112, _conversation(False)),
                (113, _talk(ParticipantId.P1, True)),
                (117, _talk(ParticipantId.P1, False)),
                (119, _stop),
            ),
        ),
    )
}


def trace_site_dir() -> Path | None:
    """The web simulator shows the real studio layout (D-054), when the repo has it."""
    path = Path(__file__).resolve().parents[3] / "site" / "multimediesenteret"
    return path if (path / "devices.yaml").exists() else None


def record(story: Story, *, seed: int = 1) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from cutcut.api.app import create_app

    clock = FakeClock()
    sim, auth = build_live_sim(
        clock, seed=seed, site_dir=trace_site_dir(), cameras=True, vision=True
    )
    studio = sim.studio
    studio.set_login_mode("open", "admin", "trace")  # the studio's own setting (D-057)
    api = TestClient(create_app(studio, auth, run_loop=False))
    loop = asyncio.new_event_loop()
    rest: list[list[Any]] = []
    last_rest: dict[str, str] = {}
    client = studio.hub.connect()
    messages: list[list[Any]] = []
    steps = sorted(story.steps, key=lambda s: s[0])
    next_step = 0
    next_keyframe = 0
    last_meters = -METERS_EVERY_MS
    end_ms = story.duration_s * 1000
    t = 0
    while t <= end_ms:
        while next_step < len(steps) and steps[next_step][0] * 1000 <= t:
            steps[next_step][1](sim)
            next_step += 1
        sim.before_tick()
        studio.tick()
        if t % HEALTH_EVERY_MS == 0:
            cams = studio.deps.cameras
            if cams is not None:  # as CameraService.run does: status every 10 s, position often
                if t % 10_000 == 0:
                    loop.run_until_complete(cams.poll_status())
                loop.run_until_complete(cams.poll_positions())
            loop.run_until_complete(studio.health.step())
        if t >= next_keyframe:
            shows = tuple(f"/api/shows/{s}" for s in sorted(studio.deps.site.shows))
            _snapshot_rest(api, REST_PATHS + shows, t, rest, last_rest)
            state = studio.state().model_dump(mode="json")
            state["runtime"] = _RUNTIME
            messages.append([t, {"type": "state", "seq": 0, "full": True, "data": state}])
            next_keyframe += KEYFRAME_MS
        while not client.queue.empty():
            msg = client.queue.get_nowait()
            if msg["type"] == "state":
                data = {k: v for k, v in msg["data"].items() if k != "runtime"}
                if not data:
                    continue
                msg = {**msg, "data": data}
            elif msg["type"] == "meters":
                if t - last_meters < METERS_EVERY_MS:
                    continue
                last_meters = t
                msg = {**msg, "data": _round_meters(msg["data"])}
            messages.append([t, msg])
        clock.advance(TICK_MS)
        t += TICK_MS
    studio.hub.disconnect(client)
    loop.close()
    return {
        "version": TRACE_VERSION,
        "story": story.id,
        "title": story.title,
        "seed": seed,
        "duration_ms": end_ms,
        "keyframe_ms": KEYFRAME_MS,
        "messages": messages,
        "rest": rest,
    }


def _snapshot_rest(
    api: Any, paths: tuple[str, ...], t: int, rest: list[list[Any]], last: dict[str, str]
) -> None:
    for path in paths:
        res = api.get(path)
        if res.status_code != 200:
            continue
        body = res.json()
        key = path.split("?")[0]
        text = json.dumps(body, sort_keys=True)
        if last.get(key) != text:
            last[key] = text
            rest.append([t, key, body])


def _round_meters(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        k: {**m, "level_db": round(m["level_db"], 1), "vad": round(m["vad"], 2)}
        for k, m in data.items()
    }


def dumps(trace: dict[str, Any]) -> str:
    return json.dumps(trace, separators=(",", ":"), ensure_ascii=False) + "\n"


def default_trace_dir() -> Path:
    """Where the web simulator reads traces from (served as static files on Vercel)."""
    return Path(__file__).resolve().parents[3] / "ui" / "apps" / "simulator" / "public" / "traces"


def write_all(out_dir: Path, *, check: bool = False) -> list[str]:
    """Write every story (and ``index.json``). With ``check``, write nothing and return the
    files that are missing or stale instead – used by CI so Vercel always shows today's engine.
    """
    files = {f"{s.id}.json": dumps(record(s)) for s in STORIES.values()}
    files["index.json"] = (
        json.dumps(
            [{"id": s.id, "title": s.title, "file": f"{s.id}.json"} for s in STORIES.values()],
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    changed = []
    for name, text in files.items():
        path = out_dir / name
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            changed.append(name)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
    return changed
