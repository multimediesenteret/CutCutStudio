# `cutcut.api` – REST og WebSocket

Plan: [`docs/plans/api.md`](../../../docs/plans/api.md). Spesifikasjonen 10.1, 10.2, 12.4. Full beskrivelse: [`docs/reference/openapi.json`](../../../docs/reference/openapi.json) (generert; `uv run python tools/gen_openapi.py`), og interaktivt på `/api/docs` når appen kjører.

| Fil | Innhold |
| --- | --- |
| `app.py` | `create_app(studio, auth)`: alle stier, WebSocket `/ws`, statiske filer for skjermene, og tikk-løkken (30 ms) |
| `auth.py` | Roller `touch`, `operator`, `admin`; innlogging med brukernavn + PIN; informasjonskapsel `HttpOnly`, `SameSite=Strict`, 8 timer |

**Roller (D-045):**

| Rolle | Hvem | Kan |
| --- | --- | --- |
| `touch` | Forespørsler fra PC-en selv uten innlogging | Start uten kort («Gjest», D-057), økt, showvalg, opptak, hjelp, logg ut |
| `operator` | Tekniker på teknikerlisten med PIN. Listen ligger i appen (Innstillinger → Teknikere, D-060); `site/<studio>/staff.yaml` er bare utgangspunktet. Er listen tom, slipper admin-PIN-en inn som admin, så en ny PC kan settes opp | I tillegg AUTO, LÅS, kutt, preview, content, forhåndsvalg, logg, kvittere varsler |
| `admin` | Administrator på listen med admin-PIN | I tillegg brytere og skyggemodus |

Andre maskiner uten innlogging får bare `GET /api/health`. I simulatoren (`dev_admin`) er lokale forespørsler admin, så teknikervinduet kan prøves uten PIN.

**WebSocket `/ws?topics=state,meters,...`:** første melding er full tilstand (`"full": true`), deretter bare endringer: `state` 10 Hz (bare endrede felt), `meters` 20 Hz, `decision`, `alert`, `touch`. En treg klient mister de eldste meldingene og får full tilstand på nytt; den kan aldri bremse motoren.

**Feil:** ikke lov nå → `409` med norsk setning som kan vises direkte; ugyldige data → `422`.
