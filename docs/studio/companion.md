# Companion-sidene til CutCut

CutCut klipper ved å trykke på knapper i Companion (spesifikasjonen 7.1, ADR-0009):
- **Side 10 «REGI»** brukes av motoren.
- **Side 11 «OPERATØR»** er for mennesker og for reservekutt.

Knappene lages fra studio-oppsettet, så de alltid stemmer med det motoren trykker på (`site/<studio>/equipment/companion_map.yaml` og inngangene i `shows/`).

## Filene

`uv run cutcut companion-pages --site site/ntnu-studio` skriver tre filer til `site/ntnu-studio/equipment/companion/`:

| Fil | Innhold |
| --- | --- |
| `cutcut-side-10.companionconfig` | Rad 0 setter preview (kamera, fugleperspektiv, laptop, SuperSource). Rad 1–2 kjører layoutmakroene (7.2). Rad 3 er TAKE CUT og TAKE MIX |
| `cutcut-side-11.companionconfig` | Direkte programkutt for nødbruk og «Kun lyd» (mediaspiller 1 på program) |
| `cutcut-variabler.companionconfig` | Variablene motoren skriver (`regi_*`) og `cutcut_pages_version` |

Filene er i Companions eget eksportformat (versjon 12, Companion 4.3). Companion 5.x importerer det og oppgraderer selv. En test feiler hvis filene ikke stemmer med studio-oppsettet. Kjør kommandoen på nytt etter endringer i knappekart eller innganger.

Når knappene endres slik at gamle sider ikke lenger passer, økes `companion.pages_version` i `devices.yaml`. Helsesjekken `H-COMP-1` blir da rød til de nye filene er importert.

## Slik importerer du (én gang per studio, og ved ny versjon)

1. Åpne Companion på regi-PC-en (`http://127.0.0.1:8000`) og gå til **Import / Export**.
2. **Eksporter først hele oppsettet** som sikkerhetskopi.
3. Importer variablene:
   - Velg **Import**, deretter `cutcut-variabler.companionconfig`, deretter **Full import**.
   - Velg **Import, preserving unselected components** og huk av **bare** *Custom Variables*. Andre sider og tilkoblinger berøres ikke.
4. Importer side 10:
   - Velg **Import**, deretter `cutcut-side-10.companionconfig`, deretter **Buttons**.
   - Velg side **10** som mål.
   - Når Companion spør om tilkoblingen «ATEM», velg studioets ATEM-tilkobling (modulen *Blackmagic: ATEM*).
5. Gjør det samme med `cutcut-side-11.companionconfig` til side **11**.
6. Sjekk i teknikervinduet under **Helse** at `H-COMP-1` er grønn og viser «sider v1».

## Hva knappene gjør

- **Preview og program:**
  - Preview og program settes med ATEM-modulens handlinger «ME: Set Preview input» og «ME: Set Program input» på M/E 1.
  - Inngangsnumrene kommer fra `shows/`: C1–C4 på 1–4, fugleperspektiv på 6, laptop på 7 (D-054).
  - SuperSource er 6000, og mediaspiller 1 er 3010.
- **Layouter:** kjører ATEM-makroene med numrene i spesifikasjonen 7.2. 10–13 er PiP med content, 20–25 er to og to, 30 er QUAD4, 31 er QUAD3C og 40 slår layouten av. Makroene lages i ATEM Software Control.
- **TAKE:** CUT og MIX («Perform CUT/AUTO transition»).

Maskintesten (DA-5) trykker på hver knapp og leser ATEM tilbake.
