# Multiview i NTNU-studioet (observert)

Kilde: foto av multiview-skjermen i studio, sendt av Magnus Lian 2026-10-21. Ikke et skjermbilde, men leselig nok til å se oppsett og navn. Beslutning D-053; åpne spørsmål Q37–Q39.

## Hva bildet viser

| Rute | Plass | Navn på skjermen | Innhold på bildet |
| --- | --- | --- | --- |
| Stor venstre | Øverst til venstre | Preview | Grafikken «Podkast Akrinn», med safe area-merker |
| Stor høyre | Øverst til høyre | Program | Samme grafikk |
| 1 | Rad 1, kolonne 1 | Camera 1 | Mikrofonarm nær, en person i bakgrunnen |
| 2 | Rad 1, kolonne 2 | Camera 2 | Mikrofonarm og stoler |
| 3 | Rad 1, kolonne 3 | Camera 3 | Totalbilde av rommet mot skjermen |
| 4 | Rad 1, kolonne 4 | Camera 4 | Rommet med vinduer og skjerm |
| 5 | Rad 2, kolonne 1 | Camera 6 | Ovenfra mot bordet (ser ut som fugleperspektiv) |
| 6 | Rad 2, kolonne 2 | Camera 7 | Svart (ingen kilde) |
| 7 | Rad 2, kolonne 3 | Media Player 1 | Grafikken, rød tally-ramme (på program) |
| 8 | Rad 2, kolonne 4 | Opptaksstatus | «OFF 00:00:00», datarate 0.00, cache OK, «ATEM Television Studio HD8 ISO» |

## Hva det betyr for CutCut

1. **Mikseren er en ATEM Television Studio HD8 ISO**, ikke en ATEM Mini Extreme ISO som spesifikasjonen antar. Den har 8 SDI-innganger (3G-SDI, med format- og bildefrekvensomformer på alle), SDI- og HDMI-utgang for multiview, 2 mediaspillere, ISO-opptak av alle innganger til USB-disk og 4 nettverksporter ([Blackmagic HD8 ISO-spesifikasjoner via forhandler](https://www.visuals.co.uk/blackmagic-atem-television-studio-hd8-iso.html)).
   - Alle kilder må inn som **SDI**. OBSBOT Tail 2 og laptopen har HDMI og trenger omformer (eller er allerede koblet slik) – Q38.
   - Multiview kan tas ut på **HDMI** til INOGENI-kortet, som planlagt.
   - `atem-connection` og Companion sin ATEM-modul støtter Television Studio-serien; det verifiseres i maskintesten i M2 (ADR-0012, Q7).
   - Spesifikasjonen 2.2 er skrevet for Mini Extreme ISO. Innstillingene (1080p50, utganger, makroer, eksport) gjelder fortsatt, men inngangene er SDI og modelltabellen er ikke lenger aktuell.
2. **Layouten er allerede 2 store + 8 små**, som spesifikasjonen 2.1 krever, med preview til venstre. Rutekartet er lagt inn som utkast i `site/ntnu-studio/equipment/multiview_map.yaml`.
3. **Inngangene er ikke som i spesifikasjonen.** Spesifikasjonen ønsker `C1`–`C4`, `BIRD` (5), `LAPTOP` (6), `C7` i rute 1–7 og SuperSource i rute 8. I dag vises inngang 1–4, 6 og 7, mediaspiller 1 og opptaksstatus; inngang 5, 8 og SuperSource vises ikke. CutCut leser hvilken kilde som er hvor fra rutekartet og `devices.yaml`, så koden tåler et annet kart – men det må være bestemt (Q37).
4. **Overlegg:** safe area-merker er på i preview-ruta. Spesifikasjonen vil ha dem av (mindre støy i bildeanalysen). Navneskiltene heter «Camera n»; spesifikasjonen foreslår korte navn (`C1` …) som også vises i loggen.
5. **Mediaspiller 1 brukes til grafikk** («Podkast Akrinn»). Spesifikasjonen bruker mediaspiller 1 til «Kun lyd»-grafikken. HD8 ISO har to mediaspillere, så «Kun lyd» kan ligge på mediaspiller 2 (Q39).
6. **Opptaksstatus-ruta** er ATEM sitt eget ISO-opptak. Pearl Nexus er fortsatt hovedopptaker (spesifikasjonen 2.2); ATEM-opptaket er av, som spesifikasjonen anbefaler.

## Hva som ikke endres

Motoren, regelverket og skjermene er uavhengige av ATEM-modellen: de snakker om `C1`, `BIRD`, `LAPTOP` osv., og `devices.yaml` kobler det til innganger. Det som må tilpasses er studio-oppsettet (`site/ntnu-studio/`), Companion-knappekartet og rutekartet – ingen kodeendring i M1.
