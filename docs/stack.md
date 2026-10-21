# Stack og utviklingsmiljø

Teknologi, versjoner og verktøy for CutCut Studio. Spesifikasjonen 3.1 er fasit for *hva* som brukes; denne filen sier *hvordan* man setter det opp og jobber med det. Holdes oppdatert når noe legges til eller byttes.

## Prinsipper for teknologivalg

1. **Stabilt foran nytt.** Velg det som er mest brukt, best vedlikeholdt og dokumentert av produsenten. Systemet skal stå i måneder uten tekniker.
2. **Direkte mot enheten.** Ingen ekstra programmer i mellom hvis enheten har et dokumentert protokoll (spesifikasjonen, Teknisk referanse).
3. **Låste versjoner.** Alt låses i `uv.lock` og `pnpm-lock.yaml`. Oppdatering skjer bevisst, i egen pull request, og testes før utrulling i servicevindu.
4. **Lokalt i drift.** Ingen skytjeneste i sanntidssløyfen (I6). Modeller og avhengigheter ligger på maskinen.

## Kjøretid (regi-PC i studio)

| Del | Valg | Versjon | Merknad |
| --- | --- | --- | --- |
| OS | Windows 11 Pro | 23H2 eller nyere | Se Q8 om NTNU-administrasjon |
| Python | CPython, pakket med appen | 3.12.x | Egen Python i `C:\CutCut\versions\<v>\` |
| Pakker Python | `uv` | siste stabile ved M1 | `uv.lock` i git |
| Node.js | LTS | 24.x | Bare for `atem-bridge` (ADR-0012) og bygging av UI |
| Pakker UI | `pnpm` (via Corepack) | 10.x | `pnpm-lock.yaml` i git |
| GPU | NVIDIA RTX, ONNX Runtime CUDA/TensorRT | | DirectML som reserve (Q20) |
| Tjenester | WinSW | 2.x/3.x | Supervisor som Windows-tjeneste |
| Touch | Microsoft Edge kiosk, tilordnet tilgang | | |
| Companion | Bitfocus Companion | 4.x/5.x, låst i studio | Kjører på samme PC |

## Biblioteker

| Område | Python | Merknad |
| --- | --- | --- |
| Server | FastAPI, uvicorn, Pydantic v2 | OpenAPI genereres til `docs/reference/` |
| Konfig | PyYAML/ruamel.yaml, Pydantic | JSON Schema genereres til `config/schema/` |
| Lyd | `sounddevice` (PortAudio) med `SD_ENABLE_ASIO`, `numpy` | RØDE ASIO-driver, 20 kanaler, 48 kHz; Silero i 512-sampler-blokker ved 16 kHz. Se Q21 og ADR-0014 |
| Tale | Silero VAD (ONNX) | |
| Bilde | OpenCV / FFmpeg, ONNX Runtime | |
| Meldingsbuss | `pyzmq` | |
| Enheter | `httpx`, `python-osc`, egen VISCA-UDP-klient | |
| ATEM | `atem-connection` i Node-prosessen `atem-bridge` | ADR-0012, akseptert (D-046). Erstatter PyATEMMax |
| Kortleser | `pyserial` | |
| Hemmeligheter | `keyring` | Windows Credential Manager |
| Lagring | `sqlite3` (WAL) | |
| Tester | pytest, pytest-asyncio, hypothesis (regler), Playwright | |
| Kvalitet | ruff (lint + format), mypy strict | |

| Område | UI | Merknad |
| --- | --- | --- |
| Rammeverk | React + TypeScript (strict) + Vite | Statisk bygg, servert av FastAPI |
| Typer | Generert fra OpenAPI (`ui/packages/client`) | Grensesnitt og motor kan ikke bli uenige om et felt |
| Design | `ui/packages/design` | Tokens med fast betydning (spesifikasjonen 12.5) |
| Tester | Vitest, Playwright (skjermbilder per touch-steg) | |
| Kvalitet | ESLint, Prettier, `tsc --noEmit` | |

Eksakte versjoner settes når første kode skrives (M1) og står deretter bare i lockfilene.

## Prosesser

Spesifikasjonen sier både «to prosesser» (seksjon 3, innledning) og «tre prosesser» (ADR-0003). Gjeldende er ADR-0003: `core`, `vision` og `stt` under én supervisor. Med ADR-0012 kommer `atem-bridge` i tillegg, og med ADR-0014 `audio-capture` (lyd fra RØDECaster via ASIO, se `docs/research/lyd-fra-rodecaster.md`). `core` må kunne klippe alene på lyd hvis alle andre prosesser er nede.

## Utviklingsmiljø

Koden utvikles på Linux (agentens skymiljø, utviklernes maskiner) og kjøres i drift på Windows. Derfor:

- **Plattformnøytral kjerne.** Alt i `core`, regler, simulator, API og UI skal kjøre og testes på Linux, macOS og Windows.
- **Windows-ting bak adaptere.** ASIO-lyd, WinSW, kiosk, Credential Manager og DirectShow-capture har et grensesnitt i `src/cutcut/common/platform/` med en Windows-implementasjon og en falsk implementasjon for test og simulator.
- **Simulatoren er standard.** `cutcut sim` (kommer i M1) starter motoren med simulert lyd, simulerte enheter og begge skjermer.

### Kom i gang (fylles ut i M1)

```bash
git clone https://github.com/multimediesenteret/cutcutstudio
cd cutcutstudio
./tools/setup-git.sh          # git-identitet, se AGENTS.md 3
uv sync                       # Python og avhengigheter
corepack enable && pnpm install
uv run cutcut sim             # motor + simulator + skjermer
```

## CI (GitHub Actions)

| Jobb | Når | Hva |
| --- | --- | --- |
| `commit-identity` | Hver PR og push | Alle commits har forfatter og committer `Multimediesenteret <magnus.lian@ntnu.no>` |
| `python` | Fra M1 | ruff, mypy, pytest (unit, rules, integration) på `ubuntu-latest` og `windows-latest` |
| `ui` | Fra M1 | lint, typesjekk, Vitest, Playwright |
| `docs` | Fra M1 | Genererte filer i `docs/reference/` uten avvik; sporbarhet regel → test; README-kommandoer kjører |
| `security` | Ukentlig og per PR | `pip-audit`, `pnpm audit`, søk etter testkortets nummer i logg og database (I8) |
| `release` | Ved tag `v*` | Windows-pakke, SBOM, sjekksum (se `docs/RELEASE.md`) |

## Modeller

Modellfiler (ONNX) ligger ikke i git. `models/manifest.yaml` har navn, versjon, URL og SHA-256; de lastes ned ved installasjon og sjekkes ved oppstart. Lisens for hver modell noteres i manifestet.
