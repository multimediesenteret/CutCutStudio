# Auto-regi for videopodcast – evaluering og arkitektur

Oct 20, 2026 · @Magnus Lian

Dette er evalueringen og bakgrunnen for valgene. Den samlede app-spesifikasjonen som skal bygges ligger i fanen App-spesifikasjon, og gjelder der de to er uenige.

## Kortversjon

Anbefaling: bygg en egen «regimotor» som lytter på RØDECaster-kanalene, tar beslutninger med en eksplisitt regelmotor og sender kutt via Companion til ATEM Mini Extreme ISO. Det er fullt gjennomførbart med hyllevare: alle ledd har dokumenterte grensesnitt, og ingen del krever ny forskning.

Det som skiller proff klipping fra «video følger lyd» er ikke reaksjonstid, men regi-grammatikk: bekreftet taletur før kutt, minimum bildelengde, ignorering av «mm/ja», egen håndtering av krysstale og latter, reaksjonsbilder og totaler med variasjon. Rask respons alene gir nervøs klipping hvis reglene rundt ikke er strenge nok.

Sannsynlige årsaker til at dagens oppsett klipper dårlig (må verifiseres i studio):

- **Lekkasje mellom mikrofoner (bleed):** gjesten høres svakt i vertens mic, og systemet tror begge snakker.
- **Feil lydpunkt:** mates detektoren post-fader eller med main mix, påvirker fader og mute deteksjonen.
- **Korte innskudd:** latter, «mm» og hosting utløser kutt fordi bekreftelsestiden er for kort.
- **Ingen synlig forklaring:** når operatøren ikke ser *hvorfor* et kutt skjedde, er det umulig å tune.

Alt kjøres live, uten etterarbeid, på én Windows-PC med NVIDIA-skjermkort. Tre grep gir mest effekt: (1) per-kanal tale-deteksjon med nevralt nettverk pluss relativ nivåsammenligning, (2) en regelmotor der hvert kutt logges med årsak, og (3) «øyne»: ATEM-multiviewen tas inn via et capture-kort, slik at systemet ser munnbevegelse, ansikter og utsnitt. Bildet brukes til å bekrefte hvem som snakker, avvise lekkasje, velge reaksjonsbilder og rette opp utsnitt på kameraer som ikke er på lufta.

## Hva slike systemer gjør

Automatisk klipping av samtaler med flere kameraer er en kjent oppgave, og mønstrene er etablerte praksis, ikke nyvinning:

- **Lyd bestemmer *når*, oppsettet bestemmer *hvordan*.** Hvem som snakker, avgjøres per mikrofon. Bildet hentes fra forhåndsdefinerte vinkler.
- **Et kamera på lufta flyttes aldri.** Innramming rettes bare på kameraer som ikke er på program eller preview.
- **Regler mot kutt på hoste, latter og enkeltord**, med minimum bildelengde og bekreftelsestid.
- **Operatøren kan alltid overstyre med ett trykk**, og systemet slåss ikke mot det.
- **Det som skiller resultatene**, er hvor gjennomsiktig regi-logikken er: kan operatøren se *hvorfor* et kutt skjedde, kan reglene justeres.

CutCut Studio bygger på de samme prinsippene, med regler som logges med årsak for hvert kutt, og som kan finjusteres live.

## SOTA-teknologi

Med én mikrofon per person er lyd alene nok til å vite hvem som snakker; det vanskelige er å skille ekte tale fra lekkasje og småord. Riktig stabel er fem lag: de tre første er lyd og regler og er obligatoriske, de to siste er videolaget.

| Lag | Teknologi | Hva den løser | Kostnad i drift |
| --- | --- | --- | --- |
| 1. Tale-deteksjon per kanal | [Silero VAD](https://pypi.org/project/silero-vad) (MIT, ONNX) | Skiller tale fra pust, bord-dunk, latter-støy. Under 1 ms per 30 ms lydblokk på én CPU-tråd | Ubetydelig, CPU |
| 2. Dominans og bleed-avvisning | Egen kode: nivå i dB relativt til de andre kanalene, + lekkasjematrise målt ved oppsett | Gjestens stemme i vertens mic. Kanal regnes aktiv bare hvis VAD > terskel OG den ligger X dB over alle andre | Ubetydelig, CPU |
| 3. Regimotor | Tilstandsmaskin med eksplisitte regler (se Klipperegler) | Bekreftelsestid, min/maks bildelengde, krysstale, reaksjonsbilder | Ubetydelig, CPU |
| 4. Ansikt og munn | Ansiktsdetektor (SCRFD eller YuNet) + ansiktspunkter (MediaPipe Face Landmarker) | Finner hvem som er i bildet, munnåpning, hoderetning og smil per person | GPU, 10–15 bilder/s per kamera |
| 5. Audiovisuell taler-deteksjon | [Light-ASD](https://ar5iv.labs.arxiv.org/html/2303.04439): ca. 1 M parametere, 94,1 % mAP, 4,5 ms per bilde på RTX 3090 | Kombinerer munnbevegelse med lyd og sier om personen i bildet faktisk er den som høres | GPU, lav |

Tre funn påvirker designet direkte:

- **RØDECaster gir rene kanaler over USB.** USB 1 kan settes i multitrack, og hver kanal kan hentes ut pre-fader, så fader og mute ikke påvirker deteksjonen. Ingen splitterkabler trengs. På Windows leses sporene via RØDECaster sin ASIO-driver.
- **Lyd bestemmer, bilde bekrefter.** Med én mic per person er lyden raskest og sikrest. Bildet kommer 100–150 ms senere, og brukes derfor innenfor bekreftelsesvinduet som ja/nei og til å velge *hvilket* bilde, ikke til å starte kutt alene.
- **Kamerastyring og klipp skal være adskilt.** Innramming korrigeres bare når kameraet er off air, og kamerastyringen bestemmer ikke når det klippes. Samme prinsipp gjelder for utsnittskorrigering fra videolaget.

## Arkitektur

Én Windows-PC i studio gjør hele jobben: den leser RØDECaster-kanalene, ser multiviewen fra ATEM, tar beslutninger og sender kommandoer til Companion og kameraene. Companion forblir laget dere kjenner, og Stream Deck kan fortsatt brukes til manuell overstyring.

&#91;embedded content: signalflyt · lyd inn, kutt og kamerastyring ut\]

Regelmotoren er det eneste nye «smarte» leddet; alt annet er dokumenterte grensesnitt.

| Ledd | Anbefalt valg på Windows | Merknad |
| --- | --- | --- |
| Maskin | Windows 11 Pro, NVIDIA RTX-skjermkort, kablet nett | NVIDIA fordi ONNX Runtime med CUDA/TensorRT er best støttet. Companion kjører på samme PC |
| Lyd inn | RØDECaster ASIO-driver, USB 1 multitrack, pre-fader | Motoren eier ASIO-enheten. Ikke installer Virtual Devices-driveren: den er [ikke kompatibel med ASIO](https://help.rode.com/hc/en-us/articles/11891033629839-What-is-the-Virtual-Devices-Driver-for-the-R%C3%98DECaster-Pro-II-Duo) |
| Video inn | ATEM HDMI-ut 2 satt til multiview → USB-capture 1080p (UVC). Ingen NDI | ATEM Mini Extreme har [2 HDMI-utganger og multiview med 4–16 ruter](https://www.syntex.cz/media/ant/Syntex_Blackmagic_Design_ATEM_Mini_vs_Pro_vs_Extreme_EN_2_2021.pdf). Velg færrest mulig ruter som viser alle kameraene |
| Kjerne | Python 3.12 (asyncio): PortAudio/ASIO for lyd, OpenCV eller FFmpeg for capture, ONNX Runtime for modellene | Python fordi alle modellene finnes der. DirectML som reserve hvis GPU-en ikke er NVIDIA |
| Motor → Companion | [HTTP Remote Control](https://companion.free/user-guide/v4.2/remote-control/http-remote-control): `POST /api/location/<side>/<rad>/<kol>/press` og `POST /api/custom-variable/<navn>/value?value=…` | Companion kutter på ATEM. Én knapp per vinkel, som også lyser på Stream Deck |
| Motor ↔ ATEM (reserve) | PyATEMMax (Python) eller [atem-connection](https://npmjs.com/package/atem-connection) | Leser tally og program-kilde; kan kutte direkte hvis Companion feiler |
| Motor → kameraer | Egen kameradriver per merke over IP (se Kamerastyring per modell) | Motoren styrer kameraene direkte, fordi utsnitt og farge krever posisjon og verdier tilbake |
| GUI | FastAPI + WebSocket, åpnes i nettleser på studionettet | Viser multiview med overlegg (ansiktsbokser, munn-indikator, fargeavvik) i 5 bilder/s |
| Drift | Kjøres som Windows-tjeneste med autostart og vakthund | Windows Update og strømsparing styres utenfor sendetid; USB-strømsparing slås av |

OBSBOT sin egen AI-tracking anbefales av under sending. Utsnitt rettes i stedet av videolaget, og bare på kameraer som ikke er på program.

## Øyne: videolaget

Multiviewen gir systemet syn med én kabel, og viser nøyaktig det ATEM ser. Bildet brukes til å bekrefte og velge, mens lyden fortsatt starter kuttene, fordi bildet kommer 100–150 ms senere (anslag: capture + analyse).

| Signal fra bildet | Brukes til | Regel |
| --- | --- | --- |
| Munnbevegelse per person | Bekrefter at mic-en er ekte tale. Mic aktiv men munn i ro = lekkasje | V1 |
| Ansikt funnet, størrelse og plassering | Kutter aldri til et tomt, halvt eller uskarpt bilde; velger total i stedet | V2 |
| Audiovisuell taler-score (Light-ASD) | Avgjør ved krysstale, latter og hvis to deler mic | V1 |
| Reaksjon: smil, nikk, hodebevegelse | Velger det mest levende reaksjonsbildet under lange svar | V3 |
| Utsnittsfeil: hodeplass, blikkrom, bildestørrelse | Små VISCA-justeringer mens kameraet er off air | V4 |
| Kamera i bevegelse | Vinkelen er ugyldig til bildet står stille | V5 |
| Hoderetning mot en annen person | Forvarsel: øker prioriteten til den det ses mot (eksperimentelt) | V6 |

Oppløsningen er det viktigste å teste. I en 16-ruters multiview på 1080p er hver rute omtrent 480×270 piksler. Ansikter i nærbilder blir da store nok for munnanalyse, mens ansikter i totalen blir små. Light-ASD bruker ansiktsutsnitt på 112×112 piksler.

Hvis multiview ikke gir skarpe nok ansikter, er neste steg å ta kameraenes andre utgang direkte inn i PC-en, uten NDI. Canon CR-N300 har [både HDMI og 3G-SDI](https://www.fullcompass.com/common/files/60067-CRN300DataSheet.pdf), så SDI kan gå til ATEM eller en omformer mens HDMI går til et capture-kort med flere innganger. OBSBOT Tail 2 har én HDMI-utgang, og trenger da en HDMI-splitter.

Videolaget gir også et raskere oppsett: hver person snakker noen sekunder, og systemet kobler selv mic til kamera ved å se hvem sin munn beveger seg.

## Kamerastyring per modell

Alle merkene kan styres over IP, men med ulike protokoller. Motoren får derfor én felles kameradriver med samme kommandoer for alle, og en liten adapter per merke. Start med OBSBOT Tail 2 og Canon CR-N300.

| Merke | Protokoll over IP | Farge og eksponering | Status |
| --- | --- | --- | --- |
| [OBSBOT Tail 2](https://www.obsbot.com/explore/obsbot-tail-air/visca-over-ip) | VISCA over IP (bekreftet av OBSBOT) + [OSC](https://www.obsbot.com/webcam/osc) for AI-tracking | Hvitbalanse via VISCA; om R/B-gain finnes må sjekkes i OBSBOTs VISCA-tabell | Fase 1 |
| [Canon CR-N300](https://www.fullcompass.com/common/files/60067-CRN300DataSheet.pdf) | Canon XC-protokoll (HTTP), VISCA over IP som reserve | Via XC: R/B, kelvin, iris, gain, lukker, metning. Kameraet må stå i manuell for å kunne styres | Fase 1 |
| Panasonic AW-UE | [HTTP-kommandoer](https://eww.pass.panasonic.co.jp/pro-av/support/content/guide/DEF/UE150/AW-UE150HE145_InterfaceSpecification_E.pdf) `/cgi-bin/aw_ptz` og `/cgi-bin/aw_cam` | R-gain `OSG:39`, B-gain `OSG:3A` i AWB- eller VAR-modus. Minst 40 ms mellom bevegelseskommandoer | Fase 2 |
| Sony BRC/SRG | [VISCA over IP, UDP 52381](https://applicationmarket.crestron.com/content/Help/Sony/Sony_BRC-X400_SRG-X_series_Help_v1.0.pdf) | R/B-gain i manuell hvitbalanse | Fase 2 |

Felles kommandoer i driveren: hent preset, lagre preset, flytt litt (pan/tilt/zoom), les posisjon, sett hvitbalanse (kelvin eller R/B), sett eksponering, AI-tracking av/på, og status. Hver driver har sin egen kø med tempogrense, slik at et kamera aldri får kommandoer raskere enn det tåler.

## Fargematching

Fargematching gjøres i kameraene, styrt fra multiviewen: systemet måler alle bildene samtidig og justerer hvert kamera mot et referansekamera. ATEM Mini-serien har så vidt jeg vet ikke fargekorreksjon per inngang for kameraer fra andre merker, så korreksjonen må skje i kameraet.

1. **Lås kameraene:** slå av automatisk hvitbalanse og automatisk iris på alle, ellers overstyrer kameraet justeringene.
2. **Referanse i bildet:** sett et grått kort eller et fargekart der alle kameraene ser det, i showlyset.
3. **Mål:** systemet finner kortet i hver rute og regner ut avvik i hvitbalanse og lysstyrke mot referansekameraet.
4. **Juster og gjenta:** motoren sender kelvin eller R/B-gain og eksponering, måler på nytt og gjentar 3–5 ganger til avviket er under grensen.
5. **Lagre:** verdiene lagres per kamera og show-oppsett, og kan hentes med ett trykk neste gang.

Under sending endres aldri farge på et kamera som er på lufta. GUI-et viser bare et varsel hvis et kamera driver, og operatøren kan godkjenne en liten korreksjon mens kameraet er off air. Multiviewen er nedskalert, men fungerer for gjennomsnittsfarger på et kort. For finjustering av hudtoner må man se på et kamera i full oppløsning.

## Oppsett for 1–4 deltakere

Alle har hver sin mic. Motoren velger regelsett ut fra antall deltakere i show-oppsettet, og samme oppsett lagrer kameraplan, vinkler og fargeverdier.

| Deltakere | Kamera-plan (forslag) | Hva motoren gjør |
| --- | --- | --- |
| 1 | 2 kamera: nær + halvtotal | Ingen taler-bytter. Bytter vinkel i pauser hvert 12–25 s, og går til total ved stillhet |
| 2 | 3 kamera: to nærbilder + to-skudd (eller SuperSource-split) | Krysstale og ping-pong går til to-skudd. Reaksjonsbilde er den andre personen |
| 3 | 4 kamera: tre nærbilder + total | Krysstale går til total. Reaksjonsbilde velges blant to lyttere |
| 4 | 5 kamera: fire nærbilder + total | Som for 3, men lengre bekreftelse ved avbrudd, fordi flere snakker i munnen på hverandre |

Et PTZ-kamera kan dekke to roller, for eksempel nærbilde og total via presets, men bare hvis det får flytte seg mens det ikke er på lufta. ATEM Mini Extreme ISO har 8 innganger, så 5 kamera går fint.

## Klipperegler

Tolv regler dekker det en erfaren bilderegissør gjør i en samtale med 2–4 personer. Verdiene er startpunkter for tuning i studio, ikke målte fasitsvar.

| # | Regel | Hva den gjør | Rolig | Standard | Energisk |
| --- | --- | --- | --- | --- | --- |
| 1 | Aktiv tale | Mic er «aktiv» når VAD > terskel OG nivå ligger over alle andre mic-er med margin | VAD 0,7 · 9 dB | VAD 0,6 · 6 dB | VAD 0,5 · 4 dB |
| 2 | Bekreftelse | Ny taler må snakke sammenhengende så lenge før kutt | 1200 ms | 800 ms | 500 ms |
| 3 | Minste bildelengde | Ingen nye kutt før bildet har stått så lenge | 4,0 s | 2,5 s | 1,8 s |
| 4 | Småord-filter | Ytringer kortere enn dette («mm», «ja», latter) ignoreres | 1,5 s | 1,0 s | 0,7 s |
| 5 | Krysstale | To eller flere aktive samtidig i mer enn X → to-skudd eller total | 1,5 s | 1,0 s | 0,8 s |
| 6 | Ping-pong | Mer enn N bytter mellom samme to personer innen 10 s → to-skudd | 3 | 4 | 5 |
| 7 | Lang monolog | Etter X på samme taler → reaksjonsbilde av lytter i 2–3 s, så tilbake | 25 s | 15 s | 10 s |
| 8 | Stillhet | Ingen aktiv mic: bli stående; etter X → total | 4 s | 3 s | 2 s |
| 9 | Kutt-timing | Hvis gjeldende taler har en kort pause (> 150 ms) innenfor 300 ms, vent og kutt i pausen | på | på | av |
| 10 | Variasjon | Samme total/vinkel ikke to ganger på rad; vektet tilfeldig valg blant gyldige vinkler | på | på | på |
| 11 | PTZ-sikkerhet | Kamera på program flyttes aldri. Preset kjøres off air, og vinkel er ikke gyldig før den har «satt seg» | 1,5 s | 1,0 s | 0,8 s |
| 12 | Prioritet | Vekt per person (vert, gjest), brukes når to er like sterke | vert 1,2 | vert 1,1 | 1,0 |

Overstyring vinner alltid over regler: LÅS holder et kamera til det slippes, TOTAL NÅ tar total i ett bilde, og AUTO AV fryser motoren uten å endre noe på ATEM.

Hvert kutt logges med regelnummer og målte verdier, for eksempel: «KUTT → CAM2 · regel 2: Mic 2 aktiv 0,82 s (krav 0,80) · bildet hadde stått 3,4 s (krav 2,5)». Det er dette som gjør systemet mulig å tune.

Bilde-reglene virker oppå lydreglene. Er videolaget nede, faller motoren tilbake til bare lyd uten å stoppe.

| # | Regel | Hva den gjør | Startverdi |
| --- | --- | --- | --- |
| V1 | Munn bekrefter | Munnbevegelse i riktig kamera korter ned bekreftelsestiden; mic aktiv uten munnbevegelse i 400 ms regnes som lekkasje | Bekreftelse × 0,6 |
| V2 | Gyldig bilde | Ansikt må finnes, være innenfor bildet og ha riktig størrelse, ellers velges total eller to-skudd | ±25 % av målstørrelse |
| V3 | Beste reaksjon | Reaksjonsbilde velges etter høyest reaksjons-score blant lytterne | Siste 3 s |
| V4 | Utsnitt off air | Kamera som ikke er på program justeres når feilen er stor nok, men fryses så snart det er kandidat til neste kutt | Feil > 8 % av bildehøyden |
| V5 | Kamera i ro | Vinkel er gyldig først når bildet har stått stille | 0,5 s |
| V6 | Blikk (eksperimentell) | Taleren ser mot en person: den personens prioritet økes litt | Vekt × 1,1 |

## GUI

Skjermen svarer på tre spørsmål til enhver tid: hva er på lufta, hva vil motoren gjøre neste, og hvorfor. Alt annet ligger i en innstillingsfane.

- **Program-feltet øverst:** stort navn på aktivt bilde (f.eks. «CAM 2 · Gjest nær»), hvor lenge det har stått, og en fremdriftslinje mot minste bildelengde.
- **Multiview med overlegg:** live miniatyr av hvert kamera med ansiktsboks, munn-indikator og et merke for gyldig bilde eller «justerer utsnitt».
- **Én stripe per mikrofon:** navn, nivåmåler, VAD-sannsynlighet, munnbevegelse fra kameraet og status med farge: stille, snakker, bekrefter (med nedtelling), ignorert som småord, ignorert som lekkasje.
- **«Neste beslutning»:** én setning, f.eks. «Venter: Mic 3 må snakke 0,3 s til».
- **Beslutningslogg:** siste 30 kutt med regel og målte verdier, nyeste øverst.
- **Tidslinje:** de siste 60 sekundene med tale per mic og kutt markert, slik at man ser om klippingen henger etter.
- **Store knapper:** AUTO på/av, TOTAL NÅ, LÅS, og ett trykk per kamera.
- **Tuning:** forhåndsvalg Rolig / Standard / Energisk + glidere for lyd- og bilde-reglene. Endringer gjelder umiddelbart og vises i loggen.
- **Oppsett:** kobling mic → person → kamera → vinkler, målstørrelse per vinkel, og en «kalibrer»-knapp der hver person snakker 5 sekunder.

En [klikkbar prototype med simulert lyd](https://claude.ai/artifact/ULABrqirezvzQAKPaRsaXx) viser dette i praksis, slik at reglene kan prøves før noe kobles til studio.

## Byggeplan, risiko og test

Realistisk ramme er 6–8 uker for én erfaren utvikler til stabil live-drift med OBSBOT og Canon, der lyd og regler er i drift etter 4 uker og videolaget og fargematchingen legges på etterpå.

1. **Uke 1 – Lyd inn:** les RØDECaster via ASIO, kjør Silero VAD per kanal, vis meters i GUI. Mål lekkasje mellom mic-er i studio.
2. **Uke 2 – Regelmotor i skyggemodus:** regelsett for 1, 2, 3 og 4 deltakere. Motoren logger beslutninger live mens en person klipper manuelt, og loggene sammenlignes.
3. **Uke 3 – Companion og ATEM:** knapper per vinkel, tally tilbake, overstyring fra Stream Deck.
4. **Uke 4 – Kameradrivere og drift:** OBSBOT (VISCA + OSC) og Canon CR-N300 (XC). Presets, Windows-tjeneste, fallback til TOTAL. Første sendinger med bare lyd.
5. **Uke 5–6 – Videolaget:** multiview inn, ansikt og munn per rute, V1, V2 og V5. Mål ansiktsstørrelse i hver layout.
6. **Uke 7–8 – Utsnitt, reaksjoner og farge:** VISCA/XC-justering off air (V4), reaksjonsvalg (V3), fargematching mot referansekamera.
7. **Senere – Panasonic og Sony:** to nye drivere i samme mønster, ca. 1 uke hver inkludert test på ekte kamera.

| Risiko | Konsekvens | Tiltak |
| --- | --- | --- |
| Mye lekkasje mellom mic-er | Feil kutt ved krysstale | Dynamiske mic-er nær munn, gate på RØDECaster, målt lekkasjematrise, munn-bekreftelse (V1) |
| For små ansikter i multiview | Videolaget gir svake signaler | Færre ruter i multiview, eller kameraenes andre utgang inn i et capture-kort |
| Ulike kommandosett per kameramerke | En funksjon finnes ikke på alle | Felles driver med «støttes ikke»-svar; GUI viser hva hvert kamera kan |
| Automatikk i kameraet overstyrer | Farge og eksponering endrer seg | Alle kamera i manuell; motoren sjekker modus ved oppstart |
| ASIO låst av annet program | Motoren får ikke lyd | Motoren eier ASIO-enheten; opptak av lyd skjer i RØDECaster eller ATEM |
| Companion-forsinkelse eller frakobling | Kutt kommer sent eller ikke | Direkte ATEM-kutt som reserve; overvåk responstid |
| Firmware-endringer på ATEM eller kameraer | Kommandoer slutter å virke | Lås firmware i produksjon, test ved oppdatering |
| Utsnittsjustering når kameraet tas | Bildet beveger seg på lufta | V4 fryser kandidat-kameraer, V5 krever stillestående bilde |

Testplan: kjør motoren i skyggemodus på tre live-sendinger mens en person klipper manuelt, og tell avvik per 10 minutter. Mål før motoren får klippe selv: færre enn 2 kutt per 10 minutter som operatøren ville gjort annerledes.

Åpne spørsmål: hvilke multiview-layouter brukes på ATEM i dag, og skal OBSBOT og Canon blandes i samme show? Blandet oppsett gjør fargematchingen viktigere.

## Kilder

- [RØDECaster Virtual Devices multitrack](https://help.rode.com/hc/en-us/articles/15514570006927-The-R%C3%98DECaster-Pro-II-Duo-Virtual-Devices-Multitrack-Output) · [RØDECaster USB-oppsett](https://rode.com/en-si/user-guides/rodecaster-pro-ii/a-guide-to-setting-up-usb-connections-on-the-rodecaster-pro-ii)
- [Companion HTTP Remote Control](https://companion.free/user-guide/v4.2/remote-control/http-remote-control)
- [OBSBOT VISCA-guide](https://www.obsbot.com/explore/obsbot-tail-air/visca-over-ip) · [OBSBOT Tail 2 ressurser](https://www.obsbot.com/explore/obsbot-tail-2)
- [atem-connection](https://npmjs.com/package/atem-connection) · [Silero VAD](https://pypi.org/project/silero-vad) · [LoCoNet](https://arxiv.org/abs/2301.08237v2)

* [RØDECaster Virtual Devices-driver og ASIO](https://help.rode.com/hc/en-us/articles/11891033629839-What-is-the-Virtual-Devices-Driver-for-the-R%C3%98DECaster-Pro-II-Duo) · [ATEM Mini Extreme: utganger og multiview](https://www.syntex.cz/media/ant/Syntex_Blackmagic_Design_ATEM_Mini_vs_Pro_vs_Extreme_EN_2_2021.pdf)
* [OBSBOT NDI-guide](https://www.obsbot.com/ndi-guide) · [OBSBOT OSC](https://www.obsbot.com/webcam/osc) · [Light-ASD](https://ar5iv.labs.arxiv.org/html/2303.04439)

- [Canon CR-N300 datablad](https://www.fullcompass.com/common/files/60067-CRN300DataSheet.pdf) · [Panasonic AW-UE150 grensesnitt](https://eww.pass.panasonic.co.jp/pro-av/support/content/guide/DEF/UE150/AW-UE150HE145_InterfaceSpecification_E.pdf) · [Sony BRC/SRG VISCA over IP](https://applicationmarket.crestron.com/content/Help/Sony/Sony_BRC-X400_SRG-X_series_Help_v1.0.pdf)
