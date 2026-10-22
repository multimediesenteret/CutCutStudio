# CutCut Studio

*You speak. We cut cut.*

CutCut Studio er Multimediesenterets egen live auto-regi for videopodcast. Den lytter på hver mikrofon fra RØDECaster Pro II, ser kameraene gjennom ATEM-multiviewen, og klipper som en menneskelig bilderegissør: neste bilde på preview først, kutt mellom setninger, aldri flytte et kamera som er på lufta. Kutt og layouter går gjennom Bitfocus Companion til ATEM-mikseren (i studioet en Television Studio HD8 ISO); PTZ-kameraer (OBSBOT Tail 2, Canon CR-N300) styres over IP; opptak går til Epiphan Pearl Nexus. Brukeren trykker Start på en touch-skjerm (innlogging med adgangskort kommer senere).

## Status

**Klar for studioperioden.** Alt som kan bygges uten studio, er bygget og testet i CI: motor med grunnmodus og alle brytere, lyd, utstyr, videolag, skjermer, oppsett, helse og drift. Det som står igjen, er maskintester og prøving i studio etter [`docs/studio/testdag.md`](docs/studio/testdag.md). Web-simulatoren ligger på https://cutcutstudio2026.vercel.app. Se [`docs/STATUS.md`](docs/STATUS.md).

## Lisens

Apache-2.0, opphavsrett Multimediesenteret. Se `LICENSE` og `NOTICE`.

## Hvor ting ligger

| Hva | Hvor |
| --- | --- |
| **Start her** (agenter og mennesker) | [`AGENTS.md`](AGENTS.md) |
| Sjekkliste for studioperioden | [`docs/studio/testdag.md`](docs/studio/testdag.md) |
| Maskintester | [`docs/studio/maskintest.md`](docs/studio/maskintest.md) |
| Implementasjonsplaner per modul | [`docs/plans/`](docs/plans/README.md) |
| Arkitektur (prosesser, dataflyt, Mermaid) | [`docs/architecture/`](docs/architecture/README.md) |
| Runbooks for feil i studio | [`docs/runbooks/`](docs/runbooks/README.md): ingen lyd, touch svart, opptak startet ikke, kamera, strømbrudd |
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
| Det Multimediesenteret må samle inn fra studio | [`docs/intake/`](docs/intake/) |
| Leverandørfiler for studioet | [`site/multimediesenteret/equipment/`](site/multimediesenteret/equipment/) |

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

## I studio

I studio kjører CutCut som Windows-tjenesten `CutCut`. Den starter `cutcut supervisor`, som starter og passer på `core` (motor, API og skjermer på :8080), `audio-capture`, `atem-bridge` og `vision`. Installasjon og oppdatering: [`docs/studio/tjenester.md`](docs/studio/tjenester.md). Første oppsett gjøres i teknikervinduet: adresser under Oppsett → Utstyr og nettverk, og setup-hjelperens ti steg.

For hånd (feilsøking):

```bash
uv run cutcut supervisor --site site/multimediesenteret --data data   # alt, som tjenesten
uv run cutcut core --site site/multimediesenteret                     # bare motor, API og skjermer
uv run cutcut hwtest <audio|atem|camera|vision|faces|soak> --site …   # maskintestene
```

Passord og PIN-er ligger i Windows Credential Manager (`pearl_password`, `operator_pin`, `admin_pin`). Ekte IP-adresser, teknikere og varsling legges inn i appen og ligger bare på studio-PC-en (D-060).

## Bidra

Kjør `tools/setup-git.sh` (eller `.ps1`) etter kloning. Alle commits skal ha forfatter `Multimediesenteret <magnus.lian@ntnu.no>` (se `AGENTS.md` 3).
