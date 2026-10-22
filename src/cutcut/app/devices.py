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

from cutcut.common.models.site import Devices

DEVICES_KEY: Final = "site.devices"


class DeviceSettingsError(ValueError):
    """A change that would make the equipment list invalid. The message is for the screen."""


def editable_keys(devices: Devices) -> list[str]:
    keys = ["atem.ip", "pearl.ip", "companion.url"]
    keys += [f"cameras.{cid.value}.ip" for cid in devices.cameras]
    keys += [
        "alerts.enabled",
        "alerts.email",
        "alerts.smtp.host",
    ]  # Innstillinger → Varsling (HS-3)
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
        _set(data, key, value)
    try:
        return Devices.model_validate(data)
    except ValidationError as exc:
        raise DeviceSettingsError(_why(exc)) from exc


def _why(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(x) for x in err["loc"])
    msg = str(err["msg"])
    if loc.startswith("alerts.email"):
        return f"Ugyldig e-postadresse. {msg.removeprefix('Value error, ')}."
    if "own IP" in msg:
        return "To enheter kan ikke ha samme IP-adresse."
    if "IPv4" in msg or "ip" in loc:
        return f"Ugyldig IP-adresse ({loc}). Skriv den som fire tall, f.eks. 10.10.10.21."
    if "url" in loc.lower():
        return f"Ugyldig adresse ({loc}). Skriv den som http://adresse:port."
    return f"{loc}: {msg}"


def rows(base: Devices, effective: Devices, overrides: dict[str, str]) -> list[dict[str, Any]]:
    """What the setup screen shows: one row per editable address."""
    b = base.model_dump(mode="json")
    e = effective.model_dump(mode="json")
    out = []
    for key in editable_keys(base):
        if key.startswith("alerts."):
            continue  # shown under Innstillinger → Varsling, not with the equipment
        out.append(
            {
                "key": key,
                "kind": "url" if key.endswith(".url") else "ip",
                "value": _get(e, key),
                "file_value": _get(b, key),
                "overridden": key in overrides,
                "model": _get(e, key.rsplit(".", 1)[0] + ".model"),
            }
        )
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
