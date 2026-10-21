# Plan: `common` – modeller, konfig, klokke, logging, lagring, buss, plattform

Status: godkjent (D-046) · Milepæl: M1 · Spes. 3, 4, 5.8, 7.5, 12.1–12.4; ADR-0002, 0006, 0010 · Mappe: `src/cutcut/common/`

## 1. Formål og avgrensning

Felles grunnmur som alle andre moduler bygger på. Ingen regler og ingen enhetskode her.

| Del | Innhold |
| --- | --- |
| `models/` | Pydantic v2-modeller for show-oppsett (4), økt (7.5), beslutning (5.8), meldinger på bussen (6.6, lyd, ATEM), helse (8.5), API-typer |
| `ids.py` | Faste ID-er som `Enum`: `P1`–`P4`, `M1`–`M5`, `C1`–`C7`, `LAPTOP`, bilder (`CU:P2`, `BIRD` …), moduser `N1`–`N4C`, `A`, og alle regel-ID-er (`T1` … `AT6`) |
| `config/` | Lasting og validering av YAML (`site/<studio>/`, `config/defaults/`), `schema_version` med migreringer, generering av JSON Schema til `config/schema/` |
| `clock.py` | Monoton klokke for motoren og veggklokke for logg (ADR-0010). Falsk klokke for tester og simulator |
| `logging.py` | JSON-linjer, daglig rotasjon, 30 dager, `correlation_id`, regel- eller sjekk-ID per linje (12.1) |
| `store/` | SQLite i WAL-modus: økter, beslutninger, revisjonslogg, konfigversjoner, varsler. Migreringer. Rydding etter lagringstid (Q10) |
| `bus/` | ZeroMQ: PUB/SUB for hendelser, PUSH/PULL for kommandoer med kvittering. JSON med `topic`, `ts`, `seq`, `schema` |
| `platform/` | Adaptere med Windows- og falsk variant: hemmeligheter (`keyring`), Windows-tjeneste, kiosk, strømplan, lydbackend, capture |
| `privacy.py` | `redact()` som fjerner alt som ligner kortnummer før logging (I8, forsvar i dybden) |

## 2. Grensesnitt

Utdrag (fullstendige modeller skrives i M1 og genereres til `docs/reference/`):

```python
class Participant(BaseModel):
    id: ParticipantId            # P1..P4
    name: str
    mic: MicId                   # M1..M4
    camera: CameraId             # C1..C4
    role: Literal["host", "guest"]

class ShowConfig(BaseModel):
    schema_version: int
    id: str; name: str; version: int
    participants: list[Participant] = Field(min_length=1, max_length=4)
    cameras: dict[CameraId, CameraConfig]
    content: ContentConfig
    features: Features
    layouts: LayoutSwitches
    rules_preset: Literal["rolig", "standard", "energisk"]
    rules_override: dict[str, float] = {}
    # validator: hver deltaker har kamera; C5 finnes; mic/kamera unike

class Decision(BaseModel):       # spes. 5.8, uendret feltnavn
    ts: datetime; mode: Mode; action: Literal["cut", "wait", "hold", "preview"]
    shot: Shot; rule: RuleId; reason: str
    measures: dict[str, float]; blocked_by: RuleId | None
    companion: CompanionButton | None
    correlation_id: str; shadow: bool

class BusMessage(BaseModel):
    topic: str; ts: datetime; mono_ms: int; seq: int; payload: dict[str, Any]
```

`action` får verdien `preview` i tillegg til 5.8 for å logge når motoren legger noe på preview (trengs for kriteriet «preview minst 300 ms før program»).

**Konfig-filer:**

| Fil | Eier | Innhold |
| --- | --- | --- |
| `config/defaults/rules.yaml` | repo | Verdier per forhåndsvalg (Rolig/Standard/Energisk) for alle regler |
| `config/defaults/show_types.yaml` | repo | Podcast, Intervju, Panel, Kun lyd (7.5) |
| `site/<studio>/devices.yaml` | studio | IP-er, porter, ATEM-innganger, kamerakart |
| `site/<studio>/shows/*.yaml` | studio | Show-oppsett (4) |
| `site/<studio>/baseline.yaml` | studio | Fasit fra setup-hjelperen |
| `site/example/` | repo | Fiktivt studio for simulator og tester |

## 3. Tilstander og feil

- **Ugyldig konfig ved oppstart:** `core` starter ikke med feil oppsett (4), men supervisor starter da **siste gyldige versjon** fra SQLite og varsler rødt. Grunnen er oppetid: en skrivefeil i en YAML-fil skal ikke ta ned studioet.
- **Ukjent `schema_version`:** nekter å starte og varsler (12.3); migrering kjøres bare av installasjonen.
- **SQLite låst eller full disk:** skriving går via én skrivetråd med kø; ved feil logges til fil og helse blir gul. Motoren fortsetter uten lagring.
- **Bussen:** ingen meldinger på et emne i over 1 s gir hendelsen `stale(topic)`, som `core` bruker (for eksempel 6.6 og `S4`).
- **Klokka:** veggklokka kan hoppe (NTP); alle tidsregler bruker `mono_ms`.

## 4. Avhengigheter

Python 3.12, `pydantic` 2, `ruamel.yaml`, `pyzmq`, `keyring`, `orjson`. Låses i `uv.lock` ved første kode. Ingen utstyr.

## 5. Testplan

- Skjema: alle eksempelfiler i `site/example/` og spesifikasjonens YAML-eksempel validerer; ugyldige varianter avvises med forståelig feil.
- Migrering: fil med `schema_version` N−1 oppgraderes og validerer.
- Klokke: falsk klokke styrer tid deterministisk; veggklokkehopp påvirker ikke `mono_ms`.
- Logg: rotasjon og sletting etter 30 dager; `redact()` fjerner testkortets nummer.
- Lagring: krasj midt i skriving gir ingen korrupt database (WAL + `synchronous=NORMAL`), testet med drept prosess.
- Buss: tapte meldinger (`seq`-hull) oppdages; `stale` utløses etter 1 s.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| C-1 | Prosjektskjelett: `pyproject.toml`, `uv.lock`, ruff, mypy strict, pytest, CI-jobb `python` på Linux | `uv run pytest` og `mypy` grønt i CI |
| C-2 | `ids.py` og modeller for show, økt, beslutning | Spesifikasjonens eksempler validerer |
| C-3 | Konfiglasting, `rules.yaml` med tre forhåndsvalg, JSON Schema-generering | Generert skjema sjekkes i CI |
| C-4 | Klokke og logging med `correlation_id` og rotasjon | Tester grønne |
| C-5 | SQLite-lager med migreringer og rydding | Krasjtest grønn |
| C-6 | Buss med `seq`, kvittering og `stale` | Test med to prosesser |
| C-7 | Plattform-adaptere med falsk variant | Kjører på Linux uten Windows-pakker |
| C-8 | `site/example/` (fiktivt studio med 4 deltakere, C5, laptop) | Brukes av simulatoren |

## 7. Åpne spørsmål

- Q10: lagringstid for brukernavn og økthistorikk (forslag 90 dager som i 12.4).
- Q11: lisens før første kode.
