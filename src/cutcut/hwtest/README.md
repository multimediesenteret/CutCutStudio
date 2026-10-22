# `cutcut.hwtest` – maskintestene

Maskintestene sjekker det CI ikke kan: det ekte utstyret i studio, og om CutCut går i dager uten å vokse. Hver test kjøres av en tekniker med én kommando og skriver en rapport som JSON og Markdown i `data\hwtest\` (eller `--out`). Markdown-filen limes inn i GitHub-issuet. Steg for steg: [`docs/studio/maskintest.md`](../../../docs/studio/maskintest.md). Rekkefølgen i studioperioden: [`docs/studio/testdag.md`](../../../docs/studio/testdag.md).

```powershell
uv run cutcut hwtest <audio|atem|camera|vision|faces|soak> --site C:\CutCut\site …
```

| Fil | Test | Steg | Issue |
| --- | --- | --- | --- |
| `audio.py` | RØDECaster: lydkort, kanalkart, synkronitet, stabilitet, USB ut og inn, dempet mic, WASAPI | A1–A7 | AU-6 |
| `atem.py` | ATEM og Companion (`--user`) | B1–B6 | DA-5 |
| `camera.py` | Ett PTZ-kamera (`--camera C2`): protokoll, posisjon, presets, laveste zoomfart, farge, AI-tracking | KA1–KA7 | CA-5 |
| `vision.py` | Capture-kortet (INOGENI): format, rutekart, forsinkelse, stabilitet | V1–V5 | VI-4 |
| `faces.py` | Ansikt og munn på et opptak av multiviewen (`--file`) | F1–F3 | P6 |
| `pearl.py` | Epiphan Pearl: svar, opptaker, lagring, 5 s testopptak, og at en stopp uten trykk varsles innen 5 s (`--user`) | P1–P5 | SE-3 |
| `acceptance.py` | `hwtest akseptanse`: kriteriene i 10.4 fra beslutningene og feilsøkingsopptaket for en periode (`--since`, `--until`, `--data`) | A1–A5 | T-M3 |
| `soak.py` | 72-timerstesten (`--hours`, `--every`): minne, håndtak, omstarter, tilkoblinger, helse | D1–D5 | SO-8 |
| `report.py` | Felles rapportformat (`Report`, `Step`) | – | – |

Steg som flytter et kamera eller endrer preview, spør først, og teknikeren bekrefter bare når kameraet ikke er på lufta (I2). Testene kjøres aldri automatisk mot ekte utstyr (`AGENTS.md` 6). Enhetstestene i `tests/unit/hwtest/` bruker falske enheter.
