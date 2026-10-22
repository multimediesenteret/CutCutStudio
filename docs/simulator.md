# Web-simulator (Vercel)

CutCut Studio er en Windows-app og kan ikke kjøre på Vercel. For å kunne se og diskutere skjermene og klippingen uten å være i studio lager vi en **web-simulator**: de samme skjermene som i appen, drevet av simulerte data, publisert på Vercel.

## Formål

- Raskt se om regler, skjermer og flyt gir mening, uten utstyr.
- Vise skjermene til kolleger og brukere og få tilbakemelding tidlig.
- Gi hver pull request en forhåndsvisning (Vercel preview), så endringer i GUI kan vurderes før merge.

## Krav

1. **Samme GUI som appen.** Simulatoren bruker `ui/apps/touch` og `ui/apps/tech` uendret. Den lager ikke egne kopier av skjermene. Bare transporten byttes: i stedet for WebSocket mot motoren på regi-PC-en snakker skjermene med en simulert motor i nettleseren.
2. **Samme regler som appen.** Klippebeslutningene skal komme fra den samme regelkoden som kjører i studio, ikke fra en egen JavaScript-versjon som kan bli ulik.
3. **Simulerte data.** Mic-aktivitet, multiview (tegnede kamerabilder), ATEM, Companion, Pearl, kameraer og kortleser er simulert. Ingen kall til ekte utstyr, kort-API eller Panopto.
4. **Ingen persondata.** Innlogging skjer med fiktive testbrukere («Testkort A/B»). Ingen ekte navn eller kortnummer.
5. **Tydelig merket.** Fast banner «SIMULATOR – ingen ekte utstyr».
6. **Statisk side.** Ingen server eller database på Vercel. Hobby-planen holder.

## Visninger

| Visning | Innhold |
| --- | --- |
| Regibord | Program/preview, multiview med overlegg, mic-striper, neste beslutning, beslutningslogg med regel-ID, tidslinje |
| Kontrollpanel (bare simulator) | Velg antall deltakere 1–4, laptop av/på, show-type; trykk og hold per mic for å «snakke»; velg ferdig scenario; tempo 0,5×–4×; slå brytere av/på |
| Touch | Hele brukerflyten fra «vis kortet» til ferdig opptak, i 1920 × 1080 skalert |
| Tekniker | Teknikervindu, setup-hjelper og helsesiden, med mulighet til å simulere feil (kamera borte, Companion nede, ingen lyd) |

## Scenarioer

Ferdige scenarioer ligger som filer i `sim/scenarios/` og brukes både av simulatoren og av testene:

- Monolog (1 person), samtale (2), panel (3–4), krysstale, lang stillhet, laptop med ny slide, video på laptop.
- Feil: lyd borte (`S4`), Companion nede, kamera svarer ikke, Pearl uten lagring.
- Når ekte opptak finnes (Q1): avspilling av nivå- og VAD-forløp fra ekte episoder, uten selve lyden.

## Arkitektur (ADR-0013, akseptert D-046)

| Trinn | Hva | Når |
| --- | --- | --- |
| 1. Avspilling | Python-simulatoren kjører scenarioene i CI og lagrer hele forløpet (tilstand og beslutninger) som JSON. Web-simulatoren spiller det av i skjermene | M1 |
| 2. Interaktiv | Regelmotoren (ren Python uten I/O) kjøres i nettleseren med **Pyodide** (Python i WebAssembly). Kontrollpanelet sender simulert lyd inn, og beslutningene kommer fra samme kode som i studio | Etter M1 |

**Forløp (trinn 1, SIM-7):** `uv run cutcut trace` kjører hver historie i `src/cutcut/sim/trace.py` (nå «samtale» og «panel-laptop») på falsk klokke med ekte motor, studio-tjeneste og hub, og lagrer alle meldinger skjermene ville fått over `/ws`, med studioets oppsett (`site/multimediesenteret/`, D-054) i `ui/apps/simulator/public/traces/`. Full tilstand lagres hvert 10. sekund så avspillingen kan hoppe. Forløpene er deterministiske og ligger i git; testen `test_committed_traces_are_up_to_date` feiler når motoren er endret uten at forløpene er laget på nytt, så Vercel alltid viser dagens motor.

Krav til koden for at trinn 2 skal virke: regelmotoren i `src/cutcut/core/` har ingen I/O, ingen tråder og ingen Windows-avhengigheter; klokke og hendelser kommer inn utenfra. Dette er uansett et krav for deterministiske regeltester (I3).

## Publisering

- Vercel-prosjekt koblet til `main` (produksjon) og pull requests (forhåndsvisning). Se `docs/publishing.md`.
- Byggekommando og mappe står i `docs/publishing.md`. Simulatoren ligger på `/sim/`: begge skjermene i hver sin ramme, ett felles forløp, og et lite panel for å velge forløp, pause, fart og hoppe. Hver skjerm kan også åpnes alene (`/sim/touch.html`, `/sim/tech.html`).
- Før M1 publiseres GUI-konseptet i `concept/` på Vercel.

## Forhold til GUI-konseptet

`concept/` er skjermkonseptet fra forprosjektet (D-036–D-039): ferdig utseende og flyt for begge skjermene, med en forenklet JavaScript-motor. Simulatoren i M1 skal se ut og oppføre seg som konseptet, men bruke de ekte UI-appene og den ekte regelkoden.

## Forhold til prototypen

`docs/prototype/cutcut-prototype.html` er en håndlaget skisse fra forprosjektet med egen, forenklet logikk. Den er referanse for oppførsel og regel-ID-er, ikke for kode. Web-simulatoren erstatter den når M1 er ferdig.
