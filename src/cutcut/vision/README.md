# `cutcut.vision`: videolaget

Planen står i `docs/plans/vision.md` (spesifikasjonen 6). Videolaget leser ATEM-multiviewen via INOGENI og deler bildet i ruter etter rutekartet. Det sender målinger til `core`, men tar aldri beslutninger selv.

| Fil | Innhold |
| --- | --- |
| `tiles.py` | Rutene fra `site/<studio>/equipment/multiview_map.yaml`. Koordinatene er andeler (0–1), og hver rute kuttes 4 % inn så tally-rammen og navneskiltet blir borte |
| `capture.py` | Hvor bildet kommer fra. `OpenCvSource` er INOGENI (DirectShow) eller en videofil, og åpnes på nytt hvert 5. sekund når den stopper. `SyntheticSource` er en tegnet multiview til tester og demo |
| `process.py` | 15 Hz. Per rute måles signal, lysstyrke og endring fra forrige bilde. Sender `vision.frame` (alle ruter) og `vision.status` (bilder/s, størrelse, kilde, siste feil) |
| `main.py` | `cutcut vision --site … [--device N \| --file video.mp4 \| --synthetic]` |

`core` tar imot målingene og viser `H-VID-1` under Helse fra første gang videolaget melder seg. Uten videolaget klipper motoren på lyd som før.

Dette bygges videre:
- content-deteksjon (VI-2);
- bevegelse og PGM-bekreftelse (VI-3);
- maskintest for INOGENI (VI-4);
- rutekart-forslag i setup (VI-5);
- kamerabilder i teknikervinduet som utsnitt av det samme bildet (D-056).

OpenCV (`opencv-python-headless`) ligger i ekstraen `vision`: `uv sync --extra vision`.
