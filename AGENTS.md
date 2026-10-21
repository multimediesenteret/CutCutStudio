# AGENTS.md – start her

Denne filen er inngangen for alle som tar over CutCut Studio, enten AI-agent eller menneske. Alt du trenger for å komme i gang står her eller er lenket herfra. Filen endres bare via pull request godkjent av et menneske.

> **Fase nå: forprosjektet er overlevert, M0 (planer) kan starte.** Ingen produksjonskode før planene er godkjent. Les `docs/forprosjekt/overlevering.md` for startmelding, hva som mangler og hva som blokkerer hva.

**Hovedprinsipp:** prosjektet skal kunne tas over av hvem som helst, når som helst, uten muntlig overlevering. Det som ikke står i repoet, finnes ikke.

---

## 1. Hva prosjektet er (30 sekunder)

CutCut Studio er NTNU Multimediesenterets live auto-regi for videopodcast. En Windows-PC i studio lytter på hver mikrofon fra RØDECaster Pro II, ser kameraene via ATEM-multiviewen (INOGENI capture), og klipper som en menneskelig bilderegissør: neste bilde på preview først, kutt mellom setninger, aldri flytte et kamera som er på lufta. Kutt og layouter går gjennom Bitfocus Companion til ATEM Mini Extreme ISO. PTZ-kameraer (OBSBOT Tail 2, Canon CR-N300) styres over IP. Opptak går til Epiphan Pearl Nexus. Brukeren logger inn med NTNU-kortet på en touch-skjerm; teknikeren har et eget vindu med oppsett, overstyring og helsestatus.

## 2. Les i denne rekkefølgen

| # | Fil | Hvorfor |
| --- | --- | --- |
| 1 | `docs/STATUS.md` | Hvor prosjektet står akkurat nå, og neste steg |
| 2 | Denne filen, helt | Regler, oppsett, arbeidsflyt |
| 2b | `docs/forprosjekt/overlevering.md` | Startmelding, hva som mangler, rekkefølge for kilder til sannhet |
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
| – | `docs/prototype/cutcut-prototype.html` | Eldre skisse; bare referanse for regel-ID-er. GUI bygges etter `concept/` |

**Ved uenighet mellom dokumentene:** beslutningsloggen (nyeste rad) → aksepterte ADR-er → `docs/design/` og `docs/studio/` → `docs/spec/01` → `docs/spec/02` og `03` → `concept/` → `docs/prototype/`.

Markdown-eksporten av spesifikasjonen mangler tegningene (`[embedded content: …]`). De finnes i PDF-ene i `docs/spec/`.

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

## 4. Første oppgave (milepæl M0)

> Lag implementasjonsplaner i `docs/plans/<modul>.md` etter malen i spesifikasjonens 0.4, for alle moduler i rekkefølgen fra seksjon 11, og et forslag til GitHub-issues og milepæler M0–M4 i `docs/plans/milestones.md`. Bekreft eller avvis ADR-0012 (atem-bridge) i planen for ATEM. Skriv ingen produksjonskode før planene er godkjent. Oppdater `docs/STATUS.md` og legg spørsmål du trenger svar på i `docs/open-questions.md`.

Milepælene (spesifikasjonen 13.5):

| Milepæl | Ferdig når |
| --- | --- |
| M0 Planer | Planer for alle moduler er godkjent av produkteier |
| M1 Simulator | Hele brukerflyten og alle regeltester virker uten utstyr |
| M2 Skyggemodus | Motoren logger beslutninger live i studio uten å klippe, sammenlignet med menneske |
| M3 Grunnmodus i drift | Akseptansekriteriene i 10.4 for grunnmodus er oppfylt |
| M4 Brytere | Hver bryter testet alene i skyggemodus |

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

Agenter jobber i et Linux-skymiljø uten ATEM, kameraer, RØDECaster, Pearl, kortleser eller NTNU-API. Derfor:

- All logikk bygges og testes mot simulatoren (`sim/`) og falske enheter (`tests/integration/`), og skal kjøre på Linux. Windows-spesifikke deler (ASIO, WinSW, kiosk, Credential Manager) ligger bak adaptere med en falsk variant (se `docs/stack.md`).
- Hver integrasjon får et maskintestskript i `tools/hw-test/<enhet>.py` som en tekniker kjører i studio. Skriptet skriver en rapport (JSON + Markdown); resultatet kommer tilbake som issue med malen «Maskintest-rapport».
- Ekte kommandoer mot utstyr eller NTNU-tjenester kjøres bare når et menneske starter dem. Aldri fra automatiske tester.
- Opptak fra studio (`docs/intake/opptak-og-klippeliste.md`) er «maskinvare på bånd»: motoren kjøres mot dem i tester.

## 7. Arbeidsflyt

1. Ta en oppgave fra planen eller et issue. Én pull request = én leveranse, under én dags arbeid.
2. Egen gren: `agent/<kort-beskrivelse>` for agenter, `<navn>/<kort-beskrivelse>` for mennesker. Ingen direkte push til `main`. Unntak i forprosjektet: rene dokumentasjonsendringer avtalt med produkteier i samtalen kan gå rett til `main`.
3. Commit-meldinger etter *Conventional Commits*: `feat(core): …`, `fix(devices/obsbot): …`, `docs(spec): …`, `chore(ci): …`. Scope er modulnavnet fra `src/cutcut/`.
4. Pull request med malen. CI må være grønn. Et menneske godkjenner og merger; agenter merger aldri selv.
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

## 9. Kode (fra M1)

Kortversjon; detaljer i `docs/stack.md` og spesifikasjonen 3 og 12.

- Python 3.12, `uv`, mypy strict, Pydantic v2, ruff, pytest. UI: React + TypeScript + Vite i pnpm-arbeidsområde.
- Engelsk i kode og kommentarer; norsk i grensesnitt (egen språkfil).
- Regel-ID-er (`T2`, `K1`, `H3` …) og enhets-ID-er brukes uendret i kode, testnavn og logg. CI feiler hvis en regel mangler test.
- Ingen blokkerende kall i asyncio-løkken; all I/O har tidsavbrudd; enhetskommandoer er idempotente, i kø per enhet, med kretsbryter (ADR-0005).
- Hver modul kan kjøres mot simulatoren uten utstyr.
- Ingen hemmeligheter i git. De ligger i Windows Credential Manager via `keyring`. Testdata med kortnummer bruker bare det fiktive testkortet.

Kommandoene for å bygge, teste og kjøre simulatoren står i `README.md` og `docs/stack.md` så snart de finnes. Den som legger til en ny kommando, dokumenterer den der.

## 10. Krever alltid et menneske

- Endringer i `AGENTS.md`, nye ADR-er, ufravikelige regler og sikkerhetstiltak (spesifikasjonen 12.4).
- Merge til `main`, tagging av release og utrulling i studio.
- Nye avhengigheter med annen lisens enn MIT/BSD/Apache-2.0, eller som krever nett i drift.
- Alt som sender kommandoer til ekte utstyr eller NTNU-tjenester.
- Lagring av nye personopplysninger.
- Endringer i Vercel-prosjektet eller GitHub-innstillinger.

## 11. Kontakt

| Rolle | Hvem |
| --- | --- |
| Produkteier og kodeeier | Magnus Lian, NTNU Multimediesenteret · GitHub `@Multimediesenteret` · magnus.lian@ntnu.no |
| Tekniker for studiotest | Se Q12 i `docs/open-questions.md` |
| NTNU IT | Se Q12 |
