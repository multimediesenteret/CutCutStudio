# `cutcut.app` – studioet som én tjeneste

`Studio` samler motor og skall, økt og touch-flyt, opptaker (Pearl), varsler og live-data for skjermene. All tilstand ligger her, ikke i skjermene (12.5). Samme klasse kjører i studio og i simulatoren; bare utstyret er ulikt (`StudioDeps`).

| Fil | Innhold |
| --- | --- |
| `studio.py` | `Studio`: tikk, kommandoer med revisjonslogg, tilstand for skjermene, live endring av forhåndsvalg, brytere og finjustering som overlever omstart (ADR-0011), økthistorikk |
| `state.py` | Typede modeller for tilstanden og live-meldingene (`StudioState`, `Meter`, `LiveMessage`). De står i `docs/reference/openapi.json`, og skjermenes typer genereres derfra |
| `core.py` | `cutcut core`: samme `Studio` koblet til ekte utstyr – Companion (med atem-bridge som reservevei), ATEM via bussen, Pearl, lyd, PTZ-kameraene (`CameraService`) og videolaget over bussen (`vision.want`, `vision.map`). `core` binder bussen (5560 inn, 5561 ut). Starter selv om noe utstyr mangler |
| `devices.py` | Utstyrsadresser som kan endres i teknikervinduet |
| `maintenance.py` | Nattlig vedlikehold (SO-7): gamle rader slettes etter oppbevaringstiden, og en konsistent kopi av `cutcut.db` legges i `data\backup\` (7 beholdes). Kl. 03–05, aldri under en økt; har PC-en vært av om natten, tas kopien ved første rolige stund |
| `export.py` | CSV av logg og økter, og feilsøkingspakken (zip uten hemmeligheter, personliste eller kortnummer) |
| `setup_file.py` | «Lagre oppsett» og «Hent oppsett» (D-060): alt som er lagt inn i appen (adresser, teknikere, varsling, rutekart, innlogging, farge) som én YAML uten PIN eller passord. Kopi i `data\oppsett\` ved hver endring (20 beholdes) |
| `quickcheck.py` | «Sjekk dagens oppsett» (P14): Helse, multiview, navnerunde (mikrofon hørt og oppe, munn i eget kamera, med plassjekken på 1,5 s per person) og valgfritt farge med gråkort (bare målt). Rapporten lagres i loggen og som `quick_check.last`. API: `GET`/`POST /api/quick-check` |
| `seatcheck.py` | Plassjekk (P12): under nedtellingen og de første 2 minuttene sammenlignes hvem som snakker alene med hvilket kamerabilde som viser en munn som beveger seg. Feil plass, bytte og tom plass. Bryteren `seat_check` (skygge som standard: bare logget). «Bytt i CutCut» (`POST /api/seat-check`) gir personen det andre kameraet resten av økten |
| `debugrec.py` | Feilsøkingsmodus: tar opp alt som kommer inn til motoren, hver beslutning, hvert ønske til utstyret og tiden hvert Companion-kall tok, i `data\debug\` (gzip, én fil per time, 7 dager). Slås på under Helse for 1–72 timer og av selv; overlever omstart (`debug.until`). API: `GET`/`PUT /api/debug` |
| `hub.py` | Fordeling av live-meldinger til skjermene, med begrenset kø per klient |

**Innlogging** (`login_mode`, Innstillinger → Innlogging): `open` er Start-knappen («Gjest») og standard i studio; `card` er kortinnlogging, som simulatoren bruker (D-057).

Antall personer på klar-skjermen velger show-oppsettet med det antallet deltakere fra `site/<studio>/shows/`.
