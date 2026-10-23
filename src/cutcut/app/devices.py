"""Equipment addresses that the technician can change from the setup screen.

IP addresses vary between studios and change when equipment is replaced, so they must not need
a new version or a file edit. ``site/<studio>/devices.yaml`` is the starting point; changes made
on screen are stored as overrides in the database (they survive restarts), validated with the
same rules as the file (valid IPv4, every device its own address), and can be downloaded as a
new ``devices.yaml`` to commit to the studio repo (spec 9.3).
"""

from __future__ import annotations

import io
from typing import Any, Final

from pydantic import ValidationError
from ruamel.yaml import YAML

from cutcut.common.ids import CameraId
from cutcut.common.models.site import (
    CAPTURE_DELAY_MS,
    CAPTURE_LABELS,
    CAPTURE_NAMES,
    Devices,
)

DEVICES_KEY: Final = "site.devices"

# The PTZ models CutCut has a driver for (devices/cameras/factory.py). One model in the whole
# studio is recommended (D-070), but each camera can be set on its own.
CAMERA_MODELS: Final = ("OBSBOT Tail 2", "Canon CR-N300")

# Multiview capture (D-071): the method, the device name and the measured delay per method.
VIDEO_KEYS: Final = ["video.method", "video.name"] + [f"video.delay_ms.{m}" for m in CAPTURE_NAMES]


class DeviceSettingsError(ValueError):
    """A change that would make the equipment list invalid. The message is for the screen."""


def editable_keys(devices: Devices) -> list[str]:
    keys = ["atem.ip", "pearl.ip", "companion.url"]
    keys += [f"cameras.{cid.value}.ip" for cid in devices.cameras]
    keys += [f"cameras.{cid.value}.model" for cid in devices.cameras]
    keys += VIDEO_KEYS
    keys += [
        "alerts.enabled",
        "alerts.email",
        "alerts.smtp.host",
        "support.email",
    ]  # Innstillinger → Varsling (HS-3, D-065)
    return keys


def _get(data: dict[str, Any], key: str) -> Any:
    node: Any = data
    for part in key.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def _set(data: dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def apply(base: Devices, overrides: dict[str, str]) -> Devices:
    """``base`` with the overrides applied, validated like the file. Raises on bad input."""
    allowed = set(editable_keys(base))
    unknown = sorted(set(overrides) - allowed)
    if unknown:
        raise DeviceSettingsError(f"Kan ikke endres her: {', '.join(unknown)}")
    data = base.model_dump(mode="json")
    for key, value in overrides.items():
        if key.startswith("cameras.") and key.endswith(".model"):
            cam = base.cameras.get(CameraId(key.split(".")[1]))
            file_model = cam.model if cam is not None else None
            if value not in model_options(file_model):
                raise DeviceSettingsError(
                    f"Ukjent kameramodell «{value}». Velg {' eller '.join(CAMERA_MODELS)}."
                )
        _set(data, key, value)
    try:
        return Devices.model_validate(data)
    except ValidationError as exc:
        raise DeviceSettingsError(_why(exc)) from exc


def _why(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(x) for x in err["loc"])
    msg = str(err["msg"])
    if loc.startswith(("alerts.email", "support.email")):
        return f"Ugyldig e-postadresse. {msg.removeprefix('Value error, ')}."
    if "own IP" in msg:
        return "To enheter kan ikke ha samme IP-adresse."
    if "IPv4" in msg or "ip" in loc:
        return f"Ugyldig IP-adresse ({loc}). Skriv den som fire tall, f.eks. 10.10.10.21."
    if loc.startswith("video.method"):
        return "Velg INOGENI eller ATEM webkamera-utgang."
    if loc.startswith("video.delay_ms"):
        return "Forsinkelsen må være et helt antall millisekunder mellom 0 og 1000."
    if "url" in loc.lower():
        return f"Ugyldig adresse ({loc}). Skriv den som http://adresse:port."
    return f"{loc}: {msg}"


def rows(base: Devices, effective: Devices, overrides: dict[str, str]) -> list[dict[str, Any]]:
    """What the setup screen shows: one row per editable address."""
    b = base.model_dump(mode="json")
    e = effective.model_dump(mode="json")
    out = []
    for key in editable_keys(base):
        if key.startswith(("alerts.", "support.", "video.")) or key.endswith(".model"):
            continue  # Varsling, the capture panel, and the model choice inside the row
        row: dict[str, Any] = {
            "key": key,
            "kind": "url" if key.endswith(".url") else "ip",
            "value": _get(e, key),
            "file_value": _get(b, key),
            "overridden": key in overrides,
            "model": _get(e, key.rsplit(".", 1)[0] + ".model"),
        }
        if key.startswith("cameras."):
            model_key = key.rsplit(".", 1)[0] + ".model"
            row["model_key"] = model_key
            row["model_options"] = list(model_options(_get(b, model_key)))
            row["model_overridden"] = model_key in overrides
        out.append(row)
    return out


def model_options(file_model: str | None) -> tuple[str, ...]:
    """The models a camera can be set to: those with a driver, and what the file says (the
    bird's-eye camera is «Oversikt …», steered by no one)."""
    if file_model and file_model not in CAMERA_MODELS:
        return (*CAMERA_MODELS, file_model)
    return CAMERA_MODELS


def video_info(base: Devices, effective: Devices, overrides: dict[str, str]) -> dict[str, Any]:
    """The multiview capture panel (Oppsett, steg 6, D-071)."""
    v = effective.video
    return {
        "kind": v.kind,
        "method": v.method,
        "method_overridden": "video.method" in overrides,
        "file_method": base.video.method,
        "name": v.name,
        "name_used": v.device_name,
        "methods": [
            {
                "value": m,
                "label": CAPTURE_LABELS[m],
                "device_name": CAPTURE_NAMES[m],
                "delay_ms": v.delay_ms.get(m),  # type: ignore[call-overload]  # literal key
                "assumed_delay_ms": CAPTURE_DELAY_MS[m],
            }
            for m in CAPTURE_NAMES
        ],
        "delay_ms": v.expected_delay_ms,
        "measured": v.method in v.delay_ms,
    }


def values(devices: Devices) -> dict[str, str]:
    """Every address that can be set on screen, as the text the screen shows (setup file)."""
    data = devices.model_dump(mode="json")
    out: dict[str, str] = {}
    for key in editable_keys(devices):
        v = _get(data, key)
        if isinstance(v, bool):
            out[key] = "true" if v else "false"
        elif isinstance(v, list):
            out[key] = ", ".join(str(x) for x in v)
        else:
            out[key] = "" if v is None else str(v)
    return out


def to_yaml(devices: Devices) -> str:
    """The effective equipment list as a ``devices.yaml`` to commit to the studio repo."""
    yaml = YAML()
    yaml.default_flow_style = None
    buf = io.StringIO()
    buf.write(
        "# Eksportert fra CutCut Studio (Oppsett → Utstyr og nettverk).\n"
        "# Passord og nøkler ligger i Windows Credential Manager, aldri her.\n"
    )
    yaml.dump(devices.model_dump(mode="json", exclude_none=True), buf)
    return buf.getvalue()
