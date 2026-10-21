# Changelog

Etter [Keep a Changelog](https://keepachangelog.com/no/1.1.0/) og SemVer.

## [Unreleased]

### Added
- Spesifikasjon v1, teknisk referanse og evaluering (`docs/spec/`, 2026-10-21).
- ADR-0001–0012, AGENTS.md, åpne spørsmål, innsamlingsmaler og prototype.
- `AGENTS.md` utvidet til komplett startguide; `docs/stack.md`, `docs/RELEASE.md`, `docs/publishing.md`.
- Git-identitet (`tools/setup-git.*`) og CI-jobben `commit-identity`.
- Q21 (ASIO) og Q22 (Vercel-plan).
- Forprosjekt: `docs/forprosjekt/` med beslutningslogg D-001–D-031.
- `docs/simulator.md` og ADR-0013 (web-simulator på Vercel).
- `docs/research/lyd-fra-rodecaster.md` og ADR-0014 (lyd i egen prosess via ASIO); Q21 delvis, Q22 besvart, ny Q23.
- `docs/studio/rodecaster-standardoppsett.md` (firmware 1.7.6, faderkart, innstillinger) og `docs/design/farger.md` (deltakerfarger); D-032–D-035, Q23 besvart, Q24–Q25.
- Prototypen viser deltakerfarger og uthevet programleder.
- GUI-konsept i `concept/` (touch, tekniker, side om side) og `docs/design/gui-konsept.md`; D-036–D-039. Vercel-oppsett for konseptet i `docs/publishing.md`.
- `vercel.json`: forsiden og alle stier går til `concept/`; korte adresser `/touch` og `/tech`.
- Konseptet ca. 6× lettere: 10 Hz, bare endringer skrives, målere med transform, tidslinje i sammenhengende biter. Ytelseskrav i `docs/design/gui-konsept.md`.
- Overlevering: `docs/forprosjekt/overlevering.md` med startmelding, modulliste og blokkeringer. Spesifikasjonen rettet for D-035–D-045 (regel-ID-er `CT`/`PV`/`S6`, prosesser, touch-flyt, utlogging, Companion lokalt). Konseptet følger spesifikasjonen (5600 K, preset-navn, 5 s teknikertilgang). Repoet er fasit (D-040).
- Hindrer `Co-authored-by`: `.claude/settings.json` og `commit-msg`-hook.
- M0: implementasjonsplaner for alle 13 moduler og `milestones.md` i `docs/plans/`, forslag PL-01–PL-08, spørsmål Q27–Q36.
- Planene godkjent (D-046); ADR-0012–0014 akseptert. Lisens Apache-2.0 (`LICENSE`, `NOTICE`). Ingen skyggerunde: M2 er nå «Studiotest» (D-049). Vercel hopper over utrulling når skjermene ikke er endret (`ignoreCommand`, D-050).
- C-1: Python-prosjekt (`pyproject.toml`, `uv.lock`, Python 3.12), ruff, mypy strict, pytest, kommandoen `cutcut`, og CI-jobben `python` med sti-filter.
- C-2: faste ID-er (`P1`–`P4`, `M1`–`M5`, `C1`–`C7`, `LAPTOP`, moduser, alle regel-ID-er fra spesifikasjonen) og Pydantic-modeller for show-oppsett, økt, beslutning og buss. Show-oppsettet avvises hvis deltakere deler mic eller kamera, `C5` mangler, eller ATEM-innganger kolliderer.
- C-3: konfiglasting med lesbare feilmeldinger, `config/defaults/rules.yaml` med alle regelverdier for Rolig, Standard og Energisk, `config/defaults/show_types.yaml`, overstyring per show, migrering etter `schema_version` (nyere filer avvises), og genererte skjemaer i `config/schema/`.
- C-4: monoton klokke (og falsk klokke for tester), logging som JSON-linjer med `correlation_id`, daglig rotasjon og 30 dagers lagring. Alt som ligner et kortnummer fjernes fra logglinjene før de skrives (I8).
- C-5: lagring i SQLite (WAL) for økter, beslutninger, revisjonslogg, konfigversjoner, varsler og motortilstand. Skriving går i egen tråd og blokkerer aldri motoren; full kø eller diskfeil gir tapt skriving, ikke stopp. Gamle data ryddes etter lagringstid (økter 90 dager, beslutninger 30). Testet med drept prosess midt i skriving.
- C-6: intern meldingsbuss (ZeroMQ) mellom prosessene: `core` er nav, de andre kobler seg til og kan starte på nytt i hvilken som helst rekkefølge. Tapte meldinger telles, stille emner oppdages, og kommandoer får kvittering og nye forsøk.
- C-7: plattform-adaptere for hemmeligheter (Windows Credential Manager) og PC-status (CPU, minne, disk, oppetid) med falske varianter, så alt kan kjøres og testes uten Windows.
- C-8: eksempelstudio i `site/example/` (fiktivt, show for 1–4 deltakere, utstyr, teknikere og Companion-knappekart) og innlasting av et studio-oppsett som sjekker at show, utstyr og knapper stemmer med hverandre.
- K-1–K-7: regimotoren med grunnmodus. Moduser `N1`–`N4C` og `A`, tale-regler `T1`–`T12` med roller, preview før program, kutt mellom setninger (`K1`–`K4`), hold og release (`H1`–`H4`), sikkerhet (`S1`–`S4`, `S6`), fugleperspektiv `B2`–`B5`, overstyring (manuelt kutt, AUTO, LÅS, endring på ATEM respekteres) og skyggemodus. Motoren er deterministisk og testet med 85 regel- og egenskapstester.
- K-8: content fra laptop (`CT1`–`CT6`): ny slide vises innen 1 s og holdes, video og laptop-lyd holder content, statisk content går tilbake til taleren via et kort fugleperspektiv, og tapt signal kuttes bort straks. Opptaket åpner på fugleperspektiv og går så til verten (`B1`).
