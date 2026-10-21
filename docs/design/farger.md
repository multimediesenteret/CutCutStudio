# Farger i CutCut Studio

Dato: 2026-10-21 · Status: **standard** (beslutning D-033). Implementeres som tokens i `ui/packages/design`.

Grensesnittet har to slags farge som aldri blandes:

1. **Statusfarger** forteller hva som skjer (spesifikasjonen 12.5). De brukes som flater, rammer og knapper.
2. **Deltakerfarger** forteller *hvem* det gjelder. De brukes bare som markører.

## Statusfarger (uendret fra spesifikasjonen 12.5)

| Token | Betydning | Lys | Mørk |
| --- | --- | --- | --- |
| `--tally` | Program, opptak | `#D7262E` | `#FF4D55` |
| `--live` | Preview, klart, tale | `#1F8A4C` | `#3CCF7D` |
| `--amber` | Venter, advarsel | `#B67600` | `#F0B03C` |
| `--eye` | Valgt, content, bilde | `#2F6FD6` | `#7EA6FF` |

## Deltakerfarger

| Token | Deltaker | Lys tema | Mørkt tema | På RØDECaster | Mikrofonflagg |
| --- | --- | --- | --- | --- | --- |
| `--p1` | **Programleder** (fader 1) | `#D12E8A` magenta | `#FF5CB8` | Rosa/magenta | Magenta |
| `--p2` | Gjest 1 (fader 2) | `#0A93B5` cyan | `#3FCFEA` | Cyan/lyseblå | Cyan |
| `--p3` | Gjest 2 (fader 3) | `#6F4BD8` lilla | `#A68BFF` | Lilla | Lilla |
| `--p4` | Gjest 3 (fader 4) | `#E0640F` oransje | `#FF9442` | Oransje | Oransje |

Navnene i RØDE-kolonnen er nærmeste farge i mikserens palett. Eksakt navn noteres i `baseline.yaml` ved oppsett.

**Hvorfor disse:** de fire er tydelig forskjellige fra hverandre for alle, også ved rød-grønn og blå-gul fargeblindhet (målt med CIEDE2000 på simulert syn: minste avstand mellom to deltakere ≈ 15 i lyst tema og ≈ 13 i mørkt). Magenta er reservert programlederen: den er mest iøynefallende og ligger lengst unna alle statusfargene.

**Kjent nærhet:** oransje (`--p4`) ligger nær «venter» (`--amber`) og lilla (`--p3`) nær «content» (`--eye`) for noen former for fargeblindhet. Derfor reglene under.

## Regler

1. **Deltakerfarge er aldri en statusflate.** Den brukes som: venstrekant på mic-stripen, setebrikke (sirkel med tall), ansiktsboks i multiview-overlegget, felt i tidslinjen, og prikk ved navnet i logg og touch.
2. **Aldri farge alene.** Deltakerfargen står alltid sammen med tall (1–4) og navn. Status står alltid sammen med tekst («PÅ LUFTA», «PREVIEW», «VENTER»).
3. **Programlederen er uthevet** i tillegg til fargen: bredere venstrekant, større setebrikke med ring, fet skrift, alltid øverst eller til venstre.
4. **Fast rekkefølge:** P1–P4 vises alltid i samme rekkefølge og med samme farge, også om en deltaker mangler.
5. **Tekst på farge:** hvit tekst på setebrikken i begge temaer. Fargene brukes ikke til brødtekst på bakgrunn (for lav kontrast i lyst tema for cyan og oransje).
6. **Touch-skjermen** viser plassene med deltakerfarge og tall, så gjesten vet hvilken mikrofon hun eller han skal sitte ved.

## Eksempel

Prototypen (`docs/prototype/cutcut-prototype.html`) bruker fargene: mic-stripene har venstrekant og setebrikke i deltakerens farge, programlederen er uthevet, og tidslinjen viser tale og nærbilder i deltakerens farge.
