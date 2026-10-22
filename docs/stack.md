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
| OS | Windows 11 Pro | 23H2 eller nyere | Vanlig Windows, ikke sentralt administrert; Multimediesenteret installerer selv (D-062) |
| Python | CPython, pakket med appen | 3.12.x | Egen Python i `C:\CutCut\versions\<v>\` |
| Pakker Python | `uv` | siste stabile ved M1 | `uv.lock` i git |
| Node.js | LTS | 24.x | Bare for `atem-bridge` (ADR-0012) og bygging av UI |
| Pakker UI | `pnpm` (via Corepack) | 10.x | `pnpm-lock.yaml` i git |
| Maskinvare | i5-12500, 16 GB, NVIDIA RTX 4060 Ti, INOGENI 4KXUSB3 | | D-062, D-068. GPU-en brukes ikke nå: ansikt og munn går på CPU (D-067); den holdes i reserve for en tyngre taler-modell |
| Tjenester | WinSW | 2.x/3.x | Supervisor som Windows-tjeneste |
| Touch | Microsoft Edge kiosk, tilordnet tilgang | | |
| Companion | Bitfocus Companion | 4.x/5.x, låst i studio | Kjører på samme PC |

## Biblioteker

| Område | Python | Merknad |
| --- | --- | --- |
| Server | FastAPI, uvicorn, Pydantic v2 | OpenAPI genereres til `docs/reference/` |
| Konfig | ruamel.yaml, Pydantic | JSON Schema genereres til `config/schema/` |
| Lyd | `sounddevice` (PortAudio) med `SD_ENABLE_ASIO`, `numpy` | RØDE ASIO-driver, 20 kanaler, 48 kHz; Silero i 512-sampler-blokker ved 16 kHz. Se Q21 og ADR-0014 |
| Tale | Silero VAD (ONNX) | |
| Bilde | OpenCV (`opencv-python-headless`, ekstraen `vision`) | Capture-kortet via DirectShow, funnet på navnet (`pygrabber`, MIT). Ansikt: YuNet (OpenCV Zoo, MIT) gjennom OpenCV `FaceDetectorYN`, på CPU (D-067) |
| Meldingsbuss | `pyzmq` | |
| Enheter | `httpx`, egen VISCA- og OSC-klient over UDP (`devices/cameras/visca.py`, `osc.py`) | |
| ATEM | `atem-connection` i Node-prosessen `atem-bridge` | ADR-0012, akseptert (D-046). Erstatter PyATEMMax |
| Kortleser | `pyserial` | Kommer med kortinnloggingen (D-057); ikke avhengighet ennå |
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

Eksakte versjoner står bare i lockfilene (`uv.lock`, `pnpm-lock.yaml`).

## Prosesser

Supervisoren (`cutcut supervisor`, Windows-tjenesten `CutCut`) starter fire prosesser: `core` (motor, API, skjermer), `audio-capture` (lyd fra RØDECaster via ASIO, ADR-0014, `docs/research/lyd-fra-rodecaster.md`), `atem-bridge` (Node, ADR-0012) og `vision` (multiview fra INOGENI, når studioet har rutekart). `stt` er tatt ut (D-063). `core` må kunne klippe alene på lyd hvis alle andre prosesser er nede.

## Utviklingsmiljø

Koden utvikles på Linux (agentens skymiljø, utviklernes maskiner) og kjøres i drift på Windows. Derfor:

- **Plattformnøytral kjerne.** Alt i `core`, regler, simulator, API og UI skal kjøre og testes på Linux, macOS og Windows.
- **Windows-ting bak adaptere.** ASIO-lyd, WinSW, kiosk, Credential Manager og DirectShow-capture har et grensesnitt i `src/cutcut/common/platform/` med en Windows-implementasjon og en falsk implementasjon for test og simulator.
- **Simulatoren er standard.** `uv run cutcut sim` starter motoren med simulert lyd, simulerte enheter og begge skjermer.

### Kom i gang

```bash
git clone https://github.com/multimediesenteret/cutcutstudio
cd cutcutstudio
./tools/setup-git.sh          # git-identitet, se AGENTS.md 3
uv sync                       # Python 3.12 og avhengigheter (uv.lock)
uv run pytest                 # tester
uv run ruff check . && uv run ruff format --check . && uv run mypy
corepack enable && pnpm install && pnpm build
uv run cutcut sim             # alt simulert på http://127.0.0.1:8080/touch/ og /tech/
```

## CI (GitHub Actions)

| Jobb | Når | Hva |
| --- | --- | --- |
| `commit-identity` | Hver PR | Alle commits har forfatter og committer `Multimediesenteret <magnus.lian@ntnu.no>` |
| `python` | Når Python-filer endres (sti-filter) | ruff format og lint, mypy strict, pytest (med sporbarhet og genererte filer) på `ubuntu-latest` per PR; `windows-latest` ukentlig og manuelt. Ingen kjøring ved push til `main` (D-059). Fil: `.github/workflows/python.yml` |
| `ui` | Når skjermene, broen eller API-et endres | lint, typesjekk, Vitest, Playwright mot `cutcut sim`, `atem-bridge`-kontrakttest. Fil: `ui.yml` |
| `windows-service` | Når tjenesten, supervisor, bussen eller installasjonen endres | Installerer tjenesten på `windows-latest`, dreper `core` og ser at den kommer tilbake, sjekker PowerShell-skriptene og kiosk-vakten. Fil: `windows-service.yml` |
| `release` | Ved tag `v*`, og på PR som endrer `build_bundle.py` eller `install.ps1` | Windows-pakke, SBOM, sjekksum (se `docs/RELEASE.md`) |

Sporbarhet (regel → kode → test) og genererte filer i `docs/reference/` sjekkes av pytest i `python`. Det finnes ingen egen `docs`- eller `security`-jobb; I8 sjekkes av testene (`common/privacy.py` og API-testene med testkortet).

## Modeller

Modellfiler (ONNX) ligger ikke i git. `models/manifest.yaml` har navn, versjon, URL og SHA-256; de lastes ned med `uv run python tools/fetch_models.py` (sjekker SHA-256) og legges i Windows-pakken av `tools/build_bundle.py`, så studio-PC-en ikke trenger nett for dem. Nå: Silero VAD (lyd) og YuNet (ansikt). Lisens for hver modell noteres i manifestet.
