# Plan: `setup` og `health` – setup-hjelper og helsekatalog

Status: godkjent (D-046) · Milepæl: helsekjerne i M2, full setup-hjelper og katalog i M3 · Spes. 8.4, 8.5, 9.3, 10.1 (setup- og helsestier); D-018 · Mapper: `src/cutcut/setup/`, `src/cutcut/health/`, `site/<studio>/setup/*.yaml`

## 1. Formål og avgrensning

- **Helse:** sjekker hele tiden at alt er tilkoblet, fungerer og står som avtalt (8.5, tre nivåer). Det er helsesiden som gjør at studioet kan stå uten tekniker: feil oppdages og meldes før de merkes på lufta.
- **Setup-hjelper:** veiviseren i 10 steg fra tomt studio til «Klar for produksjon», med «Fiks for meg» der det er trygt og godkjenning til `baseline.yaml` (8.4).

## 2. Grensesnitt

**Sjekk som data:**

```python
class HealthCheck(Protocol):
    id: str                      # "H-ATEM-1"
    interval_s: float
    level: Literal["connected", "working", "as_agreed"]
    async def run(self, ctx: HealthContext) -> CheckResult: ...   # verdi, status, tekst, tid

class CheckResult(BaseModel):
    id: str; status: Literal["green", "yellow", "red"]; value: str
    expected: str | None; message_nb: str; ts: datetime
```

- Hele katalogen i 8.5 implementeres, ett utstyr av gangen i samme rekkefølge som driverne.
- **Hysterese:** grønt i 30 s før et varsel regnes som løst; hvert varsel logges én gang med start og slutt (8.5).
- **Aldri skadelige sjekker i drift:** sjekker som trykker knapper eller flytter noe finnes bare i setup-hjelperen.
- `GET /api/health` og `GET /api/health/checks` (10.1).
- **Varsling:** teknikervindu (lyd ved rødt), touch (bare rødt som brukeren må vite om), Companion `regi_health`, og e-post ved rødt over 1 min til mottakerne som er lagt inn i appen (Q29, D-058, D-060), sendt fra en egen oppgave som aldri påvirker motoren.
- **Morgensjekk:** ved oppstart og kl. 07:00 kjøres hele katalogen; resultatet vises som prikk på hvileskjermen.

**Setup-steg som data:** `site/<studio>/setup/NN-<navn>.yaml` med tekst (hva og hvorfor, slik gjør du), forventede verdier, hvilken sjekk som brukes og om «Fiks for meg» finnes. Samme filer genererer oppsettsguiden i `docs/setup/` (12.1).

## 3. Tilstander og feil

- En sjekk som selv feiler (unntak, tidsavbrudd) gir gult «sjekken virker ikke», aldri krasj i `core`.
- Sjekker kjører i egne asyncio-oppgaver med tidsavbrudd; de kan aldri forsinke motorens tikk.
- «Fiks for meg» og tester som flytter kamera eller endrer ATEM er sperret under opptak (8.4).
- Godkjenning skriver `baseline.yaml` og lager en commit i studio-mappen med tekniker og tid (9.3); feiler git, lagres filen likevel og helse blir gul.

## 4. Avhengigheter

Bare egne moduler og enhetsklientene. Windows-sjekker (`powercfg`, driverversjoner, NTP) går gjennom `common/platform/`.

## 5. Testplan

- Hver sjekk testes mot falsk enhet i grønn, gul og rød tilstand.
- Hysterese og «én gang per varsel» testes med blafrende enhet.
- Morgensjekk mot simulator: alle grønne; med feil: riktig prikk og logg.
- Setup-steg: YAML-skjema validerer; guide genereres uten avvik i CI.
- 10.4: «alle enheter grønne» i studio, og klemming av kamerakommando logges.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| HS-1 | Helsemotor, `CheckResult`, hysterese, `/api/health` | Tester grønne (M2) |
| HS-2 | Sjekker for prosesser, PC, lyd, Pearl, ATEM, Companion (`H-PROC`, `H-PC`, `H-AUD`, `H-PRL`, `H-ATEM-1`, `H-COMP-1`) | Grønne på test-PC og i studio (M2) |
| HS-3 | Varsling: teknikervindu, touch, Companion, e-post/Teams (Q29) | Rødt over 1 min gir melding |
| HS-4 | Morgensjekk kl. 07:00 og ved oppstart | Prikk på hvileskjermen |
| HS-5 | Setup-motor og steg-format, guide-generering | Guide i `docs/setup/` sjekkes i CI |
| HS-6 | Setup-steg 1–10, ett utstyr av gangen | Hvert steg testet i studio med tekniker |
| HS-1b | Utstyrsadresser i teknikervinduet og multiview-sjekk (`H-MV-0`–`H-MV-11`) mot rutekart, show og ATEM ved oppstart og på forespørsel (D-055, D-056) | Gjort i M1 mot simulator; mot ekte ATEM med `atem-bridge` (M2) |
| HS-7 | Resten av katalogen (`H-CAM-*`, `H-VID-*`, `H-CARD-1`, `H-CARD-2`, `H-ATEM-2/3/4`) | Komplett katalog (M3) |

## 7. Åpne spørsmål

- Q29: besvart (D-058): e-post, mottakere i appen. Q40: SMTP-relé fra IT-avdelingen.
- Q30: når kan morgensjekken og eventuelle omstarter kjøres (åpningstider)?
- Q12: tekniker som tester setup-stegene i studio.
