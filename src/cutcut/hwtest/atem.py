"""Machine test for the ATEM and Companion (DA-5, docs/plans/devices-companion-atem.md).

``cutcut hwtest atem --site site/ntnu-studio`` with CutCut running (the service): CutCut reads
the ATEM through atem-bridge, the test presses Companion's buttons directly and reads the
result back through CutCut. It answers Q7 (model and firmware) and closes ADR-0012.

| Step | What |
| --- | --- |
| B1 | ATEM connected, model, video format |
| B2 | Multiview matches the rutekart (H-MV) |
| B3 | Layout macros (spec 7.2) |
| B4 | Companion answers, the CutCut pages are imported, its ATEM connection is OK |
| B5 | Every preview button on page 10: the ATEM shows the right input, and how fast |
| B6 | TAKE CUT (changes program: only with confirmation, when nothing is on air) |

The engine is locked (LÅS) while buttons are pressed and released afterwards.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import httpx

from cutcut.common.config import Site, load_site
from cutcut.common.ids import SourceId
from cutcut.devices.atem.bridge import SUPERSOURCE, site_input_map
from cutcut.devices.companion.client import CompanionError, CompanionHttp
from cutcut.hwtest.audio import ConsoleOperator, Operator
from cutcut.hwtest.report import Report, Result, Step

READBACK_S: Final = 2.0
SLOW_MS: Final = 300.0  # spec 5.9: a preview should be visible well before the TAKE


@dataclass
class AtemTest:
    site: Site
    api: httpx.Client  # signed in to CutCut (operator)
    companion: CompanionHttp
    op: Operator
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    report: Report = field(init=False)

    def __post_init__(self) -> None:
        self.report = Report("atem", datetime.now().astimezone())

    def _atem(self) -> dict[str, Any]:
        r = self.api.get("/api/setup/atem")
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return data

    def _wait_for(self, key: str, value: int) -> float | None:
        """Seconds until the ATEM shows ``value`` as ``key``, or None."""
        t0 = self.clock()
        while self.clock() - t0 < READBACK_S:
            if self._atem().get(key) == value:
                return self.clock() - t0
            self.sleep(0.02)
        return None

    def run(self) -> Report:
        atem = self.step_atem()
        if atem is None:
            for id_, title in (
                ("B2", "Multiview"),
                ("B3", "Makroer"),
                ("B5", "Preview-knapper"),
                ("B6", "TAKE"),
            ):
                self.report.add(Step(id_, title, "hoppet over", "ATEM er ikke tilkoblet (B1)."))
            self.step_companion()
            return self.report
        self.step_multiview()
        self.step_macros(atem)
        companion_ok = self.step_companion()
        if not companion_ok:
            for id_, title in (("B5", "Preview-knapper"), ("B6", "TAKE")):
                self.report.add(Step(id_, title, "hoppet over", "Companion svarer ikke (B4)."))
            return self.report
        locked = self.api.post("/api/lock", json={"on": True}).status_code == 200
        try:
            self.step_preview()
            self.step_take()
        finally:
            if locked:
                self.api.post("/api/lock", json={"on": False})
        return self.report

    def step_atem(self) -> dict[str, Any] | None:
        a = self._atem()
        details = {
            k: a.get(k)
            for k in (
                "model",
                "video_mode",
                "program_input",
                "preview_input",
                "recording",
                "last_error",
            )
        }
        if not a.get("connected"):
            self.report.add(
                Step(
                    "B1",
                    "ATEM",
                    "feil",
                    "CutCut får ikke kontakt med ATEM via atem-bridge "
                    f"({a.get('last_error') or 'ingen feilmelding'}). Sjekk IP "
                    "under Oppsett og at atem-bridge kjører (Helse → Prosesser).",
                    details,
                    answers="Q7",
                )
            )
            return None
        want = self.site.devices.atem.model
        model = str(a.get("model") or "ukjent")
        same = want is None or model.replace(" ", "").lower() in want.replace(" ", "").lower()
        result: Result = "ok" if same and a.get("video_mode") in (None, "1080p50") else "advarsel"
        text = f"{model}, {a.get('video_mode') or 'ukjent format'}"
        if not same:
            text += f" (devices.yaml sier {want})"
        if a.get("video_mode") not in (None, "1080p50"):
            text += " – spesifikasjonen forventer 1080p50"
        self.report.add(Step("B1", "ATEM", result, text, details, answers="Q7"))
        return a

    def step_multiview(self) -> None:
        r = self.api.post("/api/setup/multiview/check")
        if r.status_code != 200:
            self.report.add(Step("B2", "Multiview", "hoppet over", f"Svar {r.status_code}."))
            return
        st = r.json()
        errors = [f for f in st.get("findings", []) if f["level"] == "error"]
        warns = [f for f in st.get("findings", []) if f["level"] == "warn"]
        details = {"findings": st.get("findings", []), "readback": st.get("readback")}
        if errors:
            self.report.add(
                Step(
                    "B2", "Multiview", "feil", "; ".join(f["message"] for f in errors[:3]), details
                )
            )
        elif warns:
            self.report.add(
                Step(
                    "B2",
                    "Multiview",
                    "advarsel",
                    "; ".join(f["message"] for f in warns[:3]),
                    details,
                )
            )
        else:
            self.report.add(Step("B2", "Multiview", "ok", "Stemmer med rutekartet.", details))

    def step_macros(self, atem: dict[str, Any]) -> None:
        problems = atem.get("macro_problems") or []
        details = {"macros": atem.get("macros"), "problems": problems}
        if problems:
            self.report.add(
                Step(
                    "B3",
                    "Makroer",
                    "advarsel",
                    f"{len(problems)} avvik, f.eks. {problems[0]}. Layoutene kan "
                    "ikke brukes før makroene er laget (7.2).",
                    details,
                )
            )
        else:
            self.report.add(Step("B3", "Makroer", "ok", "Alle layoutmakroene finnes.", details))

    def step_companion(self) -> bool:
        want = self.site.devices.companion.pages_version
        try:
            version = self.companion.pages_version()
            conns = self.companion.connections()
        except CompanionError as exc:
            self.report.add(
                Step(
                    "B4",
                    "Companion",
                    "feil",
                    f"Companion svarer ikke ({exc}). Kutt går da rett til ATEM (S5).",
                    {},
                )
            )
            return False
        atem_conns = [c for c in conns if "atem" in (c.module or "").lower()]
        details = {
            "pages_version": version,
            "expected": want,
            "connections": [c.__dict__ for c in conns],
        }
        problems = []
        if version is None:
            problems.append("CutCut-sidene er ikke importert (docs/studio/companion.md)")
        elif version != want:
            problems.append(f"sidene er versjon {version}, forventet {want}")
        if not atem_conns:
            problems.append("ingen ATEM-tilkobling i Companion")
        elif not any(c.ok for c in atem_conns):
            problems.append("ATEM-tilkoblingen i Companion er ikke OK")
        if problems:
            self.report.add(Step("B4", "Companion", "feil", "; ".join(problems) + ".", details))
            return version is not None and bool(atem_conns)
        self.report.add(
            Step(
                "B4",
                "Companion",
                "ok",
                f"Svarer, sider v{version}, ATEM-tilkoblingen er OK.",
                details,
            )
        )
        return True

    def step_preview(self) -> None:
        if not self.op.wait(
            "B5 trykker preview-knappene på Companion-side 10 én etter én. "
            "Bare PREVIEW endres, ikke det som går på lufta."
        ):
            self.report.add(Step("B5", "Preview-knapper", "hoppet over", "Valgt bort."))
            return
        inputs = {src: n for n, src in site_input_map(list(self.site.shows.values())).items()}
        inputs[SourceId.SUPERSOURCE] = SUPERSOURCE
        page = self.site.devices.companion.engine_page
        rows: dict[str, Any] = {}
        wrong, slow = [], []
        for source, b in self.site.companion_map.preview.items():
            n = inputs.get(source)
            if n is None:
                continue
            self.companion.press(page, b.row, b.col)
            took = self._wait_for("preview_input", n)
            shown = self._atem().get("preview_input")
            ms = None if took is None else round(took * 1000)
            rows[source.value] = {
                "button": f"{page}/{b.row}/{b.col}",
                "input": n,
                "shown": shown,
                "ms": ms,
            }
            if took is None:
                wrong.append(f"{source.value} (knapp {b.row}/{b.col}) ga inngang {shown}, ikke {n}")
            elif ms is not None and ms > SLOW_MS:
                slow.append(f"{source.value} {ms} ms")
        if wrong:
            self.report.add(Step("B5", "Preview-knapper", "feil", "; ".join(wrong) + ".", rows))
        elif slow:
            self.report.add(
                Step(
                    "B5",
                    "Preview-knapper",
                    "advarsel",
                    "Riktig, men tregt: " + ", ".join(slow),
                    rows,
                )
            )
        else:
            worst = max((r["ms"] for r in rows.values() if r["ms"] is not None), default=0)
            self.report.add(
                Step(
                    "B5",
                    "Preview-knapper",
                    "ok",
                    f"Alle {len(rows)} knappene gir riktig inngang, tregeste {worst} ms.",
                    rows,
                )
            )

    def step_take(self) -> None:
        if not self.op.wait(
            "B6 tester TAKE CUT. Dette ENDRER PROGRAM (det som går på lufta). "
            "Bare når ingen sender eller tar opp."
        ):
            self.report.add(Step("B6", "TAKE", "hoppet over", "Valgt bort (endrer program)."))
            return
        cmap = self.site.companion_map
        page = self.site.devices.companion.engine_page
        before = self._atem()
        shown = before.get("preview_input")
        if shown is None:
            self.report.add(Step("B6", "TAKE", "feil", "Vet ikke hva som står på preview."))
            return
        self.companion.press(page, cmap.take_cut.row, cmap.take_cut.col)
        took = self._wait_for("program_input", int(shown))
        details = {"before": before, "after": self._atem()}
        if took is None:
            self.report.add(
                Step(
                    "B6",
                    "TAKE",
                    "feil",
                    f"Program ble ikke inngang {shown} etter TAKE CUT.",
                    details,
                )
            )
        else:
            self.report.add(
                Step(
                    "B6",
                    "TAKE",
                    "ok",
                    f"TAKE CUT satte preview ({shown}) på program på {round(took * 1000)} ms.",
                    details,
                )
            )


def cutcut_session(site: Site, api_url: str | None, user: str | None) -> httpx.Client | None:
    """Sign in to the CutCut that runs (technician). ``None`` when the sign-in is refused."""
    import getpass

    url = api_url or f"http://127.0.0.1:{site.devices.api_port}"
    api = httpx.Client(base_url=url, timeout=5.0, trust_env=False)
    username = user or input("Brukernavn (tekniker): ").strip()
    pin = getpass.getpass("PIN: ")
    if api.post("/api/login", json={"username": username, "pin": pin}).status_code != 200:
        print("Innloggingen ble avvist.")
        return None
    return api


def companion_url(site: Site, api: httpx.Client) -> str:
    """Companion's address as set in the technician window, else from devices.yaml."""
    url = str(site.devices.companion.url)
    devices = api.get("/api/settings/devices")
    if devices.status_code == 200:
        for row in devices.json().get("rows", []):
            if row.get("key") == "companion.url" and row.get("value"):
                url = str(row["value"])
    return url


def main(site_dir: Path, api_url: str | None, user: str | None, out: Path) -> int:
    site = load_site(site_dir)
    api = cutcut_session(site, api_url, user)
    if api is None:
        return 2
    comp = companion_url(site, api)
    print(f"Maskintest ATEM og Companion · CutCut {api.base_url} · Companion {comp}")
    test = AtemTest(site, api, CompanionHttp(comp), ConsoleOperator())
    report = test.run()
    js, md = report.write(out)
    print("\n" + report.to_markdown())
    print(f"Rapport: {md} (lim inn i GitHub-issue DA-5) og {js}")
    return 0 if report.result != "feil" else 1
