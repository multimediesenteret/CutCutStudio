"""REST and WebSocket API (spec 10.1, 10.2). One API for touch, technician, Companion page 11
and external monitoring. Served by ``core`` on port 8080; the screens are static files here."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.websockets import WebSocketDisconnect

from cutcut import __version__
from cutcut.api.auth import COOKIE, SESSION_S, Auth, Identity, require
from cutcut.app import devices, export, setup_file
from cutcut.app.hub import TOPICS
from cutcut.app.state import LiveSchemas, StudioState
from cutcut.app.studio import CommandError, Studio
from cutcut.common.ids import Shot
from cutcut.common.models.session import ShowChoice, TouchStep, User
from cutcut.common.models.show import RulesPreset
from cutcut.health.model import CheckResult

log = logging.getLogger(__name__)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StaffIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operators: list[str] = Field(default_factory=list)
    admins: list[str] = Field(default_factory=list)


class SetupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=1_000_000)


class SetupChanges(BaseModel):
    changes: list[str]


class LoginModeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["open", "card"]


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
    background: Sequence[Callable[[], Coroutine[Any, Any, None]]] = (),
) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        tasks = (
            [
                asyncio.create_task(_loop(studio, before_tick)),
                asyncio.create_task(studio.health.loop()),
            ]
            if run_loop
            else []
        )
        tasks += [asyncio.create_task(job()) for job in background]  # e.g. the bus reader
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
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
        """Same as the status page, for external monitoring (spec 8.5). No sign-in needed."""
        state = studio.state()
        levels = {a.level for a in state.alerts}
        health = state.health.status
        overall = (
            "error"
            if "error" in levels or health == "red"
            else "warn"
            if "warn" in levels or health == "yellow"
            else "ok"
        )
        if not state.engine.audio_ok:
            overall = "error"
        dump = state.model_dump(
            mode="json", include={"engine", "recording", "runtime", "alerts", "health"}
        )
        return {"status": overall, "version": __version__, **dump}

    @app.post("/api/health/morning-check", tags=["status"])
    async def morning_check(me: Who) -> dict[str, Any]:
        """Run the whole catalogue now («Kjør morgensjekk», technician)."""
        require(me, "operator")
        result = await studio.morning_check("manuell")
        return result.model_dump(mode="json")

    @app.get("/api/health/checks", tags=["status"])
    async def health_checks() -> list[CheckResult]:
        """Latest result of every check (spec 10.1). No sign-in needed, like /api/health."""
        return studio.health.results()

    @app.get("/api/state", tags=["status"])
    async def get_state(me: Who) -> StudioState:
        return studio.state()

    @app.get("/api/session", tags=["session"])
    async def get_session(me: Who) -> dict[str, Any] | None:
        session = studio.sessions.session
        return session.model_dump(mode="json") if session is not None else None

    @app.get("/api/log", tags=["status"])
    async def get_log(me: Who, since: Annotated[int, Query(ge=0)] = 0) -> list[dict[str, Any]]:
        require(me, "operator")
        return [d for d in studio.decisions if d["mono_ms"] >= since]

    @app.get("/api/log.csv", tags=["export"], response_class=Response)
    async def log_csv(me: Who) -> Response:
        """Recent decisions as CSV (spec 8.4)."""
        require(me, "operator")
        text = export.decisions_csv(reversed(list(studio.decisions)))
        return _download(text.encode("utf-8"), "text/csv; charset=utf-8", "cutcut-logg", "csv")

    @app.get("/api/sessions", tags=["session"])
    async def sessions(
        me: Who, days: Annotated[int, Query(ge=1, le=90)] = 1
    ) -> list[dict[str, Any]]:
        """Session history, newest first: who, when, how long, started from (spec 8.4)."""
        require(me, "operator")
        since = studio.deps.clock.now() - timedelta(days=days)
        return await asyncio.to_thread(studio.session_history, since)

    @app.get("/api/sessions.csv", tags=["export"], response_class=Response)
    async def sessions_csv(me: Who, days: Annotated[int, Query(ge=1, le=90)] = 30) -> Response:
        require(me, "operator")
        since = studio.deps.clock.now() - timedelta(days=days)
        rows = await asyncio.to_thread(studio.session_history, since)
        data = export.sessions_csv(rows).encode("utf-8")
        return _download(data, "text/csv; charset=utf-8", "cutcut-okter", "csv")

    @app.get("/api/debug-package", tags=["export"], response_class=Response)
    async def debug_package(me: Who) -> Response:
        """Log, configuration, version and health as a zip, without secrets (spec 12.1)."""
        require(me, "admin")
        data = await asyncio.to_thread(export.debug_package, studio, studio.deps.clock.now())
        return _download(data, "application/zip", "cutcut-feilsok", "zip")

    def _download(data: bytes, media: str, name: str, ext: str) -> Response:
        stamp = studio.deps.clock.now().strftime("%Y-%m-%d-%H%M")
        headers = {"Content-Disposition": f'attachment; filename="{name}-{stamp}.{ext}"'}
        return Response(data, media_type=media, headers=headers)

    @app.get("/api/settings/devices", tags=["config"])
    async def get_devices(me: Who) -> dict[str, Any]:
        """Equipment addresses: the value in use, the value in devices.yaml, and what is changed."""
        require(me, "operator")
        return studio.devices_info()

    @app.put("/api/settings/devices", tags=["config"])
    async def put_devices(body: dict[str, str | None], me: Who) -> dict[str, Any]:
        """Change addresses, e.g. ``{"cameras.C2.ip": "10.10.10.32"}``; ``null`` resets one."""
        require(me, "admin")
        studio.set_devices(body, me.role, me.actor)
        return studio.devices_info()

    @app.get("/api/settings/devices.yaml", tags=["export"], response_class=Response)
    async def devices_yaml(me: Who) -> Response:
        """The equipment list in use, as a devices.yaml for the studio repo."""
        require(me, "admin")
        text = devices.to_yaml(studio.devices)
        return Response(
            text.encode("utf-8"),
            media_type="application/yaml",
            headers={"Content-Disposition": 'attachment; filename="devices.yaml"'},
        )

    @app.get("/api/setup/multiview", tags=["setup"])
    async def multiview(me: Who) -> dict[str, Any]:
        """Rutekart against shows and ATEM, plus the recommended layout (D-055)."""
        require(me, "operator")
        return studio.multiview_status()

    @app.post("/api/setup/multiview/check", tags=["setup"])
    async def multiview_check(me: Who) -> dict[str, Any]:
        """Check the multiview now and warn if it is wrong (also done once at start-up)."""
        require(me, "operator")
        return studio.check_multiview_now(me.role, me.actor)

    @app.get("/api/setup/atem", tags=["setup"])
    async def atem(me: Who) -> dict[str, Any]:
        """What CutCut reads from the ATEM, in ATEM input numbers (machine test DA-5)."""
        require(me, "operator")
        return studio.atem_status()

    @app.get("/api/vision/thumb/{source}", tags=["status"], response_class=Response)
    async def vision_thumb(source: str, me: Who) -> Response:
        """The newest cut-out of a camera window (C1…, LAPTOP) or PVW/PGM, as JPEG (D-056)."""
        require(me, "operator")
        data = studio.vision_thumb(source)
        if data is None:
            raise HTTPException(404, "Ingen bilder fra videolaget nå")
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/setup/mics", tags=["setup"])
    async def mics(me: Who) -> dict[str, Any]:
        """Setup step 5: what has been measured, and what is saved as fasit (AU-7)."""
        require(me, "admin")
        return studio.mic_check_status()

    @app.post("/api/setup/mics/{what}", tags=["setup"])
    async def mic_measure(what: str, me: Who) -> dict[str, Any]:
        """Measure one mic (``M1`` … ``M5``: a person talks for 6 s) or ``noise`` (3 s quiet)."""
        require(me, "admin")
        if what == "save":
            return studio.mic_check_save(me.role, me.actor)
        return studio.mic_check_start(what, me.role, me.actor)

    @app.delete("/api/setup/mics", tags=["setup"])
    async def mic_reset(me: Who) -> Ok:
        require(me, "admin")
        studio.mic_check_reset(me.role, me.actor)
        return Ok()

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

    @app.post("/api/touch/start", tags=["session"])
    async def start_without_card(me: Who) -> Ok:
        """«Start uten kort» (D-057): the touch screen starts a session for «Gjest»."""
        studio.start_without_card(me.role, me.actor)
        return Ok()

    @app.get("/api/settings/staff", tags=["config"])
    async def get_staff(me: Who) -> dict[str, Any]:
        """Technicians who can sign in (Innstillinger → Teknikere). Kept in the app, not in
        the repository. ``first_setup``: the list is empty and the admin PIN lets one in."""
        require(me, "admin")
        return studio.staff_info()

    @app.put("/api/settings/staff", tags=["config"])
    async def put_staff(body: StaffIn, me: Who) -> dict[str, Any]:
        """Replace the list. At least one admin, and you stay admin yourself."""
        require(me, "admin")
        studio.set_staff(body.operators, body.admins, me.role, me.actor)
        return studio.staff_info()

    @app.get("/api/settings/setup.yaml", tags=["export"], response_class=Response)
    async def setup_download(me: Who) -> Response:
        """«Lagre oppsett»: everything entered in the app as one file (no PINs or passwords)."""
        require(me, "admin")
        setup = studio.setup_export()
        name = setup_file.filename(setup.studio, studio.deps.clock.now())
        studio._audit(me.role, me.actor, "setup_export")
        return Response(
            setup_file.dump(setup).encode("utf-8"),
            media_type="application/yaml",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.post("/api/settings/setup/check", tags=["config"])
    async def setup_check(body: SetupIn, me: Who) -> SetupChanges:
        """«Hent oppsett», step 1: what the file would change. Nothing is changed."""
        require(me, "admin")
        return SetupChanges(changes=studio.setup_import(body.text, me.role, me.actor, apply=False))

    @app.post("/api/settings/setup/import", tags=["config"])
    async def setup_import(body: SetupIn, me: Who) -> SetupChanges:
        """«Hent oppsett», step 2: use the file. Everything is checked before anything changes."""
        require(me, "admin")
        return SetupChanges(changes=studio.setup_import(body.text, me.role, me.actor, apply=True))

    @app.get("/api/settings/alerts", tags=["config"])
    async def get_alerts(me: Who) -> dict[str, Any]:
        """Email alerts (HS-3): who gets them, the relay, and how the last one went."""
        require(me, "operator")
        return studio.alerts_info()

    @app.post("/api/settings/alerts/test", tags=["config"])
    async def test_alert(me: Who) -> Ok:
        """«Send testvarsel»: one email now. Admin only; 409 with the reason if it fails.
        Change the address with ``PUT /api/settings/devices {"alerts.email": "…"}``."""
        require(me, "admin")
        await studio.test_alert(me.role, me.actor)
        return Ok()

    @app.get("/api/settings/login", tags=["config"])
    async def get_login(me: Who) -> dict[str, str]:
        require(me, "operator")
        return {"mode": studio.login_mode}

    @app.put("/api/settings/login", tags=["config"])
    async def put_login(body: LoginModeIn, me: Who) -> Ok:
        """Innlogging: «open» (Start-knapp) or «card» (adgangskort). Admin only (D-057)."""
        require(me, "admin")
        studio.set_login_mode(body.mode, me.role, me.actor)
        return Ok()

    @app.post("/api/touch/again", tags=["session"])
    async def again(me: Who) -> Ok:
        """«Ta et nytt opptak» on the done screen: back to ready for the same user."""
        studio.again(me.role, me.actor)
        return Ok()

    @app.post("/api/touch/heartbeat", tags=["status"])
    async def touch_heartbeat(me: Who) -> Ok:
        """The touch screen is alive (every 5 s, SO-6)."""
        studio.touch_heartbeat()
        return Ok()

    @app.get("/api/touch/heartbeat", tags=["status"])
    async def touch_heartbeat_age() -> dict[str, int | None]:
        """For the kiosk guard on the same PC: how long since the touch screen was heard."""
        return {"age_ms": studio.touch_heartbeat_age()}

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

    @app.post("/api/rules/overrides", tags=["tuning"])
    async def rule_overrides(body: dict[str, float | None], me: Who) -> Ok:
        """Fine-tune single rule values on top of the preset; ``null`` resets one (ADR-0011)."""
        require(me, "admin")
        studio.set_overrides(body, me.role, me.actor)
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
                {
                    "type": "state",
                    "seq": 0,
                    "full": True,
                    "data": studio.state().model_dump(mode="json"),
                }
            )
            while True:
                msg = await client.queue.get()
                if client.resync:
                    client.resync = False
                    await websocket.send_json(
                        {
                            "type": "state",
                            "seq": msg["seq"],
                            "full": True,
                            "data": studio.state().model_dump(mode="json"),
                        }
                    )
                    continue
                await websocket.send_json(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            studio.hub.disconnect(client)

    if extra_routes is not None:
        extra_routes(app, who)

    def custom_openapi() -> dict[str, Any]:
        """Add the live (WebSocket) payload models, so the UI types can be generated."""
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi
        from pydantic.json_schema import models_json_schema

        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        _, defs = models_json_schema(
            [(LiveSchemas, "serialization")], ref_template="#/components/schemas/{model}"
        )
        schema.setdefault("components", {}).setdefault("schemas", {}).update(defs["$defs"])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    if ui_dir is not None and ui_dir.is_dir():

        @app.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            return RedirectResponse("/touch/")

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
