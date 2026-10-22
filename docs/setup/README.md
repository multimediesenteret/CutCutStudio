# Oppsettsguide

<!-- Generert fra config/defaults/setup/*.yaml av tools/gen_setup_guide.py. Ikke rediger for hånd. -->

Samme steg som setup-hjelperen på teknikersiden (`/tech` → Oppsett). Hvert steg sjekkes med helsesjekkene i høyre kolonne og godkjennes av teknikeren.

| Steg | Sjekkes med | Fiks for meg |
| --- | --- | --- |
| 1 Nett og IP | `H-NET-*`, `H-ATEM-1`, `H-COMP-1`, `H-PRL-1`, `H-CAM-C*` | – |
| 2 PC og Windows | `H-PC-*`, `H-PROC-*` | – |
| 3 ATEM | `H-ATEM-1`, `H-ATEM-2`, `H-ATEM-4`, `H-VID-2` | Gi inngangene riktige navn |
| 4 Kameraer | `H-CAM-C*`, `H-CAM-MOVE` | – |
| 5 RØDECaster | `H-AUD-1` | – |
| 6 Multiview | `H-VID-1`, `H-VID-2`, `H-VID-3` | – |
| 7 Companion | `H-COMP-1` | – |
| 8 Makroer og grafikk | `H-ATEM-3` | – |
| 9 Pearl og kort | `H-PRL-1` | – |
| 10 Generalprøve | teknikeren | – |

## 1. Nett og IP

Alt utstyr må ha fast IP, ellers finner ikke CutCut det igjen etter en omstart.

1. Koble alt utstyret til **studio-switchen** (egen switch, ingen VLAN): ATEM, Pearl, kameraene og regi-PC-en.
2. Gi hver enhet fast IP etter IP-planen for studioet (ikke DHCP).
3. Regi-PC-en har **to nettverkskort**: ett på studio-switchen med fast adresse i samme nett som utstyret, uten gateway, og ett på **campusnettet** for e-post og oppdateringer.
4. Skriv adressene inn under **Enheter** på oppsettsiden.
5. ATEM svarer på **9910/UDP**, Companion på **HTTP**, Pearl på **443**, kameraene på **VISCA** (OBSBOT) eller **XC** (Canon).

**Sjekk:** `H-NET-*`, `H-ATEM-1`, `H-COMP-1`, `H-PRL-1`, `H-CAM-C*`.

## 2. PC og Windows

Strømsparing og oppdateringer midt i et opptak er den vanligste grunnen til at en studio-PC stopper.

1. Strøm: PC, ATEM, RØDECaster og studio-switchen på **UPS**. BIOS: **slå på etter strømbrudd**.
2. Installer **NVIDIA-driveren** og **Companion** på denne PC-en. INOGENI trenger ingen driver; sett den i en **USB 3-port rett på hovedkortet**.
3. Strømplan: **Høy ytelse**, skjerm og disk slås aldri av.
4. Enhetsbehandling → USB-rotnav: fjern haken for **La datamaskinen slå av denne enheten**.
5. Windows Update → Aktive timer: **07:00–23:00**.
6. Tid: synkroniser mot **NTP** (samme tid som Pearl).
7. Noter driverversjonene for NVIDIA, RØDECaster ASIO, capture-kortet og TWN3. **Ikke oppdater** dem midt i et semester uten å kjøre veiviseren på nytt.

**Sjekk:** `H-PC-*`, `H-PROC-*`.

## 3. ATEM

ATEM må gå i 1080p50 fordi alle kameraene gjør det, og navnene må stemme så CutCut og teknikeren snakker om de samme kildene.

1. ATEM Software Control → Innstillinger → Videostandard: **1080p50**.
2. Innganger: navn **C1**–**C4**, **BIRD**, **LAPTOP**, **C7** (eller trykk «Fiks for meg»).
3. HDMI ut 2: **Multiview**. Layout og ruter som under **Multiview** på oppsettsiden.
4. Mediaspiller 1: «Kun lyd»-grafikken. Mediaspiller 2: bakgrunnen.
5. Sett inn disken for ISO-opptak hvis show-typen tar opp ISO.
6. Trykk **Lagre ATEM som fasit** når alt stemmer.

**Fiks for meg:** «Gi inngangene riktige navn». CutCut gir ATEM-inngangene navnene over. Bildet på lufta endres ikke.

**Sjekk:** `H-ATEM-1`, `H-ATEM-2`, `H-ATEM-4`, `H-VID-2`.

## 4. Kameraer

CutCut flytter bare kameraer som svarer på protokollen og står i manuell modus; ellers kan bildet endre seg uten at noen ba om det.

1. **OBSBOT Tail 2:** fast IP, **VISCA over IP** og **OSC** på, NDI av, HDMI **1080p50**, manuell hvitbalanse og eksponering.
2. **Canon CR-N300:** fast IP, **XC-protokoll** på, egen API-bruker, HDMI/SDI **1080/50P**, manuell hvitbalanse og eksponering.
3. **Fugleperspektiv:** HDMI **1080p50**, manuell hvitbalanse.
4. Kjør maskintesten per kamera: `cutcut hwtest camera --camera C2`.

**Sjekk:** `H-CAM-C*`, `H-CAM-MOVE`.

## 5. RØDECaster

CutCut kutter etter hvem som snakker, så hver mikrofon må komme inn på sitt eget spor.

1. Fader 1–4 = **M1**–**M4**, fader 5 = **laptop**.
2. USB 1: **multitrack, pre-fader**.
3. Hovedmiksen går til ATEM.
4. Under **Mikrofoner** på oppsettsiden: la hver person si noen ord, og mål stillhet. Lekkasjen lagres som fasit.

**Sjekk:** `H-AUD-1`.

## 6. Multiview

CutCut ser kameraene gjennom multiviewen, så rutekartet må vise hvilken rute som er hvilken kilde.

1. ATEM: multiview ut på **HDMI** til INOGENI 4KXUSB3, i **1080p50**.
2. CutCut finner INOGENI på navnet (`video` i devices.yaml) og leser **1080p50 YUY2**.
3. Sett opp multiviewen i ATEM som det anbefalte oppsettet under **Multiview** på oppsettsiden.
4. Trykk **Foreslå fra bildet**: CutCut finner rutene i bildet og leser kildene fra ATEM. Dra hjørnene på plass om noe er skjevt, og trykk **Lagre rutekart**.
5. Forsinkelsen fra ATEM til PC måles med et blinkende testbilde.

**Sjekk:** `H-VID-1`, `H-VID-2`, `H-VID-3`.

## 7. Companion

Teknikerens knapper og ATEM- og Pearl-tilkoblingen går gjennom Companion.

1. Importer **cutcut-pages.companionconfig** (side 10 og 11). Companion har ikke API for import, så dette gjøres for hånd.
2. Legg inn ATEM- og Pearl-tilkoblingen i Companion.
3. Sjekken leser **cutcut_pages_version**.

**Sjekk:** `H-COMP-1`.

## 8. Makroer og grafikk

Layoutene (to- og tredelt bilde) er makroer i ATEM; uten dem kan CutCut bare kutte mellom enkeltbilder.

1. Lag makroene fra spesifikasjonen 7.2 med **riktig nummer og navn**.
2. Legg «Kun lyd»-grafikken og bakgrunnen i mediaspillerne.

**Sjekk:** `H-ATEM-3`.

## 9. Pearl og kort

Pearl tar opp; kortleseren sier hvem som bruker studioet.

1. Pearl: egen bruker for CutCut, én opptaker, inngang fra ATEM, **NTP** på.
2. TWN3-leseren i **COM-port-modus**.
3. Kort-API-nøkkelen legges i Windows Credential Manager, aldri i en fil.
4. Ta et testopptak på **5 s** fra Pearl-menyen og sjekk at det finnes.

**Sjekk:** `H-PRL-1`.

## 10. Generalprøve

Siste sjekk med ekte mennesker: kutter CutCut slik det skal i dette rommet?

1. Alle deltakerne sitter på sine plasser og snakker i **5 minutter**.
2. Følg kuttene i teknikervinduet. Avvik noteres før du godkjenner.

**Sjekk:** teknikeren godkjenner når alt ser riktig ut.
