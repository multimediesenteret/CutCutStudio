# `cutcut.vision`: videolaget

Planen står i `docs/plans/vision.md` (spesifikasjonen 6). Videolaget leser ATEM-multiviewen via capture-kortet (DeckLink Mini Recorder HD, D-062) og deler bildet i ruter etter rutekartet. Det sender målinger til `core`, men tar aldri beslutninger selv.

| Fil | Innhold |
| --- | --- |
| `tiles.py` | Rutene fra `site/<studio>/equipment/multiview_map.yaml`. Koordinatene er andeler (0–1), og hver rute kuttes 4 % inn så tally-rammen og navneskiltet blir borte |
| `capture.py` | Hvor bildet kommer fra. `OpenCvSource` er capture-kortet (DirectShow; DeckLink-kortet finnes på navnet fra `video` i `devices.yaml`) eller en videofil, og åpnes på nytt hvert 5. sekund når den stopper. `SyntheticSource` er en tegnet multiview til tester og demo |
| `process.py` | 15 Hz. Per rute måles signal, lysstyrke og endring fra forrige bilde. Sender `vision.frame` (alle ruter) og `vision.status` (bilder/s, størrelse, kilde, siste feil). Mens teknikervinduet viser bilder, sendes også `vision.thumbs`: små JPEG-utsnitt av kamera-, laptop-, preview- og programrutene, maks 2 per sekund (D-056) |
| `content.py` | Content-deteksjon på laptop-ruta (VI-2, 6.2). `NO_SIGNAL` etter 0,3 s svart. `NEW_SLIDE` når over 15 % endres og bildet så står stille i 0,5 s (holdes 2 s). `VIDEO` ved bevegelse i 1 s. Ellers `STATIC`. Sendes som `vision.content`, 5 Hz og straks ved endring |
| `motion.py` | Bevegelse og programbekreftelse (VI-3). Et kamera som panorerer, endrer over 35 % av ruta i to bilder på rad og regnes som i bevegelse til det har stått stille i 0,5 s (`V5`), så motoren ikke kutter til det (`S1`). Programruta sammenlignes med kameraene i små, normaliserte gråbilder. Sendes som `vision.moving` og `vision.pgm`, 5 Hz |
| `main.py` | `cutcut vision --site … [--device N \| --file video.mp4 \| --synthetic]`. Lytter på `vision.want` fra `core` og sender utsnitt i 10 s etter siste ønske, og på `vision.map` (rutekartet fra setup-hjelperen) |
| `grid.py` | Finner de 2 + 8 rutene og program-siden i et bilde av multiviewen (VI-5) |

`core` tar imot målingene. Fra første gang videolaget melder seg, viser Helse `H-VID-1` (bilder) og `H-VID-3` (programruta mot ATEM, gult etter 3 s uenighet). `S1` bruker både det kameraene selv melder og det videolaget ser; en stille videolag holder ikke kameraer tilbake lenger enn 1 s. Uten videolaget klipper motoren på lyd som før.

Teknikervinduet henter utsnittene fra `GET /api/vision/thumb/{kilde}` (C1…, LAPTOP, PVW, PGM) to ganger i sekundet, på Oversikt og Kameraer. Hvert kall ber `core` sende `vision.want` (høyst hvert 2. sekund), så videolaget bare lager bilder mens noen ser. Når videolaget ikke svarer, vises de tegnede bildene, og bildet kommer tilbake av seg selv.

Maskintesten for kortet er `cutcut hwtest vision` (VI-4, `docs/studio/maskintest.md`).

**Rutekart fra bildet (VI-5, `grid.py`):** setup-steg 6 finner de 2 + 8 rutene i bildet av hele multiviewen (utsnittet `MV`, 960 × 540). Strekene mellom rutene gir et skarpt sprang i lysstyrke langs hele raden eller kolonnen; CutCut leter etter hvert forventet sprang nær der 2 + 8-oppsettet har det, innenfor den delen av bildet som ikke er svart. Svarte kanter og forskyvning fra capture-kortet følges. Program finnes på den røde tally-rammen når ATEM ikke kan leses; ellers kommer kildene fra ATEM. Teknikeren ser forslaget tegnet på bildet, kan dra hjørnene og lagrer. Rutekartet lagres i appen (`setup.multiview_map`) over `equipment/multiview_map.yaml`, følger med i «Lagre oppsett», og sendes til videolaget som `vision.map` med en gang og hvert 10. sekund, så et omstartet videolag får det innen sekunder. Kan ikke endres under opptak.

OpenCV (`opencv-python-headless`) ligger i ekstraen `vision`: `uv sync --extra vision`.
