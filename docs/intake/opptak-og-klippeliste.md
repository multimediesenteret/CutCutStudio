# Opptak og klippeliste (Q1–Q2)

Dette er det viktigste Multimediesenteret kan levere. Uten ekte lydspor og en fasit fra en menneskelig klipper kan reglene bare tunes mot simulatoren.

## Hva som tas opp per episode

3–5 episoder, helst med ulikt antall deltakere (1, 2, 3–4) og minst én med laptop-content.

| Fil | Kilde | Format |
| --- | --- | --- |
| `mic1.wav` … `micN.wav` | RØDECaster-ens eget multitrack-opptak til kort eller USB-disk (P11); CutCut bruker USB-strømmen samtidig | 48 kHz, 24 bit, mono per spor |
| `multiview.mp4` | ATEM-ens webkamera-utgang (USB-C, Multi View) på en annen PC, eller gjennomgangen på INOGENI til en opptaker, mens INOGENI går til CutCut | 1080p50 |
| `program.mp4` | ATEM program (ISO-mappen) | som tatt opp |
| `iso/` | ATEM ISO-filer per inngang | som tatt opp |
| `meta.yaml` | Se under | YAML |

Slå på **feilsøkingsmodus** før opptaket (Helse → Feilsøkingsmodus). Start alle opptak før første ord, og klapp én gang i hendene foran kamera og mic etter start. `cutcut opptak importer` (P11) setter lydfilene på plass i tid ut fra feilsøkingsopptaket; klappet er en kontroll og synkroniserer videoen.

## `meta.yaml`

```yaml
episode: 2026-11-04-podkast-a
participants:
  - mic: 1
    role: host        # host | guest
    camera: C1
  - mic: 2
    role: guest
    camera: C2
content_input: 6      # eller null
sync_clap_s: 3.42     # tidspunkt for klappet i mic1.wav
consent: true         # alle deltakere har samtykket til bruk i utvikling
notes: ""
```

## Klippeliste (`cutlist.csv`)

Lages av en erfaren klipper som ser opptaket og noterer hvor *hun eller han* ville kuttet. Den trenger ikke matche det som faktisk ble sendt. Tid er sekunder fra klappet.

```csv
time_s,source,comment
0.00,BIRD,åpning
6.80,CU:P1,programleder starter
21.35,CU:P2,gjest 1 svarer
24.10,CU:P1,reaksjon fra programleder
```

`source` bruker bilde-ID-ene fra spesifikasjonens ordliste: `CU:P1`–`CU:P4` (nærbilde av deltaker), `BIRD`, `WIDE`, `CONTENT`, eller layouter som `PIP:P1+CONTENT`, `PIP:P1+P2`, `QUAD4`, `QUAD3C`.

## Personvern

Opptakene inneholder stemme og ansikt. Alle skriver under på [`samtykke-opptak.md`](samtykke-opptak.md) før opptaket. Opptakene legges **ikke** i dette repoet, men på en intern disk, og slettes når justeringen er ferdig, senest etter 12 måneder (D-072; `cutcut opptak rydd`). Skriv stien inn i Q1 i `docs/open-questions.md`. Tester i CI bruker syntetiske spor.
