# Plan: `api` – REST, WebSocket og roller

Status: godkjent (D-046) · Milepæl: M1 · Spes. 10.1, 10.2, 12.4, 12.5; D-036, D-045 · Mappe: `src/cutcut/api/`

**Leveransestatus 2026-10-22:** A-1–A-6 er bygget.

## 1. Formål og avgrensning

Ett API for touch, tekniker, Companion side 11 og ekstern overvåkning. Alle endringer som påvirker sendingen logges med hvem (rolle og bruker) og når. Alle stier fra 10.1 og 10.2 implementeres, pluss `POST /touch/step` (D-036) og `POST /touch/again` (U-5), `POST /rules/overrides` (U-8), og eksportene `GET /log.csv`, `/sessions`, `/sessions.csv`, `/debug-package` (A-6).

## 2. Grensesnitt

- FastAPI i `core`-prosessen, uvicorn med én arbeider, port 8080 (10.1). Statiske filer for `touch` og `tech` serveres fra samme server.
- OpenAPI genereres til `docs/reference/openapi.json`; TypeScript-typer genereres derfra (`ui/packages/client`). CI feiler ved avvik.
- **WebSocket `/ws`:** klienten abonnerer på emner (`state`, `meters`, `decision`, `vision`, `health`, `alert`, `session`, `touch`). Touch abonnerer bare på det den viser. Første melding er full tilstand, deretter bare endringer med `seq`. Mangler klienten en `seq`, ber den om full tilstand på nytt.
- **Takt:** tilstand 10 Hz, målere 20 Hz som én kompakt liste (spes. 10.2), vision 5 Hz, resten ved endring.
- Kommandoer over WebSocket er de samme som REST og går gjennom samme kode.
- **Idempotens:** `POST /recording` og `POST /session` tar `request_id`; samme forespørsel to ganger gir samme svar. Start og stopp fra touch og tekniker samtidig avgjøres av motoren, aldri av skjermene (10.4).

**Roller (12.4, D-045):**

| Rolle | Hvordan | Får |
| --- | --- | --- |
| `touch` | Bare fra `127.0.0.1` | Økt, showvalg, opptak start/stopp, hjelp, logg ut |
| `operator` | Ansattkort på touch (hold logo 5 s) eller brukernavn + passord/PIN i teknikervinduet; må stå på teknikerlisten i `site/` | Oversikt, Kameraer, Opptak, Helse, Logg; AUTO, LÅS, kutt, preview, forhåndsvalg |
| `admin` | Som operator, men på admin-listen | I tillegg Regi, Oppsett, Innstillinger, setup-stier |

Informasjonskapsel `HttpOnly`, `SameSite=Strict`, 8 timer, utlogging ved inaktivitet. Kortnummer finnes ikke i API-et (I8).

## 3. Tilstander og feil

- Kommando som ikke er lov i tilstanden (for eksempel `DELETE /session` under opptak) gir `409` med norsk forklaring.
- Ugyldig data gir `422` med feltvise feil.
- Treg klient på WebSocket: meldinger slås sammen (siste tilstand vinner), klienten kobles fra hvis køen passerer 2 s; motoren påvirkes aldri.
- API-et kan aldri blokkere motoren: alle handlere er asynkrone og kort-levde; tunge jobber (eksport) går i egen tråd.

## 4. Avhengigheter

`fastapi`, `uvicorn`, `common`, `core`. Ingen nye lisenser.

## 5. Testplan

- Kontraktstester for hver sti med rollene (riktig rolle slipper inn, feil rolle får `403`).
- WebSocket: full tilstand ved tilkobling, diff-sekvens, gjenoppkobling, treg klient.
- Samtidig start/stopp fra to klienter gir én tilstand (10.4).
- I8-søk i alle API-svar etter en simulert økt.
- `GET /api/health` har stabilt format for Multimediesenteret-overvåkning.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| A-1 | App, statiske filer, `GET /health`, `GET /state`, OpenAPI til `docs/reference/` | CI sjekker generert fil |
| A-2 | WebSocket med emner, diff og `seq` | Klient-test grønn |
| A-3 | Økt- og touch-stier, opptak, hjelp | Touch-flyt via API i simulator |
| A-4 | Overstyring: AUTO, LÅS, kutt, preview, brytere, content | Regeltester for overstyring via API |
| A-5 | Roller, innlogging, revisjonslogg | Rolle-tester grønne |
| A-6 | Shows, logg med eksport (CSV og feilsøkingspakke, 12.1) | Eksport inneholder ikke hemmeligheter |

Setup- og helse-stiene kommer i M3 (`setup-health.md`).

## 7. Åpne spørsmål

- Q33: hvem står på teknikerlisten og admin-listen, og skal PIN brukes som reserve?
- 12.4 sier HTTPS med sertifikat fra IT-avdelingen for teknikervindu fra andre maskiner. Trengs det i første versjon, eller er teknikervinduet bare på regi-PC-en til M3? (Q9)
