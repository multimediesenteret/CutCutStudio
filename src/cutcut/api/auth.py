"""Roles and sign-in (spec 12.4, D-045).

* ``touch``: requests from the PC itself (127.0.0.1) without a sign-in.
* ``operator`` / ``admin``: technicians on the staff list, kept in the application
  (Innstillinger → Teknikere; ``site/<studio>/staff.yaml`` is only the starting point). While
  the list is empty, the admin PIN signs anyone in as admin, so a new PC can be set up.
  signed in with username + PIN (PIN in Windows Credential Manager). A session cookie that is
  ``HttpOnly`` and ``SameSite=Strict`` lasts 8 hours.
* Requests from other machines without a sign-in get nothing.

In the simulator (``dev_admin``) local requests are treated as admin, so the technician
screen can be tried without PINs. That switch is never on in the studio.
"""

from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import Final, Literal

from fastapi import HTTPException
from starlette.requests import HTTPConnection

from cutcut.common.models.site import Staff
from cutcut.common.platform.secrets import SecretMissingError, SecretStore

Role = Literal["touch", "operator", "admin"]
RANK: Final = {"touch": 0, "operator": 1, "admin": 2}
COOKIE: Final = "cutcut_session"
SESSION_S: Final = 8 * 3600
LOCAL_HOSTS: Final = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


@dataclass(frozen=True)
class Identity:
    role: Role
    actor: str


@dataclass
class Auth:
    staff: Staff
    secrets: SecretStore
    dev_admin: bool = False
    sessions: dict[str, tuple[Identity, float]] = field(default_factory=dict)

    def sign_in(self, username: str, pin: str) -> tuple[str, Identity]:
        role = self.staff.role_of(username)
        if role is None and self.staff.empty:
            # First setup on a new PC: nobody is on the list yet, so the admin PIN lets one in
            # to add the technicians (Innstillinger → Teknikere).
            role = "admin"
        if role is None:
            raise HTTPException(401, "Brukeren står ikke på teknikerlisten.")
        try:
            expected = self.secrets.get("admin_pin" if role == "admin" else "operator_pin")
        except SecretMissingError as exc:
            raise HTTPException(503, "PIN er ikke satt opp på denne PC-en.") from exc
        if not hmac.compare_digest(pin.encode(), expected.encode()):
            raise HTTPException(401, "Feil PIN.")
        token = secrets.token_urlsafe(32)
        identity = Identity(role="admin" if role == "admin" else "operator", actor=username)
        self.sessions[token] = (identity, time.monotonic() + SESSION_S)
        return token, identity

    def sign_out(self, token: str | None) -> None:
        if token:
            self.sessions.pop(token, None)

    def identify(self, request: HTTPConnection) -> Identity:
        token = request.cookies.get(COOKIE)
        if token and token in self.sessions:
            identity, expires = self.sessions[token]
            if time.monotonic() < expires:
                return identity
            self.sessions.pop(token, None)
        host = request.client.host if request.client else ""
        if host in LOCAL_HOSTS:
            return Identity("admin", "simulator") if self.dev_admin else Identity("touch", "touch")
        raise HTTPException(401, "Logg inn som tekniker.")


def require(identity: Identity, role: Role) -> None:
    if RANK[identity.role] < RANK[role]:
        raise HTTPException(403, "Du har ikke tilgang til dette.")
