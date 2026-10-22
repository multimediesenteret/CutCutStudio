"""Video confirmation V1–V5, PV3 and reaction shots R1–R3 (spec 6.5, 5.13; P7).

The engine gets per-camera measurements from the video layer (P6): face found and usable,
mouth movement, smile and nod, face position. With ``video_confirm`` and ``reactions`` off it
cuts exactly as base mode."""

from __future__ import annotations

from collections.abc import Mapping

from cutcut.common.ids import CameraId, RuleId, SourceId
from cutcut.core.inputs import TileFrame
from cutcut.core.intents import NudgeCamera
from tests.rules.harness import Harness, started

VC = {"video_confirm": True}
BOTH = {"video_confirm": True, "reactions": True}


def tiles(
    h: Harness,
    *,
    mouth: dict[str, float] | None = None,
    react: dict[str, float] | None = None,
    face: bool = True,
    moving: set[str] | None = None,
    pos: dict[str, tuple[float, float]] | None = None,
) -> None:
    v: dict[SourceId, TileFrame] = {}
    for p in h.show.participants:
        cam = SourceId(p.camera.value)
        x, y = (pos or {}).get(p.id.value, (0.5, 0.42))
        v[cam] = TileFrame(
            face_ok=face,
            mouth=(mouth or {}).get(p.id.value, 0.0),
            smile=(react or {}).get(p.id.value, 0.0),
            moving=p.id.value in (moving or set()),
            face_x=x,
            face_y=y,
        )
    h.vision = v


def first_cut_ms(h: Harness, shot: str) -> int:
    return next(d.mono_ms for d in h.cuts() if d.shot == shot)


def test_V1_a_moving_mouth_shortens_T2() -> None:
    base, vc = started(), started(features=VC)
    for h in (base, vc):
        tiles(h, mouth={"P2": 0.8})
        h.talk("P2")
        h.run(2500)
    assert first_cut_ms(vc, "CU:P2") < first_cut_ms(base, "CU:P2")
    assert any(d.rule is RuleId.V1 for d in vc.cuts())


def test_V1_an_active_mic_with_a_still_mouth_is_leakage() -> None:
    h = started(features=VC)
    tiles(h)  # every mouth still
    h.talk("P2")
    h.run(3000)
    assert h.program != "CU:P2"
    assert [d for d in h.waits() if d.blocked_by is RuleId.V1]


def test_V1_off_means_the_mic_alone_decides() -> None:
    h = started()
    tiles(h)
    h.talk("P2")
    h.run(3000)
    assert h.program == "CU:P2"


def test_V2_no_valid_face_no_take() -> None:
    h = started(features=VC)
    tiles(h, mouth={"P2": 0.8}, face=False)
    h.talk("P2")
    h.run(3000)
    assert h.program != "CU:P2"


def test_V2_a_valid_face_is_taken() -> None:
    h = started(features=VC)
    tiles(h, mouth={"P2": 0.8})
    h.talk("P2")
    h.run(3000)
    assert h.program == "CU:P2"


def test_V3_the_reaction_shot_shows_who_reacts_most() -> None:
    h = started(3, features=BOTH, overrides={"R2_min_gap_s": 600})  # only T7 here, not R1
    tiles(h, mouth={"P1": 0.8}, react={"P3": 0.9})
    h.phrases("P1", 30_000)
    shots = [d.shot for d in h.cuts() if d.rule is RuleId.V3]
    assert shots
    assert set(shots) == {"CU:P3"}


def test_V3_off_uses_the_usual_listener() -> None:
    h = started(3, features=VC)
    tiles(h, mouth={"P1": 0.8}, react={"P3": 0.9})
    h.phrases("P1", 30_000)
    assert not [d for d in h.cuts() if d.rule is RuleId.V3]


def test_V4_a_face_too_low_is_corrected_off_air() -> None:
    h = started(features=VC)
    tiles(h, mouth={"P1": 0.8}, pos={"P2": (0.5, 0.60)})  # P2's face sits low
    h.talk("P1")
    h.run(6000)
    nudges = [i for _, i in h.intents if isinstance(i, NudgeCamera)]
    assert nudges
    assert nudges[0].camera is CameraId.C2
    assert nudges[0].tilt < 0  # tilt down so the face moves up


def test_V4_never_on_air() -> None:
    h = started(features=VC)
    tiles(h, mouth={"P1": 0.8})
    h.talk("P1")
    h.run(3000)
    assert h.program == "CU:P1"
    since = h.now
    tiles(h, mouth={"P1": 0.8}, pos={"P1": (0.5, 0.60)})  # P1's face sits low, on program
    h.run(6000)
    late = [i for t, i in h.intents if t > since and isinstance(i, NudgeCamera)]
    assert not [i for i in late if i.camera is CameraId.C1]


def test_V5_a_moving_picture_is_not_a_valid_angle() -> None:
    h = started(features=VC)
    tiles(h, mouth={"P2": 0.8}, moving={"P2"})
    h.talk("P2")
    h.run(2500)
    assert h.program != "CU:P2"
    assert [d for d in h.waits() if d.blocked_by is RuleId.V5]


def test_V5_a_still_picture_is_valid() -> None:
    h = started(features=VC)
    tiles(h, mouth={"P2": 0.8})
    h.talk("P2")
    h.run(2500)
    assert not [d for d in h.waits() if d.blocked_by is RuleId.V5]


def test_PV3_the_preview_must_stand_still_before_take() -> None:
    h = started(features=VC)
    tiles(h, mouth={"P2": 0.8}, moving={"P2"})
    h.talk("P2")
    h.run(300)
    tiles(h, mouth={"P2": 0.8})  # just stopped moving
    h.run(2500)
    assert [d for d in h.waits() if d.blocked_by is RuleId.PV3]
    assert h.program == "CU:P2"  # taken once it stood still V5_still_s


def test_PV3_off_without_video_confirm() -> None:
    h = started()
    tiles(h, mouth={"P2": 0.8}, moving={"P2"})
    h.talk("P2")
    h.run(2500)
    assert not [d for d in h.waits() if d.blocked_by is RuleId.PV3]


def react_scene(features: Mapping[str, object]) -> Harness:
    h = started(features=dict(features))
    tiles(h, mouth={"P1": 0.8})
    h.talk("P1")
    h.run(9000)
    tiles(h, mouth={"P1": 0.8}, react={"P2": 0.9})
    h.run(500)
    h.stop("P1")
    h.run(800)
    h.talk("P1")
    h.run(4000)
    return h


def test_R1_a_listener_who_reacts_gets_a_reaction_shot_in_the_pause() -> None:
    h = react_scene(BOTH)
    r1 = [d for d in h.cuts() if d.rule is RuleId.R1]
    assert r1
    assert r1[0].shot == "CU:P2"
    assert h.program == "CU:P1"  # and back to the speaker (H4)


def test_R1_in_shadow_is_only_logged() -> None:
    h = react_scene({"video_confirm": True, "shadow": ["reactions"]})
    assert not [d for d in h.cuts() if d.rule is RuleId.R1]
    assert [d for d in h.decisions if d.switch == "reactions"]


def test_R2_not_on_a_short_answer() -> None:
    h = started(features=BOTH)
    tiles(h, mouth={"P1": 0.8}, react={"P2": 0.9})
    h.talk("P1")
    h.run(4000)  # P1 on air only a short while
    h.stop("P1")
    h.run(800)
    assert not [d for d in h.cuts() if d.rule is RuleId.R1]


def test_R2_at_most_one_reaction_per_gap() -> None:
    h = react_scene(BOTH)
    for _ in range(3):
        h.stop("P1")
        h.run(800)
        h.talk("P1")
        h.run(3000)
    assert len([d for d in h.cuts() if d.rule is RuleId.R1]) == 1


def test_R3_the_listener_who_starts_talking_is_the_speaker() -> None:
    h = started(features=BOTH)
    tiles(h, mouth={"P1": 0.8})
    h.talk("P1")
    h.run(9000)
    tiles(h, mouth={"P1": 0.8, "P2": 0.8}, react={"P2": 0.9})
    h.run(500)
    h.stop("P1")
    h.run(800)
    assert h.program == "CU:P2"  # the reaction shot
    h.talk("P2")
    h.run(3000)
    assert h.program == "CU:P2"
    assert any(d.rule is RuleId.R3 for d in h.decisions)


def test_R3_a_listener_who_stays_quiet_returns_to_the_speaker() -> None:
    h = react_scene(BOTH)
    assert not any(d.rule is RuleId.R3 for d in h.decisions)
