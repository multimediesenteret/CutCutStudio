# CutCut Studio

*You speak. We cut cut.*

CutCut Studio er NTNU Multimediesenterets egen live auto-regi for videopodcast. Den lytter på hver mikrofon fra RØDECaster Pro II, ser kameraene gjennom ATEM-multiviewen, og klipper som en menneskelig bilderegissør: neste bilde på preview først, kutt mellom setninger, aldri flytte et kamera som er på lufta. Kutt og layouter går gjennom Bitfocus Companion til ATEM Mini Extreme ISO; PTZ-kameraer (OBSBOT Tail 2, Canon CR-N300) styres over IP; opptak går til Epiphan Pearl Nexus. Brukeren logger inn med NTNU-kortet på en touch-skjerm.

## Status

**M1 Simulator er nesten ferdig:** motor, simulator, API og begge skjermene virker; web-simulatoren ligger på https://cutcutstudio2026.vercel.app/sim/. Planene er godkjent (`docs/plans/`); se `docs/STATUS.md`.

## Lisens

Apache-2.0, opphavsrett NTNU Multimediesenteret. Se `LICENSE` og `NOTICE`.

## Hvor ting ligger

| Hva | Hvor |
| --- | --- |
| **Start her** (agenter og mennesker) | [`AGENTS.md`](AGENTS.md) |
| Arkitektur (prosesser, dataflyt, Mermaid) | [`docs/architecture/`](docs/architecture/README.md) |
| Runbooks for feil i studio | [`docs/runbooks/`](docs/runbooks/) – mal i `_mal.md` |
| Stack og utviklingsmiljø | [`docs/stack.md`](docs/stack.md) |
| Versjonering og release | [`docs/RELEASE.md`](docs/RELEASE.md) |
| Publisering (Vercel, Windows-pakke) | [`docs/publishing.md`](docs/publishing.md) |
| Beslutninger fra forprosjektet | [`docs/forprosjekt/beslutningslogg.md`](docs/forprosjekt/beslutningslogg.md) |
| Web-simulator (Vercel) | [`docs/simulator.md`](docs/simulator.md) |
| Research | [`docs/research/`](docs/research/) |
| Standardoppsett i studio | [`docs/studio/`](docs/studio/) |
| Farger og design | [`docs/design/farger.md`](docs/design/farger.md), [`docs/design/gui-konsept.md`](docs/design/gui-konsept.md) |
| Skjermkonsept (Vercel) | [`concept/`](concept/) – åpne `concept/index.html` |
| Spesifikasjonen | [`docs/spec/`](docs/spec/) – start med `01-app-spesifikasjon.md` |
| Status og neste steg | [`docs/STATUS.md`](docs/STATUS.md) |
| Åpne spørsmål og hvem som svarer | [`docs/open-questions.md`](docs/open-questions.md) |
| Arkitekturbeslutninger | [`docs/adr/`](docs/adr/) |
| Klikkbar prototype (oppførsel, regel-ID-er) | [`docs/prototype/cutcut-prototype.html`](docs/prototype/cutcut-prototype.html) – åpne i nettleser |
| Det NTNU må samle inn fra studio | [`docs/intake/`](docs/intake/) |
| Leverandørfiler for studioet | [`site/ntnu-studio/equipment/`](site/ntnu-studio/equipment/) |

## Kjøre lokalt

Krever [`uv`](https://docs.astral.sh/uv/) (henter selv Python 3.12) og Node 22+ med `corepack enable` (for skjermene).

```bash
./tools/setup-git.sh       # git-identitet (AGENTS.md 3)
uv sync                    # Python og avhengigheter, låst i uv.lock
pnpm install && pnpm build # skjermene, til ui/dist
uv run cutcut sim          # motor, simulator og begge skjermer på http://127.0.0.1:8080
```

Åpne http://127.0.0.1:8080/touch/ og http://127.0.0.1:8080/tech/ (under Helse kan du slå på samtale, slides og feil). Alt utstyr er simulert. Testkort `04A1B2C3` og `04D4E5F6`, PIN `1234` for tekniker. CI kjører de samme kommandoene: `uv sync`, `pnpm install`, `pnpm build` og `uv run cutcut sim --smoke`, og Playwright går gjennom begge skjermene mot simulatoren.

Kvalitet, som i CI:

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
pnpm lint && pnpm typecheck && pnpm test
```

## Bidra

Kjør `tools/setup-git.sh` (eller `.ps1`) etter kloning. Alle commits skal ha forfatter `Multimediesenteret <magnus.lian@ntnu.no>` (se `AGENTS.md` 3).
