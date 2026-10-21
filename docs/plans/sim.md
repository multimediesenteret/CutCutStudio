# Plan: `sim` – simulator, scenarioer og avspilling

Status: godkjent (D-046) · Milepæl: M1 · Spes. 10.3, 13.3; ADR-0013; `docs/simulator.md` · Mappe: `sim/`, `tests/integration/fakes/`

## 1. Formål og avgrensning

Gjør at hele CutCut kan kjøres og testes uten utstyr, i CI og på en utviklers maskin, og lager forløpene som web-simulatoren på Vercel spiller av.

| Del | Innhold |
| --- | --- |
| `sim/voices.py` | Syntetiske talere: tur-taking, pauser, frasegrenser, krysstale, latter, småord, lekkasje mellom mic-er. Lager `MicFrame` direkte (samme melding som `audio-capture`, PL-02) |
| `sim/vision.py` | Syntetiske ruter: ansikt funnet, munn, bevegelse, content-tilstander |
| `sim/devices/` | Falske enheter: ATEM-tilstand, Companion HTTP, Pearl REST, kameraer (VISCA/OSC/XC), kortleser, NTNU-API. Samme kode brukes som testservere i `tests/integration/` |
| `sim/scenarios/*.yaml` | Ferdige scenarioer (liste under). Deterministiske med frø |
| `sim/replay.py` | Avspilling av ekte forløp (nivå og VAD per mic) fra opptak (Q1) |
| `sim/trace.py` | Skriver hele forløpet (tilstand, beslutninger, målere) som komprimert JSON for web-simulatoren |
| `cutcut sim` | Starter motor, simulator og begge skjermer lokalt (mål: under 10 min fra ren klone, 12.1) |

**Scenarioer (fra `docs/simulator.md`):** monolog (1), samtale (2), panel (3 og 4), krysstale, lang stillhet, latter, laptop med ny slide, video på laptop, laptop koblet fra, vert med korte innskudd, programleder demper en gjest (`S6`). Feil: lyd borte (`S4`), Companion nede (`S5`), ATEM borte, kamera svarer ikke, Pearl stopper uten trykk, Pearl lite lagring, kortleser frakoblet, NTNU-API nede, videolaget dør.

## 2. Grensesnitt

```yaml
# sim/scenarios/samtale-2.yaml
id: samtale-2
seed: 42
show: site/example/shows/podcast-standard.yaml   # 2 deltakere
duration_s: 600
script:                      # valgfritt; uten script brukes stokastisk tur-taking
  - { at: 0,   speaker: P1, for: 12 }
  - { at: 12,  speaker: P2, for: 25, overlap_ms: 400 }
faults:
  - { at: 300, kind: audio_lost, for: 4 }
expect:                      # sjekkes av testen
  - { rule: S4, within_s: [302, 303] }
  - { never: cut_to_moving_camera }
```

Simulatoren kjører på falsk klokke, raskere enn sanntid i CI (10 min scenario på sekunder), og i sanntid for `cutcut sim`.

## 3. Tilstander og feil

Simulatoren skal kunne lage alle feil i 9.1, slik at skjermene og motoren kan prøves mot dem. Falske enheter kan konfigureres til tidsavbrudd, treg respons, feil svar og frakobling.

## 4. Avhengigheter

`common`, `core`, `numpy` (bare for tale-syntese), `httpx`/`starlette` for falske HTTP-enheter. Ingen utstyr.

## 5. Testplan

- Hvert scenario er en integrasjonstest med `expect`-sjekker.
- Determinisme: samme frø gir samme forløp og samme beslutninger.
- Falske enheter testes mot protokollbeskrivelsene i `docs/spec/02-teknisk-referanse.md` (samme bytes for VISCA, samme JSON for Pearl).
- Når Q1 kommer: avspilling av ekte forløp; avvik i kutt mot forrige versjon rapporteres i PR.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| SIM-1 | Syntetiske talere → `MicFrame` | Monolog og samtale kjører |
| SIM-2 | Scenario-format med `expect` og frø | 5 scenarioer grønne i CI |
| SIM-3 | Falske enheter: ATEM, Companion, Pearl | Integrasjonstester mot dem |
| SIM-4 | Falske enheter: kameraer, kortleser, NTNU-API | Tester mot dem |
| SIM-5 | Alle scenarioer og feil fra listen | Alle grønne |
| SIM-6 | `cutcut sim` med begge skjermer | README-kommandoen kjøres i CI |
| SIM-7 | `trace.py`: forløp til JSON for Vercel | Web-simulatoren spiller det av |
| SIM-8 | `replay.py` for ekte forløp | Venter på Q1 (M2) |

## 7. Åpne spørsmål

- Q1–Q2: ekte opptak og klippeliste. Uten dem tunes reglene bare mot syntetiske talere.
