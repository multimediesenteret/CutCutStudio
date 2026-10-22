# Multiview og inngangskart i studioet

Kilde: foto av multiview-skjermen i studio, sendt av Magnus Lian 2026-10-21. Ikke et skjermbilde, men leselig nok til å se oppsett og navn. Beslutning D-053 og D-054 (inngangskart bekreftet av Magnus Lian samme dag).

## Hva bildet viser

| Rute | Plass | Navn på skjermen | Innhold på bildet |
| --- | --- | --- | --- |
| Stor venstre | Øverst til venstre | Preview | Grafikken «Podkast Akrinn», med safe area-merker |
| Stor høyre | Øverst til høyre | Program | Samme grafikk |
| 1 | Rad 1, kolonne 1 | Camera 1 | **Programleder** (`C1`) |
| 2 | Rad 1, kolonne 2 | Camera 2 | **Gjest 1** (`C2`) |
| 3 | Rad 1, kolonne 3 | Camera 3 | **Gjest 2** (`C3`) |
| 4 | Rad 1, kolonne 4 | Camera 4 | **Gjest 3** (`C4`) |
| 5 | Rad 2, kolonne 1 | Camera 6 | **Oversikt / fugleperspektiv** (`C5` i CutCut) |
| 6 | Rad 2, kolonne 2 | Camera 7 | **Laptop** (`LAPTOP`), svart når ingen er koblet til |
| 7 | Rad 2, kolonne 3 | Media Player 1 | Intern mediaspiller som studioet ikke bruker |
| 8 | Rad 2, kolonne 4 | Opptaksstatus | «OFF 00:00:00», datarate 0.00, cache OK, «ATEM Television Studio HD8 ISO» |

## Inngangskart (D-054)

Bekreftet av Magnus Lian 2026-10-21: Camera 1 = programleder, Camera 2–4 = gjest 1–3, Camera 6 = oversikt, Camera 7 = laptop. Mediaspilleren er intern og brukes ikke. Kameraene er koblet til mikseren; noen studioer bruker HDMI og andre HD-SDI, og det har ikke betydning for CutCut. Oppsettet ligger i `site/multimediesenteret/` (`devices.yaml`, `shows/`), og `uv run cutcut sim --site site/multimediesenteret` kjører simulatoren med det. Teknikervinduet og web-simulatoren bruker de samme navnene som multiviewen («Camera 6 · Fugleperspektiv»).

## Hva det betyr for CutCut

1. **Mikseren er en ATEM Television Studio HD8 ISO**, ikke en ATEM Mini Extreme ISO som spesifikasjonen antar. Den har 8 SDI-innganger (3G-SDI, med format- og bildefrekvensomformer på alle), SDI- og HDMI-utgang for multiview, 2 mediaspillere, ISO-opptak av alle innganger til USB-disk og 4 nettverksporter ([Blackmagic HD8 ISO-spesifikasjoner via forhandler](https://www.visuals.co.uk/blackmagic-atem-television-studio-hd8-iso.html)).
   - Kameraene er koblet til mikseren (HDMI eller HD-SDI avhengig av studio); det påvirker ikke CutCut.
   - Multiview kan tas ut på **HDMI** til INOGENI-kortet, som planlagt.
   - `atem-connection` og Companion sin ATEM-modul støtter Television Studio-serien; det verifiseres i maskintesten i M2 (ADR-0012, Q7).
   - Spesifikasjonen 2.2 er skrevet for Mini Extreme ISO. Innstillingene (1080p50, utganger, makroer, eksport) gjelder fortsatt, men inngangene er SDI og modelltabellen er ikke lenger aktuell.
2. **Layouten er allerede 2 store + 8 små**, som spesifikasjonen 2.1 krever, med preview til venstre. Rutekartet ligger i `site/multimediesenteret/equipment/multiview_map.yaml`.
3. **Inngangene avviker fra spesifikasjonens forslag** (`BIRD` på 5, `LAPTOP` på 6): i studio er oversikten på 6 og laptopen på 7. CutCut leser dette fra `site/multimediesenteret/`, så ingen kode endres. SuperSource vises ikke i multiview; den trengs først med layouter (M4).
4. **Overlegg:** safe area-merker er på i preview-ruta. Spesifikasjonen vil ha dem av (mindre støy i bildeanalysen). Navneskiltene heter «Camera n»; spesifikasjonen foreslår korte navn (`C1` …) som også vises i loggen.
5. **Mediaspiller 1 er intern og brukes ikke** av studioet, så CutCut kan legge «Kun lyd»-grafikken der som spesifikasjonen sier (Q39 besvart).
6. **Opptaksstatus-ruta** er ATEM sitt eget ISO-opptak. Pearl Nexus er fortsatt hovedopptaker (spesifikasjonen 2.2); ATEM-opptaket er av, som spesifikasjonen anbefaler.

## Anbefalt oppsett (D-055)

CutCut regner ut det anbefalte oppsettet fra studioets show-oppsett og viser det under **Oppsett → Multiview** i teknikervinduet, side om side med rutekartet og det ATEM faktisk viser.

| Rute | Anbefalt | Hvorfor |
| --- | --- | --- |
| Stor venstre / høyre | Preview / Program | Vanlig ATEM-rekkefølge; skjermene tegner det likt |
| 1–4 | Camera 1–4: programleder, gjest 1–3 | Setene leses fra venstre til høyre, som på touch-skjermen |
| 5 | Camera 6: oversikt (fugleperspektiv) | CutCut leser den (antall personer, latter, bevegelse) |
| 6 | Camera 7: laptop | CutCut leser den (content-deteksjon, 6.2) |
| 7 | SuperSource | Viser hvilken layout som er klar (M4); fram til da er ruta ufarlig |
| 8 | Media Player 1 | «Kun lyd»-grafikken, så teknikeren ser hva modus `A` sender |

**Innstillinger i ATEM Software Control → Multiview:** tally-rammer på, safe area av, lydmålere av, navneskilt på (CutCut kutter 4 % inn og ser dem ikke), utgang på HDMI til opptakskortet i 1080p50.

**I studio i dag** avviker bare rute 7 og 8 (Media Player 1 og opptaksstatus), som CutCut ikke leser, og safe area er på. Det er forslag og en advarsel, ikke feil: CutCut virker med oppsettet slik det står. Bytter dere til det anbefalte, endres rutekartet (`equipment/multiview_map.yaml`) samtidig.

## Feil oppdages ved oppstart

Multiview-oppsettet endres ikke under bruk, så CutCut sjekker det **ved oppstart** (så snart ATEM kan leses, senest etter 30 s), i morgensjekken (M2) og når teknikeren trykker **Sjekk nå** under Oppsett (D-056). Teknikeren får varsel under Helse når noe ikke stemmer:

| Sjekk | Nivå | Hva |
| --- | --- | --- |
| `H-MV-0` | Feil | Studioet har ikke noe rutekart |
| `H-MV-1` | Feil | Rutekartet sier ikke hvor en kamera CutCut kan klippe til, er |
| `H-MV-2` | Feil | Rutekartet leser et kamera fra feil inngang (show-oppsett og rutekart er uenige) |
| `H-MV-3` | Feil | ATEM har ikke 2 + 8-layout |
| `H-MV-4` | Feil | Preview og program har byttet plass |
| `H-MV-5` | Feil / advarsel | En rute viser noe annet enn rutekartet: feil hvis CutCut leser ruta, ellers advarsel |
| `H-MV-6`, `H-MV-7`, `H-MV-8` | Advarsel | Safe area på, lydmålere på, tally av |
| `H-MV-10` | Advarsel | Multiview er ikke 1080p50 |
| `H-MV-11` | Forslag | Avvik fra det anbefalte oppsettet |

Sjekk mot rutekart og show-oppsett virker allerede. Sjekk mot det ATEM viser (`H-MV-3`–`H-MV-10`) virker i simulatoren nå, og mot ekte ATEM når `atem-bridge` er på plass (M2). Prøv det i simulatoren: Helse → «Noen har endret ATEM-multiviewen», så Oppsett → Sjekk nå.

## Hva som ikke endres

Motoren, regelverket og skjermene er uavhengige av ATEM-modellen: de snakker om `C1`, `BIRD`, `LAPTOP` osv., og `devices.yaml` kobler det til innganger. Det som må tilpasses er studio-oppsettet (`site/multimediesenteret/`), Companion-knappekartet og rutekartet – ingen kodeendring i M1.
