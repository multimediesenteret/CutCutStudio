# Plan: `supervisor` og drift – tjenester, kiosk, installasjon, utrulling

Status: godkjent (D-046) · Milepæl: grunnversjon i M2 (PL-07), full drift i M3 · Spes. 2.6, 3, 8.2 (kiosk), 9 (alle), 10.4, 12.2–12.4; D-019, D-042; ADR-0001, 0003, 0007 · Mapper: `src/cutcut/supervisor/`, `installer/`, `tools/`

## 1. Formål og avgrensning

Det som gjør at CutCut står i måneder uten tekniker: prosesser som restartes, en PC som starter selv, en touch-skjerm som alltid kommer tilbake, og oppdateringer som ruller tilbake av seg selv.

## 2. Grensesnitt og oppbygging

**Lag for lag – hvem passer på hvem:**

| Lag | Passes på av | Hvordan |
| --- | --- | --- |
| PC-en | BIOS + UPS | «Power on after AC loss», UPS med ryddig nedstenging, automatisk innlogging for kiosk-brukeren (Q31) |
| Windows-tjenesten `CutCut` (supervisor) | Windows tjenestebehandler via WinSW | Automatisk start, omstart ved krasj (5 s, 10 s, 30 s) |
| `core`, `audio-capture`, `vision`, `stt`, `atem-bridge` | supervisor | Hjerteslag hvert sekund; 3 tapte = drep og start; økende pause (1, 2, 5, 10, 30 s) og varsel hvis en prosess starter mer enn 5 ganger på 10 min |
| Companion | egen WinSW-tjeneste (Q35) | Automatisk start og omstart; låst versjon |
| Touch (Edge kiosk) | Windows tilordnet tilgang + `kiosk-vakt` | Tilordnet tilgang starter Edge på nytt; vakten (liten oppgave i kiosk-brukerens økt, startet av Oppgaveplanlegger ved innlogging) laster siden på nytt hvis touch-hjerteslaget stopper i 10 s |

Tjenester kan ikke vise vinduer på skjermen (Windows' økt 0). Derfor kjører alt som har skjerm (Edge kiosk, kiosk-vakt) i kiosk-brukerens økt, og alt annet som tjenester.

**Supervisor:** liten Python-prosess uten avhengigheter utover `common`. Leser prosesslisten fra konfig, starter prosessene med riktig prioritet (`core` og `audio-capture` høy, `vision` normal, `stt` lav), samler hjerteslag over bussen, og rapporterer `H-PROC-*`. Den er bevisst enkel: ingen regler, ingen nett utover lokal buss.

**På regi-PC-en (12.2):**

```text
C:\CutCut\
  versions\0.2.0\  versions\0.3.0\  # hver med egen Python (python-build-standalone via uv), Node, UI og bro
  current  → versions\0.3.0\        # katalog-lenke; tjenesten starter alltid denne
  site\                             # studio-oppsett (git)
  data\  cutcut.db  logs\  exports\  backup\
  models\
```

**Installasjon og utrulling (12.3):**

- CI bygger én zip per tag: Python, avhengigheter, bygget UI, `atem-bridge` med Node, WinSW-filer, SBOM og SHA-256.
- `install.ps1` (kjøres av tekniker i servicevindu): sjekker sjekksum → pakker ut ved siden av → prøver den nye versjonen mot studio-oppsettet → bytter `current` → restarter tjenesten → venter til den nye versjonen svarer på `/api/health`. Feiler den: `current` tilbake og tjenesten restartes. Tre siste versjoner beholdes. Konfigmigrering kommer med første `schema_version` 2; i dag leser den nye versjonen oppsettet slik det er (gjort, SO-4).
- Ingen automatisk oppdatering av CutCut, Windows, drivere eller fastvare utenfor servicevinduet.

**Windows-oppsett (9.2) som skript:** `tools/windows/setup-pc.ps1` gjør alt som kan gjøres lokalt (strømplan, USB-strømsparing av, aktive timer, kiosk-bruker, brannmurregel for 8080, tjenester) og skriver rapport. Skriptet kan kjøres på nytt og endrer bare det som avviker. Om det er lov avhenger av Q8 (sentralt administrert PC).

**Rydding:** logger 30 dager, økthistorikk etter Q10, eksporter 30 dager, nattlig kopi av `cutcut.db` til `data\backup\` (7 kopier). Diskplass under 10 % gir gult; under 5 % slettes eldste eksporter først, aldri opptak.

**Nattlig vedlikehold (forslag, Q30):** kl. 04:00 hvis ingen økt er aktiv: touch lastes på nytt og `stt`/`vision` restartes. `core` og `audio-capture` restartes ikke uten grunn. Ingen omstart av PC-en uten servicevindu.

## 3. Tilstander og feil

Alle radene i spes. 9.1 er krav og testes. I tillegg:

| Situasjon | Gjør |
| --- | --- |
| En prosess restarter i løkke | Etter 5 omstarter på 10 min: venter 5 min mellom forsøk, rødt varsel; `core` fortsetter uten den |
| `core` selv restarter i løkke | Supervisor starter forrige versjon av konfigen; hvis det ikke hjelper, rødt varsel og touch viser «Studioet er ute av drift – kontakt …» |
| Strømbrudd | UPS holder; ved lavt batteri ryddig nedstenging; PC-en starter selv når strømmen kommer; morgensjekk kjøres |
| Windows har installert oppdatering og vil starte på nytt | Aktive timer og utsatt omstart; omstart aldri under økt (Q8, Q30) |

## 4. Avhengigheter

WinSW (MIT) 2.x/3.x, PowerShell 5.1+, `uv` og python-build-standalone, Node 24 LTS (pakket). Windows 11 Pro med tilordnet tilgang. UPS med USB-tilkobling (Q31).

## 5. Testplan

- Drapstester (10.4): drep hver prosess under scenario; `core` tilbake innen 5 s med samme økt; videolaget dør uten at kuttingen stopper.
- Omstartsløkke og backoff testes med en prosess som krasjer med vilje.
- Installasjon: installer N, så N+1 med feil som får morgensjekken til å feile → automatisk tilbake til N.
- **72-timerstest** (10.4) i studio (eller på test-PC-en) med motoren i drift: minne (RSS per prosess hvert 10. min), håndtak, tilkoblinger, logger. Grense: under 5 % vekst etter første time.
- Nattlig soak i CI på Linux mot simulatoren (8 timer simulert drift på falsk klokke), og på Windows-testmaskin hvis den finnes (Q28).
- Windows-oppsettskriptet testes i en Windows-VM (eller `windows-latest`) i tørrkjøringsmodus.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| SO-1 | Supervisor med hjerteslag, backoff og `H-PROC-*` (Linux og Windows) | Drapstest grønn (M2) |
| SO-2 | WinSW-definisjoner for `CutCut` og Companion | Starter etter omstart av Windows i studio (M2) |
| SO-3 | Pakke-bygg i CI ved tag, SBOM og sjekksum | Zip lastes opp til GitHub-release |
| SO-4 | `install.ps1` med tilbakerulling | Rulletest grønn |
| SO-5 | `setup-pc.ps1` for Windows-oppsett (9.2) | Rapport viser alle punkter grønne |
| SO-6 | Kiosk: bruker, tilordnet tilgang, kiosk-vakt | Touch kommer tilbake etter at Edge drepes |
| SO-7 | Rydding, nattlig backup av database | Disk stabil i 72-timerstest |
| SO-8 | 72-timerstest i studio | Kriteriet i 10.4 oppfylt (M3) |
| SO-9 | Runbooks i `docs/runbooks/`: «Ingen lyd», «Touch er svart», «Opptak startet ikke», «Kamera beveger seg ikke», «Etter strømbrudd» | Gjennomgått med tekniker |

## 7. Åpne spørsmål

- Q8: er regi-PC-en sentralt administrert, og kan kiosk, tjenester, strømplan og oppdateringstider settes lokalt?
- Q28: finnes en Windows-maskin vi kan teste på før studio (gjerne lik regi-PC-en)?
- Q30: servicevindu og åpningstider.
- Q31: UPS, «power on after AC loss», og er automatisk innlogging for kiosk-brukeren tillatt?
- Q35: Companion som tjeneste.
