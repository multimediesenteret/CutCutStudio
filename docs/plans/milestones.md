# Milepæler, issues og arbeidsflyt

Status: godkjent (D-046), endret ved D-049 · Spes. 11, 13.5; `docs/RELEASE.md`; `AGENTS.md` 7

Issues er forslag. De opprettes i GitHub (med milepæl og etikett) når produkteier har godkjent planene. Hvert issue er én pull request på under én dags arbeid. ID-en i første kolonne viser til leveransen i planen.

## Faser

| Milepæl | Versjon | Hva du får | Ferdig når | Kan starte når |
| --- | --- | --- | --- | --- |
| **M0 Planer** | – | Disse planene | Produkteier har godkjent | Nå |
| **M1 Simulator** | 0.1.0 | Hele CutCut uten utstyr: motor med grunnmodus, simulator, API, touch og tekniker; web-simulatoren på Vercel erstatter konseptet | Touch-flyten går i Playwright og alle regeltester er grønne | M0 godkjent, Q11 og Q12 besvart |
| **M2 Studiotest** | 0.2.0 | CutCut klipper live i studio: lyd inn, ATEM, Companion (preview + TAKE), Pearl start/stopp og status, helse, supervisor som Windows-tjeneste. Økt startes fra teknikervinduet (kort kommer i M3). Først på test-PC-en (Dell SFF, Q28), så i studio | Testsendinger klippes via preview og vurderes av operatør; motoren står i dager uten tilsyn | M1 ferdig; test-PC klar |
| **M3 Grunnmodus i drift** | 1.0.0 | CutCut klipper via preview, kortinnlogging, opptak fra touch, kameradrivere, content og fugleperspektiv, setup-hjelper, kiosk, installasjon med tilbakerulling | Akseptansekriteriene i 10.4 for grunnmodus, inkludert 72 timer | M2 ferdig |
| **M4 Brytere** | 1.x | Videolag, utsnitt, reaksjoner, zoom, layouter, AI-tracking, live tekst, farge, Panopto | Hver bryter testet alene i studio | M3 i drift |

Hver milepæl avsluttes med en demonstrasjon for produkteier: i M1 på Vercel, fra M2 i studio.

## Issues

### M1 Simulator (ca. 45 issues)

| ID | Tittel |
| --- | --- |
| C-1 | chore: Python-skjelett, uv, ruff, mypy strict, pytest, CI `python` |
| C-2 | feat(common): ID-er og modeller for show, økt, beslutning |
| C-3 | feat(common): konfiglasting, `rules.yaml`, JSON Schema |
| C-4 | feat(common): klokke og logging |
| C-5 | feat(common): SQLite-lager |
| C-6 | feat(common): buss med `seq` og `stale` |
| C-7 | feat(common): plattform-adaptere med falsk variant |
| C-8 | feat(site): `site/example/` |
| K-1 … K-10 | feat(core): moduser, `T`, `PV`, `K`, `H`, `S`, overstyring og skyggemodus, `B`/`CT`, skall, sporbarhet |
| SIM-1 … SIM-7 | feat(sim): talere, scenarioer, falske enheter, `cutcut sim`, forløp til Vercel |
| A-1 … A-6 | feat(api): app, WebSocket, økt, overstyring, roller, logg |
| SE-1 | feat(session): økt-tilstandsmaskin mot simulator |
| U-1 … U-10 | feat(ui): design, klient, touch, tekniker, simulator på Vercel |
| D-1 | docs: `docs/architecture/` (Mermaid), README «kom i gang», runbook-mal |

### M2 Studiotest (ca. 28 issues)

| ID | Tittel |
| --- | --- |
| AU-1 … AU-7 | feat(audio): `audio-capture`, VAD, frasegrenser, lekkasje, ASIO, maskintest |
| DA-1 … DA-5 | feat(devices): `atem-bridge`, ATEM-klient, avstemming, Companion-klient, maskintester |
| SE-2, SE-3 | feat(devices/pearl): status, start og stopp |
| DA-6, DA-7 | feat(devices): klipping via preview + TAKE, `S5` reservekutt |
| HS-1, HS-2 | feat(health): helsemotor og første sjekker |
| SO-1, SO-2 | feat(supervisor): supervisor og WinSW |
| SIM-8 | feat(sim): avspilling av ekte forløp (når Q1 finnes) |
| T-M2 | test: testsendinger i studio, vurdert av operatør |

### M3 Grunnmodus i drift (ca. 35 issues)

| ID | Tittel |
| --- | --- |
| DA-8, DA-9 | feat(devices): ISO-opptak, Companion-sider |
| SE-4 … SE-7 | feat(session): kortleser, NTNU-API, show-typer, Panopto-felt |
| VI-1 … VI-5 | feat(vision): lett videolag og content-deteksjon |
| CA-1 … CA-6 | feat(devices/cameras): drivere, grenser, helse |
| HS-3 … HS-7 | feat(health/setup): varsling, morgensjekk, setup-hjelper, full katalog |
| SO-3 … SO-9 | feat(ops): pakke, installasjon, Windows-oppsett, kiosk, rydding, 72 timer, runbooks |
| T-M3 | test: akseptansekriteriene i 10.4 |

### M4 Brytere (ca. 12 issues)

F-1 … F-11, VI-6, CA-7 (se `features.md`).

## Arbeidsflyt med gratis GitHub og Vercel Hobby

Repoet er privat på gratis GitHub, og Vercel er på Hobby. Begge har grenser, og vi vil ha kontroll og backup uten å bruke dem opp.

**Hva grensene er (kontrollert 21.10.2026):**

| Tjeneste | Grense som betyr noe for oss |
| --- | --- |
| GitHub Free, privat repo | 2000 Actions-minutter per måned på standard Linux-maskiner; 500 MB artefaktlager. Windows-maskiner koster mer per minutt. **Beskyttelse av `main` (branch protection) er ikke tilgjengelig** for private repoer på gratisplanen |
| Vercel Hobby | 100 utrullinger per døgn, 45 min byggetid per utrulling. Statiske filer uten byggesteg regnes ikke som bygg. Commit-forfatter må være kontoeier (D-026) |

**Slik jobber agenten:**

1. **Lokale commits ofte, push sjelden.** Agenten committer hvert lille steg lokalt, men pusher til GitHub når en leveranse er ferdig eller ved slutten av en arbeidsøkt (typisk 1–3 ganger per dag). Det gir backup uten å starte CI og Vercel for hvert lille steg.
2. **Én gren og én pull request per leveranse** (`AGENTS.md` 7). PR-en åpnes som utkast når første push skjer, og markeres klar når den er ferdig.
3. **CI bare når det trengs:**
   - Sti-filtre: endringer bare i `docs/` kjører bare `commit-identity`; Python-jobben kjører når `src/`, `sim/`, `tests/` eller `config/` endres; UI-jobben når `ui/` endres.
   - `concurrency` med `cancel-in-progress`, så en ny push stopper forrige kjøring.
   - Linux på hver PR. Windows bare ved merge til `main`, ukentlig og før release (eller på egen Windows-maskin, se Q28).
   - Mellomlager for `uv` og `pnpm`. Forventet bruk: 5–8 min per PR-push på Linux, godt under 2000 min per måned med 1–3 pusher per dag.
4. **Vercel bygger bare når skjermene endres:** `ignoreCommand` i `vercel.json` hopper over utrulling når ingenting i `ui/` eller `concept/` er endret (krever eiers godkjenning, Q27). Før M1 er konseptet statisk og koster nesten ingenting.
5. **Backup:** GitHub er backup av kode og dokumentasjon. Studioets data (database, logger) tas nattlig kopi av lokalt på regi-PC-en (`supervisor-ops.md`); kopi til NTNU-lagring kan legges til (Q29/Q30).

**Siden `main` ikke kan beskyttes (Q27), foreslås tre alternativer:**

| Alternativ | Fordeler | Ulemper |
| --- | --- | --- |
| A. Behold privat, gratis; agenten pusher aldri til `main`, bare til egne grener og PR-er | Ingen kostnad | Ingen teknisk sperre; bygger på disiplin. CI-sjekken `commit-identity` fanger fortsatt feil forfatter |
| B. GitHub Pro på kontoen | Beskyttelse av `main`, flere Actions-minutter | Månedlig kostnad |
| C. Gjør repoet offentlig | Beskyttelse av `main` og ubegrensede Actions-minutter på standard maskiner gratis | Koden blir synlig; krever lisens (Q11) og at ingen hemmeligheter eller studio-detaljer ligger i repoet (de skal uansett ikke ligge der) |

Agentens anbefaling: **A nå** (forprosjekt og M1 er bare kode og dokumentasjon), og ta stilling til B eller C før M2, når studiospesifikke data begynner å komme inn.

## Hva produkteier må gjøre per milepæl

| Når | Hva |
| --- | --- |
| Før M1 | Godkjenne planene (PR `agent/m0-plans`), svare på Q11, Q12, Q27, Q36. Si ja eller nei til å opprette issues og milepæler i GitHub |
| Under M1 | Se på Vercel-forhåndsvisninger av PR-er og gi tilbakemelding på skjermene sammen med lærerne |
| Før M2 | Tilgang til regi-PC i studio (Q8), studioinventar (Q18, Q26), tekniker som kjører maskintester (Q12), UPS og strøm (Q31) |
| Før M3 | NTNU-API-nøkkel (Q4), personvern (Q10), varsling (Q29), servicevindu (Q30) |
| Før M4 | Canon XC (Q6), GPU (Q20), Panopto (Q5) |
