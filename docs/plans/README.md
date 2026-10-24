# Implementasjonsplaner

Status: **godkjent av produkteier 2026-10-21 (D-046)**, med endring D-049 (ingen skyggerunde) · Dato: 2026-10-21 · Av: agent (Claude) for Multimediesenteret

Én fil per modul, i rekkefølgen fra spesifikasjonen seksjon 11, etter malen i 0.4:

1. Formål og avgrensning (seksjoner og regel-ID-er)
2. Grensesnitt (Pydantic-modeller)
3. Tilstander og feil
4. Avhengigheter (låste versjoner, utstyr)
5. Testplan (regeltester, falske enheter, simulator, 10.4)
6. Leveranser (steg under én dag, hvert med «ferdig når»)
7. Åpne spørsmål (legg dem også i `docs/open-questions.md`)

## Planene

| # | Plan | Dekker | Spes. 11 steg | Milepæl |
| --- | --- | --- | --- | --- |
| 1 | [`common.md`](common.md) | Modeller, konfig og skjema, klokke, logging, lagring, meldingsbuss, plattform-adaptere | 2 | M1 |
| 2 | [`core.md`](core.md) | Regimotor: moduser, regler, roller, preview-tilstander, beslutninger, skyggemodus | 2 | M1 |
| 3 | [`sim.md`](sim.md) | Python-simulator, scenarioer, avspilling, opptak av forløp til web-simulatoren | 2 | M1 |
| 4 | [`api.md`](api.md) | FastAPI REST og WebSocket, roller, OpenAPI | 3 | M1 |
| 5 | [`ui.md`](ui.md) | Design, klient, touch, tekniker, web-simulator på Vercel | 3 | M1 |
| 6 | [`audio.md`](audio.md) | `audio-capture` (ADR-0014), VAD, dominans, lekkasje, frasegrenser, `S6` | 4 | M2 |
| 7 | [`devices-companion-atem.md`](devices-companion-atem.md) | Companion-klient, `atem-bridge` (ADR-0012), makrosjekk | 5 | M2–M3 |
| 8 | [`session.md`](session.md) | Kortleser, kort-API, økter, show-typer, Pearl | 6 | M2–M3 |
| 9 | [`vision.md`](vision.md) | Capture, rutekart, content-deteksjon, ansikt og munn | 7 | M3–M4 |
| 10 | [`devices-cameras.md`](devices-cameras.md) | `obsbot`, `canon_xc`, grenser, presets, AI-tracking | 8 | M3 |
| 11 | [`setup-health.md`](setup-health.md) | Setup-hjelperen og helsekatalogen | 8 | M3 |
| 12 | [`supervisor-ops.md`](supervisor-ops.md) | Supervisor, WinSW, kiosk, morgensjekk, installasjon, utrulling | 9 | M2–M3 |
| 13 | [`features.md`](features.md) | Bryterne og steg 11 (farge, Panopto) | 10–11 | M4 |
| – | [`for-studio.md`](for-studio.md) | Rekkefølgen for alt som lages før studioperioden (D-066): capture og nett, skyggemodus, bryterne, tung videoanalyse, farge, sjekkliste | 10–11 | M4 |
| – | [`p10-p14.md`](p10-p14.md) | Forslag 2026-10-24: annen kilde på lufta (feil i dag), opptak til justering, plassjekk, lyd som tilpasser seg økten, rask sjekk før økt | – | M4 og senere |
| – | [`milestones.md`](milestones.md) | Milepæler, issues, arbeidsflyt for GitHub og Vercel | – | – |

## Beslutninger planene foreslår

Disse må godkjennes av produkteier sammen med planene. Når de er godkjent, føres de inn i beslutningsloggen og ADR-ene får ny status.

| ID | Forslag | Hvor |
| --- | --- | --- |
| PL-01 | **ADR-0012 bekreftes:** `atem-bridge` i Node.js 24 LTS med `atem-connection`. Kontrakt mot `core` er JSON over ZeroMQ, så broen kan byttes uten at `core` endres. Endelig etter maskintest av ATEM-modellen (Q7) | `devices-companion-atem.md` |
| PL-02 | **ADR-0014 bekreftes med presisering:** `audio-capture` gjør både innlesing *og* lydanalysen (VAD, nivå, frasegrenser, dempet-sjekk) og sender bare *målinger* til `core`, ikke rå lyd. `core` blir da ren regelkode uten lyd-avhengigheter, og simulatoren og web-simulatoren lager nøyaktig de samme meldingene | `audio.md`, `core.md` |
| PL-03 | **ADR-0013 bekreftes:** trinn 1 (avspilling av ferdige forløp) i M1; trinn 2 (motoren i nettleseren med Pyodide) etter M1 | `sim.md`, `ui.md` |
| PL-04 | `core` er en ren funksjon `step(state, inputs, now) → (state, decisions, commands)` uten I/O. Alt rundt (klokke, buss, enheter) ligger i et tynt skall. Gir I3, deterministiske tester og web-simulator med samme kode | `core.md` |
| PL-05 | **Skyggemodus** er en egen motortilstand: motoren tar alle beslutninger og logger dem, men sender ingen kommandoer. Bygges i M1 som verktøy, men er ikke krav i noen milepæl mens studioet ikke er i bruk (D-049); tas i bruk for nye brytere og oppdateringer når studioet er i drift | `core.md` |
| PL-06 | Videolaget deles i to: **lett** (capture, ruter, content-deteksjon og program-bekreftelse på CPU) i M3, og **tungt** (ansikt, munn, taler-modell på GPU) i M4. Grunnmodus avhenger aldri av GPU | `vision.md` |
| PL-07 | Supervisor og WinSW kommer allerede i M2, fordi studiotesten skal stå i studio i dager uten tilsyn | `supervisor-ops.md` |
| PL-08 | Tuning-verdier for `K`, `H`, `B`, `CT`, `L` per forhåndsvalg (tabell i `core.md`) som startpunkt, til de kan måles mot opptak (Q1–Q2) | `core.md` |

## Oppetid først

Multimediesenteret har sagt at oppetid og at det fungerer er det viktigste, og at studioet står uten tekniker nesten hele tiden. Alle planene følger disse prinsippene, i tillegg til I1–I8:

1. **Sendingen er aldri avhengig av CutCut (I1).** ATEM og Pearl går videre alene. CutCut kan krasje uten at noe faller ut på lufta.
2. **Alt restarter av seg selv.** Hver prosess har hjerteslag; supervisor restarter den med økende pause. Supervisor restartes av Windows (WinSW). PC-en starter selv etter strømbrudd (BIOS + automatisk innlogging). Edge kiosk restartes av Windows tilordnet tilgang.
3. **Tilstanden overlever omstart.** Økt, showvalg, opptaksstatus og brytere ligger i SQLite. `core` er tilbake innen 5 s med samme økt (10.4).
4. **Grunnmodus er liten.** Lyd + regler + Companion + Pearl-status. Alt annet (ansikt og munn, utsnitt, zoom, layouter, AI-tracking) er brytere som kan feile uten at grunnmodus merker det.
5. **Feil vises før de merkes.** Helsesjekker, morgensjekk kl. 07:00, varsel til tekniker utenfor studio ved rødt over 1 min (Q29).
6. **Brukeren ser aldri teknikk.** Touch viser én setning og «Trenger du hjelp?». Gule avvik vises aldri på touch.
7. **Ingen vekst over tid.** Logger roteres, databasen ryddes, minne måles i 72-timerstest og nattlig i simulator-soak.
8. **Endringer bare i servicevindu**, med automatisk tilbakerulling hvis morgensjekken feiler.
