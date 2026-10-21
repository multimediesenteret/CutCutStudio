# `cutcut.health` – helsesjekkene

Spesifikasjonen 8.5 og `docs/plans/setup-health.md`. Helsesjekkene sjekker hele tiden at utstyret er tilkoblet, virker og står som avtalt. Feil skal oppdages og meldes før de merkes på lufta.

| Fil | Innhold |
| --- | --- |
| `model.py` | `CheckResult`: ID, status (grønn, gul, rød), verdi, forventet verdi, melding, tid, og hvor lenge avviket har vart |
| `engine.py` | `HealthEngine` kjører hver sjekk med eget intervall og egen tidsgrense |
| `checks.py` | Katalogen, bygd av små lesefunksjoner så den virker likt i studio og simulator. Så langt bare `H-AUD-1`; resten kommer i HS-2 |

Slik oppfører `HealthEngine` seg:
- En sjekk som henger eller feiler, blir gul («sjekken virker ikke»). Den forsinker aldri motoren.
- Et avvik åpnes med en gang, men lukkes først etter 30 s grønt (hysterese). En enhet som går av og på, gir derfor ett avvik.
- Hvert avvik logges én gang ved start og én gang ved slutt.

I studioet blir et åpent avvik et varsel i teknikervinduet: rødt gir feil, gult gir advarsel. Når avviket lukkes, forsvinner varselet av seg selv.

Touch-skjermen viser bare røde avvik som brukeren må vite om (`for_user`). Lyd som forsvinner, får brukeren allerede beskjed om fra motoren (`S4`), så `H-AUD-1` er bare for teknikeren.

`GET /api/health` (samlet status for NTNUs overvåkning) og `GET /api/health/checks` krever ikke innlogging.

Sjekker trykker aldri knapper og flytter aldri noe. Slikt finnes bare i setup-hjelperen.
