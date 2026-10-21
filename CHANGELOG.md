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
