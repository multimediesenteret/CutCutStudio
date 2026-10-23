# Research: multiview fra ATEM-ens webkamera-utgang (USB-C) i stedet for INOGENI

Dato: 2026-10-23 · Status: begge metodene er bygget og kan velges; hvilken som blir standard avgjøres av A/B-testen i studioperioden (Q41, D-071)

## Spørsmålet

Nyere Blackmagic-miksere har en USB-C-utgang som Windows ser som et vanlig webkamera («Webcam Out»). I ATEM Software Control kan man velge hva den skal vise, også **Multi View** (Outputs → Webcam Out → Multi View). Da kan regi-PC-en ta multiviewen rett fra mikseren over én USB-kabel, uten INOGENI 4KXUSB3 i mellom. Holder det for videolaget, og hva må justeres?

## Det vi vet

| Fakta | Kilde |
| --- | --- |
| ATEM Television Studio HD8 ISO har **2 × USB-C** som brukes til «external drive recording, webcam out, software control, software updates and switcher connection» | Blackmagic, tekniske data for HD8 ISO |
| Webkamera-utgangen gir **720p eller 1080p i programmets bildefrekvens**, altså 1080p50 hos oss | Blackmagic, tekniske data for HD8 ISO |
| Blackmagic oppgir ikke om multiviewen kan rutes til webkamera-utgangen på HD8 ISO. På ATEM Mini Extreme ISO G2 står det uttrykkelig at multiviewen er «routable to … 2 × USB-C webcam outputs» | Blackmagic, tekniske data for HD8 ISO og ATEM Mini Extreme ISO G2 |
| ATEM Mini-manualen: «You can also route sources to the webcam output using ATEM Mini Extreme switchers». På enklere modeller viser USB-utgangen alltid program | ATEM Mini-manualen (s. 121), og Manchester Video |
| Skjermbildet fra Multimediesenteret (ATEM Mini Extreme ISO): Outputs → Webcam Out har «Multi View» i lista | Eier, 2026-10-23 |
| Windows ser mikseren som et webkamera med navnet «Blackmagic Design», uten driver | ATEM Mini-manualen (s. 11) |
| B&H oppgir USB-utgangen på HD8 ISO som «USB-C (10-Bit 4:2:2 RGB)». Brukere melder at ATEM Mini komprimerer webkamerabildet som MJPEG | B&H; Manchester Video |
| På ATEM Mini Pro kan man ikke ta opp på lokal SSD mens USB-porten brukes som webkamera. HD8 ISO har to porter og intern disk, men ingen kilde sier sikkert at ISO-opptak og webkamera går samtidig | Manchester Video; Blackmagic, tekniske data |
| Bare én PC kan være koblet til USB-porten om gangen. Kabelen må være USB-C 3.1 Gen 1; vanlige telefonkabler er ofte for dårlige | Manchester Video |
| Brukere melder om forsinkelse og avvikende kontrast (fargeområde) på webkamera-utgangen | Blackmagic-forumet, «ATEM Mini – USB-C Output Contrast and Delay» |
| INOGENI 4KXUSB3: UVC uten driver, YUY2/NV12 **ukomprimert** på USB 3; forsinkelse er ikke oppgitt | INOGENI, datablad |

## Hva det betyr for CutCut

| | INOGENI 4KXUSB3 | ATEM webkamera-utgang |
| --- | --- | --- |
| Utstyr | Egen boks, HDMI-kabel fra multiview-utgangen og USB 3 til PC-en | Ingen ekstra boks: én USB-C-kabel fra mikseren |
| Bildet | Ukomprimert YUY2 | Sannsynligvis komprimert (MJPEG); kan gi gjenstander i de små rutene og bruker CPU på å pakke ut |
| Forsinkelse | Ikke oppgitt; måles | Ikke oppgitt; brukere melder om noe mer forsinkelse; måles |
| Multiview-utgangen | Opptatt av INOGENI | **Ledig** til en skjerm i regien |
| Avstand | HDMI kan gå langt; USB-delen er kort | USB 3 er kort (rundt 3 m uten aktiv kabel): mikseren må stå nær PC-en |
| Risiko | Kjent oppsett, testet i CI med samme kode | Må bekreftes på HD8 ISO: at Multi View finnes i Webcam Out-lista, at bildet holder 1080p50, og at **ISO-opptaket virker samtidig** |

Rutekartet er det samme: begge viser den samme 1080p-multiviewen.

## Hva som er bygget (D-071)

- **Valg i oppsettet:** «Multiview-capture» under Oppsett, steg 6 (Multiview), og i Utstyr og nettverk: *INOGENI 4KXUSB3* (standard) eller *ATEM webkamera-utgang (USB-C)*. Valget lagres i appen (`video.method`) og tas i bruk av videolaget med en gang, uten omstart (bussmeldingen `vision.source`).
- **Navn på enheten:** CutCut finner kortet på navnet: «INOGENI» eller «Blackmagic Design». Navnet kan overstyres (`video.name`) hvis Windows kaller enheten noe annet, for eksempel når regi-PC-en også har et DeckLink-kort.
- **Forsinkelse:** motoren venter på bildet så lenge som forsinkelsen tilsier før munnbevegelse og lekkasjesjekken (V1) brukes. Utgangspunkt per metode: 60 ms for INOGENI og 120 ms for ATEM-utgangen. `cutcut hwtest vision` (V4) måler den riktige verdien og lagrer den for metoden som er valgt (`video.delay_ms`); den målte verdien gjelder foran utgangspunktet.
- **Maskintesten** skriver metoden i rapporten, så de to kan sammenlignes: format og bildefrekvens (V2), om rutene har bilde (V3), forsinkelse (V4) og stabilitet (V5).

## Det som må testes i studio (testdag.md)

1. I ATEM Software Control på HD8 ISO: finnes **Outputs → Webcam Out → Multi View**?
2. Kjør `cutcut hwtest vision` med begge metodene og sammenlign V2–V5.
3. Start ISO-opptak på ATEM-en mens webkamera-utgangen er i bruk: går begge?
4. Se på rutene i teknikervinduet: er bildet skarpt nok til ansikt og munn (P6)?
5. Velg standard ut fra resultatet og noter det i Q41.

## Kilder

- [ATEM Television Studio HD8 ISO, tekniske data (Blackmagic)](https://www.blackmagicdesign.com/products/atemtelevisionstudio/techspecs/W-APS-21)
- [ATEM Mini Extreme / Extreme ISO G2, tekniske data (Blackmagic)](https://www.blackmagicdesign.com/products/atemmini/techspecs/W-APS-17)
- [ATEM Television Studio HD8 ISO hos B&H](https://www.bhphotovideo.com/c/product/1971566-REG/blackmagic_design_swatemtvstc_hd08iso_2_atem_television_studio_hd8.html)
- ATEM Mini-manualen (Blackmagic, lagt ved av eier 2026-10-23), s. 10–11 og 121
- [Impossible features of the ATEM Mini and Mini Pro (Manchester Video)](https://www.manchestervideo.com/2020/06/24/impossible-features-of-the-blackmagic-design-atem-mini-and-mini-pro/)
- [ATEM Mini – USB-C Output Contrast and Delay (Blackmagic-forumet)](https://forum.blackmagicdesign.com/viewtopic.php?t=108315)
- [INOGENI 4KXUSB3 datablad](https://www.fullcompass.com/common/files/88448-4KXUSB3SpecSheet.pdf)
