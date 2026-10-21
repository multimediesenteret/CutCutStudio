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
