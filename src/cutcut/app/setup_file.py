"""«Lagre oppsett» and «Hent oppsett»: everything entered in the application, as one file.

Equipment addresses, technicians, email alerts, sign-in mode, rules tuning and the microphone
fasit are entered on the screens and kept in the database on the studio PC, never in the
repository. This file is how they move: download it to keep a copy, upload it to set up a
new PC or go back to an earlier setup. CutCut also writes a copy itself to
``data\\oppsett\\`` on every change (the newest 20, plus ``oppsett-siste.yaml``).

The file is YAML so a technician can read it. It holds no PINs or passwords: those stay in
Windows Credential Manager (spec 12.4).
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML

from cutcut.common.models.baseline import Baseline
from cutcut.common.models.site import Staff

KIND: Final = "cutcut-oppsett"
KEEP: Final = 20
LATEST: Final = "oppsett-siste.yaml"


class Tuning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: str
    features: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, float] = Field(default_factory=dict)


class SetupFile(BaseModel):
    """What the file holds. Every part is optional: a file with only ``staff`` changes only
    the technicians."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["cutcut-oppsett"] = KIND
    schema_version: Literal[1] = 1
    studio: str
    exported: datetime | None = None
    cutcut: str | None = None
    devices: dict[str, str] | None = None  # the addresses that can be set on screen
    staff: Staff | None = None
    login_mode: Literal["open", "card"] | None = None
    show_type: str | None = None
    tuning: Tuning | None = None
    baseline: Baseline | None = None


class SetupFileError(ValueError):
    """The file cannot be used. ``str()`` is a Norwegian message for the screen."""


def dump(setup: SetupFile) -> str:
    yaml = YAML()
    yaml.default_flow_style = False
    buf = io.StringIO()
    buf.write(
        "# Oppsett fra CutCut Studio («Lagre oppsett»). Hentes inn under Innstillinger → Oppsett.\n"
        "# Ingen PIN eller passord: de ligger i Windows Credential Manager.\n"
    )
    yaml.dump(setup.model_dump(mode="json", exclude_none=True), buf)
    return buf.getvalue()


def parse(text: str) -> SetupFile:
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(text)
    except Exception as exc:
        raise SetupFileError(f"Filen kan ikke leses som YAML: {exc}") from exc
    if not isinstance(data, dict) or data.get("kind") != KIND:
        raise SetupFileError("Dette er ikke en oppsettfil fra CutCut («kind: cutcut-oppsett»).")
    try:
        return SetupFile.model_validate(data)
    except ValueError as exc:
        errors = getattr(exc, "errors", None)
        if callable(errors):
            first = errors()[0]
            where = ".".join(str(x) for x in first["loc"])
            msg = str(first["msg"]).removeprefix("Value error, ")
            raise SetupFileError(f"Feil i oppsettfilen ({where}): {msg}") from exc
        raise SetupFileError(str(exc)) from exc


def filename(studio: str, when: datetime) -> str:
    return f"cutcut-oppsett-{studio}-{when:%Y%m%d-%H%M%S}.yaml"


def autosave(folder: Path, setup: SetupFile, when: datetime, *, keep: int = KEEP) -> Path:
    """``oppsett-siste.yaml`` and a dated copy; the oldest copies over ``keep`` go."""
    folder.mkdir(parents=True, exist_ok=True)
    text = dump(setup)
    latest = folder / LATEST
    tmp = latest.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(latest)
    dated = folder / filename(setup.studio, when)
    dated.write_text(text, encoding="utf-8")
    copies = sorted(p for p in folder.glob("cutcut-oppsett-*.yaml"))
    for old in copies[:-keep]:
        old.unlink(missing_ok=True)
    return dated
