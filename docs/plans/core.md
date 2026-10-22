# Plan: `core` – regimotoren

Status: godkjent (D-046) · Milepæl: M1 · Spes. 5 (alle underseksjoner), 9.1, 10.4; D-010, D-035, D-041; I2–I5, I7 · Mappe: `src/cutcut/core/`

**Leveransestatus 2026-10-22:** K-1–K-10 er bygget (M1). Bryterreglene (`L`, `F`, `Z`, `AT`, `V`, `R`) er bygget før studioperioden (P2–P7, `for-studio.md`).

## 1. Formål og avgrensning

Motoren som bestemmer hva som skal på preview og program. Grunnmodus i M1: moduser (5.1), prioritetsrekkefølge (5.2), `T` (5.3), `S` (5.7), `PV` (5.9), `K` (5.10), `H` (5.11), roller (5.12), overstyring. `B` og `CT` bygges i M1 mot simulerte målinger, og tas i bruk i studio når videolaget finnes (M3). `V`, `R`, `F`, `Z`, `L`, `AT` er brytere (M4, `features.md`), men plassen i motoren lages nå.

**Ikke her:** lyd- og bildeanalyse (de kommer som målinger), enhetskommunikasjon (motoren sender *ønsker*, et skall utfører dem).

## 2. Grensesnitt

**Ren kjerne (PL-04).** Ingen I/O, ingen tråder, ingen `asyncio`, ingen klokke-kall. Alt kommer inn som data:

```python
@dataclass(frozen=True)
class Inputs:
    now_ms: int                               # monoton tid
    audio: dict[MicId, MicFrame]              # fra audio-capture (audio.md)
    vision: dict[Source, TileFrame] | None    # None = videolaget borte
    content: ContentFrame | None
    atem: AtemReadback | None                 # hva som faktisk er på PGM/PVW
    commands: list[OperatorCommand]           # AUTO, LÅS, kutt, preview, brytere
    config: EffectiveConfig                   # show + preset + overstyringer

def step(state: EngineState, inp: Inputs) -> tuple[EngineState, list[Decision], list[DeviceIntent]]: ...
```

`MicFrame` (per 30 ms tikk): `active`, `vad`, `level_db`, `dominance_db`, `pause_ms`, `phrase_end`, `pitch_falling`, `in_main_mix` (for `S6`), `leak` (beregnet av audio-capture).

`DeviceIntent` er det motoren *vil*: `SetPreview(shot)`, `Take(cut|mix)`, `DirectCut(shot)`, `RunMacro(n)`, `SetCompanionVar(name, value)`, `CameraMove(...)`. Skallet (`core/runtime.py`) gjør dem om til kommandoer via `devices/`, eller logger dem i skyggemodus.

**Skall (`core/runtime.py`):** asyncio-løkke som hvert 30. ms samler siste målinger fra bussen, kaller `step`, sender beslutninger til logg og WebSocket, og intents til enhetskøene. Tikket er driftssikkert: tar et `step` over 10 ms, logges det; tar det over 30 ms, hoppes neste tikk over i stedet for å hope seg opp.

**Motortilstand (`engine_mode`):**

| Tilstand | Beslutninger | Kommandoer | Brukes |
| --- | --- | --- | --- |
| `LIVE` | ja | ja | drift |
| `SHADOW` | ja, merket `shadow: true` | nei, bare logg (PL-05) | nye brytere og oppdateringer når studioet er i drift (D-049) |
| `PAUSED` | nei (AUTO av, LÅS, modus `A`) | bare operatørens | overstyring |

**Preview-tilstander (5.9):** `IDLE → ARMED → READY → TAKE → IDLE` som eksplisitt tilstandsmaskin med regel-ID på hver overgang.

**Regler som kode:** én funksjon per regel-ID i `core/rules/<gruppe>.py`, med konstanten `RULE_ID = "T2"`. Prioritetsrekkefølgen i 5.2 er én liste som evalueres i orden; første regel som gir kutt vinner, og alle som holder igjen gir `blocked_by`. Hold og release (5.11) er filtre som brukes på alle unntatt overstyring og tapt content.

**Roller (5.12):** vert/gjest gir multiplikatorer og tillegg (T12, T3 +1 s for gjest, korte innskudd fra vert < 1,5 s gir ikke kutt), lest fra `Participant.role`.

## 3. Tilstander og feil

| Situasjon | Motoren gjør | Regel |
| --- | --- | --- |
| Ingen lydmålinger i over 2 s | `DirectCut(BIRD)`, `PAUSED`, varsel rødt | `S4` |
| Lyden tilbake | Går tilbake til forrige `engine_mode` etter 2 s stabil lyd, varsel løses | `S4` |
| Videolaget borte i over 1 s | Fortsetter på lyd alene, `vision`-regler av, gult «Bare lyd» | 6.6 |
| Companion svarer ikke | Intents går som direkte ATEM-kutt; layouter stoppes; feiler også ATEM: `PAUSED` og varsel | `S5` |
| ATEM viser noe annet enn motoren ba om | Motoren tar ATEM sin tilstand som sannhet og venter 5 s (manuelt inngrep) | I5, 5.2 punkt 1 |
| Mic aktiv, men ikke i hovedmiksen | Ingen kutt til personen; mic-stripen viser «dempet på mikser» | `S6` |
| Ugyldig eller manglende bilde for en deltaker | Modusens reservebilde | `S2`, 5.1 |
| Kamera i bevegelse | Ikke kandidat før stille i 0,5 s | `S1`, `V5` |
| Mer enn ett kutt per sekund | Blokkeres alltid | `S3` |

Motoren stopper aldri opptak (I7) og flytter aldri kamera på PGM/PVW (I2): `CameraMove`-intents til et kamera på PGM/PVW avvises i kjernen *og* i driveren.

**Omstart:** `EngineState` serialiseres til SQLite hvert sekund og ved hver beslutning. Etter omstart lastes den, men motoren starter i `IDLE` med det ATEM faktisk viser, slik at den aldri kutter rett etter oppstart (5 s ro).

## 4. Avhengigheter

Bare standardbiblioteket og `common`. Ingen numpy i kjernen (gjør Pyodide-trinnet lett). Tester: `pytest`, `hypothesis`.

## 5. Testplan

- **Per regel-ID:** minst én test som slår til og én som ikke gjør det (10.3). Testnavn: `test_T2_fires_after_confirm`, `test_T2_does_not_fire_on_short_burst`. Sporbarhetsskriptet lager `docs/reference/traceability.md` og CI feiler hvis en regel mangler test (12.1).
- **Determinisme (I3):** samme forløp kjørt to ganger gir identisk beslutningslogg (hash sammenlignes).
- **Egenskapstester (hypothesis):** for vilkårlige forløp gjelder alltid: maks ett kutt per sekund (`S3`), ingen kutt til kamera i bevegelse (`S1`), ingen tilbake til forrige bilde innen 4 s (`H2`), ingen `CameraMove` mot PGM/PVW (I2).
- **Moduser:** alle `N1`–`N4C` og `A` med riktig utvalg og reservebilder (10.4).
- **Overstyring:** manuelt kutt vinner og gir 5 s ro; LÅS holder; AUTO av stopper alt unntatt `S`.
- **Ytelse:** `step` under 2 ms i snitt og under 10 ms i 99,9 % på en vanlig CI-maskin (gir god margin for kravet «kutt innen 150 ms»).
- **Grunnmodus = brytere av** (10.4): samme forløp med alle brytere av og med brytere på + videolag borte gir samme kutt.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| K-1 | `Inputs`, `EngineState`, `step`-skjelett, modusvalg (5.1) | Modustester grønne |
| K-2 | `T1`–`T9`, `T12` med roller (5.3, 5.12) | Regeltester grønne |
| K-3 | Preview-tilstander og `PV1`–`PV4` | Tilstandsmaskin testet |
| K-4 | Kuttpunkt `K1`–`K4` | Regeltester grønne |
| K-5 | Hold og release `H1`–`H4` | Egenskapstest for `H2` grønn |
| K-6 | Sikkerhet `S1`–`S6` | Egenskapstester for `S1`, `S3` grønne |
| K-7 | Overstyring, LÅS, AUTO, `engine_mode` med skyggemodus | Tester grønne |
| K-8 | `B1`–`B5` og `CT1`–`CT6` mot simulerte målinger | Alle moduser testet |
| K-9 | Skall: tikk-løkke, intents, serialisering og omstart | Drept prosess er tilbake med samme økt |
| K-10 | Sporbarhetsskript og regeltabell til `docs/reference/` | CI feiler ved regel uten test |

## Vedlegg: tuning-forslag (PL-08)

Spesifikasjonen har verdier per forhåndsvalg bare for `T`. Forslag for resten, til de kan måles mot opptak (Q1–Q2). Standard er spesifikasjonens verdi.

| Regel | Rolig | Standard | Energisk |
| --- | --- | --- | --- |
| `K1` pause før kutt ved turbytte | 400 ms | 300 ms | 200 ms |
| `K2` frasegrense ved overlapp | 300 ms (fallende tone: 200) | 250 ms (150) | 200 ms (120) |
| `K3` maks ventetid | 2,0 s | 1,5 s | 1,0 s |
| `K4` pause for ikke-taler-kutt | 350 ms | 250 ms | 200 ms |
| `H1` sterkere bevis etter kutt | `T2` × 1,8 i 6 s | × 1,5 i 5 s | × 1,3 i 4 s |
| `H2` ikke tilbake til forrige bilde | 6 s | 4 s | 3 s |
| `H3` release | 1,5 s | 1,0 s | 0,7 s |
| `B1` åpning / etter content | 5 s / 4 s | 4 s / 3 s | 3 s / 2 s |
| `B5` variasjon: maks andel, minst mellom | 10 %, 60 s | 15 %, 45 s | 20 %, 30 s |
| `CT2` hold ny slide | 8 s | 6 s | 4 s |
| `CT4` tilbake til taler etter | 8 s | 6 s | 4 s |
| `L` minste tid / ikke samme layout innen | 8 s / 45 s | 6 s / 30 s | 5 s / 20 s |
| `PV1` minste tid mellom preview-bytter | 0,5 s | 0,5 s | 0,5 s |

`T` brukes som i evalueringen (Rolig/Standard/Energisk-tabellen i `docs/spec/03-evaluering-og-bakgrunn.md`).

## 7. Åpne spørsmål

- Q24 avgjør om `S6` trengs (pre-fader med dempet mic). Regelen bygges uansett; den kan slås av i `rules.yaml`.
- Q34: godkjenner produkteier tuning-forslaget over som startpunkt?
- Q1–Q2: ekte opptak og klippeliste trengs for å tune og for kriteriet «under 2 feilkutt per 10 min».
