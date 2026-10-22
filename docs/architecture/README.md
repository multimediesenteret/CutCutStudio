# Arkitektur

Status: M1 (simulator). Oppdateres når en prosess eller dataflyt endres. Tegningene er Mermaid og vises direkte på GitHub.

Kildene er spesifikasjonen (seksjon 3, 10 og 12), ADR-0001–0014 og planene i `docs/plans/`. Regel-ID-ene står i `docs/reference/rules.md`.

## 1. Prosesser i studio (mål for M2–M3)

Alt kjører på én Windows-PC (ADR-0001). Sendingen går gjennom ATEM og Pearl og er aldri avhengig av CutCut (I1): stopper CutCut, står siste bilde, og opptaket fortsetter.

```mermaid
flowchart LR
  subgraph PC["Regi-PC (Windows 11)"]
    direction LR
    SUP["supervisor<br/>(WinSW-tjeneste)"]
    AUD["audio-capture<br/>ASIO, VAD, nivå"]
    VIS["vision<br/>multiview, content"]
    STT["stt<br/>live tekst (bryter)"]
    CORE["core<br/>regimotor + API :8080"]
    BRIDGE["atem-bridge<br/>(Node, ADR-0012)"]
    COMP["Companion<br/>(egen tjeneste)"]
    DB[("SQLite WAL<br/>data/cutcut.db")]
    LOGS[["JSON-linjer<br/>data/logs/"]]
  end
  RODE["RØDECaster Pro II<br/>USB 1 multitrack"] --> AUD
  ATEM["ATEM Television Studio HD8 ISO"] -- multiview HDMI --> VIS
  AUD -- "målinger 50 Hz<br/>ZeroMQ PUB→:5560" --> CORE
  VIS -- "fliser, content" --> CORE
  STT -- tekst --> CORE
  CORE -- "kutt, preview<br/>(HTTP)" --> COMP
  COMP --> ATEM
  BRIDGE -- "tilbakelesing PGM/PVW" --> CORE
  ATEM <--> BRIDGE
  CORE -- "start/stopp, status" --> PEARL["Epiphan Pearl Nexus"]
  CORE --- DB
  CORE --- LOGS
  SUP -. "starter, hjerteslag, omstart" .-> AUD & VIS & STT & CORE & BRIDGE
  CORE -- "HTTP + WebSocket" --> TOUCH["Touch-skjerm<br/>(Edge kiosk)"]
  CORE -- "HTTP + WebSocket" --> TECH["Teknikervindu"]
  CARD["Kortleser"] --> CORE
  CORE -- "oppslag (bare brukernavn)" --> Multimediesenteret["kort-API"]
```

| Prosess | Ansvar | Kan feile uten at grunnmodus stopper? |
| --- | --- | --- |
| `core` | Regimotor, økt, API, lagring, varsler | Nei – men sendingen går videre (I1), og `core` er tilbake innen 5 s med samme økt |
| `audio-capture` | Leser mic-ene, sender målinger (ikke lyd) (ADR-0014, PL-02) | Nei – uten lyd går motoren til fugleperspektiv (`S4`) |
| `vision` | Multiview: content, programbekreftelse, senere ansikt og munn | Ja |
| `stt` | Live tekst | Ja |
| `atem-bridge` | Tilbakelesing og makrosjekk mot ATEM | Ja (motoren stoler da på Companion-kvittering) |
| `supervisor` | Starter alt, ser hjerteslag, restarter med økende pause | Ja (Windows restarter den) |

## 2. Slik det kjører i M1 (`uv run cutcut sim`)

I M1 kjører alt i én prosess, med falske enheter. Det er nøyaktig den samme `Studio`-klassen og den samme motoren som i studio; bare `StudioDeps` er ulik.

```mermaid
flowchart LR
  subgraph SIM["cutcut sim (én prosess)"]
    VOICES["Voices / Conversation<br/>syntetisk tale"] --> RT
    FAKES["FakeAtem · FakePearl<br/>FakeCardReader · FakeCardApi"] --> RT
    RT["CoreRuntime<br/>tikk hvert 30. ms"] --> ENG["Engine.step()<br/>ren funksjon (I3)"]
    ENG --> RT
    RT -- intents --> FAKES
    STUDIO["Studio<br/>økt, touch, varsler"] --> RT
    STUDIO --> HUB["Hub<br/>live-meldinger"]
    API["FastAPI :8080<br/>REST + /ws"] --> STUDIO
    HUB --> API
  end
  API --> UI["ui/dist: /touch/ og /tech/"]
  CTRL["/api/sim/*<br/>snakk, slide, kort, feil"] --> SIM
```

## 3. Fra lyd til kutt

Motoren er en ren funksjon `step(inputs) → resultat` (PL-04). Alt med tid, I/O og enheter ligger i skallet (`CoreRuntime`). Hver beslutning logges med regel-ID og `correlation_id` (I4).

```mermaid
sequenceDiagram
  autonumber
  participant A as audio-capture
  participant R as CoreRuntime (30 ms)
  participant E as Engine.step
  participant X as Executor (Companion)
  participant B as atem-bridge
  participant L as Logg / SQLite
  A->>R: MicFrame (VAD, nivå, dominans)
  R->>E: Inputs (mics, fliser, content, kommandoer, tilbakelesing)
  E-->>R: Intents (SetPreview / Take) + Decision(regel-ID)
  R->>L: Decision med correlation_id (I4)
  R->>X: SetPreview(kandidat)  — PV1: minst 300 ms på preview
  Note over E: venter på kuttpunkt (K1–K4) og hold-regler (H1–H4)
  R->>X: Take
  X->>B: (ATEM bytter bilde)
  B-->>R: AtemReadback(PGM, PVW)
  Note over R,E: S1: kamera i bevegelse kuttes aldri inn · I2: kamera på PGM/PVW flyttes aldri
```

## 4. Touch-flyten

Motoren eier stegene; touch-skjermen viser dem bare. Teknikeren kan flytte touch til et hvilket som helst steg (`POST /api/touch/step`).

```mermaid
stateDiagram-v2
  [*] --> idle
  idle --> ready: kort skannet (kortoppslag)
  ready --> countdown: Start opptak
  ready --> idle: Logg ut / 3 min uten berøring
  countdown --> ready: Stopp før Pearl
  countdown --> rec: Pearl bekrefter
  countdown --> ready: Pearl svarer ikke innen 10 s (varsel)
  rec --> done: Hold 2 s / tekniker stopper
  rec --> rec: Pearl stopper selv → varsel, aldri automatisk stopp (I7)
  done --> ready: Ta et nytt opptak
  done --> idle: Ferdig / 30 s
```

## 5. Hvor data ligger

| Data | Hvor | Hvor lenge | Hvorfor der |
| --- | --- | --- | --- |
| Studio-oppsett (utstyr, show, knappekart) | `site/<studio>/` (eget git-repo) | Versjonert | Lesbart, kan rulles tilbake (ADR-0006) |
| Regelverdier per forhåndsvalg | `config/defaults/rules.yaml` | Versjonert | Samme i studio, simulator og tester |
| Økter, beslutninger, revisjonslogg, varsler | SQLite WAL, `data/cutcut.db` | Økter 90 d, beslutninger 30 d, revisjon 365 d | Overlever omstart, skrives i egen tråd |
| Motorinnstillinger (AUTO, LÅS, content, skygge), tuning | SQLite `kv` | Til de endres | `core` er tilbake med samme innstillinger etter omstart |
| Logger | `data/logs/*.jsonl` | 30 d, roteres ved midnatt | Feilsøking, `correlation_id` gjennom hele kjeden |
| Hemmeligheter (PIN, nøkler) | Windows Credential Manager | – | Aldri i git, logg eller eksport |
| Kortnummer | Ingen steder | – | I8: brukes bare til oppslaget og glemmes |

## 6. Skjermene

```mermaid
flowchart LR
  subgraph client["@cutcut/client"]
    STORE["Store<br/>(siste tilstand)"]
    WS["WsTransport<br/>gjenoppkobling 250 ms → 5 s"]
    RP["ReplayTransport<br/>forløp fra cutcut trace"]
  end
  CORE["core :8080<br/>/ws + REST"] <--> WS --> STORE
  TRACE["traces/*.json<br/>(Vercel /sim/)"] --> RP --> STORE
  STORE --> TOUCH["@cutcut/touch"]
  STORE --> TECH["@cutcut/tech"]
```

Appene vet ikke hvilken transport de har. Det er hele forskjellen mellom studio og web-simulatoren (ADR-0013). Mister skjermen forbindelsen, vises siste tilstand gråtonet med «Kobler til igjen»; den blir aldri blank (12.5).
