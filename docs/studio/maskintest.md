# Maskintester på test-PC-en og i studio

Maskintestene sjekker det CI ikke kan: det ekte utstyret. Hver test kjøres med én kommando, og teknikeren følger instruksjonene på skjermen. Til slutt skrives en rapport som Markdown og JSON. Markdown-filen limes inn i GitHub-issuet.

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

## Capture-kortet INOGENI (VI-4)

Stopp videolaget først: kortet kan bare åpnes av ett program om gangen. Med `--user` måles også forsinkelsen, og da må CutCut og Companion kjøre:

```powershell
uv run cutcut hwtest vision --site C:\CutCut\site --device 0 --user tekniker1
```

| Steg | Hva skjer | Svarer på |
| --- | --- | --- |
| V1 Kortet | Kortet åpnes og gir bilder | |
| V2 Format | 1920 × 1080 og bilder per sekund (50 ventet) | |
| V3 Rutekart | Alle ruter med en CutCut-kilde har bilde | |
| V4 Forsinkelse | Bytter PREVIEW mellom to kameraer fem ganger og måler når ATEM og når preview-ruta på PC-en viser det. Endrer ikke program | `H-VID-2` |
| V5 Stabilitet | Leser bilder i `--minutes` (60): tapte bilder, svarte bilder og gjenåpninger | |

Motoren låses (LÅS) mens testen kjører, og låses opp etterpå.
