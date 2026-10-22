"""Machine test for the PTZ cameras (CA-5, docs/plans/devices-cameras.md 5).

``cutcut hwtest camera --site C:\\CutCut\\site C2`` talks straight to the camera with the same
driver CutCut uses, and writes the same report as the other machine tests. It answers Q16
(``SetAiEnable``) and gives the numbers for ``Calibration``.

| Step | What | Moves the camera |
| --- | --- | --- |
| KA1 | The protocol answers: power, how fast (under 200 ms) | no |
| KA2 | Position can be read, and stays put when nobody moves it | no |
| KA3 | Manual white balance and exposure (H-CAM-*) | no |
| KA4 | Store a test preset, step away, recall it: back where it was, and how fast | yes |
| KA5 | The slowest zoom speed (``Z3``): how far it gets in 2 s | yes |
| KA6 | Colour temperature over OSC changes the R/B gain (OBSBOT) | no (colour) |
| KA7 | AI-tracking on follows a person, off stands still (Q16, OBSBOT) | yes |

Steps that move or recolour the camera ask first and are skipped when the camera is on program
or preview (I2), as far as CutCut can tell. While the test runs, ``H-CAM-MOVE`` turns red in
CutCut: that is expected.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, TypeVar

from cutcut.common.config import Site, load_site
from cutcut.common.ids import CameraId
from cutcut.devices.cameras import visca
from cutcut.devices.cameras.base import PTZPosition
from cutcut.devices.cameras.factory import make_driver
from cutcut.devices.cameras.obsbot import ObsbotDriver
from cutcut.devices.cameras.service import moved
from cutcut.devices.cameras.visca_ptz import ViscaPtz
from cutcut.hwtest.audio import ConsoleOperator, Operator
from cutcut.hwtest.report import Report, Result, Step

T = TypeVar("T")

ANSWER_MS: Final = 200.0
TEST_PRESET: Final = 99  # a slot the studio does not use
STEP_DEG: Final = 10.0
SETTLE_S: Final = 4.0  # long enough for a preset move at normal speed
BACK_DEG: Final = 1.0  # «back where it was»
WATCH_S: Final = 10.0


@dataclass
class CameraTest:
    cam: CameraId
    driver: ViscaPtz
    op: Operator
    on_air: Callable[[], bool | None] = lambda: None  # None: CutCut cannot tell
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    clock: Callable[[], float] = time.perf_counter
    report: Report = field(init=False)

    def __post_init__(self) -> None:
        self.report = Report(f"kamera-{self.cam.value}", datetime.now().astimezone())
        self.report.env["camera"] = f"{self.cam.value} {type(self.driver).__name__}"

    # --- helpers -------------------------------------------------------------------------

    async def _timed(self, coro: Awaitable[T]) -> tuple[T, float]:
        t0 = self.clock()
        out = await coro
        return out, (self.clock() - t0) * 1000

    def _may_move(self, sid: str, title: str, what: str) -> bool:
        if self.on_air():
            self.report.add(
                Step(sid, title, "hoppet over", "Kameraet er på program eller preview (I2).")
            )
            return False
        if not self.op.wait(f"{sid}: {what} Bare når kameraet ikke er på lufta."):
            self.report.add(Step(sid, title, "hoppet over", "Valgt bort av tekniker."))
            return False
        return True

    async def _raw(self) -> tuple[int, int, int]:
        c = self.driver.client
        pan, tilt = visca.parse_pan_tilt(await c.inquiry(visca.INQ_PAN_TILT))
        zoom = visca.parse_zoom(await c.inquiry(visca.INQ_ZOOM))
        return pan, tilt, zoom

    # --- steps ---------------------------------------------------------------------------

    async def run(self) -> Report:
        if not await self.step_protocol():
            for sid, title in (
                ("KA2", "Posisjon"),
                ("KA3", "Manuell modus"),
                ("KA4", "Presets"),
                ("KA5", "Laveste zoomfart"),
                ("KA6", "Fargetemperatur over OSC"),
                ("KA7", "AI-tracking"),
            ):
                self.report.add(Step(sid, title, "hoppet over", "Kameraet svarer ikke (KA1)."))
            return self.report
        await self.step_position()
        await self.step_manual()
        await self.step_presets()
        await self.step_zoom()
        await self.step_kelvin()
        await self.step_tracking()
        return self.report

    async def step_protocol(self) -> bool:
        try:
            await self.driver.connect()
            st, ms = await self._timed(self.driver.status())
        except Exception as e:
            self.report.add(Step("KA1", "Protokoll", "feil", f"Svarer ikke: {e}"))
            return False
        if not st.online:
            why = st.last_error or "svarer ikke"
            self.report.add(Step("KA1", "Protokoll", "feil", f"VISCA: {why}."))
            return False
        res: Result = "ok" if ms / 3 <= ANSWER_MS else "advarsel"  # status: three questions
        self.report.add(
            Step(
                "KA1",
                "Protokoll",
                res,
                f"VISCA svarer, {ms / 3:.0f} ms per spørsmål (krav under {ANSWER_MS:.0f} ms).",
                {"ms_per_inquiry": round(ms / 3, 1)},
            )
        )
        return True

    async def step_position(self) -> None:
        a = await self.driver.position()
        raw = await self._raw()
        await self.sleep(2.0)
        b = await self.driver.position()
        details = {"position": str(a), "raw_units": raw}
        if a is None or b is None:
            self.report.add(Step("KA2", "Posisjon", "feil", "Posisjonen kan ikke leses.", details))
        elif moved(a, b):
            self.report.add(
                Step(
                    "KA2",
                    "Posisjon",
                    "advarsel",
                    f"Posisjonen endret seg uten kommando ({a} → {b}). AI-tracking på?",
                    details,
                )
            )
        else:
            self.report.add(Step("KA2", "Posisjon", "ok", f"Leses og står stille: {a}.", details))

    async def step_manual(self) -> None:
        st = await self.driver.status()
        if st.mode == "manuell":
            msg = "Manuell hvitbalanse og eksponering."
            self.report.add(Step("KA3", "Manuell modus", "ok", msg))
        else:
            self.report.add(
                Step(
                    "KA3",
                    "Manuell modus",
                    "advarsel",
                    f"Kameraet står i {st.mode}. Sett manuell i kameraets meny eller app.",
                )
            )

    async def step_presets(self) -> None:
        title = "Presets"
        if not self._may_move(
            "KA4", title, f"Lagrer preset {TEST_PRESET}, snur {STEP_DEG:.0f}° og henter den igjen."
        ):
            return
        start = await self.driver.position()
        raw0 = await self._raw()
        if start is None:
            self.report.add(Step("KA4", title, "feil", "Posisjonen kan ikke leses."))
            return
        await self.driver.store_preset(TEST_PRESET)
        await self.driver.move_to(start.pan + STEP_DEG, start.tilt, 0.5)
        await self.sleep(SETTLE_S)
        away = await self.driver.position()
        raw1 = await self._raw()
        t0 = self.clock()
        await self.driver.recall_preset(TEST_PRESET, 0.5)
        back: PTZPosition | None = None
        while self.clock() - t0 < SETTLE_S * 2:
            await self.sleep(0.2)
            back = await self.driver.position()
            if back is not None and abs(back.pan - start.pan) < BACK_DEG:
                break
        secs = self.clock() - t0
        details: dict[str, Any] = {
            "start": str(start),
            "away": str(away),
            "back": str(back),
            "raw_start": raw0,
            "raw_away": raw1,
            "pan_units_for_10_deg": raw1[0] - raw0[0],
        }
        turned = away is not None and abs(away.pan - start.pan) >= STEP_DEG / 2
        home = back is not None and abs(back.pan - start.pan) < BACK_DEG
        if not turned:
            self.report.add(Step("KA4", title, "feil", "Kameraet snudde ikke på move_to.", details))
        elif not home:
            msg = "Preset førte ikke kameraet tilbake."
            self.report.add(Step("KA4", title, "feil", msg, details))
        else:
            self.report.add(
                Step(
                    "KA4",
                    title,
                    "ok",
                    f"Preset lagret og hentet; tilbake på {secs:.1f} s. "
                    f"{STEP_DEG:.0f}° er {raw1[0] - raw0[0]} enheter (Calibration).",
                    details,
                )
            )

    async def step_zoom(self) -> None:
        title = "Laveste zoomfart"
        if not self._may_move("KA5", title, "Zoomer inn med laveste fart i 2 s og tilbake."):
            return
        c = self.driver.client
        z0 = (await self._raw())[2]
        await c.command(visca.zoom_drive(1, 0))
        await self.sleep(2.0)
        await c.command(visca.zoom_drive(0, 0))
        z1 = (await self._raw())[2]
        await c.command(visca.zoom_direct(z0))
        per_s = (z1 - z0) / 2
        details = {"zoom_before": z0, "zoom_after": z1, "units_per_s": per_s}
        if z1 <= z0:
            self.report.add(Step("KA5", title, "feil", "Zoomen beveget seg ikke.", details))
            return
        pct = per_s / 0x4000 * 100
        self.report.add(
            Step(
                "KA5",
                title,
                "ok",
                f"Laveste fart: {pct:.1f} % av zoomområdet per sekund (Z3).",
                details,
            )
        )

    async def step_kelvin(self) -> None:
        title = "Fargetemperatur over OSC"
        if not isinstance(self.driver, ObsbotDriver):
            self.report.add(Step("KA6", title, "hoppet over", "Bare OBSBOT (Canon venter på XC)."))
            return
        if not self._may_move("KA6", title, "Setter 3200 K og så 5600 K (endrer fargen)."):
            return
        c = self.driver.client
        gains: dict[int, tuple[int, int]] = {}
        for k in (3200, 5600):
            await self.driver.set_white_balance(kelvin=k)
            await self.sleep(1.0)
            r = visca.parse_gain(await c.inquiry(visca.INQ_R_GAIN))
            b = visca.parse_gain(await c.inquiry(visca.INQ_B_GAIN))
            gains[k] = (r, b)
        details = {"rb_gain": gains}
        if gains[3200] == gains[5600]:
            self.report.add(
                Step(
                    "KA6",
                    title,
                    "advarsel",
                    "R/B-gain endret seg ikke. Se på bildet om fargen endret seg.",
                    details,
                )
            )
        else:
            msg = "OSC virker: R/B-gain følger kelvin. Satt til 5600 K."
            self.report.add(Step("KA6", title, "ok", msg, details))

    async def _watch(self) -> bool:
        a = await self.driver.position()
        end = self.clock() + WATCH_S
        while self.clock() < end:
            await self.sleep(0.5)
            b = await self.driver.position()
            if a is not None and b is not None and moved(a, b):
                return True
        return False

    async def step_tracking(self) -> None:
        title = "AI-tracking"
        if not isinstance(self.driver, ObsbotDriver):
            self.report.add(Step("KA7", title, "hoppet over", "Kameraet har ikke AI-tracking."))
            return
        if not self._may_move(
            "KA7", title, f"Slår på AI-tracking. Gå sakte foran kameraet i {WATCH_S:.0f} s."
        ):
            return
        await self.driver.set_auto_tracking(True)
        followed = await self._watch()
        await self.driver.set_auto_tracking(False)
        self.op.wait(f"Tracking er av. Gå foran kameraet igjen i {WATCH_S:.0f} s.")
        still = not await self._watch()
        details = {"followed_with_on": followed, "still_with_off": still}
        res: Result
        if followed and still:
            res, msg = "ok", "SetAiEnable virker: kameraet fulgte med på, og sto stille med av."
        elif not followed:
            res, msg = "feil", "Kameraet fulgte ikke med da tracking ble slått på (Q16: nei)."
        else:
            res, msg = "feil", "Kameraet fulgte fortsatt etter at tracking ble slått av."
        self.report.add(Step("KA7", title, res, msg, details, answers="Q16"))


def main(site_dir: Path, camera: str, out: Path, on_air: Callable[[], bool | None] | None) -> int:
    site: Site = load_site(site_dir)
    cam = CameraId(camera)
    dev = site.devices.cameras.get(cam)
    driver = make_driver(cam, dev) if dev is not None else None
    if not isinstance(driver, ViscaPtz):
        print(f"{camera} har ingen styrbar driver i devices.yaml (IP og modell).")
        return 2
    print(f"Maskintest kamera {cam.value} · {dev.model if dev else ''} · {driver.host}")
    test = CameraTest(cam, driver, ConsoleOperator(), on_air or (lambda: None))
    try:
        report = asyncio.run(test.run())
    finally:
        driver.close()
    js, md = report.write(out)
    print("\n" + report.to_markdown())
    print(f"Rapport: {md} (lim inn i GitHub-issue CA-5) og {js}")
    return 0 if report.result != "feil" else 1
