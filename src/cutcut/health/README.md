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
| `H-PRL-1` | Pearl svarer, har ingen feil, har plass | 5 s | Rødt (også for brukeren) når Pearl ikke svarer eller har under 15 min igjen; gult under 60 min |
| `H-ATEM-1` | Program og preview kan leses | 1 s | Rødt (også for brukeren) etter 15 s oppstart |
| `H-COMP-1` | Companions HTTP-API og `cutcut_pages_version` | 5 s | Rødt: svarer ikke (`S5` tar over), sidene mangler eller har feil versjon |

Lagringen på Pearl regnes om til minutter med 20 Mbit/s til bitraten er målt i maskintesten (DA-5). Dette kommer senere:
- `H-PC` for GPU-temperatur og klokke (NTP) kommer med test-PC-en (Q8, Q20).
- `H-AUD-2` (støy i stillhet) trenger støygulvet i `baseline.yaml` fra setup steg 5.
- `H-PRL-2`, opptak som stopper av seg selv, er en hendelse og varsles av økta (I7).

I studioet blir et åpent avvik et varsel i teknikervinduet: rødt gir feil, gult gir advarsel. Når avviket lukkes, forsvinner varselet av seg selv.

Touch-skjermen leser sjekkene direkte, ikke varslene. Den sperrer start bare mens en sjekk merket for brukeren (`for_user`: Pearl og ATEM) er rød. Teknikerens avvik kan stå åpent i 30 s etter at feilen er rettet, men brukeren blir ikke holdt tilbake så lenge. Lyd som forsvinner, får brukeren beskjed om fra motoren (`S4`).

`GET /api/health` (samlet status for NTNUs overvåkning) og `GET /api/health/checks` krever ikke innlogging.

**Morgensjekk (HS-4):** hele katalogen og multiview-sjekken (D-056) kjøres 20 s etter oppstart og hver morgen kl. 07:00 etter PC-ens klokke. Starter studioet etter 07:00, teller oppstartssjekken som dagens morgensjekk. Teknikeren kan også trykke «Kjør alle nå» (`POST /api/health/morning-check`).
- Hvileskjermen viser resultatet som en liten prikk: grønn, eller gul når teknikeren har noe å se på. Brukeren får aldri detaljene.
- Teknikervinduet viser hvilke sjekker som ikke var grønne.

Sjekker trykker aldri knapper og flytter aldri noe. Slikt finnes bare i setup-hjelperen.
