"""SIM-7: traces for the web simulator."""

from __future__ import annotations

from pathlib import Path

from cutcut.__main__ import main
from cutcut.core.runtime import TICK_MS
from cutcut.sim.trace import KEYFRAME_MS, STORIES, TRACE_VERSION, default_trace_dir, record


def _steps(trace: dict[str, object]) -> list[str]:
    seen: list[str] = []
    for _, msg in trace["messages"]:  # type: ignore[attr-defined]
        data = msg["data"]
        if msg["type"] == "state" and "touch" in data:
            step = data["touch"]["step"]
            if not seen or seen[-1] != step:
                seen.append(step)
    return seen


def test_trace_is_deterministic() -> None:
    story = STORIES["samtale"]
    assert record(story) == record(story)


def test_trace_has_format_and_keyframes() -> None:
    trace = record(STORIES["samtale"])
    assert trace["version"] == TRACE_VERSION
    msgs = trace["messages"]
    assert msgs[0][0] == 0
    assert msgs[0][1]["full"] is True
    fulls = [t for t, m in msgs if m.get("full")]
    expected = list(range(0, trace["duration_ms"] + 1, KEYFRAME_MS))
    assert len(fulls) == len(expected)
    assert all(0 <= f - e < TICK_MS for f, e in zip(fulls, expected, strict=True))
    times = [t for t, _ in msgs]
    assert times == sorted(times)


def test_every_story_goes_through_the_whole_touch_flow() -> None:
    for story in STORIES.values():
        assert _steps(record(story)) == ["idle", "ready", "countdown", "rec", "done", "idle"]


def test_trace_contains_no_card_uid() -> None:
    """I8: the card number never leaves the card reader."""
    text = str(record(STORIES["samtale"]))
    assert "04A1B2C3" not in text


def test_committed_traces_are_up_to_date() -> None:
    """Vercel shows today's engine: regenerate with ``uv run cutcut trace``."""
    assert main(["trace", "--check"]) == 0


def test_trace_command_writes_files(tmp_path: Path) -> None:
    assert main(["trace", "--out", str(tmp_path)]) == 0
    assert {p.name for p in tmp_path.iterdir()} == {f"{s}.json" for s in STORIES} | {"index.json"}
    assert default_trace_dir().name == "traces"


def test_trace_mirrors_the_studio_setup() -> None:
    """The web simulator shows the app as set up in the studio: Start button, «Gjest»,
    and the pages that read REST (Oppsett, Kameraer, Helse) have answers (U-9)."""
    trace = record(STORIES["samtale"])
    states = [
        m[1]["data"] for m in trace["messages"] if m[1]["type"] == "state" and m[1].get("full")
    ]
    assert states[0]["touch"]["login"] == "open"
    users = [((s.get("session") or {}).get("user") or {}).get("display_name") for s in states]
    assert "Gjest" in users
    paths = {r[1] for r in trace["rest"]}
    assert {"/api/setup/steps", "/api/cameras", "/api/rules", "/api/settings/staff"} <= paths
    assert any(c["status"] != "unknown" for c in states[-1]["health"]["checks"])
