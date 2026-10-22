"""The health catalogue (spec 8.5), built from small getters so it runs the same in the
studio and in the simulator. Every check only reads: none presses a button or moves a camera.

| ID | What | Every | Red/yellow |
| --- | --- | --- | --- |
| ``H-AUD-1`` | audio-capture measurements arrive | 1 s | red after 2 s |
| ``H-PROC-*`` | processes, from the supervisor | 1–2 s | yellow |
| ``H-PC-1/2/3`` | disk, memory, CPU | 30 s | yellow; disk red under 2 GB |
| ``H-PRL-1`` | Pearl answers, no error, storage | 5 s | red offline or < 15 min |
| ``H-ATEM-1`` | ATEM program/preview readable | 1 s | red |
| ``H-COMP-1`` | Companion API and page version | 5 s | red |
| ``H-CAM-<C>`` | PTZ camera answers under 200 ms, in manual | 10 s | yellow |
| ``H-CAM-MOVE`` | no camera moved without CutCut asking | 2 s | red |
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from cutcut.common.platform.system import SystemSnapshot
from cutcut.devices.atem.macros import LAYOUT_MACROS
from cutcut.devices.atem.macros import check as atem_macro_check
from cutcut.health.engine import FuncCheck
from cutcut.health.model import CheckLevel, CheckResult

AUDIO_RED_MS = 2_000  # S4: two seconds without measurements (spec 5.7)


def audio_stream(
    age_ms: Callable[[], int | None],
    now: Callable[[], datetime],
    detail: Callable[[], dict[str, object]] | None = None,
) -> FuncCheck:
    """``H-AUD-1``: measurements from audio-capture arrive (the ASIO stream is alive).

    When audio-capture says why (``audio.status``: no RØDECaster, stream stopped), the
    message says so too."""

    def run() -> CheckResult:
        age = age_ms()
        why = (detail() if detail else {}).get("last_error")
        if age is None:
            status, value, msg = "red", "ingen lyd", "Ingen lyd fra audio-capture ennå."
        elif age > AUDIO_RED_MS:
            status, value = "red", f"{age / 1000:.1f} s siden"
            msg = "Lyden fra RØDECaster har stoppet. Motoren klipper ikke på lyd (S4)."
            if why:
                msg += f" audio-capture: {why}."
        else:
            status, value, msg = "green", f"{age} ms", "Lyden kommer jevnt."
        return CheckResult(
            id="H-AUD-1",
            status=status,  # type: ignore[arg-type]
            value=value,
            expected=f"under {AUDIO_RED_MS} ms",
            message=msg,
            ts=now(),
            # The touch screen already hears about lost audio from the engine (S4), at once
            # and only while it lasts; this check is for the technician.
        )

    return FuncCheck("H-AUD-1", 1.0, run)


def _result(
    cid: str,
    status: str,
    value: str,
    message: str,
    now: Callable[[], datetime],
    *,
    expected: str | None = None,
    level: CheckLevel = "connected",
    for_user: bool = False,
) -> CheckResult:
    return CheckResult(
        id=cid,
        status=status,  # type: ignore[arg-type]
        value=value,
        expected=expected,
        message=message,
        ts=now(),
        level=level,
        for_user=for_user,
    )


# -- H-PROC: processes, from the supervisor (SO-1) ---------------------------------------------

PROC_FLAP = 5  # restarts in 10 minutes (spec 9.1)


@dataclass(frozen=True)
class ProcessReading:
    name: str
    running: bool
    restarts_10min: int = 0
    last_reason: str | None = None


def process(
    name: str, get: Callable[[], ProcessReading | None], now: Callable[[], datetime]
) -> FuncCheck:
    """``H-PROC-<name>``: yellow while the supervisor restarts it, or when it keeps falling
    over. The studio keeps working (spec 8.5: «Gult; supervisor restarter»)."""
    cid = f"H-PROC-{name}"

    def run() -> CheckResult:
        p = get()
        if p is None:
            return _result(cid, "yellow", "ukjent", f"Ingen status for {name}.", now)
        if not p.running:
            why = f" ({p.last_reason})" if p.last_reason else ""
            return _result(cid, "yellow", "nede", f"{name} startes på nytt{why}.", now)
        if p.restarts_10min > PROC_FLAP:
            msg = f"{name} er startet på nytt {p.restarts_10min} ganger på 10 minutter."
            return _result(
                cid, "yellow", f"{p.restarts_10min} omstarter", msg, now, expected="høyst 5"
            )
        return _result(cid, "green", "kjører", f"{name} kjører.", now)

    return FuncCheck(cid, 1.0, run, level="working")


def supervisor(age_ms: Callable[[], int], now: Callable[[], datetime]) -> FuncCheck:
    """``H-PROC-supervisor``: the supervisor itself still reports (every 2 s)."""

    def run() -> CheckResult:
        age = age_ms()
        if age > 10_000:
            return _result(
                "H-PROC-supervisor",
                "yellow",
                f"{age // 1000} s siden",
                "Supervisor sender ikke status. Prosessene startes ikke på nytt om de faller ut.",
                now,
                expected="hvert 2. s",
            )
        return _result("H-PROC-supervisor", "green", "sender", "Supervisor passer på.", now)

    return FuncCheck("H-PROC-supervisor", 2.0, run, level="working")


VIDEO_STALE_MS = 2_000
VIDEO_MIN_FPS = 10


def video(
    frame_age_ms: Callable[[], int | None],
    status: Callable[[], dict[str, object]],
    now: Callable[[], datetime],
) -> FuncCheck:
    """``H-VID-1``: the video layer gets pictures from the capture card at full rate, with
    signal (spec 8.5). Yellow: the engine cuts on sound alone meanwhile (6.6)."""

    def run() -> CheckResult:
        age = frame_age_ms()
        st = status()
        expected = f"minst {VIDEO_MIN_FPS} bilder/s"
        if age is None or age > VIDEO_STALE_MS:
            why = st.get("last_error") or "ingen bilder"
            return _result(
                "H-VID-1",
                "yellow",
                "ingen bilder",
                f"Videolaget får ikke bilder ({why}). Motoren klipper på lyd.",
                now,
                expected=expected,
            )
        fps = int(str(st.get("fps") or 0))
        if fps < VIDEO_MIN_FPS:
            return _result(
                "H-VID-1",
                "yellow",
                f"{fps} bilder/s",
                "Videolaget får for få bilder. Sjekk USB 3-porten til INOGENI.",
                now,
                expected=expected,
            )
        return _result(
            "H-VID-1", "green", f"{fps} bilder/s", "Videolaget får bilder.", now, expected=expected
        )

    return FuncCheck("H-VID-1", 2.0, run, level="working")


PGM_MISMATCH_MS = 3_000


def program_confirm(
    seen: Callable[[], str | None],
    atem_says: Callable[[], str | None],
    mismatch_ms: Callable[[], int],
    now: Callable[[], datetime],
) -> FuncCheck:
    """``H-VID-3``: the program window in the multiview shows the camera the ATEM says is on
    program (VI-3). Yellow after 3 s apart: the rutekart or the multiview is probably wrong, and
    CutCut would judge the wrong picture."""

    def run() -> CheckResult:
        a, v = atem_says(), seen()
        if a is None or v is None:
            return _result(
                "H-VID-3",
                "green",
                "ikke sammenlignbart",
                "Program sammenlignes når både ATEM og videolaget ser et kamera.",
                now,
            )
        if a != v and mismatch_ms() >= PGM_MISMATCH_MS:
            return _result(
                "H-VID-3",
                "yellow",
                f"bildet ligner {v}",
                f"ATEM sier {a} på program, "
                f"men programruta ligner {v}. Sjekk rutekartet (Oppsett).",
                now,
                expected=a,
                level="as_agreed",
            )
        return _result("H-VID-3", "green", v, "Programruta viser det ATEM sier.", now, expected=a)

    return FuncCheck("H-VID-3", 2.0, run, level="as_agreed")


TOUCH_STALE_MS = 30_000


def touch_screen(age_ms: Callable[[], int | None], now: Callable[[], datetime]) -> FuncCheck:
    """``H-PROC-touch``: the touch screen in the studio sends its heartbeat (spec 8.5). Yellow:
    the kiosk guard reloads Edge by itself (SO-6)."""

    def run() -> CheckResult:
        age = age_ms()
        if age is None or age > TOUCH_STALE_MS:
            value = "ingen kontakt" if age is None else f"{age // 1000} s siden"
            msg = "Touch-skjermen svarer ikke. Kiosk-vakten laster den på nytt."
            return _result("H-PROC-touch", "yellow", value, msg, now, expected="hvert 5. s")
        return _result("H-PROC-touch", "green", "svarer", "Touch-skjermen er i gang.", now)

    return FuncCheck("H-PROC-touch", 5.0, run, level="working")


# -- H-PC: the PC ------------------------------------------------------------------------------

DISK_YELLOW_GB = 20.0
DISK_RED_GB = 2.0  # the database and logs need room to write
MEMORY_YELLOW_PCT = 90.0
CPU_YELLOW_PCT = 85.0


def pc(snapshot: Callable[[], SystemSnapshot], now: Callable[[], datetime]) -> list[FuncCheck]:
    """``H-PC-1`` disk, ``H-PC-2`` memory, ``H-PC-3`` CPU, every 30 s (spec 8.5).

    GPU temperature and the NTP clock come with the test PC (Q8, Q20)."""

    def disk() -> CheckResult:
        s = snapshot()
        value = f"{s.disk_free_gb:.0f} GB ledig ({s.disk_free_percent:.0f} %)"
        expected = f"over {DISK_YELLOW_GB:.0f} GB"
        if s.disk_free_gb < DISK_RED_GB:
            msg = "Disken er nesten full. Logg og database kan slutte å skrive."
            return _result("H-PC-1", "red", value, msg, now, expected=expected, level="working")
        if s.disk_free_gb < DISK_YELLOW_GB:
            msg = "Lite plass igjen på disken."
            return _result("H-PC-1", "yellow", value, msg, now, expected=expected, level="working")
        return _result("H-PC-1", "green", value, "Nok plass på disken.", now, expected=expected)

    def memory() -> CheckResult:
        s = snapshot()
        value = f"{s.memory_percent:.0f} % brukt"
        expected = f"under {MEMORY_YELLOW_PCT:.0f} %"
        if s.memory_percent >= MEMORY_YELLOW_PCT:
            msg = "Minnet er nesten fullt."
            return _result("H-PC-2", "yellow", value, msg, now, expected=expected, level="working")
        return _result("H-PC-2", "green", value, "Nok minne.", now, expected=expected)

    def cpu() -> CheckResult:
        s = snapshot()
        value = f"{s.cpu_percent:.0f} %"
        expected = f"under {CPU_YELLOW_PCT:.0f} %"
        if s.cpu_percent >= CPU_YELLOW_PCT:
            msg = "Prosessoren er nesten fullt belastet. Motoren kan bli treg."
            return _result("H-PC-3", "yellow", value, msg, now, expected=expected, level="working")
        return _result("H-PC-3", "green", value, "Prosessoren har nok kapasitet.", now)

    return [
        FuncCheck("H-PC-1", 30.0, disk, level="working"),
        FuncCheck("H-PC-2", 30.0, memory, level="working"),
        FuncCheck("H-PC-3", 30.0, cpu, level="working"),
    ]


# -- H-PRL-1: Pearl ----------------------------------------------------------------------------

PEARL_MBPS = 20.0  # assumed total recording bitrate until measured in the machine test (DA-5)
STORAGE_YELLOW_MIN = 60  # spec 8.5: over 60 min
STORAGE_RED_MIN = 15


@dataclass(frozen=True)
class PearlReading:
    online: bool
    error: str | None = None
    free_bytes: int | None = None  # main storage; None: unknown


def storage_minutes(free_bytes: int) -> int:
    return int(free_bytes * 8 / (PEARL_MBPS * 1e6) / 60)


def pearl(get: Callable[[], PearlReading], now: Callable[[], datetime]) -> FuncCheck:
    """``H-PRL-1``: Pearl answers, has no error, and has room for an hour of recording.

    An offline Pearl is red for the user too: nothing would be recorded. That a recording
    stops by itself is the session's own alarm (``H-PRL-2``, I7)."""

    def run() -> CheckResult:
        p = get()
        if not p.online:
            return _result(
                "H-PRL-1",
                "red",
                "svarer ikke",
                "Pearl svarer ikke. Opptak kan ikke startes.",
                now,
                for_user=True,
            )
        if p.free_bytes is not None:
            minutes = storage_minutes(p.free_bytes)
            value = f"{minutes} min ledig"
            expected = f"over {STORAGE_YELLOW_MIN} min"
            if minutes < STORAGE_RED_MIN:
                msg = "Pearl er nesten full. Et opptak nå kan stoppe av seg selv."
                return _result("H-PRL-1", "red", value, msg, now, expected=expected, for_user=True)
            if minutes < STORAGE_YELLOW_MIN:
                msg = "Lite plass på Pearl. Flytt eller slett gamle opptak."
                return _result("H-PRL-1", "yellow", value, msg, now, expected=expected)
        if p.error:
            return _result("H-PRL-1", "yellow", "feil", f"Pearl melder: {p.error}", now)
        value = f"{storage_minutes(p.free_bytes)} min ledig" if p.free_bytes else "svarer"
        return _result("H-PRL-1", "green", value, "Pearl er klar.", now)

    return FuncCheck("H-PRL-1", 5.0, run)


# -- H-ATEM-1 ---------------------------------------------------------------------------------

ATEM_GRACE_S = 15.0  # atem-bridge needs a few seconds to connect after start


def atem(
    connected: Callable[[], bool], uptime_s: Callable[[], float], now: Callable[[], datetime]
) -> FuncCheck:
    """``H-ATEM-1``: program and preview can be read (spec 8.5). Red, also for the user."""

    def run() -> CheckResult:
        if connected():
            return _result("H-ATEM-1", "green", "tilkoblet", "ATEM svarer.", now)
        if uptime_s() < ATEM_GRACE_S:
            return _result("H-ATEM-1", "green", "kobler til", "Kobler til ATEM …", now)
        return _result(
            "H-ATEM-1",
            "red",
            "ikke tilkoblet",
            "ATEM svarer ikke. CutCut kan ikke klippe.",
            now,
            for_user=True,
        )

    return FuncCheck("H-ATEM-1", 1.0, run)


def atem_macros(
    read: Callable[[], dict[int, str] | None], now: Callable[[], datetime]
) -> FuncCheck:
    """``H-ATEM-3``: the layout macros (spec 7.2) are in the ATEM with the right names.
    Yellow: the layouts are then switched off; the rest of the studio is not affected."""

    def run() -> CheckResult:
        found = read()
        if found is None:
            return _result("H-ATEM-3", "green", "venter på ATEM", "ATEM er ikke lest ennå.", now)
        problems = atem_macro_check(found)
        expected = f"{len(LAYOUT_MACROS)} makroer (7.2)"
        if problems:
            more = f" (+{len(problems) - 1} til)" if len(problems) > 1 else ""
            return _result(
                "H-ATEM-3",
                "yellow",
                f"{len(problems)} avvik",
                f"{problems[0]}{more}. Layoutene kan ikke slås på før makroene er laget.",
                now,
                expected=expected,
                level="as_agreed",
            )
        return _result(
            "H-ATEM-3", "green", "alle finnes", "Layoutmakroene finnes.", now, expected=expected
        )

    return FuncCheck("H-ATEM-3", 300.0, run, level="as_agreed")


# -- H-COMP-1 ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class CompanionReading:
    reachable: bool
    pages_version: int | None = None  # None with pages_read: the pages are not imported
    pages_read: bool = False  # False in the simulator: nothing to read
    error: str | None = None


def companion(
    read: Callable[[], CompanionReading], expected_version: int, now: Callable[[], datetime]
) -> FuncCheck:
    """``H-COMP-1``: Companion's HTTP API answers and has CutCut's pages in the right version.

    ``read`` may block on the network; it runs in a worker thread. Red when down (cuts then
    go straight to the ATEM, ``S5``) or when the pages are another version (buttons would do
    the wrong thing). Not for the user: the reserve keeps the studio working."""

    async def run() -> CheckResult:
        r = await asyncio.to_thread(read)
        expected = f"svarer, sider v{expected_version}"
        if not r.reachable:
            why = f" ({r.error})" if r.error else ""
            msg = f"Companion svarer ikke{why}. Kutt går rett til ATEM (S5)."
            return _result("H-COMP-1", "red", "svarer ikke", msg, now, expected=expected)
        if r.pages_read and r.pages_version is None:
            return _result(
                "H-COMP-1",
                "red",
                "ingen CutCut-sider",
                "CutCut-sidene er ikke importert i Companion (cutcut-pages).",
                now,
                expected=expected,
                level="as_agreed",
            )
        if r.pages_version is not None and r.pages_version != expected_version:
            return _result(
                "H-COMP-1",
                "red",
                f"sider v{r.pages_version}",
                "Companion har feil versjon av CutCut-sidene. Importer cutcut-pages på nytt.",
                now,
                expected=expected,
                level="as_agreed",
            )
        value = f"sider v{r.pages_version}" if r.pages_version is not None else "svarer"
        return _result("H-COMP-1", "green", value, "Companion svarer.", now, expected=expected)

    return FuncCheck("H-COMP-1", 5.0, run)


# -- H-CAM: PTZ cameras (CA-6) ---------------------------------------------------------------

CAM_ANSWER_MS = 200  # spec 8.5: «Svar under 200 ms»
CAM_START_GRACE_S = 15.0  # the first status read is still under way
CAM_MOVE_RED_S = 10.0  # H-CAM-MOVE stays red this long after the camera moved by itself


@dataclass(frozen=True)
class CameraReading:
    name: str  # «Camera 2» as on the screens
    read: bool  # a status has been read at least once
    online: bool
    steered: bool  # the circuit breaker is closed: CutCut can steer it
    mode: str = ""
    answer_ms: float | None = None
    last_error: str | None = None
    since_start_s: float = 0.0
    moved_by_itself_s: float | None = None  # seconds since it moved without being asked


def camera(cid: str, get: Callable[[], CameraReading], now: Callable[[], datetime]) -> FuncCheck:
    """``H-CAM-<camera>``: the camera answers fast, and is in manual white balance and
    exposure as set up. Yellow when not: the picture still comes over SDI/HDMI, only the
    steering (presets, framing) is missing."""

    def run() -> CheckResult:
        r = get()
        expected = f"svar under {CAM_ANSWER_MS} ms, manuell"
        if not r.read:
            if r.since_start_s < CAM_START_GRACE_S:
                return _result(cid, "green", "starter", f"Spør {r.name} for første gang.", now)
            return _result(cid, "yellow", "ukjent", f"{r.name} har ikke svart ennå.", now)
        if not r.online or not r.steered:
            why = f" ({r.last_error})" if r.last_error else ""
            msg = (
                f"{r.name} svarer ikke{why}. Bildet kommer fortsatt, "
                "men CutCut kan ikke styre kameraet."
            )
            return _result(cid, "yellow", "svarer ikke", msg, now, expected=expected)
        if r.answer_ms is not None and r.answer_ms > CAM_ANSWER_MS:
            msg = f"{r.name} svarer tregt ({r.answer_ms:.0f} ms)."
            return _result(
                cid, "yellow", f"{r.answer_ms:.0f} ms", msg, now, expected=expected, level="working"
            )
        if r.mode != "manuell":
            msg = f"{r.name} står i {r.mode}. Sett manuell hvitbalanse og eksponering i setup."
            return _result(cid, "yellow", r.mode, msg, now, expected=expected, level="as_agreed")
        value = f"{r.answer_ms:.0f} ms" if r.answer_ms is not None else "svarer"
        return _result(cid, "green", value, f"{r.name} svarer og står i manuell.", now)

    return FuncCheck(cid, 10.0, run)


def camera_move(get: Callable[[], list[CameraReading]], now: Callable[[], datetime]) -> FuncCheck:
    """``H-CAM-MOVE``: red when a camera moved without CutCut asking and without AI-tracking
    (spec 8.5): someone turned it by hand, or tracking is on when it should not be."""

    def run() -> CheckResult:
        bad = [
            r.name
            for r in get()
            if r.moved_by_itself_s is not None and r.moved_by_itself_s < CAM_MOVE_RED_S
        ]
        if bad:
            names = " og ".join(bad)
            msg = f"{names} har flyttet seg uten at CutCut ba om det. Sjekk kameraet og presetene."
            return _result(
                "H-CAM-MOVE", "red", names, msg, now, expected="står stille", level="as_agreed"
            )
        return _result("H-CAM-MOVE", "green", "i ro", "Ingen kameraer har flyttet seg selv.", now)

    return FuncCheck("H-CAM-MOVE", 2.0, run, level="as_agreed")


# -- H-VARSEL-1: email alerts can be sent (HS-3) ----------------------------------------------


def alert_mail(info: Callable[[], dict[str, object]], now: Callable[[], datetime]) -> FuncCheck:
    """``H-VARSEL-1``: alerts outside the studio can reach someone. Yellow when nobody is set
    up to get them or the last email failed: the studio works, but nobody hears about red."""

    def run() -> CheckResult:
        a = info()
        cid, expected = "H-VARSEL-1", "e-post kan sendes"
        if not a.get("email"):
            msg = "Ingen får varsel på e-post. Legg inn en adresse under Innstillinger → Varsling."
            return _result(
                cid, "yellow", "ingen mottaker", msg, now, expected=expected, level="as_agreed"
            )
        if not a.get("smtp_host"):
            msg = "Ingen SMTP-server er satt opp, så varsler kan ikke sendes på e-post."
            return _result(
                cid, "yellow", "ingen SMTP", msg, now, expected=expected, level="as_agreed"
            )
        if a.get("last_error"):
            msg = f"Siste varsel på e-post feilet: {a['last_error']}"
            return _result(cid, "yellow", "feilet", msg, now, expected=expected, level="working")
        return _result(cid, "green", "klar", "Varsler sendes på e-post.", now, expected=expected)

    return FuncCheck("H-VARSEL-1", 30.0, run, level="as_agreed")
