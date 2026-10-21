from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from cutcut.common.ids import CameraId, MicId, Mode, RuleId
from cutcut.common.models import Decision, Session, ShowChoice, ShowConfig

FIXTURES = Path(__file__).parents[2] / "fixtures"


def spec_show() -> dict[str, Any]:
    data: dict[str, Any] = YAML(typ="safe").load(FIXTURES / "spec_show_example.yaml")
    return data


def test_spec_show_example_validates() -> None:
    show = ShowConfig.model_validate(spec_show())
    assert [p.id for p in show.participants] == ["P1", "P2", "P3"]
    assert show.cameras[CameraId.C5].role == "bird"
    assert show.rules_override == {"T7_reaction_after_s": 18}
    assert not show.has_wide


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["participants"].append(dict(d["participants"][0])), "unique"),
        (lambda d: d["participants"][1].update(mic="M1"), "own mic"),
        (lambda d: d["participants"][1].update(mic="M5"), "laptop audio"),
        (lambda d: d["participants"][1].update(camera="C1"), "own camera"),
        (lambda d: d["participants"][2].update(camera="C4"), "not configured"),
        (lambda d: d["cameras"].pop("C5"), "C5"),
        (lambda d: d["cameras"]["C2"].pop("ip"), "needs an ip"),
        (lambda d: d["cameras"]["C3"].update(atem_input=2), "unique"),
        (lambda d: [p.update(role="guest") for p in d["participants"]], "host"),
        (lambda d: d.update(ai_tracking=["C5"]), "AI tracking"),
        (lambda d: d.update(unknown_field=1), "Extra inputs"),
        (lambda d: d.update(participants=[]), "at least 1"),
    ],
)
def test_invalid_show_is_rejected(mutate: Any, message: str) -> None:
    data = copy.deepcopy(spec_show())
    mutate(data)
    with pytest.raises(ValidationError, match=message):
        ShowConfig.model_validate(data)


def test_session_example_from_spec_validates() -> None:
    # spec 7.5, with "recording" and "publish" as written there
    session = Session.model_validate(
        {
            "session_id": "2026-10-20T14:02:11-kanordm",
            "user": {"username": "kanordm", "display_name": "Kari Nordmann"},
            "show": {"type": "podcast", "guests": 2, "video": True, "laptop": False},
            "mode": "N3",
            "recording": {"state": "started", "started_by": "touch", "duration_s": 2472},
            "publish": {"target": "panopto", "folder": "Mine opptak", "state": "pending"},
        }
    )
    assert session.show.participants == 3
    assert session.mode is Mode.N3


def test_session_has_no_field_for_card_uid() -> None:
    # I8: the card number must never be stored. No model may grow such a field.
    for model in (Session, ShowChoice):
        assert not any("uid" in name or "card" in name for name in model.model_fields)


def test_decision_example_from_spec_validates() -> None:
    decision = Decision.model_validate(
        {
            "ts": "2026-10-20T19:04:11.320+02:00",
            "mode": "N3C",
            "action": "cut",
            "shot": "CU:P2",
            "rule": "T2",
            "reason": "Gjest A aktiv 0,52 s (krav 0,48 s), munn 0,81, 12 dB over de andre",
            "measures": {"run_ms": 520, "vad": 0.88, "mouth": 0.81, "dominance_db": 12},
            "blocked_by": None,
            "companion": {"page": 10, "row": 0, "col": 1},
        }
    )
    assert decision.rule is RuleId.T2
    assert decision.shot == "CU:P2"


def test_decision_rejects_unknown_shot() -> None:
    with pytest.raises(ValidationError, match="unknown shot"):
        Decision.model_validate(
            {
                "ts": "2026-10-20T19:04:11+02:00",
                "mode": "N2",
                "action": "cut",
                "shot": "CU:P9",
                "rule": "T2",
                "reason": "x",
            }
        )


def test_mic_m5_is_laptop() -> None:
    assert ShowConfig.model_validate(spec_show()).content.audio_mic is MicId.M5
