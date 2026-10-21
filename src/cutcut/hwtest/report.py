"""A machine-test report: steps with a result, written as JSON and Markdown (AU-6, DA-5).

The Markdown is meant to be pasted into the GitHub issue as is («rapport i issue»)."""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from cutcut import __version__

Result = Literal["ok", "advarsel", "feil", "hoppet over"]
ICON = {"ok": "✅", "advarsel": "⚠️", "feil": "❌", "hoppet over": "⏭️"}


@dataclass
class Step:
    id: str
    title: str
    result: Result
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    answers: str | None = None  # the open question this step answers, e.g. "Q24"


@dataclass
class Report:
    name: str
    started: datetime
    steps: list[Step] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.env = {
            "cutcut": __version__,
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()} ({platform.version()})",
            "machine": platform.node(),
            **self.env,
        }

    def add(self, step: Step) -> Step:
        self.steps.append(step)
        return step

    @property
    def result(self) -> Result:
        results = {s.result for s in self.steps}
        if "feil" in results:
            return "feil"
        if "advarsel" in results:
            return "advarsel"
        return "ok"

    def to_json(self) -> str:
        data = {
            "name": self.name,
            "started": self.started.isoformat(timespec="seconds"),
            "result": self.result,
            "env": self.env,
            "steps": [asdict(s) for s in self.steps],
        }
        return json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n"

    def to_markdown(self) -> str:
        lines = [
            f"## Maskintest: {self.name} {ICON[self.result]}",
            "",
            f"Kjørt {self.started:%Y-%m-%d %H:%M} · CutCut {self.env['cutcut']} · "
            f"{self.env['os']} · {self.env['machine']}",
            "",
            "| Steg | Resultat | Hva vi fant |",
            "| --- | --- | --- |",
        ]
        for s in self.steps:
            answer = f" **Svar på {s.answers}.**" if s.answers else ""
            summary = s.summary.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {s.id} {s.title} | {ICON[s.result]} {s.result} | {summary}{answer} |")
        for s in self.steps:
            if s.details:
                lines += ["", f"<details><summary>{s.id} detaljer</summary>", "", "```json"]
                lines.append(json.dumps(s.details, ensure_ascii=False, indent=2, default=str))
                lines += ["```", "", "</details>"]
        extra = {k: v for k, v in self.env.items() if k not in ("cutcut", "os", "machine")}
        if extra:
            lines += ["", "Miljø: " + ", ".join(f"{k} {v}" for k, v in extra.items())]
        return "\n".join(lines) + "\n"

    def write(self, out: Path) -> tuple[Path, Path]:
        out.mkdir(parents=True, exist_ok=True)
        stem = f"{self.started:%Y%m%d-%H%M}-{self.name}"
        js, md = out / f"{stem}.json", out / f"{stem}.md"
        js.write_text(self.to_json(), encoding="utf-8")
        md.write_text(self.to_markdown(), encoding="utf-8")
        return js, md
