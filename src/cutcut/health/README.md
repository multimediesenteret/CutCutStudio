# `cutcut.health` – helsesjekkene

Spesifikasjonen 8.5 og `docs/plans/setup-health.md`. Helsesjekkene sjekker hele tiden at utstyret er tilkoblet, virker og står som avtalt. Feil skal oppdages og meldes før de merkes på lufta.

| Fil | Innhold |
| --- | --- |
| `model.py` | `CheckResult`: ID, status (grønn, gul, rød), verdi, forventet verdi, melding, tid, og hvor lenge avviket har vart |
| `engine.py` | `HealthEngine` kjører hver sjekk med eget intervall og egen tidsgrense |
| `checks.py` | Katalogen, bygd av små lesefunksjoner så den virker likt i studio og simulator (tabellen under) |

Slik oppfører `HealthEngine` seg:
- En sjekk som henger eller feiler, blir gul («sjekken virker ikke»). Den forsinker aldri motoren.
- Et avvik åpnes med en gang, men lukkes først etter 30 s grønt (hysterese). En enhet som går av og på, gir derfor ett avvik.
- Hvert avvik logges én gang ved start og én gang ved slutt.

| ID | Sjekker | Hvert | Avvik |
| --- | --- | --- | --- |
| `H-AUD-1` | Målinger fra `audio-capture` kommer | 1 s | Rødt etter 2 s |
| `H-PROC-<prosess>` | Prosessene, fra supervisor (SO-1). Legges til når supervisor melder dem | 1 s | Gult: nede eller over 5 omstarter på 10 min |
| `H-PROC-supervisor` | Supervisor selv sender status | 2 s | Gult etter 10 s stille |
| `H-PC-1`, `-2`, `-3` | Disk der data ligger, minne, CPU | 30 s | Gult under 20 GB / over 90 % / over 85 %; rødt under 2 GB disk |
| `H-NET-1` | Et nettverkskort på studio-switchen, i samme nett som ATEM (D-064) | 10 s | Rødt |
| `H-NET-2` | Et nettverkskort ut (campusnettet) for e-post og oppdateringer | 30 s | Gult; studioet virker uten |
| `H-PRL-1` | Pearl svarer, har ingen feil, har plass | 5 s | Rødt (også for brukeren) når Pearl ikke svarer eller har under 15 min igjen; gult under 60 min |
| `H-ATEM-1` | Program og preview kan leses | 1 s | Rødt (også for brukeren) etter 15 s oppstart |
| `H-ATEM-3` | Layoutmakroene (7.2) finnes i ATEM med riktig navn (`cutcut.devices.atem.macros`) | 5 min, og i morgensjekken | Gult. Layout-bryteren kan ikke slås på |
| `H-VID-1` | Videolaget får bilder, minst 10 per sekund. Legges til når videolaget melder seg | 2 s | Gult. Motoren klipper på lyd |
| `H-VID-3` | Programruta viser det ATEM sier er på program (VI-3) | 2 s | Gult etter 3 s uenighet. Sjekk rutekartet |
| `H-CAM-C1`… | Hvert PTZ-kamera svarer under 200 ms og står i manuell hvitbalanse og eksponering (CA-6) | 10 s | Gult: bildet kommer fortsatt, men CutCut kan ikke styre kameraet |
| `H-CAM-MOVE` | Ingen kameraer har flyttet seg uten at CutCut ba om det og uten AI-tracking (posisjonen leses hvert 2. s) | 2 s | Rødt i 10 s etter at det skjedde |
| `H-VARSEL-1` | Varsler kan sendes på e-post: mottaker og SMTP-relé er satt, og siste e-post gikk (HS-3) | 30 s | Gult: ingen hører om rødt utenfor studio |
| `H-ATEM-2` | ATEM som i fasiten: videoformat, inngangsnavn og AUX-utgangene (HDMI ut 2). Fasiten lagres under Oppsett → ATEM | 30 s | Gult ved avvik; rødt når multiview-sjekken fant at multiviewen er endret |
| `H-ATEM-4` | ATEMs ISO-disk: finnes, formatert, ledig tid | 10 s | Gult under 60 min; rødt når showet skal ta opp ISO og disken mangler eller er full |
| `H-VID-2` | Capture-kortet gir hele multiviewen (1920 × 1080) og videolaget holder følge | 5 s | Gult |
| `H-COMP-1` | Companions HTTP-API og `cutcut_pages_version` | 5 s | Rødt: svarer ikke (`S5` tar over), sidene mangler eller har feil versjon |

Lagringen på Pearl regnes om til minutter med 20 Mbit/s til bitraten er målt i maskintesten (DA-5). Dette kommer senere:
- `H-PC` for GPU-temperatur og klokke (NTP) kommer med test-PC-en (Q8, Q20).
- `H-AUD-2` (støy i stillhet) trenger støygulvet i `baseline.yaml` fra setup steg 5.
- `H-PRL-2`, opptak som stopper av seg selv, er en hendelse og varsles av økta (I7).

I studioet blir et åpent avvik et varsel i teknikervinduet: rødt gir feil, gult gir advarsel. Når avviket lukkes, forsvinner varselet av seg selv.

Touch-skjermen leser sjekkene direkte, ikke varslene. Den sperrer start bare mens en sjekk merket for brukeren (`for_user`: Pearl og ATEM) er rød. Teknikerens avvik kan stå åpent i 30 s etter at feilen er rettet, men brukeren blir ikke holdt tilbake så lenge. Lyd som forsvinner, får brukeren beskjed om fra motoren (`S4`).

`GET /api/health` (samlet status for Multimediesenterets overvåkning) og `GET /api/health/checks` krever ikke innlogging.

**Morgensjekk (HS-4):** hele katalogen og multiview-sjekken (D-056) kjøres 20 s etter oppstart og hver morgen kl. 07:00 etter PC-ens klokke. Starter studioet etter 07:00, teller oppstartssjekken som dagens morgensjekk. Teknikeren kan også trykke «Kjør alle nå» (`POST /api/health/morning-check`).
- Hvileskjermen viser resultatet som en liten prikk: grønn, eller gul når teknikeren har noe å se på. Brukeren får aldri detaljene.
- Teknikervinduet viser hvilke sjekker som ikke var grønne.

Sjekker trykker aldri knapper og flytter aldri noe. Slikt finnes bare i setup-hjelperen.

**Varsling (HS-3, `notify.py`):** av som standard (`alerts.enabled`), slås på under Innstillinger → Varsling. Når det er på: rødt i over ett minutt gir én e-post, og «OK igjen» når saken lukkes. Et opptak som ikke starter eller stopper av seg selv (`H-PRL-1`, `H-PRL-2`), gir e-post med en gang. Høyst ti i timen. Sendes fra helseløkka i en egen tråd, aldri fra motorens tikk. Mottakere og SMTP-relé står i `alerts` i `devices.yaml` og kan endres under Innstillinger → Varsling (D-058). Companion-variabelen `regi_health` følger verste åpne sak (`ok`, `warn`, `error`).

`H-CARD-1` (kortleseren) og `H-CARD-2` (kort-API) kommer med kortinnloggingen (SE-4, SE-5, M4). Studioet bruker Start-knappen til appen har vært testet en stund (D-057), så de ville bare vært gule.

**Setup-hjelperen (HS-5, HS-6, `cutcut/setup/steps.py`):** ti steg som data i `config/defaults/setup/`. Hvert steg peker på helsesjekkene som viser resultatet (`H-CAM-C*` er lov). «Sjekk steget» kjører dem med en gang (`HealthEngine.run_matching`); de er de samme sjekkene som i drift og bare leser. «Godkjenn steget» lagres med tekniker og tid i databasen (`setup.approvals`) og logges; et steg med rød sjekk kan ikke godkjennes, og en godkjenning skjuler aldri en sjekk som er rød senere. «Fiks for meg» finnes bare der det er trygt (nå: ATEM-inngangsnavn i steg 3), krever bekreftelse og er sperret under opptak. API: `GET /api/setup/steps`, `POST /api/setup/steps/{steg}/check|fix|approve`.

**Fargematching (P8, `cutcut/setup/color.py`, spes. 6.4):** setup-steg 4 finner gråkortet i hver kamerarute (jevne, fargeløse blokker, verken mørke eller utbrent), måler rødt mot blått og lysstyrke, og justerer hvitbalanse og gain mot referansekameraet i høyst fem runder til forskjellen er under 3 %. Kamerakommandoene går gjennom kameravakten, så et kamera på lufta hoppes over. Siste resultat lagres i appen (`setup.color`).
