"""REST and WebSocket API (spec 10.1, 10.2). One API for touch, technician, Companion page 11
and external monitoring. Served by ``core`` on port 8080; the screens are static files here."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.websockets import WebSocketDisconnect

from cutcut import __version__
from cutcut.api.auth import COOKIE, SESSION_S, Auth, Identity, require
from cutcut.app.hub import TOPICS
from cutcut.app.studio import CommandError, Studio
from cutcut.common.ids import Shot
from cutcut.common.models.session import ShowChoice, TouchStep, User
from cutcut.common.models.show import RulesPreset

log = logging.getLogger(__name__)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionIn(_In):
    username: str = Field(pattern=r"^[a-z0-9._-]{1,64}$")
    display_name: str | None = Field(default=None, max_length=120)


class ShowIn(_In):
    guests: int = Field(ge=0, le=3)
    video: bool = True
    type: str | None = None
    laptop: bool = False


class StepIn(_In):
    step: TouchStep


class RecordingIn(_In):
    action: Literal["start", "stop"]


class OnIn(_In):
    on: bool


class ShotIn(_In):
    shot: Shot


class ContentIn(_In):
    enabled: bool


class PresetIn(_In):
    preset: RulesPreset


class LoginIn(_In):
    username: str
    pin: str = Field(min_length=4, max_length=12)


class Ok(BaseModel):
    ok: bool = True


TickHook = Callable[[], None]


def create_app(
    studio: Studio,
    auth: Auth,
    *,
    ui_dir: Path | None = None,
    run_loop: bool = True,
    before_tick: TickHook | None = None,
    extra_routes: Callable[[FastAPI, Callable[..., Awaitable[Identity]]], None] | None = None,
) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(_loop(studio, before_tick)) if run_loop else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="CutCut Studio",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.exception_handler(CommandError)
    async def _command_error(_: Request, exc: CommandError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    async def who(request: Request) -> Identity:
        return auth.identify(request)

    Who = Annotated[Identity, Depends(who)]  # noqa: N806 - a type alias for routes below

    # -- read ------------------------------------------------------------------------------

    @app.get("/api/health", tags=["status"])
    async def health() -> dict[str, Any]:
        """Same as the status page, for NTNU monitoring (spec 8.5). No sign-in needed."""
        state = studio.state()
        errors = [a for a in state["alerts"] if a["level"] == "error"]
        warns = [a for a in state["alerts"] if a["level"] == "warn"]
        overall = "error" if errors else "warn" if warns else "ok"
        if not state["engine"]["audio_ok"]:
            overall = "error"
        return {
            "status": overall,
            "version": __version__,
            "engine": state["engine"],
            "recording": state["recording"],
            "runtime": state["runtime"],
            "alerts": state["alerts"],
        }

    @app.get("/api/state", tags=["status"])
    async def get_state(me: Who) -> dict[str, Any]:
        return studio.state()

    @app.get("/api/session", tags=["session"])
    async def get_session(me: Who) -> dict[str, Any] | None:
        session = studio.sessions.session
        return session.model_dump(mode="json") if session is not None else None

    @app.get("/api/log", tags=["status"])
    async def get_log(me: Who, since: Annotated[int, Query(ge=0)] = 0) -> list[dict[str, Any]]:
        require(me, "operator")
        return [d for d in studio.decisions if d["mono_ms"] >= since]

    @app.get("/api/shows", tags=["config"])
    async def shows(me: Who) -> list[dict[str, Any]]:
        require(me, "operator")
        return [
            {"id": s.id, "name": s.name, "participants": len(s.participants)}
            for s in studio.deps.site.shows.values()
        ]

    @app.get("/api/shows/{show_id}", tags=["config"])
    async def show(show_id: str, me: Who) -> dict[str, Any]:
        require(me, "operator")
        if show_id not in studio.deps.site.shows:
            raise HTTPException(404, "Ukjent show")
        return studio.deps.site.shows[show_id].model_dump(mode="json")

    @app.get("/api/rules", tags=["config"])
    async def rules(me: Who) -> dict[str, Any]:
        require(me, "operator")
        return studio.rules_info()

    @app.get("/api/me", tags=["auth"])
    async def me_(me: Who) -> dict[str, str]:
        return {"role": me.role, "actor": me.actor}

    # -- auth ------------------------------------------------------------------------------

    @app.post("/api/login", tags=["auth"])
    async def login(body: LoginIn, response: Response) -> dict[str, str]:
        token, identity = auth.sign_in(body.username, body.pin)
        response.set_cookie(COOKIE, token, max_age=SESSION_S, httponly=True, samesite="strict")
        return {"role": identity.role, "actor": identity.actor}

    @app.post("/api/logout", tags=["auth"])
    async def logout(request: Request, response: Response) -> Ok:
        auth.sign_out(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE)
        return Ok()

    # -- session and touch -----------------------------------------------------------------

    @app.post("/api/session", tags=["session"])
    async def start_session(body: SessionIn, me: Who) -> Ok:
        """Technician starts a session for a user without a card (spec 7.5, 10.1)."""
        require(me, "operator")
        user = User(username=body.username, display_name=body.display_name or body.username)
        studio.login(user, me.role, me.actor, source="tech")
        return Ok()

    @app.put("/api/session/show", tags=["session"])
    async def set_show(body: ShowIn, me: Who) -> Ok:
        studio.set_show(
            ShowChoice(
                type=body.type or studio.deps.show_types.default,
                guests=body.guests,
                video=body.video,
                laptop=body.laptop,
            ),
            me.role,
            me.actor,
        )
        return Ok()

    @app.delete("/api/session", tags=["session"])
    async def end_session(me: Who) -> Ok:
        studio.logout(me.role, me.actor)
        return Ok()

    @app.post("/api/touch/step", tags=["session"])
    async def touch_step(body: StepIn, me: Who) -> Ok:
        require(me, "operator")
        studio.touch_step(body.step, me.role, me.actor)
        return Ok()

    @app.post("/api/touch/touched", tags=["session"])
    async def touched(me: Who) -> Ok:
        studio.touched()
        return Ok()

    @app.post("/api/help", tags=["session"])
    async def help_(me: Who) -> Ok:
        studio.help(me.role, me.actor)
        return Ok()

    @app.post("/api/alerts/{alert_id}/ack", tags=["status"])
    async def ack(alert_id: int, me: Who) -> Ok:
        require(me, "operator")
        studio.acknowledge(alert_id, me.role, me.actor)
        return Ok()

    @app.post("/api/recording", tags=["session"])
    async def recording(body: RecordingIn, me: Who) -> Ok:
        by: Literal["touch", "tech"] = "touch" if me.role == "touch" else "tech"
        if body.action == "start":
            studio.start_recording(by, me.role, me.actor)
        else:
            studio.stop_recording(by, me.role, me.actor)
        return Ok()

    # -- override and tuning (operator / admin) ---------------------------------------------

    @app.post("/api/auto", tags=["override"])
    async def auto(body: OnIn, me: Who) -> Ok:
        require(me, "operator")
        studio.set_auto(body.on, me.role, me.actor)
        return Ok()

    @app.post("/api/lock", tags=["override"])
    async def lock(body: OnIn, me: Who) -> Ok:
        require(me, "operator")
        studio.set_lock(body.on, me.role, me.actor)
        return Ok()

    @app.post("/api/cut", tags=["override"])
    async def cut(body: ShotIn, me: Who) -> Ok:
        require(me, "operator")
        studio.cut(body.shot, me.role, me.actor)
        return Ok()

    @app.post("/api/preview", tags=["override"])
    async def preview(body: ShotIn, me: Who) -> Ok:
        require(me, "operator")
        studio.preview(body.shot, me.role, me.actor)
        return Ok()

    @app.post("/api/content", tags=["override"])
    async def content(body: ContentIn, me: Who) -> Ok:
        require(me, "operator")
        studio.set_content(body.enabled, me.role, me.actor)
        return Ok()

    @app.post("/api/features", tags=["tuning"])
    async def features(body: dict[str, bool], me: Who) -> Ok:
        require(me, "admin")
        studio.set_features(body, me.role, me.actor)
        return Ok()

    @app.post("/api/preset", tags=["tuning"])
    async def preset(body: PresetIn, me: Who) -> Ok:
        require(me, "operator")
        studio.set_preset(body.preset, me.role, me.actor)
        return Ok()

    @app.post("/api/shadow", tags=["tuning"])
    async def shadow(body: OnIn, me: Who) -> Ok:
        require(me, "admin")
        studio.set_shadow(body.on, me.role, me.actor)
        return Ok()

    # -- live ------------------------------------------------------------------------------

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        try:
            auth.identify(websocket)
        except HTTPException:
            await websocket.close(code=4401)
            return
        topics_param = websocket.query_params.get("topics")
        topics = frozenset(topics_param.split(",")) if topics_param else TOPICS
        await websocket.accept()
        client = studio.hub.connect(topics)
        try:
            await websocket.send_json(
                {"type": "state", "seq": 0, "data": studio.state(), "full": True}
            )
            while True:
                msg = await client.queue.get()
                if client.resync:
                    client.resync = False
                    await websocket.send_json(
                        {"type": "state", "seq": msg["seq"], "data": studio.state(), "full": True}
                    )
                    continue
                await websocket.send_json(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            studio.hub.disconnect(client)

    if extra_routes is not None:
        extra_routes(app, who)

    if ui_dir is not None and ui_dir.is_dir():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app


async def _loop(studio: Studio, before_tick: TickHook | None) -> None:
    """Tick the studio every 30 ms. An exception is logged; the loop never dies."""
    from cutcut.core.runtime import TICK_MS

    next_tick = studio.now
    while True:
        try:
            if before_tick is not None:
                before_tick()
            studio.tick()
        except Exception:
            log.exception("studio tick failed")
        next_tick += TICK_MS
        now = studio.now
        if now > next_tick + TICK_MS:
            next_tick = now
        await asyncio.sleep(max(0, next_tick - now) / 1000)
