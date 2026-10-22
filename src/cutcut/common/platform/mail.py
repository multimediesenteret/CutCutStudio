"""Email through the studio's SMTP relay (HS-3). Blocking: call it from a worker thread, never
from the engine's loop. The password, if the relay needs one, is ``smtp_password`` in Windows
Credential Manager (spec 12.4)."""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from cutcut.common.models.site import SmtpConfig

TIMEOUT_S = 10.0


class MailError(Exception):
    """The mail could not be sent. ``str()`` is a Norwegian message for the screens."""


@dataclass
class SmtpMailer:
    cfg: SmtpConfig
    password: str = ""

    def send(self, to: list[str], subject: str, body: str) -> None:
        if not self.cfg.host:
            raise MailError("Ingen SMTP-server er satt opp (alerts.smtp.host).")
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.cfg.sender, ", ".join(to), subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.cfg.host, self.cfg.port, timeout=TIMEOUT_S) as smtp:
                if self.cfg.starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if self.cfg.username:
                    smtp.login(self.cfg.username, self.password)
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as e:
            raise MailError(f"E-post til {', '.join(to)} feilet: {e}") from e
