# CutCut Studio

*You speak. We cut cut.*

CutCut Studio er NTNU Multimediesenterets egen live auto-regi for videopodcast. Den lytter på hver mikrofon fra RØDECaster Pro II, ser kameraene gjennom ATEM-multiviewen, og klipper som en menneskelig bilderegissør: neste bilde på preview først, kutt mellom setninger, aldri flytte et kamera som er på lufta. Kutt og layouter går gjennom Bitfocus Companion til ATEM Mini Extreme ISO; PTZ-kameraer (OBSBOT Tail 2, Canon CR-N300) styres over IP; opptak går til Epiphan Pearl Nexus. Brukeren logger inn med NTNU-kortet på en touch-skjerm.

## Status

Ingen kode ennå. Første steg er implementasjonsplaner (se `docs/STATUS.md`).

## Hvor ting ligger

| Hva | Hvor |
| --- | --- |
| Regler for AI-agenter | [`AGENTS.md`](AGENTS.md) |
| Spesifikasjonen (fasit) | [`docs/spec/`](docs/spec/) – start med `01-app-spesifikasjon.md` |
| Status og neste steg | [`docs/STATUS.md`](docs/STATUS.md) |
| Åpne spørsmål og hvem som svarer | [`docs/open-questions.md`](docs/open-questions.md) |
| Arkitekturbeslutninger | [`docs/adr/`](docs/adr/) |
| Klikkbar prototype (oppførsel, regel-ID-er) | [`docs/prototype/cutcut-prototype.html`](docs/prototype/cutcut-prototype.html) – åpne i nettleser |
| Det NTNU må samle inn fra studio | [`docs/intake/`](docs/intake/) |
| Leverandørfiler for studioet | [`site/ntnu-studio/equipment/`](site/ntnu-studio/equipment/) |

## Kjøre lokalt

Kommer i milepæl M1 (simulator). Målet er at `uv sync && uv run cutcut sim` starter motor, simulator og begge skjermer på under 10 minutter fra ren klone.
