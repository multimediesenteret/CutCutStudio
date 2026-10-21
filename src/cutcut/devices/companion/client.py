"""HTTP client for Bitfocus Companion (spec 7.1, ADR-0009).

Companion runs on the same PC and is called on ``127.0.0.1``. Every call has a short timeout
(300 ms): a slow Companion must never hold up a cut (ADR-0005). Endpoints from the Companion
user guide, «HTTP remote control» (Companion 3.x–5.x).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import quote

import httpx

TIMEOUT_S: Final = 0.3


class CompanionError(Exception):
    """Companion did not answer, or answered with an error."""


@dataclass(frozen=True)
class CompanionConnection:
    id: str
    label: str
    module: str
    enabled: bool
    ok: bool
    status: str


class CompanionHttp:
    def __init__(self, base_url: str, *, timeout_s: float = TIMEOUT_S) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            trust_env=False,  # studio equipment is on the local network, never via a proxy
        )

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, **kw: Any) -> httpx.Response:
        try:
            res = self._http.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise CompanionError(f"Companion svarer ikke ({type(exc).__name__})") from exc
        if res.status_code >= 400:
            raise CompanionError(f"Companion svarte {res.status_code} på {path}")
        return res

    def press(self, page: int, row: int, col: int) -> None:
        self._call("POST", f"/api/location/{page}/{row}/{col}/press")

    def set_var(self, name: str, value: str) -> None:
        self._call(
            "POST",
            f"/api/custom-variable/{quote(name, safe='')}/value",
            content=value.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )

    def get_var(self, name: str) -> str | None:
        try:
            res = self._call("GET", f"/api/custom-variable/{quote(name, safe='')}/value")
        except CompanionError:
            return None
        return res.text

    def pages_version(self) -> int | None:
        """``cutcut_pages_version`` from the imported Companion pages (DA-9). ``None`` if the
        variable is missing, i.e. the CutCut pages are not imported."""
        value = self.get_var("cutcut_pages_version")
        try:
            return int(value) if value is not None else None
        except ValueError:
            return None

    def connections(self) -> list[CompanionConnection]:
        """Companion's own connections (ATEM module etc.). Used by ``H-COMP-1``."""
        data = self._call("GET", "/api/connections").json()
        out = []
        for c in data if isinstance(data, list) else []:
            status = c.get("status")
            text = (
                str(status.get("category") or status.get("level") or status)
                if isinstance(status, dict)
                else str(status)
            )
            out.append(
                CompanionConnection(
                    id=str(c.get("id", "")),
                    label=str(c.get("label", "")),
                    module=str(c.get("moduleId", "")),
                    enabled=bool(c.get("enabled", True)),
                    ok=text.lower() in ("good", "ok", "connected"),
                    status=text,
                )
            )
        return out
