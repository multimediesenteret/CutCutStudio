"""Exports from the technician window (A-6, spec 8.4 and 12.1).

* CSV of decisions and of the session history, for a spreadsheet.
* A debug package (zip) with log, configuration, version and health that can be handed to a
  person or an AI for analysis. It never contains secrets: PINs and keys live in the Windows
  Credential Manager and are not read here, the staff list is left out, and everything goes
  through :func:`cutcut.common.privacy.redact` so nothing that looks like a card number
  survives (I8).
"""

from __future__ import annotations

import csv
import io
import json
import platform
import zipfile
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from cutcut import __version__
from cutcut.common.privacy import redact, redact_text

if TYPE_CHECKING:
    from cutcut.app.studio import Studio

DECISION_COLUMNS: Final = (
    "ts",
    "action",
    "shot",
    "rule",
    "reason",
    "mode",
    "blocked_by",
    "shadow",
    "correlation_id",
)
SESSION_COLUMNS: Final = (
    "started_at",
    "ended_at",
    "username",
    "display_name",
    "duration_s",
    "participants",
    "video",
    "started_by",
    "stopped_by",
    "recording",
    "publish",
    "session_id",
)
LOG_TAIL_LINES: Final = 5000
# Only these files from site/<studio>/ go in the package; staff.yaml (names) stays out.
SITE_FILES: Final = ("devices.yaml", "shows/*.yaml", "equipment/*.yaml", "baseline.yaml")


def to_csv(rows: Iterable[dict[str, Any]], columns: Sequence[str]) -> str:
    """Semicolon CSV with BOM, which Excel with Norwegian settings opens correctly."""
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(columns)
    for row in rows:
        w.writerow([_cell(row.get(c)) for c in columns])
    return buf.getvalue()


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "ja" if v else "nei"
    return redact_text(str(v))


def decisions_csv(decisions: Iterable[dict[str, Any]]) -> str:
    return to_csv(decisions, DECISION_COLUMNS)


def sessions_csv(sessions: Iterable[dict[str, Any]]) -> str:
    return to_csv(sessions, SESSION_COLUMNS)


def _json(value: Any) -> str:
    return json.dumps(redact(value), ensure_ascii=False, indent=2, default=str) + "\n"


def _jsonl(rows: Iterable[Any]) -> str:
    return "".join(json.dumps(redact(r), ensure_ascii=False, default=str) + "\n" for r in rows)


def _tail(path: Path, lines: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(kunne ikke lese {path.name}: {exc})\n"
    return redact_text("\n".join(text.splitlines()[-lines:]) + "\n")


def debug_package(studio: Studio, now: datetime) -> bytes:
    """Build the zip. Blocking (reads the database and files): call it in a thread."""
    deps = studio.deps
    state = studio.state().model_dump(mode="json")
    since_day = now - timedelta(days=1)
    files: dict[str, str] = {
        "README.txt": (
            "CutCut Studio – feilsøkingspakke\n"
            f"Laget: {now.isoformat()}\nVersjon: {__version__}\n\n"
            "state.json      nåtilstand (som GET /api/state)\n"
            "rules.json      regelverdier, forhåndsvalg og finjustering\n"
            "decisions.jsonl beslutninger siste døgn\n"
            "audit.jsonl     hvem endret hva, siste 7 dager\n"
            "sessions.json   økter siste 7 dager\n"
            "site/           studio-oppsett uten personliste\n"
            "logs/           siste linjer av hver logg\n\n"
            "Ingen hemmeligheter eller kortnummer er med.\n"
        ),
        "version.json": _json(
            {
                "cutcut": __version__,
                "python": platform.python_version(),
                "platform": platform.platform(),
                "studio": deps.site.devices.studio,
                "simulator": deps.simulator,
                "show": studio.show.id,
            }
        ),
        "state.json": _json(state),
        "rules.json": _json(studio.rules_info()),
        "sessions.json": _json(studio.session_history(now - timedelta(days=7))),
    }
    if deps.store is not None:
        deps.store.flush()
        decisions = [
            d.model_dump(mode="json") for d in deps.store.decisions_since(since_day, 20_000)
        ]
        files["audit.jsonl"] = _jsonl(deps.store.audit_since(now - timedelta(days=7)))
        files["store.json"] = _json(
            {
                "written": deps.store.stats.written,
                "dropped": deps.store.stats.dropped,
                "errors": deps.store.stats.errors,
                "last_error": deps.store.stats.last_error,
                "integrity_ok": deps.store.integrity_ok(),
            }
        )
    else:
        decisions = list(studio.decisions)
    files["decisions.jsonl"] = _jsonl(decisions)

    root = deps.site.root
    for pattern in SITE_FILES:
        for path in sorted(root.glob(pattern)):
            files[f"site/{path.relative_to(root).as_posix()}"] = redact_text(
                path.read_text(encoding="utf-8", errors="replace")
            )
    if deps.log_dir is not None and deps.log_dir.is_dir():
        for path in sorted(deps.log_dir.glob("*.jsonl")):
            files[f"logs/{path.name}"] = _tail(path, LOG_TAIL_LINES)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(f"cutcut-feilsok/{name}", text)
    return buf.getvalue()
