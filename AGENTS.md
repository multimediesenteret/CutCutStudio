# AGENTS.md – start her

Denne filen er inngangen for alle som tar over CutCut Studio, enten AI-agent eller menneske. Alt du trenger for å komme i gang står her eller er lenket herfra. Filen endres bare via pull request godkjent av et menneske.

> **Fase nå: klar for studioperioden (D-066).** Alt som kan bygges uten studio, er bygget og testet i CI (P1–P9 i `docs/plans/for-studio.md`). Det som står igjen, er maskintester og prøving i studio etter `docs/studio/testdag.md`. Se `docs/STATUS.md` for hvor arbeidet står.

**Hovedprinsipp:** prosjektet skal kunne tas over av hvem som helst, når som helst, uten muntlig overlevering. Det som ikke står i repoet, finnes ikke.

---

## 1. Hva prosjektet er (30 sekunder)

CutCut Studio er Multimediesenterets live auto-regi for videopodcast. En Windows-PC i studio lytter på hver mikrofon fra RØDECaster Pro II, ser kameraene via ATEM-multiviewen (INOGENI 4KXUSB3), og klipper som en menneskelig bilderegissør: neste bilde på preview først, kutt mellom setninger, aldri flytte et kamera som er på lufta. Kutt og layouter går gjennom Bitfocus Companion til ATEM Television Studio HD8 ISO. PTZ-kameraer (OBSBOT Tail 2, Canon CR-N300) styres over IP. Opptak går til Epiphan Pearl Nexus. Brukeren trykker Start på en touch-skjerm (adgangskort kommer senere, D-057); teknikeren har et eget vindu med oppsett, overstyring og helsestatus.

## 2. Les i denne rekkefølgen

| # | Fil | Hvorfor |
| --- | --- | --- |
| 1 | `docs/STATUS.md` | Hvor prosjektet står akkurat nå, og neste steg |
| 2 | Denne filen, helt | Regler, oppsett, arbeidsflyt |
| 2b | `docs/studio/testdag.md` og `docs/plans/for-studio.md` | Hva som gjenstår i studio, og rekkefølgen arbeidet før studio ble gjort i |
| 2c | `docs/architecture/README.md` | Prosesser, dataflyt og hvor data ligger |
| 3 | `docs/forprosjekt/beslutningslogg.md` | Alle beslutninger fra forprosjektet. **Nyere rader går foran spesifikasjonen** |
| 4 | `docs/spec/01-app-spesifikasjon.md` | Hva som skal bygges. Særlig seksjon 0, 5, 11, 12 og 13 |
| 5 | `docs/stack.md` | Teknologi, versjoner, utviklingsmiljø, CI |
| 6 | `docs/open-questions.md` | Hva som ikke er avklart. Ikke bygg på åpne svar |
| 7 | `docs/adr/README.md` | Arkitekturbeslutninger |
| 8 | `docs/RELEASE.md` | Versjonering og dokumentasjonsplikt per versjon |
| 9 | `docs/publishing.md` og `docs/simulator.md` | Hva som publiseres hvor; web-simulatoren på Vercel |
| – | `docs/spec/02-teknisk-referanse.md` | Oppslagsverk: protokoller, kommandoer, API-er per enhet |
| – | `docs/spec/03-evaluering-og-bakgrunn.md` | Hvorfor valgene er tatt |
| – | `docs/studio/` | Standardoppsett for utstyret i studio (f.eks. RØDECaster) |
| – | `docs/design/` | Farger, GUI-konsept og visuelle regler for alle skjermer |
| – | `concept/` | Klikkbart skjermkonsept (touch og tekniker) som UI-et skal bygges etter |
| – | `docs/research/` | Research bak beslutninger (f.eks. lyd fra RØDECaster) |
| – | `docs/forprosjekt/overlevering.md` | Historisk: overleveringen fra forprosjektet (2026-10-21) |
| – | `docs/prototype/cutcut-prototype.html` | Eldre skisse; bare referanse for regel-ID-er. GUI bygges etter `concept/` |

**Ved uenighet mellom dokumentene:** beslutningsloggen (nyeste rad) → aksepterte ADR-er → `docs/design/` og `docs/studio/` → `docs/spec/01` → `docs/spec/02` og `03` → `concept/` → `docs/prototype/`.

Markdown-eksporten av spesifikasjonen mangler tegningene (`[embedded content: …]`). PDF-ene er fjernet (D-061); arkitekturen er tegnet på nytt i `docs/architecture/`.

## 3. Git-identitet (obligatorisk)

Alle commits i dette repoet skal ha **samme forfatter og committer**:

```text
user.name  = Multimediesenteret
user.email = magnus.lian@ntnu.no
```

Grunnen er at web-delene publiseres på Vercel Hobby, som blokkerer utrulling når en commit har en forfatter som ikke er kontoeieren. Gjelder både mennesker og agenter.

- Kjør `tools/setup-git.sh` (Linux/macOS) eller `tools/setup-git.ps1` (Windows) etter kloning. Det setter identiteten lokalt i repoet.
- Ikke legg til `Co-authored-by:`-linjer i commit-meldinger. Vercel kan regne dem som ekstra bidragsytere. Tre sperrer: `.claude/settings.json` slår av Claude Codes medforfatter-linje (`attribution`), `tools/setup-git.*` aktiverer en `commit-msg`-hook som fjerner slike linjer, og CI-jobben `commit-identity` stopper pull requests som likevel har dem.
- CI-jobben `commit-identity` feiler hvis en commit i en pull request har en annen forfatter eller committer.
- Har du laget en commit med feil identitet: `git commit --amend --reset-author --no-edit` (siste commit), eller `git rebase -r <base> --exec "git commit --amend --no-edit --reset-author"` for flere.

## 4. Milepæler og hvor du starter

Milepælene (spesifikasjonen 13.5, `docs/plans/milestones.md`):

| Milepæl | Ferdig når | Status 2026-10-22 |
| --- | --- | --- |
| M0 Planer | Planer for alle moduler er godkjent av produkteier | Ferdig (D-046) |
| M1 Simulator | Hele brukerflyten og alle regeltester virker uten utstyr | Ferdig |
| M2 Studiotest | Motoren klipper live i studio via preview (lyd, ATEM, Companion, Pearl, supervisor). Ingen skyggerunde først (D-049) | Bygget; prøves i studioperioden |
| M3 Grunnmodus i drift | Akseptansekriteriene i 10.4 for grunnmodus er oppfylt | Bygget; prøves i studioperioden |
| M4 Brytere | Hver bryter testet alene i studio (D-049) | Bygget (P1–P9); prøves i studioperioden |

**Hvor du starter:** les `docs/STATUS.md` («Neste steg» og åpne issues). Er studioperioden ikke gjort, er jobben å støtte den: rette det maskintestene og prøvingen finner. Er den gjort, er jobben å justere grenseverdier mot opptakene (Q1, Q2) og lukke M2–M4.

## 5. Ufravikelige regler (spesifikasjonen 0.2)

- **I1** Sendingen avhenger aldri av at CutCut kjører.
- **I2** Kamera på program eller preview flyttes aldri (unntak: langsom zoom `Z` når slått på).
- **I3** Regelmotoren er deterministisk og lærer ikke i sanntid. Modeller måler, regler bestemmer.
- **I4** Hver beslutning logges med regel-ID og målte verdier.
- **I5** Mennesket vinner alltid; motoren tilpasser seg det den leser tilbake.
- **I6** Ingen skytjeneste i sanntidssløyfen.
- **I7** Opptak stoppes aldri automatisk.
- **I8** Kortnummer (UID) lagres og logges aldri.

En endring som bryter én av disse, avvises uansett hvor god den ellers er.

## 6. Du har ikke tilgang til utstyret

Agenter jobber i et Linux-skymiljø uten ATEM, kameraer, RØDECaster, Pearl, kortleser eller kort-API. Derfor:

- All logikk bygges og testes mot simulatoren (`sim/`) og falske enheter (`tests/integration/`), og skal kjøre på Linux. Windows-spesifikke deler (ASIO, WinSW, kiosk, Credential Manager) ligger bak adaptere med en falsk variant (se `docs/stack.md`).
- Hver integrasjon har en maskintest, `cutcut hwtest <audio|atem|camera|vision|faces|soak>` (`src/cutcut/hwtest/`, `docs/studio/maskintest.md`), som en tekniker kjører i studio. Den skriver en rapport (JSON + Markdown); resultatet kommer tilbake som issue med malen «Maskintest-rapport».
- Ekte kommandoer mot utstyr eller Multimediesenteret-tjenester kjøres bare når et menneske starter dem. Aldri fra automatiske tester.
- Opptak fra studio (`docs/intake/opptak-og-klippeliste.md`) er «maskinvare på bånd»: motoren kjøres mot dem i tester.

## 7. Arbeidsflyt

1. Ta en oppgave fra planen eller et issue. Én pull request = én leveranse eller ett tema; heller færre og større enn mange små (D-059).
2. Egen gren: `agent/<kort-beskrivelse>` for agenter, `<navn>/<kort-beskrivelse>` for mennesker. Ingen direkte push til `main`. Unntak i forprosjektet: rene dokumentasjonsendringer avtalt med produkteier i samtalen kan gå rett til `main`.
3. Commit-meldinger etter *Conventional Commits*: `feat(core): …`, `fix(devices/obsbot): …`, `docs(spec): …`, `chore(ci): …`. Scope er modulnavnet fra `src/cutcut/`.
4. Pull request med malen. CI må være grønn. **Agenten merger selv når all CI er grønn** (D-052), med metoden *rebase* så forfatteren beholdes og det ikke blir merge-commits (Vercel Hobby). Unntak som alltid krever et menneske står i 10.
5. **Ferdig betyr dokumentert** (se 8). En pull request uten oppdatert dokumentasjon er ikke ferdig.
6. Avslutt hver arbeidsøkt med å oppdatere `docs/STATUS.md`, også om arbeidet ikke er ferdig.

Ny arkitekturbeslutning = ny fil i `docs/adr/` med neste nummer (mal: `docs/adr/template.md`). Gamle ADR-er endres ikke; de får status «Erstattet av ADR-NNNN».

## 8. Dokumentasjonsplikt

Dokumentasjonen holdes oppdatert *i samme pull request* som koden den beskriver.

| Når du … | … oppdaterer du |
| --- | --- |
| Avslutter en arbeidsøkt | `docs/STATUS.md` (ferdig, pågår, kjente feil, neste steg) |
| Endrer eller lager en modul | `src/cutcut/<modul>/README.md` (ansvar, inn/ut, regel-ID-er, akseptanse) |
| Endrer en regel | Regelens test, `docs/reference/traceability.md` og regeltabellen i `docs/reference/` (generert, spesifikasjonen 12.1), og spesifikasjonen hvis oppførselen endres |
| Tar en arkitekturbeslutning | Ny `docs/adr/NNNN-*.md` og en rad i `docs/forprosjekt/beslutningslogg.md` |
| Gjør research | Ny fil i `docs/research/` med kilder |
| Lærer noe nytt om en enhet | `docs/spec/02-teknisk-referanse.md`, med kilde |
| Får svar på et spørsmål | `docs/open-questions.md` (svar, dato, hvem) |
| Løser en hendelse som tok over 10 min | Ny runbook i `docs/runbooks/` |
| Endrer API eller konfig | Genererte filer i `docs/reference/` (CI feiler ved avvik) |
| Endrer noe brukeren merker | `CHANGELOG.md` under `[Unreleased]` |
| Lager en release | Sjekklisten i `docs/RELEASE.md` |

Repoet er fasit fra overleveringen 21.10.2026. Spesifikasjonen i `docs/spec/*.md` redigeres direkte her (Claude Docs-dokumentet er arkiv). Endringer i oppførsel avtales med produkteier, føres inn i beslutningsloggen og deretter i spesifikasjonen i samme pull request. PDF-ene er et øyeblikksbilde fra overleveringen.

## 9. Kode

Kortversjon; detaljer i `docs/stack.md` og spesifikasjonen 3 og 12.

- Python 3.12, `uv`, mypy strict, Pydantic v2, ruff, pytest. UI: React + TypeScript + Vite i pnpm-arbeidsområde.
- Engelsk i kode og kommentarer; norsk i grensesnitt (egen språkfil).
- Regel-ID-er (`T2`, `K1`, `H3` …) og enhets-ID-er brukes uendret i kode, testnavn og logg. CI feiler hvis en regel mangler test.
- Ingen blokkerende kall i asyncio-løkken; all I/O har tidsavbrudd; enhetskommandoer er idempotente, i kø per enhet, med kretsbryter (ADR-0005).
- Hver modul kan kjøres mot simulatoren uten utstyr.
- Ingen hemmeligheter i git. De ligger i Windows Credential Manager via `keyring`. Testdata med kortnummer bruker bare det fiktive testkortet.

Kommandoene for å bygge, teste og kjøre simulatoren står i `README.md` og `docs/stack.md`. Den som legger til en ny kommando, dokumenterer den der og i README-en til modulen. CI kjører det samme som `uv run pytest`, `ruff`, `mypy` og `pnpm format:check && pnpm lint && pnpm typecheck && pnpm test`.

## 10. Krever alltid et menneske

- Endringer i `AGENTS.md`, nye ADR-er, ufravikelige regler og sikkerhetstiltak (spesifikasjonen 12.4).
- Merge av pull requests som endrer `AGENTS.md`, ufravikelige regler eller sikkerhetstiltak, eller som har rød CI. Tagging av release og utrulling i studio. (Andre pull requests merger agenten selv når CI er grønn, D-052.)
- Nye avhengigheter med annen lisens enn MIT/BSD/Apache-2.0, eller som krever nett i drift.
- Alt som sender kommandoer til ekte utstyr eller Multimediesenteret-tjenester.
- Lagring av nye personopplysninger.
- Endringer i Vercel-prosjektet eller GitHub-innstillinger.

## 11. Kontakt

| Rolle | Hvem |
| --- | --- |
| Produkteier og kodeeier | Magnus Lian, Multimediesenteret · GitHub `@Multimediesenteret` · magnus.lian@ntnu.no |
| Tekniker for studiotest | Se Q12 i `docs/open-questions.md` |
| Multimediesenteret IT | Se Q12 |
