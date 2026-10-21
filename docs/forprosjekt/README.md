# Forprosjekt

CutCut Studio er i **forprosjekt**. Det skrives ingen kode. Målet er at alt en AI-agent eller utvikler trenger for å bygge første versjon, ligger ferdig i dette repoet.

## Hvordan forprosjektet jobber

- Produkteier (Magnus Lian, NTNU Multimediesenteret) og Claude går gjennom krav, utstyr og teknologi i samtaler.
- Alt som avtales, skrives inn i repoet i samme økt: beslutninger i `beslutningslogg.md`, research i `docs/research/`, åpne spørsmål i `docs/open-questions.md`, arkitektur i `docs/adr/`.
- Spesifikasjonen (`docs/spec/`) ble skrevet i et Claude Docs-dokument og eksportert hit. Nyere beslutninger står i beslutningsloggen og går foran til spesifikasjonen er eksportert på nytt.

## Hva som er gjort

| Område | Hvor |
| --- | --- |
| Evaluering av marked og SOTA | `docs/spec/03-evaluering-og-bakgrunn.md` |
| Full app-spesifikasjon med regler, skjermer, integrasjoner, drift | `docs/spec/01-app-spesifikasjon.md` |
| Protokoller og kommandoer per enhet | `docs/spec/02-teknisk-referanse.md` |
| Klikkbar prototype | `docs/prototype/cutcut-prototype.html` |
| Arkitekturbeslutninger | `docs/adr/` |
| Overlevering til agent, milepæler | `AGENTS.md`, spes. 13 |
| Stack, versjonering, publisering | `docs/stack.md`, `docs/RELEASE.md`, `docs/publishing.md` |
| Web-simulator | `docs/simulator.md` |
| Research: lyd fra RØDECaster | `docs/research/lyd-fra-rodecaster.md` |

## Ferdig når

Forprosjektet er ferdig og koding (M0, deretter M1) kan starte når:

- [ ] Produkteier har godkjent spesifikasjonen og beslutningsloggen.
- [ ] Spørsmålene som blokkerer M0–M1 er besvart: Q11 (lisens), Q12 (kontaktpersoner).
- [ ] ADR-0012, 0013 og 0014 er avgjort eller eksplisitt overlatt til agentens planer.
- [ ] Studioinventaret (`docs/intake/studio-inventar.md`) er fylt ut.
- [ ] Opptak og klippeliste (Q1–Q2) er bestilt, med dato. De trengs ikke for M1, men for M2.
- [ ] Spesifikasjonen er eksportert på nytt med beslutningene D-030 og D-031 innarbeidet (eller beslutningsloggen er godkjent som tillegg).
