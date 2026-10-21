# Multiview og inngangskart i NTNU-studioet

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

Bekreftet av Magnus Lian 2026-10-21: Camera 1 = programleder, Camera 2–4 = gjest 1–3, Camera 6 = oversikt, Camera 7 = laptop. Mediaspilleren er intern og brukes ikke. Kameraene er koblet til mikseren; noen studioer bruker HDMI og andre HD-SDI, og det har ikke betydning for CutCut. Oppsettet ligger i `site/ntnu-studio/` (`devices.yaml`, `shows/`), og `uv run cutcut sim --site site/ntnu-studio` kjører simulatoren med det. Teknikervinduet og web-simulatoren bruker de samme navnene som multiviewen («Camera 6 · Fugleperspektiv»).

## Hva det betyr for CutCut

1. **Mikseren er en ATEM Television Studio HD8 ISO**, ikke en ATEM Mini Extreme ISO som spesifikasjonen antar. Den har 8 SDI-innganger (3G-SDI, med format- og bildefrekvensomformer på alle), SDI- og HDMI-utgang for multiview, 2 mediaspillere, ISO-opptak av alle innganger til USB-disk og 4 nettverksporter ([Blackmagic HD8 ISO-spesifikasjoner via forhandler](https://www.visuals.co.uk/blackmagic-atem-television-studio-hd8-iso.html)).
   - Kameraene er koblet til mikseren (HDMI eller HD-SDI avhengig av studio); det påvirker ikke CutCut.
   - Multiview kan tas ut på **HDMI** til INOGENI-kortet, som planlagt.
   - `atem-connection` og Companion sin ATEM-modul støtter Television Studio-serien; det verifiseres i maskintesten i M2 (ADR-0012, Q7).
   - Spesifikasjonen 2.2 er skrevet for Mini Extreme ISO. Innstillingene (1080p50, utganger, makroer, eksport) gjelder fortsatt, men inngangene er SDI og modelltabellen er ikke lenger aktuell.
2. **Layouten er allerede 2 store + 8 små**, som spesifikasjonen 2.1 krever, med preview til venstre. Rutekartet ligger i `site/ntnu-studio/equipment/multiview_map.yaml`.
3. **Inngangene avviker fra spesifikasjonens forslag** (`BIRD` på 5, `LAPTOP` på 6): i studio er oversikten på 6 og laptopen på 7. CutCut leser dette fra `site/ntnu-studio/`, så ingen kode endres. SuperSource vises ikke i multiview; den trengs først med layouter (M4).
4. **Overlegg:** safe area-merker er på i preview-ruta. Spesifikasjonen vil ha dem av (mindre støy i bildeanalysen). Navneskiltene heter «Camera n»; spesifikasjonen foreslår korte navn (`C1` …) som også vises i loggen.
5. **Mediaspiller 1 er intern og brukes ikke** av studioet, så CutCut kan legge «Kun lyd»-grafikken der som spesifikasjonen sier (Q39 besvart).
6. **Opptaksstatus-ruta** er ATEM sitt eget ISO-opptak. Pearl Nexus er fortsatt hovedopptaker (spesifikasjonen 2.2); ATEM-opptaket er av, som spesifikasjonen anbefaler.

## Hva som ikke endres

Motoren, regelverket og skjermene er uavhengige av ATEM-modellen: de snakker om `C1`, `BIRD`, `LAPTOP` osv., og `devices.yaml` kobler det til innganger. Det som må tilpasses er studio-oppsettet (`site/ntnu-studio/`), Companion-knappekartet og rutekartet – ingen kodeendring i M1.
