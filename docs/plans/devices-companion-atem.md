# Plan: `devices/companion` og `atem-bridge`

Status: godkjent (D-046) · Milepæl: M2 (lesing og klipping via preview, D-049) og M3 (ISO, Companion-sider) · Spes. 2.2, 5.6, 5.7 (`S5`), 7.1, 7.2, 7.7, 8.4 steg 3, 7, 8, 8.5 (`H-ATEM-*`, `H-COMP-1`); ADR-0004, 0005, 0009, 0012; Q7 · Mapper: `src/cutcut/devices/companion/`, `src/cutcut/devices/atem/`, `bridges/atem/`

**Leveransestatus 2026-10-22:** DA-1–DA-9 er bygget. Maskintesten (DA-5) og klipping via preview i studio (DA-6) gjøres i studioperioden.

## 1. Formål og avgrensning

- **Companion-klienten** trykker knapper på side 10 (preview, layout, TAKE) og skriver `regi_*`-variablene (7.1). Kutt og layouter går alltid hit i drift (ADR-0009).
- **`atem-bridge`** leser hele ATEM-tilstanden (program, preview, tally, SuperSource, makroer, mediaspillere, multiview, opptak og ISO-disk) og kan gjøre direkte kutt som reserve (`S5`), starte og stoppe ISO-opptak (7.7) og kjøre makroer i setup-hjelperen.
- **Avstemming (ADR-0004):** hvert sekund sammenlignes det motoren ønsket med det ATEM viser. Avvik betyr manuelt inngrep (I5); motoren tilpasser seg.

**ADR-0012 bekreftes (PL-01):** Node.js 24 LTS med `atem-connection`, i egen prosess under supervisor.

| Hvorfor Node-broen | Hvordan risikoen holdes nede |
| --- | --- |
| `atem-connection` er det best vedlikeholdte ATEM-biblioteket og brukes av Companion selv | Broen er liten (mål: under 500 linjer), uten logikk; den oversetter bare tilstand og kommandoer |
| Samme bibliotek som Companion: oppfører seg likt mot samme ATEM og fastvare | Versjonen av `atem-connection` låses, og oppdateres sammen med ATEM-fastvaren etter maskintest |
| Python-alternativet (PyATEMMax) er mindre brukt | Kontrakten mot `core` er JSON-meldinger; broen kan byttes uten endringer i `core` |

Node er allerede med i stacken for å bygge UI. Node-kjøretiden pakkes inn i Windows-pakken (ingen global installasjon).

## 2. Grensesnitt

**Bro ↔ core over ZeroMQ (JSON):**

| Retning | Emne | Innhold |
| --- | --- | --- |
| bro → core | `atem.state` | Ved endring + hvert sekund: `program`, `preview`, `transition`, `supersource`, `macros`, `media_players`, `multiview`, `recording`, `iso_disk`, `model`, `firmware` |
| bro → core | `atem.status` | `connected`, `last_error`, `rtt_ms` |
| core → bro | `atem.cmd` | `{id, op: "cut"|"preview"|"run_macro"|"iso_start"|"iso_stop"|"set_input_name", args}`; svar `atem.ack {id, ok, error}` |

**Companion-klient (`httpx`, `127.0.0.1:8000`):**

```python
class CompanionClient(Protocol):
    async def press(self, page: int, row: int, col: int) -> None: ...      # tidsavbrudd 300 ms
    async def set_var(self, name: str, value: str) -> None: ...
    async def get_var(self, name: str) -> str | None: ...                   # cutcut_pages_version
    async def connections(self) -> list[CompanionConnection]: ...           # H-COMP-1
```

Knappekartet (side 10, rad 0–3) ligger i `site/<studio>/equipment/companion_map.yaml`, ikke i koden. `Shot → knapp` slås opp der.

**Kø per enhet med kretsbryter (ADR-0005):** maks én kommando i luften per enhet; ny `SetPreview` erstatter en som ikke er sendt ennå (siste vinner); 3 feil på rad åpner kretsbryteren i 10 s og gir varsel.

## 3. Tilstander og feil

| Situasjon | Gjør |
| --- | --- |
| Companion svarer ikke (tidsavbrudd 300 ms, 3 på rad) | `S5`: direkte kutt via broen; layouter sperres; gult «Reservekutt» |
| Broen mister ATEM | Gjenoppkobler selv (`atem-connection`); `core` gjør ingen kutt, ATEM står på siste bilde; rødt «ATEM» |
| Broen krasjer | Supervisor starter den; `core` venter, ingen kutt imens |
| `cutcut_pages_version` feil | Gult; kutt via Companion tillates ikke før riktig side er importert, reservekutt brukes |
| Makro mangler eller har feil navn (`H-ATEM-3`) | Gult; bryteren `layouts` sperres |
| Operatør trykker på ATEM eller Stream Deck | Avstemming ser avviket; motoren tar det som sannhet og venter 5 s (I5) |
| Companion sin ATEM-tilkobling er nede, men HTTP svarer | Oppdages via `/api/connections`; behandles som Companion nede |

`regi_*`-variablene skrives bare ved endring og maks 5 ganger per sekund, så Companion ikke belastes.

## 4. Avhengigheter

Node 24 LTS, `atem-connection` (MIT), `zeromq` for Node (prebygd for Windows x64) eller, hvis det gir trøbbel, JSON-linjer over lokal TCP bak samme kontrakt. Python: `httpx`. Utstyr: ATEM Television Studio HD8 ISO i studioet (D-053; Q7 delvis), Companion 5.x låst (teknisk referanse), Stream Deck XL.

## 5. Testplan

- Bro: enhetstester med `atem-connection` sin tilstandsmodell (uten ATEM); kontrakttest mot `core` med en falsk bro i Python.
- Companion: falsk Companion i `sim/devices/` (riktige stier, tidsavbrudd, feil); test av kø, siste-vinner og kretsbryter.
- `S5`: Companion dør midt i scenario → neste kutt går via broen.
- Avstemming: falsk ATEM endrer program uten motoren → motoren venter 5 s og loggfører.
- Ytelse: fra `Take` i kjernen til HTTP-kall mot falsk Companion under 20 ms (del av 150 ms-kravet).
- **Maskintester:** `cutcut hwtest atem` (B1–B6: modell og videoformat, multiview mot rutekartet, makroer, Companion og `cutcut_pages_version`, hver preview-knapp lest tilbake fra ATEM, TAKE bare med bekreftelse; `docs/studio/maskintest.md`). Avgjør Q7 og endelig ADR-0012.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| DA-1 | `bridges/atem/` med lesing og `atem.state`; pakket Node | Kontrakttest grønn |
| DA-2 | ATEM-klient i `core` + avstemming | Avviks-test grønn |
| DA-3 | Companion-klient med kø og kretsbryter | Tester mot falsk Companion |
| DA-4 | `regi_*`-variabler | Vises i falsk Companion |
| DA-5 | Maskintestskript ATEM og Companion | Kjørt på test-PC eller i studio, rapport i issue (M2) |
| DA-6 | Klipping via preview + TAKE i `LIVE` | Motoren klipper via preview i studio (spes. 11 steg 5, M2) |
| DA-7 | `S5` reservekutt og makrosjekk ved oppstart | Tester grønne |
| DA-8 | ISO-opptak fra teknikervinduet (7.7) | Start/stopp/status mot falsk og ekte ATEM. Gjort mot falsk ATEM og fiksturen; mot ekte ATEM i maskintesten. Knappen på Companion side 11 venter på at handlingen i ATEM-modulen er prøvd i studio |
| DA-9 | Companion-eksport: `cutcut-side-10`, `cutcut-side-11` og `cutcut-variabler` (`.companionconfig`, laget med `cutcut companion-pages`) | Importert i studio, versjon leses |

## 7. Åpne spørsmål

- Q7: ATEM-modell og om `atem-connection` og Companion støtter G2 fullt (tilstand, makroer, SuperSource, opptak). Fant ingen bekreftelse i offentlige kilder per 21.10.2026; maskintesten avgjør.
- Q35: skal Companion kjøre som Windows-tjeneste (uten skrivebord), eller i kiosk-brukerens økt? Påvirker automatisk omstart.
- Q9: IP-plan og VLAN.
