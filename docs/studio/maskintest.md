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
