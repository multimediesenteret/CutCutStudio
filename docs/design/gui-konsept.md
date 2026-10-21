# GUI-konsept: touch og tekniker

Dato: 2026-10-21 · Status: **konsept godkjent som retning** (D-036–D-039). Kode: `concept/`. Publiseres på Vercel.

## Hvem skjermene er for

| Skjerm | Bruker | Hvor ofte | Hovedjobb |
| --- | --- | --- | --- |
| Touch (16:9, 1920 × 1080, kiosk) | Studenter og ansatte som bruker rommet | 90 % av all bruk | Skanne kort, trykke Start, avslutte. Ingen teknikk |
| Tekniker (16:9-skjerm, vanlig nettleservindu) | Tekniker | Oppsett og innimellom følge med | Se alt på én side; oppsett og detaljer i menyer |

## Touch-skjermen

**Prinsipp:** skann kort og trykk Start. Alt annet er valgfritt, og standardvalgene er klare.

Flyt (erstatter de seks skjermene i spesifikasjonen 8.1–8.2):

| Skjerm | Innhold | Valg |
| --- | --- | --- |
| Hvile | «Hold NTNU-kortet ditt mot leseren», status «Studio klart» | Ingen |
| Klar | «Hei, Kari!» · Hvem er med (4 plasser i deltakerfarger, programleder alltid med) · Video og lyd / Kun lyd · bordplan · **Start opptak** | Antall personer og video/lyd. Standard: 2 personer, video |
| Lydsjekk | Nedtelling 3–2–1 mens bordplanen lyser når folk snakker | Ingen |
| Opptak | Opptakstid, hva som er i bildet nå, mikrofoner som lyser, «Trenger du hjelp?», **Avslutt opptak** (hold inne 2 s) | Hjelp, Avslutt |
| Ferdig | «Takk! Opptaket er lagret», lengde, Panopto-konto, logges ut automatisk etter 30 s | Ferdig, Nytt opptak |

Regler:

- Alt passer på 1920 × 1080 uten scrolling. Flaten skaleres til skjermen.
- Trykkflater minst 120 px; viktigste knapp 196 px høy. Ingen hover.
- Ingen dialogbokser: å avslutte bekreftes ved å holde knappen inne i 2 sekunder.
- Show-type velges ikke av brukeren. Den følger av antall personer og studio-oppsettet (teknikeren kan definere flere show-typer senere).
- Feil vises bare når brukeren må vite det, med én setning og uten tekniske ord: «Noe er galt med lyden. Teknikeren er varslet.» Gule avvik vises aldri.
- Teknikertilgang: hold logoen inne i 3 s (ansattkort eller PIN).
- Mørkt tema som standard, så skjermen ikke lyser opp rommet. Tema kan byttes med én knapp.

## Teknikervinduet

**Prinsipp:** full oversikt på én side; alt som er oppsett ligger bak menyen.

**Oversikt** (passer 1920 × 1080 uten scrolling):

- Venstre: multiview (6 ruter med PGM/PVW-ramme og deltakerfarge, klikk for manuelt kutt) og tidslinjen for siste 60 s (tale per person i deltakerfarge, lekkasje i grått, program med kutt), med live tekst under.
- Høyre: på lufta nå, preview og neste beslutning, AUTO / Lås / Bird nå, forhåndsvalg Rolig–Standard–Energisk; mikrofonene med fader, kanal, nivå og tilstand; beslutningsloggen med regel-ID.
- Toppen: innlogget bruker og show, opptaksstatus (Pearl + ISO) med Start/Stopp (stopp bekreftes med et ekstra klikk), helsestatus.
- Varsellinje når en bruker trykker «Trenger du hjelp?».

**Menyen til venstre:** Oversikt · Regi (tuning og brytere) · Kameraer (bilde, status, presets, AI-tracking) · Opptak (Pearl, ATEM ISO, dagens opptak) · Helse (alle H-sjekker, morgensjekk) · Oppsett (veiviseren i 10 steg fra spesifikasjonen 8.4) · Logg · Innstillinger (tema, farger).

Regler:

- Statusfarger og deltakerfarger blandes aldri (`docs/design/farger.md`).
- Presets og «Fiks for meg» er sperret for kamera på program eller preview og under opptak (I2).
- Lyst, mørkt eller systemtema; valget huskes per maskin.
- Virker også på smal skjerm (meny nederst), men er laget for 16:9.

## Teknologi som må virke i Windows-appen

Konseptet bruker bare det som også virker i Edge kiosk og WebView2 uten nett:

- **Skrift:** Segoe UI Variable og Cascadia Mono følger med Windows 11. Ingen nettfonter.
- **Grafikk:** ren CSS, inline SVG og canvas. Ingen bildefiler fra nett, ingen CDN.
- **CSS:** grid, flex, `aspect-ratio`, `color-mix()` og egendefinerte egenskaper; alt støttes av Chromium-baserte Edge.
- **Input:** pointer events (touch og mus likt), ingen hover-avhengighet, ingen `alert`/`confirm`.
- **Tilstand:** i appen kommer all tilstand fra motoren over WebSocket (spesifikasjonen 12.5). `BroadcastChannel` og `localStorage` brukes bare i konseptet (tema lagres i appen i motorens konfig).
- **Ingen service worker, ingen ekstern innlogging, ingen sporing.**

## Ytelse

Skjermene skal være lette og kjappe; de står på hele dagen, og touch-PC-en gjør også klippingen.

| Krav | Grense | Målt i konseptet (21.10.2026) |
| --- | --- | --- |
| Oppdateringsfrekvens for tilstand | 10 Hz (målere kan tegnes raskere lokalt) | 10 Hz |
| CPU i hovedtråden, touch | under 30 ms per sekund | 14 ms/s (før: 112) |
| CPU i hovedtråden, tekniker | under 50 ms per sekund | 27 ms/s (før: 148) |
| Layout-beregninger | under 15 per sekund | touch 2, tekniker 10 |

Slik holdes det lavt:

- Bare endrede verdier skrives til siden (tekst og klasser sammenlignes først).
- Målere og fremdriftsstriper flyttes med `transform: scaleX()`, som ikke trigger ny layout.
- Tidslinjen tegnes på canvas i sammenhengende biter, ikke én strek per sample; størrelsen leses med `ResizeObserver`, ikke hver gang.
- Kamerabilder tegnes bare på nytt når kilden endres; «snakker»-markøren er en CSS-klasse.
- Motoren sender bare endringer (logg og tekst bare når de er nye), ikke hele tilstanden hver gang.
- Ingen animasjoner annet enn `transform` og `opacity`.
