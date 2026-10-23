# Maskintester på test-PC-en og i studio

Maskintestene sjekker det CI ikke kan: det ekte utstyret, og om CutCut går i dager uten å vokse. Hver test kjøres med én kommando, og teknikeren følger instruksjonene på skjermen. Til slutt skrives en rapport som Markdown og JSON. Markdown-filen limes inn i GitHub-issuet.

## Lyd: RØDECaster (AU-6)

```powershell
cd C:\CutCut\current
uv run cutcut hwtest audio --site C:\CutCut\site
```

Varer ca. 70 minutter med standard stabilitetstest. Med `--minutes 5` går det raskere. Trengs bare én person ved hver mikrofon underveis, og noen som kan trekke ut USB-kabelen.

| Steg | Hva skjer | Svarer på |
| --- | --- | --- |
| A1 Lydkort | Finner RØDECaster på ASIO (og WASAPI) med 20 kanaler | Q21 |
| A2 Kanalkart | Én og én snakker i 5 s. Stemmen skal være sterkest på egen kanal (mic N på kanal 2N+1) | |
| A3 Synkronitet | Hvor langt hovedmiksen ligger etter mic-sporet | |
| A4 Stabilitet | Lytter i 60 min og teller over- og underflyt og stopp | Q21 |
| A5 USB ut og inn | Kabelen trekkes ut og settes inn igjen. Hvor fort kommer lyden tilbake? | |
| A6 Dempet mic | MUTE på mic 1 mens personen snakker. Er stemmen fortsatt på multitrack-sporet? | Q24 |
| A7 WASAPI-reserve | Reserven leverer lyd | |

- **Hoppe over:** svar `h` ved en instruksjon for å hoppe over steget.
- **Ingen lyd lagres** med mindre du ber om det: `--save-wav` lagrer 5 s fra mic 1 til feilsøking.
- **Rapporten** havner i `C:\ProgramData\CutCut\data\hwtest\`, eller i mappen du gir med `--out`.

## ATEM og Companion (DA-5)

Kjøres med CutCut i gang (tjenesten), Companion i gang og CutCut-sidene importert:

```powershell
uv run cutcut hwtest atem --site C:\CutCut\site --user tekniker1
```

| Steg | Hva skjer | Svarer på |
| --- | --- | --- |
| B1 ATEM | Tilkoblet via atem-bridge, modell, videoformat (1080p50) | Q7 |
| B2 Multiview | Sjekken mot rutekartet (`H-MV`) | |
| B3 Makroer | Layoutmakroene i 7.2 finnes med riktig navn | |
| B4 Companion | Svarer, sidene har riktig versjon, ATEM-tilkoblingen i Companion er OK | |
| B5 Preview-knapper | Trykker hver preview-knapp på side 10. ATEM skal vise riktig inngang, og vi måler hvor fort | |
| B6 TAKE | TAKE CUT. **Endrer program**: bare med bekreftelse, når ingen sender | |

Motoren låses (LÅS) mens knappene trykkes, og låses opp etterpå.

## PTZ-kameraer (CA-5)

Ett kamera av gangen, med kameraets IP og modell i `devices.yaml`. Testen snakker direkte med kameraet med den samme driveren som CutCut bruker. CutCut kan gjerne kjøre samtidig, men da blir `H-CAM-MOVE` rødt mens testen flytter kameraet. Det er ventet.

```powershell
uv run cutcut hwtest camera --site C:\CutCut\site --camera C2
```

| Steg | Hva skjer | Flytter kameraet | Svarer på |
| --- | --- | --- | --- |
| KA1 Protokoll | VISCA svarer, og hvor fort (krav under 200 ms) | nei | |
| KA2 Posisjon | Posisjonen leses og står stille når ingen rører kameraet | nei | |
| KA3 Manuell modus | Manuell hvitbalanse og eksponering (`H-CAM-*`) | nei | |
| KA4 Presets | Lagrer preset 99, snur 10°, henter preset 99 og måler tiden. Gir tallet for `Calibration` (enheter per 10°) | ja | |
| KA5 Laveste zoomfart | Zoomer inn med laveste fart i 2 s og tilbake (`Z3`) | ja | |
| KA6 Fargetemperatur | 3200 K og 5600 K over OSC; R/B-gain skal endre seg (OBSBOT). Står på 5600 K etterpå | nei, men fargen endres | |
| KA7 AI-tracking | Tracking på: gå foran kameraet, det skal følge. Av: det skal stå stille (OBSBOT) | ja | Q16 |

Steg som flytter kameraet eller endrer fargen, spør først. Bekreft bare når kameraet ikke er på program eller preview (I2). Canon hopper over KA6 og KA7 til XC er på plass (Q6).

## Multiview inn i PC-en: INOGENI eller ATEM USB-C (VI-4, D-071)

Stopp videolaget først: enheten kan bare åpnes av ett program om gangen. Med `--user` måles også forsinkelsen, og da må CutCut og Companion kjøre:

```powershell
uv run cutcut hwtest vision --site C:\CutCut\site --user tekniker1
```

Testen bruker metoden som er valgt under Oppsett, steg 6 (med `--user`; ellers `video` i `devices.yaml`), og finner enheten på navnet: «INOGENI» eller «Blackmagic Design». Finner testen den ikke, kan den velges etter nummer med `--device 0`.

**A/B-test av de to metodene (Q41).** Kjør testen én gang per metode, uten å bytte i oppsettet. Koble til begge: INOGENI på multiview-utgangen, og USB-C fra ATEM-en med **Output → Webcam Out → Multi View** valgt i ATEM Software Control.

```powershell
uv run cutcut hwtest vision --site C:\CutCut\site --user tekniker1 --metode inogeni
uv run cutcut hwtest vision --site C:\CutCut\site --user tekniker1 --metode atem_usb
```

Sammenlign V2–V5 i de to rapportene, og se på rutene i teknikervinduet (skarphet i ansikt og munn). Start også et ISO-opptak på ATEM-en mens webkamera-utgangen er i bruk, og sjekk at begge går. V4 lagrer den målte forsinkelsen for metoden som ble testet (admin), og motoren bruker den når den metoden er valgt.

| Steg | Hva skjer | Svarer på |
| --- | --- | --- |
| V1 Kortet | Kortet åpnes og gir bilder | |
| V2 Format | 1920 × 1080 og bilder per sekund (50 ventet) | |
| V3 Rutekart | Alle ruter med en CutCut-kilde har bilde | |
| V4 Forsinkelse | Bytter PREVIEW mellom to kameraer fem ganger og måler når ATEM og når preview-ruta på PC-en viser det. Endrer ikke program. Lagrer ATEM → PC for metoden (`video.delay_ms`) | `H-VID-2`, D-071 |
| V5 Stabilitet | Leser bilder i `--minutes` (60): tapte bilder, svarte bilder og gjenåpninger | |

Motoren låses (LÅS) mens testen kjører, og låses opp etterpå.

## Pearl (SE-3)

Snakker med Pearl med samme klient som CutCut, og passordet fra Credential Manager (`pearl_password`). Med `--user` brukes adressen fra teknikervinduet, og P5 kjøres. Kjøres aldri mens Pearl tar opp: da hoppes P4 og P5 over (I7).

```powershell
uv run cutcut hwtest pearl --site C:\CutCut\site --user tekniker1
```

| Steg | Hva skjer | Godkjent når |
| --- | --- | --- |
| P1 Pearl svarer | Fastvare og svartid | Svar innen 1 s |
| P2 Opptaker | Opptakeren i oppsettet finnes, og hvilken tilstand den har | Ikke i feil |
| P3 Lagring | Ledig plass | Over 10 % ledig |
| P4 Testopptak | Starter, tar opp 5 s og stopper (spør først). Sjekk etterpå at filen finnes på Pearl | Starter innen 10 s og stopper |
| P5 Stopp uten trykk | CutCut starter et opptak for «maskintest»; du stopper det på Pearl selv og trykker Enter | CutCut varsler innen 5 s (10.4) |

## Ansikt og munn på et opptak (P6)

Kjøres på et opptak av multiviewen fra en testsending (`multiview.mp4` fra `docs/intake/opptak-og-klippeliste.md`), ikke på kortet direkte. Trenger modellen (`uv run python tools/fetch_models.py`) og ekstraen `vision`.

```powershell
uv run cutcut hwtest faces --site C:\CutCut\site --file D:\opptak\multiview.mp4
```

| Steg | Hva | Godkjent når |
| --- | --- | --- |
| F1 Ansikt per rute | Andel av rundene med ansikt, og med brukbart ansikt (`V2`) | Minst 90 % brukbart i hver kamerarute |
| F2 Munn i bevegelse | Hvor ofte munnen regnes som i bevegelse per rute, til sammenligning med hvem som snakket | Tallene stemmer med opptaket (vurderes) |
| F3 Tid per runde | Alle rutene analysert, snitt og høyest | Under 200 ms, så 5 runder i sekundet holder |

`--rounds` (standard 1500, ca. 5 minutter) gir hvor mye av opptaket som brukes. Tallene brukes til å justere grensene i `vision/faces.py` og `V1`/`V2` før `video_confirm` prøves (`docs/studio/testdag.md` 4.3 og 5.5).

## 72-timerstesten (SO-8)

Kjøres ved siden av CutCut-tjenesten i hele testperioden (spes. 10.4). Den logger ikke inn og endrer ingenting: prosessene og helsen leses fra `/api/health`, og minne og håndtak måles med psutil på samme PC.

```powershell
uv run cutcut hwtest soak --site C:\CutCut\site --hours 72
```

| Steg | Hva | Godkjent når |
| --- | --- | --- |
| D1 Minne | RSS per prosess, med barneprosesser | Under 5 % vekst etter første time (eller under 10 MB) |
| D2 Håndtak | Håndtak per prosess (åpne filer utenfor Windows) | Under 5 % vekst etter første time (eller under 50) |
| D3 Omstarter | Ny pid eller kortere oppetid mellom to målinger | Ingen |
| D4 Tilkoblinger | `H-ATEM-1`, `H-COMP-1`, `H-PRL-1`, `H-CAM-*` og `H-AUD-1` | Ingen går fra grønn til noe annet |
| D5 Helse | Samlet status fra `/api/health` | Grønn eller gul i alle målinger |

- **Første time** regnes ikke med i veksten: modeller og hurtigbuffere fylles da.
- **Målingene** skrives fortløpende til `72-timer-<tid>.jsonl` i rapportmappen. `--every 1 --hours 2` gir en rask prøve.
- **Ctrl+C** avbryter, og rapporten skrives med det som er målt. Er testen for kort til å vurdere vekst, sier D1 og D2 det.

## Akseptanse fra loggen (T-M3)

Regner ut kriteriene i 10.4 som kan måles fra det CutCut har skrevet ned, for en periode: en testsending, en dag eller hele studioperioden. Leser beslutningene i databasen og, når feilsøkingsmodus var på, opptaket i `data\debug`. Sender ingenting, og CutCut kan kjøre samtidig.

```powershell
uv run cutcut hwtest akseptanse --since "2026-11-04 09:00" --until "2026-11-04 09:40"
```

| Steg | Kriterium | Krever |
| --- | --- | --- |
| A1 Kutt innen 150 ms | 95 % av kuttene når Companion innen 150 ms etter beslutningen; tregeste vises | Feilsøkingsmodus på |
| A2 Kuttpunkt | Minst 90 % av taler-kuttene på `K1` eller `K2` | – |
| A3 Preview før TAKE | Minst 300 ms på preview i 95 % av taler-kuttene | – |
| A4 Ingen kutt tilbake | Ingen kutt tilbake til forrige bilde innen 4 s (`H2`); en persons kutt teller ikke | – |
| A5 Kutt og overstyringer | Kutt per 10 min og hvor ofte en person tok over, til operatørens vurdering (Q2) | – |

`--data` er CutCuts datamappe (standard `C:\CutCut\data`). Uten `--since` brukes dagen i dag.

## Feilsøkingsmodus

Ikke en test, men det som gjør testene og feilsøkingen mulig. Teknikervinduet → **Helse** → **Feilsøkingsmodus** → 1, 8 eller 24 timer (admin); den slår seg av selv. Mens den er på:

- tas alt som kommer inn til motoren opp (lyd- og videomålinger, ATEM, kameraer), sammen med hver beslutning og hvor lang tid hvert Companion-kall tok, i `data\debug\<dato>T<time>.jsonl.gz`;
- logger `core` mer (DEBUG);
- vises «Feilsøking» øverst i teknikervinduet.

Opptaket tas vare på i 7 dager og stopper selv ved 5 GB. Det har ingen passord, PIN eller kortnummer. «Feilsøkingspakke» under Logg tar med siste time. Ha den på hele studioperioden (`testdag.md` 1.11).
