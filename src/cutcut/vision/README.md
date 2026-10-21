# `cutcut.vision`: videolaget

Planen står i `docs/plans/vision.md` (spesifikasjonen 6). Videolaget leser ATEM-multiviewen via INOGENI og deler bildet i ruter etter rutekartet. Det sender målinger til `core`, men tar aldri beslutninger selv.

| Fil | Innhold |
| --- | --- |
| `tiles.py` | Rutene fra `site/<studio>/equipment/multiview_map.yaml`. Koordinatene er andeler (0–1), og hver rute kuttes 4 % inn så tally-rammen og navneskiltet blir borte |
| `capture.py` | Hvor bildet kommer fra. `OpenCvSource` er INOGENI (DirectShow) eller en videofil, og åpnes på nytt hvert 5. sekund når den stopper. `SyntheticSource` er en tegnet multiview til tester og demo |
| `process.py` | 15 Hz. Per rute måles signal, lysstyrke og endring fra forrige bilde. Sender `vision.frame` (alle ruter) og `vision.status` (bilder/s, størrelse, kilde, siste feil) |
| `content.py` | Content-deteksjon på laptop-ruta (VI-2, 6.2). `NO_SIGNAL` etter 0,3 s svart. `NEW_SLIDE` når over 15 % endres og bildet så står stille i 0,5 s (holdes 2 s). `VIDEO` ved bevegelse i 1 s. Ellers `STATIC`. Sendes som `vision.content`, 5 Hz og straks ved endring |
| `motion.py` | Bevegelse og programbekreftelse (VI-3). Et kamera som panorerer, endrer over 35 % av ruta i to bilder på rad og regnes som i bevegelse til det har stått stille i 0,5 s (`V5`), så motoren ikke kutter til det (`S1`). Programruta sammenlignes med kameraene i små, normaliserte gråbilder. Sendes som `vision.moving` og `vision.pgm`, 5 Hz |
| `main.py` | `cutcut vision --site … [--device N \| --file video.mp4 \| --synthetic]` |

`core` tar imot målingene. Fra første gang videolaget melder seg, viser Helse `H-VID-1` (bilder) og `H-VID-3` (programruta mot ATEM, gult etter 3 s uenighet). `S1` bruker både det kameraene selv melder og det videolaget ser; en stille videolag holder ikke kameraer tilbake lenger enn 1 s. Uten videolaget klipper motoren på lyd som før.

Dette bygges videre:
- maskintest for INOGENI (VI-4);
- rutekart-forslag i setup (VI-5);
- kamerabilder i teknikervinduet som utsnitt av det samme bildet (D-056).

OpenCV (`opencv-python-headless`) ligger i ekstraen `vision`: `uv sync --extra vision`.
