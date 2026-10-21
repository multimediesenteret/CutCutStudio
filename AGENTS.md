# AGENTS.md – regler for AI-agenter

Denne filen gjelder alle AI-agenter som jobber i repoet. Den endres bare via pull request godkjent av et menneske.

## Før du gjør noe

1. Les `docs/STATUS.md` (hvor prosjektet står nå).
2. Les `docs/spec/01-app-spesifikasjon.md` helt, særlig seksjon 0 (agent-brief), 5 (regimotor), 11 (byggerekkefølge), 12 (utviklingsgrunnlag) og 13 (overlevering).
3. Bruk `docs/spec/02-teknisk-referanse.md` som oppslagsverk for protokoller og kommandoer. Nye funn legges inn der, med kilde.
4. Les `docs/open-questions.md`. Ikke bygg på et svar som står som åpent; lag en falsk enhet eller et konfigpunkt i stedet, og noter det.

Markdown-eksporten mangler tegningene (vist som `[embedded content: …]`). De finnes i PDF-ene i `docs/spec/`; se der når en tegning er nevnt.

## Første oppgave

> Lag implementasjonsplaner i `docs/plans/<modul>.md` etter malen i spesifikasjonens 0.4, for alle moduler i rekkefølgen fra seksjon 11, og et forslag til GitHub-issues og milepæler M0–M4 i `docs/plans/milestones.md`. Bekreft eller avvis ADR-0012 (atem-bridge) i planen for ATEM. Skriv ingen produksjonskode før planene er godkjent. Oppdater `docs/STATUS.md` og legg spørsmål du trenger svar på i `docs/open-questions.md`.

## Ufravikelige regler (spesifikasjonen 0.2)

- **I1** Sendingen avhenger aldri av at CutCut kjører.
- **I2** Kamera på program eller preview flyttes aldri (unntak: langsom zoom `Z` når slått på).
- **I3** Regelmotoren er deterministisk og lærer ikke i sanntid. Modeller måler, regler bestemmer.
- **I4** Hver beslutning logges med regel-ID og målte verdier.
- **I5** Mennesket vinner alltid; motoren tilpasser seg det den leser tilbake.
- **I6** Ingen skytjeneste i sanntidssløyfen.
- **I7** Opptak stoppes aldri automatisk.
- **I8** Kortnummer (UID) lagres og logges aldri.

En endring som bryter én av disse, avvises uansett hvor god den ellers er.

## Du har ikke tilgang til utstyret

Du jobber uten ATEM, kameraer, RØDECaster, Pearl, kortleser eller NTNU-API.

- Bygg og test alt mot simulatoren (`sim/`) og falske enheter (`tests/integration/`).
- Hver ny integrasjon får et maskintestskript i `tools/hw-test/<enhet>.py` som en tekniker kjører i studio. Skriptet skriver en rapport (JSON + Markdown); resultatet kommer tilbake som issue med malen «Maskintest-rapport».
- Send aldri kommandoer til ekte utstyr fra automatiske tester. Ekte kommandoer kjøres bare når et menneske starter dem.
- Opptak fra studio (når de finnes, se `docs/intake/opptak-og-klippeliste.md`) er «maskinvare på bånd»: kjør motoren mot dem i tester.

## Arbeidsflyt

- Egen gren per oppgave (`agent/<kort-beskrivelse>`). Du merger aldri selv; et menneske godkjenner hver pull request.
- *Conventional Commits*: `feat(core): …`, `fix(devices/obsbot): …`, `docs(spec): …`.
- Små pull requests: én leveranse fra planen, under én dags arbeid.
- Avslutt hver arbeidsøkt med å oppdatere `docs/STATUS.md`: ferdig, pågår, kjente feil, neste steg.
- Ny arkitekturbeslutning = ny fil i `docs/adr/` (neste nummer). Gamle ADR-er endres ikke; de får status «Erstattet av ADR-NNNN».

## Kode (når planene er godkjent)

- Python 3.12, `uv`, mypy strict, Pydantic v2, ruff. UI: React + TypeScript + Vite, pnpm.
- Engelsk i kode og kommentarer; norsk i grensesnitt (egen språkfil).
- Regel-ID-er (`T2`, `K1`, `H3` …) og enhets-ID-er brukes uendret i kode, testnavn og logg. CI skal feile hvis en regel mangler test (`docs/reference/traceability.md`).
- Ingen blokkerende kall i asyncio-løkken; all I/O har tidsavbrudd; enhetskommandoer er idempotente, i kø per enhet, med kretsbryter (ADR-0005).
- Hver modul kan kjøres mot simulatoren uten utstyr.
- Ingen hemmeligheter i git. De ligger i Windows Credential Manager via `keyring`. Testdata med kortnummer bruker bare det fiktive testkortet.

## Krever alltid et menneske

- Endringer i `AGENTS.md`, `docs/adr/` (nye beslutninger), ufravikelige regler og sikkerhetstiltak (spesifikasjonen 12.4).
- Nye avhengigheter med annen lisens enn MIT/BSD/Apache-2.0, eller som krever nett i drift.
- Alt som sender kommandoer til ekte utstyr eller NTNU-tjenester.
- Lagring av nye personopplysninger.
