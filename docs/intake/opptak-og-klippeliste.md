# Opptak og klippeliste (Q1–Q2)

Dette er det viktigste NTNU kan levere. Uten ekte lydspor og en fasit fra en menneskelig klipper kan reglene bare tunes mot simulatoren.

## Hva som tas opp per episode

3–5 episoder, helst med ulikt antall deltakere (1, 2, 3–4) og minst én med laptop-content.

| Fil | Kilde | Format |
| --- | --- | --- |
| `mic1.wav` … `micN.wav` | RØDECaster multitrack, USB 1, **pre-fader** | 48 kHz, 24 bit, mono per spor |
| `multiview.mp4` | ATEM multiview-utgang via INOGENI (samme oppsett som i drift) | 1080p50 |
| `program.mp4` | ATEM program (ISO-mappen) | som tatt opp |
| `iso/` | ATEM ISO-filer per inngang | som tatt opp |
| `meta.yaml` | Se under | YAML |

Start alle opptak før første ord, og klapp én gang i hendene foran kamera og mic etter start. Klappet brukes til å synkronisere filene.

## `meta.yaml`

```yaml
episode: 2026-11-04-podkast-a
participants:
  - mic: 1
    role: host        # host | guest
    camera: CAM1
  - mic: 2
    role: guest
    camera: CAM2
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
6.80,CAM1,vert starter
21.35,CAM2,gjest svarer
24.10,CAM1,reaksjon fra vert
```

`source` bruker samme ID-er som spesifikasjonen: `CAM1`–`CAM4`, `BIRD`, `CONTENT`, eller layout-navn (`PIP_P1_CONTENT` osv.).

## Personvern

Opptakene inneholder stemme og ansikt. Innhent samtykke, legg dem **ikke** i dette repoet, men på et lagringssted NTNU godkjenner, og skriv stien inn i Q1 i `docs/open-questions.md`. Tester i CI kan bruke korte, anonymiserte utdrag eller syntetiske spor.
