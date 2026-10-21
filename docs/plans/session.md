# Plan: `session` og `devices/pearl` – kort, økter, show-typer, opptak

Status: godkjent (D-046) · Milepæl: M2 (Pearl status, start og stopp) og M3 (kort, NTNU-API) · Spes. 2.5, 5.1 (`A`), 7.4, 7.5, 7.6 (forberedt), 8.1–8.2, 9.1, 10.4; D-013, D-014, D-016, D-036, D-043; ADR-0008; I6, I7, I8 · Mapper: `src/cutcut/session/`, `src/cutcut/devices/pearl/`

## 1. Formål og avgrensning

Hele brukerreisen fra kort til ferdig opptak: kortleser, oppslag i NTNU-API, økt, showvalg (antall personer, video eller kun lyd), opptak i Pearl, utlogging. Panopto er bare forberedt i datamodell og GUI (7.6); publisering bygges i M4 (`features.md`).

## 2. Grensesnitt

**Kortleser (ADR-0008):** `pyserial` mot TWN3 i virtuell COM-port (USB-ID `09D8:0320`). Porten finnes automatisk på USB-ID, ikke på COM-nummer (nummeret kan endre seg etter Windows-oppdatering). UID leses, brukes til ett oppslag og overskrives i minnet; den sendes aldri til logg, database, buss eller API (I8).

**NTNU-API:** `httpx` mot `tia/v4/autorisasjon/mifareid`, tjenestenøkkel fra `keyring`, 3 s tidsavbrudd, ingen hurtigbuffer av kortnummer. Svar → `User(username, display_name)`. Svarformat er ukjent (Q4); adapteren skrives mot en falsk tjeneste og et antatt format, og byttes når eksempelsvar finnes.

**Økt (7.5):** én aktiv økt; modell som i spesifikasjonen. Tilstander:

```text
IDLE ──kort/tekniker──► READY ──Start──► COUNTDOWN ──3-2-1──► RECORDING ──hold Avslutt 2 s──► DONE ──30 s / Ferdig──► IDLE
  ▲                        │ 3 min uten trykk                                                    │ Nytt opptak
  └────────────────────────┴─────────────────────────────────────────────────────────────────────┘ (til READY)
```

- Utlogging aldri under opptak (D-043). Nytt kort under opptak avvises; samme kort igjen gjør ingenting.
- `show` fra touch: `guests` og `video`; `type` hentes fra studio-oppsettet (D-036). Kun lyd gir modus `A`.
- Touch-steget er en del av økt-tilstanden og sendes på `touch`-emnet. Tekniker kan flytte det (`POST /touch/step`).

**Pearl (`devices/pearl/`):** REST v2.0 med Basic-autentisering (passord i `keyring`), polling som i 7.4 (status 2 s, innganger 5 s, lagring og system 30 s). `start`/`stop` er idempotente: motoren leser status før og etter, og «Starter…» vises til Pearl sier `started` (12.5). `started_by` = `touch`, `tech` eller `streamdeck` (det siste oppdages når Pearl starter uten at motoren ba om det).

## 3. Tilstander og feil

| Situasjon | Gjør | Brukeren ser |
| --- | --- | --- |
| Kort ikke gjenkjent | Tilbake til hvile etter 5 s | «Kortet ble ikke gjenkjent – prøv igjen» |
| NTNU-API svarer ikke | Gult `H-NTNU-1`; tekniker kan godkjenne «Start uten innlogging», opptaket merkes `ukjent bruker` | «Kortet kunne ikke sjekkes nå» + Hjelp |
| Kortleser frakoblet | Gult `H-CARD-1`; prøver å åpne porten hvert 10. sekund | «Kortleser mangler – trykk Hjelp» |
| Pearl svarer ikke ved Start | Ingen opptak startes; rødt; «Start» går tilbake etter 10 s med feiltekst | «Opptaket startet ikke. Teknikeren er varslet.» |
| Pearl stopper uten at noen trykket | Rødt med lyd innen 5 s (10.4); prøver **ikke** å starte selv (I7) | «Noe er galt med opptaket – trykk Hjelp» |
| Lite lagring (under 60 min) | Gult til tekniker; før Start: rødt hvis under 20 min (forslag) | Bare ved rødt |
| `core` restarter under opptak | Økten lastes fra SQLite; Pearl tar opp videre (I1); skjermene viser «Kobler til igjen» i maks 5 s | Kort blink |

## 4. Avhengigheter

`pyserial`, `httpx`, `keyring`. Utstyr: ELATEC TWN3 MIFARE (konfigurert med TWNConfig som i Crestron-studioene), Pearl Nexus fastvare ≥ 4.24.1, NTNU-API-nøkkel (Q4).

## 5. Testplan

- Tilstandsmaskin for økt: alle overganger, inkludert avvisning av nytt kort under opptak og automatisk utlogging.
- **I8-test i CI:** hele flyten med testkortets UID; søk etter UID-en (hex, omvendt hex, desimal) i logger, SQLite, bussopptak og API-svar skal gi null treff.
- Falsk Pearl: start/stopp, `starting` som henger, `error`, stopp uten trykk, lite lagring.
- Samtidig start fra touch og tekniker gir ett opptak; stopp fra én side kan ikke «vinnes» av den andre (10.4).
- Kun lyd (`A`): ingen kamerabevegelser, mediaspiller-knappen trykkes, opptak som vanlig.
- **Maskintester:** `tools/hw-test/pearl.py` (fastvare, opptaker-ID, 5 s testopptak, status mot Pearl sitt eget grensesnitt) og `tools/hw-test/twn3.py` (port, testkort gir samme hex som Crestron; UID skrives bare maskert i rapporten).

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| SE-1 | Økt-modell og tilstandsmaskin mot simulator | Touch-flyt i Playwright grønn (M1) |
| SE-2 | Pearl-klient: status, innganger, lagring, system | Pearl-status vises i teknikervinduet på test-PC/studio (M2) |
| SE-3 | Pearl start/stopp, idempotent, «Starter…» | Tester grønne; maskintest (M2) |
| SE-4 | Kortleser med automatisk portvalg og I8-test | I8-test grønn i CI |
| SE-5 | NTNU-API-adapter (falsk + ekte bak samme grensesnitt) | Kort → «Velkommen» under 2 s mot falsk tjeneste; ekte når Q4 er besvart |
| SE-6 | Show-typer (`show_types.yaml`) og Kun lyd | Kun lyd-test grønn |
| SE-7 | Panopto-felt i modell og GUI (bare visning) | Vises på ferdig-skjermen som «forberedt» |

## 7. Åpne spørsmål

- Q4: NTNU-API-nøkkel, svarformat, kortformat (hex og byte-rekkefølge som Crestron).
- Q10: lagringstid for brukernavn og økthistorikk.
- Q17: hvor lenge opptak skal ligge på Pearl og ATEM-disk.
- Q5: Panopto (M4).
