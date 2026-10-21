"""The studio running live on the simulator: what ``cutcut sim`` serves (SIM-6).

Synthetic talkers feed the runtime every tick, fake devices react to the engine, and a small
control API (``/api/sim/...``) lets a person or a test "talk", show a slide, scan a test card
or break things – exactly what the Vercel control panel will do.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from cutcut.api.auth import Auth, Identity
from cutcut.app.studio import Studio, StudioDeps
from cutcut.common.clock import Clock
from cutcut.common.config import example_site_dir, load_rule_presets, load_show_types, load_site
from cutcut.common.ids import CameraId, ParticipantId
from cutcut.common.models.session import User
from cutcut.common.platform.secrets import FakeSecretStore
from cutcut.common.platform.system import FakeSystem
from cutcut.common.store import Store
from cutcut.core.inputs import ContentState
from cutcut.setup.multiview import readback_from_map
from cutcut.sim.fakes import FakeAtem, FakeCardReader, FakeNtnuApi, FakePearl
from cutcut.sim.vision import SimVision
from cutcut.sim.voices import Conversation, Voices

SIM_PIN = "1234"


@dataclass
class LiveSim:
    studio: Studio
    atem: FakeAtem
    pearl: FakePearl
    card_reader: FakeCardReader = field(default_factory=FakeCardReader)
    ntnu: FakeNtnuApi = field(default_factory=FakeNtnuApi)
    seed: int = 1
    conversation_on: bool = False
    content: ContentState | None = None
    audio_lost: bool = False
    moving: set[CameraId] = field(default_factory=set)
    mv_wrong: bool = False
    vision: SimVision | None = None  # cutcut sim --vision

    def __post_init__(self) -> None:
        self._voices_for_show()

    def _voices_for_show(self) -> None:
        self.voices = Voices(self.studio.show, seed=self.seed)
        self.conversation = Conversation(self.voices, seed=self.seed)
        self._show_id = self.studio.show.id

    def before_tick(self) -> None:
        if self.studio.show.id != self._show_id:  # participants changed on the ready screen
            self._voices_for_show()
        now = self.studio.now
        if self.conversation_on:
            self.conversation.update(now)
        card = self.card_reader.read()
        if card is not None:
            self._card(card)
        rt = self.studio.runtime
        if not self.audio_lost:
            rt.feed_audio(self.voices.frames(now))
        rt.feed_content(self.content)
        rt.feed_atem(self.atem.readback())
        rt.feed_cameras_moving(frozenset(self.moving))
        if self.vision is not None:
            rb = self.atem.readback()
            self.vision.tick(
                now,
                rb.program if rb else None,
                rb.preview if rb else None,
                {c.value for c in self.moving},
            )

    def multiview_wrong(self, on: bool) -> None:
        """Someone changed the ATEM multiview: windows 1 and 2 swapped, safe area on."""
        self.mv_wrong = on
        mv = self.studio.deps.site.multiview
        if mv is None:
            return
        rb = readback_from_map(mv)
        if on:
            w = list(rb.windows)
            w[0], w[1] = w[1], w[0]
            rb = rb.model_copy(update={"windows": w, "safe_area": True})
        self.atem.multiview = rb

    def _card(self, card: str) -> None:
        try:
            found = self.ntnu.lookup(card)
        except TimeoutError:
            self.studio.apply(self.studio.sessions.lookup_failed())
            return
        if found is None:
            self.studio.apply(self.studio.sessions.card_not_recognised())
            return
        username, name = found
        self.studio.login(User(username=username, display_name=name), "touch", "card")


def build_live_sim(
    clock: Clock,
    *,
    seed: int = 1,
    store: Store | None = None,
    site_dir: Path | None = None,
    vision: bool = False,
) -> tuple[LiveSim, Auth]:
    site = load_site(site_dir or example_site_dir())
    atem, pearl = FakeAtem(), FakePearl()
    if site.multiview is not None:
        atem.multiview = readback_from_map(site.multiview)
    deps = StudioDeps(
        site=site,
        show_types=load_show_types(),
        presets=load_rule_presets(),
        clock=clock,
        executor=atem,
        recorder=pearl,
        store=store,
        simulator=True,
        system=FakeSystem(),
    )
    studio = Studio(deps)
    secrets = FakeSecretStore({"operator_pin": SIM_PIN, "admin_pin": SIM_PIN})
    auth = Auth(site.staff, secrets, dev_admin=True)
    sim = LiveSim(studio, atem, pearl, seed=seed)
    if vision and site.multiview is not None:
        sim.vision = SimVision(site.multiview, studio.runtime)
        studio.on_vision_want = lambda: sim.vision.want(studio.now) if sim.vision else None
    return sim, auth


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TalkIn(_In):
    participant: ParticipantId
    on: bool
    dominance_db: float = 12.0
    muted: bool | None = None  # fader down on the RØDECaster (S6, AU-7)


class OnIn(_In):
    on: bool


class ContentIn(_In):
    state: ContentState | None


class CardIn(_In):
    card: str


class FaultIn(_In):
    kind: Literal[
        "audio_lost",
        "atem_down",
        "companion_down",
        "camera_moving",
        "pearl_fail",
        "ntnu_down",
        "card_reader_down",
        "multiview_wrong",
        "pearl_offline",
        "disk_full",
    ]
    on: bool
    camera: CameraId | None = None


def sim_routes(sim: LiveSim) -> Callable[[FastAPI, Callable[..., Awaitable[Identity]]], None]:
    """Control API for the simulator. Only mounted by ``cutcut sim``, never in the studio."""

    def add(app: FastAPI, who: Callable[..., Awaitable[Identity]]) -> None:
        @app.get("/api/sim", tags=["simulator"])
        async def status() -> dict[str, object]:
            return {
                "conversation": sim.conversation_on,
                "content": sim.content,
                "audio_lost": sim.audio_lost,
                "atem_online": sim.atem.online,
                "companion_online": sim.atem.companion_online,
                "moving": sorted(c.value for c in sim.moving),
                "multiview_wrong": sim.mv_wrong,
                "pearl_online": sim.pearl.online,
                "disk_full": sim.studio.deps.system is not None
                and sim.studio.deps.system.snapshot(Path(".")).disk_free_gb < 2,
                "test_cards": ["04A1B2C3", "04D4E5F6"],
            }

        @app.post("/api/sim/talk", tags=["simulator"])
        async def talk(body: TalkIn) -> dict[str, bool]:
            if body.participant not in sim.voices.voices:
                raise HTTPException(409, f"{body.participant.value} er ikke med i oppsettet")
            if body.muted is not None:
                sim.voices.voices[body.participant].muted = body.muted
            if body.on:
                sim.voices.talk(body.participant, sim.studio.now, body.dominance_db)
            else:
                sim.voices.stop(body.participant, sim.studio.now)
            return {"ok": True}

        @app.post("/api/sim/conversation", tags=["simulator"])
        async def conversation(body: OnIn) -> dict[str, bool]:
            sim.conversation_on = body.on
            if not body.on:
                for pid in list(sim.voices.voices):
                    sim.voices.stop(pid, sim.studio.now)
            return {"ok": True}

        @app.post("/api/sim/content", tags=["simulator"])
        async def content(body: ContentIn) -> dict[str, bool]:
            sim.content = body.state
            return {"ok": True}

        @app.post("/api/sim/laptop-audio", tags=["simulator"])
        async def laptop_audio(body: OnIn) -> dict[str, bool]:
            sim.voices.laptop.talking = body.on
            return {"ok": True}

        @app.post("/api/sim/card", tags=["simulator"])
        async def card(body: CardIn) -> dict[str, bool]:
            sim.card_reader.present(body.card)
            return {"ok": True}

        @app.post("/api/sim/fault", tags=["simulator"])
        async def fault(body: FaultIn) -> dict[str, bool]:
            match body.kind:
                case "audio_lost":
                    sim.audio_lost = body.on
                case "atem_down":
                    sim.atem.online = not body.on
                case "companion_down":
                    sim.atem.companion_online = not body.on
                case "camera_moving":
                    if body.camera is None:
                        raise HTTPException(422, "camera mangler")
                    (sim.moving.add if body.on else sim.moving.discard)(body.camera)
                case "pearl_fail":
                    if body.on:
                        sim.pearl.fail()
                case "ntnu_down":
                    sim.ntnu.online = not body.on
                case "card_reader_down":
                    sim.card_reader.connected = not body.on
                case "multiview_wrong":
                    sim.multiview_wrong(body.on)
                case "pearl_offline":
                    sim.pearl.online = not body.on
                case "disk_full":
                    system = sim.studio.deps.system
                    if isinstance(system, FakeSystem):
                        system.value = replace(
                            system.value,
                            disk_free_gb=1.2 if body.on else 400.0,
                            disk_free_percent=0.5 if body.on else 80.0,
                        )
            return {"ok": True}

    return add
