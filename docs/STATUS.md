# Status

Oppdatert: 2026-10-21 · av: Multimediesenteret (med Claude)

## Hvor vi er

- **Fase:** forprosjektet er overlevert; M0 (planer) kan starte. Ingen produksjonskode ennå.
- **Milepæl:** før M0.
- **Spesifikasjon:** v1, 20.10.2026 (`docs/spec/`). Kilden er Claude Docs-dokumentet «CutCut Studio – spesifikasjon og evaluering»; eksporten i repoet oppdateres når den endres.
- **Prototype:** `docs/prototype/cutcut-prototype.html` (simulert lyd, ingen ekte utstyr).

## Ferdig

- Spesifikasjon, teknisk referanse og evaluering.
- Arkitekturbeslutninger ADR-0001–0014 (0012–0014 er forslag som bekreftes eller avvises i M0-planene).
- `AGENTS.md` som startpunkt, `docs/stack.md`, `docs/RELEASE.md`, `docs/publishing.md`.
- Git-identitet og CI-sjekk `commit-identity` for Vercel Hobby.
- Beslutningslogg D-001–D-031 for hele forprosjektet.
- Web-simulator beskrevet (`docs/simulator.md`, ADR-0013).
- Research på lyd fra RØDECaster (`docs/research/lyd-fra-rodecaster.md`, ADR-0014).
- RØDECaster standardoppsett og deltakerfarger (D-032–D-035); prototypen oppdatert med fargene.
- GUI-konsept for touch og tekniker i `concept/`, publisert på Vercel (D-036–D-039).
- Løse tråder ryddet før overlevering: ID-kollisjoner, prosessliste, touch-flyt i spesifikasjonen, utlogging, roller (D-040–D-045). Overlevering: `docs/forprosjekt/overlevering.md`.

## Pågår

- NTNU samler inn det som står i `docs/open-questions.md` og `docs/intake/`.

## Kjente feil

Ingen.

## Neste steg

1. Forprosjekt: fullføre sjekklisten i `docs/forprosjekt/README.md`.
2. Agent (etter godkjent forprosjekt): implementasjonsplaner (se første oppgave i `AGENTS.md`).
3. Eier: beskytt `main` på GitHub (se `docs/forprosjekt/overlevering.md`). Konseptet er publisert på https://cutcutstudio2026.vercel.app.
4. NTNU: opptak og klippeliste (Q1–Q2), studioinventar (`docs/intake/studio-inventar.md`), kontaktpersoner og lisens (Q11–Q12).
