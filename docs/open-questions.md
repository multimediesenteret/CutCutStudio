# Åpne spørsmål

Hver rad har en ID som brukes i issues, planer og commit-meldinger («venter på Q4»). Når et spørsmål er besvart: skriv svaret, dato og hvem, sett status til **Besvart**, og legg svaret inn i spesifikasjonen eller studio-oppsettet. Slett aldri rader.

Status: **Åpen** · **Delvis** · **Besvart**

## Data og beslutninger fra Multimediesenteret (spesifikasjonen 13.2)

| ID | Spørsmål / mangler | Trengs til | Ansvar | Blokkerer | Status | Svar |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | Opptak fra 3–5 ekte sendinger: hvert mic-spor som WAV, multiview som video, ATEM ISO-filer. Se `docs/intake/opptak-og-klippeliste.md` | Tuning av lydregler, avspillingstester, videolag | Multimediesenteret | Steg 4, 7 | Åpen | |
| Q2 | Menneskelig klippeliste for de samme opptakene (format i `docs/intake/`) | Fasit for «feilkutt per 10 min» (10.4) | Multimediesenteret | Akseptanse | Åpen | |
| Q3 | Studiotegning og bilder: bordplan, kameraplassering, lys, bilde av hvert utsnitt | Rutekart, presets, utsnittsregler | Multimediesenteret | Steg 6–8 | Åpen | |
| Q4 | Kort-API: nøkkel, svarformat, eksempelsvar, kortformat (hex, byte-rekkefølge som i Crestron) | Kortinnlogging | Multimediesenteret IT | Etter idriftsetting (D-057, D-065) | Åpen | Trengs ikke før kortinnloggingen bygges; studioet bruker Start-knappen |
| Q5 | Panopto: hvordan opptak havner på brukerens egen konto uten passord | Publisering | Multimediesenteret + Panopto-admin | Senere | Åpen | |
| Q6 | Canon XC-kommandoliste fra Canon | Canon-driver | Multimediesenteret via Canon | Steg 8 | Åpen | |
| Q7 | ATEM-modell (Extreme ISO eller G2) og bekreftet støtte i `atem-connection` og Companion | Integrasjon | Multimediesenteret | Steg 5 | Delvis | Studioet har **ATEM Television Studio HD8 ISO** (foto av multiview 2026-10-21, D-053). Støtte i `atem-connection` og Companion verifiseres i maskintesten (M2) |
| Q8 | Er regi-PC-en sentralt administrert (Intune/gruppepolicy)? Kan kiosk, tjenester, strømplan og oppdateringstider settes lokalt? | Drift (9) | Multimediesenteret IT | Steg 9 | Besvart | Nei. Vanlig Windows, installert av Multimediesenteret (D-062, 2026-10-22, Magnus Lian) |
| Q9 | Nett: VLAN, IP-plan bekreftet, brannmur ut mot kort-API og Panopto | Alt | Multimediesenteret IT | Steg 5 | Besvart | Egen uadministrert switch for alt utstyret, faste IP-er, ingen VLAN. PC-en har ett nettverkskort mot switchen og ett mot campusnettet for trafikk ut (D-064, 2026-10-22, Magnus Lian) |
| Q10 | Personvern: behandlingsgrunnlag og lagringstid for brukernavn og økthistorikk (live tekst er tatt ut, D-063) | Lagring og logg | Personvernombud | Før produksjon | Åpen | |
| Q11 | Lisens for repoet og eierskap til koden | Avhengigheter, deling | Multimediesenteret | Steg 1 | Besvart | Apache-2.0, opphavsrett Multimediesenteret; agenten valgte etter ønske fra produkteier (D-047, 2026-10-21, Magnus Lian) |
| Q12 | Kontaktpersoner: produkteier, tekniker for studiotest, IT-kontakt | Godkjenning | Multimediesenteret | Steg 1 | Besvart | Magnus Lian (magnus.lian@ntnu.no) er produkteier, kontakt for studiotest og IT-kontakt inntil annet er sagt (D-048, 2026-10-21) |

## Tekniske spørsmål (spesifikasjonen 11)

| ID | Spørsmål | Ansvar | Status | Svar |
| --- | --- | --- | --- | --- |
| Q13 | Hvilket kamera er fugleperspektiv, og har det IP-styring? | Multimediesenteret | Delvis | Camera 6 på ATEM er oversikt/fugleperspektiv (`C5`, D-054). Om det har IP-styring, er ikke avklart; CutCut flytter det uansett ikke (ingen driver uten IP) |
| Q14 | Står laptopen alltid på samme inngang, eller kan det komme flere content-kilder? | Multimediesenteret | Delvis | Laptopen er Camera 7 på ATEM (`LAPTOP`, D-054). Om det kan komme flere content-kilder, er ikke avklart; CutCut støtter én |
| Q15 | Montering og kabellengde til touch-skjermen (trengs forlenger for skjermsignal og USB?) | Multimediesenteret | Åpen | |
| Q16 | Virker OSC `SetAiEnable` på studioets OBSBOT-fastvare, og hvor rolig er tracking med fart «lat»? | Tekniker (hw-test) | Åpen | `SetAiEnable` står ikke i OBSBOTs OSC-tabeller i `site/multimediesenteret/equipment/obsbot/`; driveren bruker adressen fra spesifikasjonen til maskintesten (CA-5) har svart |
| Q17 | Hvor lenge skal opptak ligge på Pearl og ATEM-disken før lokal sletting? | Multimediesenteret | Åpen | |
| Q18 | Fastvareversjoner på alt utstyr (fylles i `docs/intake/studio-inventar.md`) | Tekniker | Åpen | |
| Q19 | Skal OBSBOT og Canon blandes i samme show? (Avgjør hvor viktig fargematching er) | Multimediesenteret | Åpen | |
| Q20 | Hvilken GPU har regi-PC-en? (Avgjør CUDA/TensorRT eller DirectML for videolaget) | Multimediesenteret | Besvart | NVIDIA GeForce RTX 4060 Ti (D-062, 2026-10-22, Magnus Lian). Ansikt og munn går likevel på CPU med YuNet (D-067); GPU-en er reserve |
| Q21 | Lyd med ASIO på Windows: virker RØDE ASIO via `sounddevice` (`SD_ENABLE_ASIO`) med 20 kanaler, synkront og stabilt? Research: `docs/research/lyd-fra-rodecaster.md`. Bekreftes med `cutcut hwtest audio` (A1, A4) | Tekniker (hw-test) | Delvis | Research 2026-10-21 anbefaler ASIO i egen prosess (ADR-0014); venter på maskintest |
| Q22 | Vercel: passer Hobby-planen for Multimediesenteret-prosjektet? | Multimediesenteret | Besvart | Ja. Intern prototyping ved universitet, ikke kommersielt. Bare web-simulatoren publiseres (2026-10-21, Magnus Lian) |
| Q23 | RØDECaster-firmware og faderkart | Claude (valgt) | Besvart | Firmware 1.7.6, fast faderkart med programleder på fader 1. `docs/studio/rodecaster-standardoppsett.md` (2026-10-21) |
| Q24 | Inneholder pre-fader multitrack-sporet lyd fra en mic som er dempet på RØDECaster? Avgjør om regel `S6` trengs eller om post-fader er bedre. Testes med `cutcut hwtest audio` (A6) | Tekniker (hw-test) | Åpen | `S6` er laget (AU-4) og sammenligner med hovedmiksen, så den virker uansett svar. Maskintesten avgjør om den trengs |
| Q25 | Eksakte fargenavn i RØDECaster-paletten for magenta, cyan, lilla og oransje (noteres i `baseline.yaml`) | Tekniker | Åpen | |
| Q26 | Kamerakart: hvilket kamera ser hvem? Konseptet antar CAM 1 = Canon CR-N300 på programleder, CAM 2–4 = OBSBOT Tail 2 på gjestene, CAM 5 = fast fugleperspektiv, IN 6 = laptop. Stemmer det, og hvor mange OBSBOT finnes? | Multimediesenteret | Besvart | Kamera 1 = verten, kamera 2–4 = gjest 1–3, som i ATEM (D-065, 2026-10-22, Magnus Lian) |

## Fra implementasjonsplanene (M0, 2026-10-21)

| ID | Spørsmål | Ansvar | Blokkerer | Status | Svar |
| --- | --- | --- | --- | --- | --- |
| Q27 | GitHub og Vercel: beskyttelse av `main` finnes ikke for private repoer på gratis GitHub. Velg A (privat, disiplin), B (GitHub Pro) eller C (offentlig repo). Godkjenn også CI med sti-filtre og `ignoreCommand` i `vercel.json` (se `docs/plans/milestones.md`) | Eier | M1 | Besvart | Først alternativ A (D-050, 2026-10-21). Nå: repoet er offentlig (D-059), agenten merger selv når CI er grønn (D-052), og agenten pusher aldri direkte til `main`. `ignoreCommand` i `vercel.json` godkjent (Magnus Lian) |
| Q28 | Finnes en Windows-maskin (gjerne lik regi-PC-en) vi kan teste på før studio, eventuelt som egen GitHub Actions-maskin (gratis minutter, ekte Windows)? | Multimediesenteret | M2 | Besvart | Regi-PC-en er kjent: i5-12500, 16 GB, RTX 4060 Ti, 250 GB SSD; capture med INOGENI (D-062, D-068, 2026-10-22, Magnus Lian) |
| Q29 | Varsling utenfor studio ved rødt over 1 min: e-post, Teams eller begge? Hvem skal få det? | Multimediesenteret | M3 | Besvart | E-post (D-058, 2026-10-22, Magnus Lian). Mottakere legges inn i appen under Innstillinger → Varsling (D-060). Av som standard; settes opp etter at studioet er tatt i bruk (D-065) |
| Q30 | Åpningstider og servicevindu: når kan CutCut gjøre nattlig vedlikehold (forslag 04:00) og når kan Windows og CutCut oppdateres? | Multimediesenteret | M2 | Besvart | Multimediesenteret styrer servicevinduet selv (D-065, 2026-10-22, Magnus Lian) |
| Q31 | Strøm: finnes UPS for PC, ATEM, RØDECaster og switch? Kan BIOS settes til «power on after AC loss», og er automatisk innlogging for kiosk-brukeren tillatt? | Multimediesenteret IT | M3 | Besvart | UPS og strøm tas med i sjekklistene for oppsett (D-065, 2026-10-22, Magnus Lian) |
| Q32 | Standardvalg på touch: 2 personer og video (D-036), eller hentes det fra studio-oppsettet? | Eier | M1 | Delvis | Touch-skjermen er en vanlig touch-skjerm. Standardvalget (2 personer og video, D-036) beholdes til noe annet er bestemt (2026-10-22) |
| Q33 | Hvem står på teknikerlisten (`operator`) og admin-listen, og skal PIN brukes som reserve? | Eier | M1 (fiktivt), M3 (ekte) | Besvart | Ingen teknikerlister nå; admin-PIN gir tilgang. Support-e-post settes i appen, standard eierens adresse (D-065, 2026-10-22, Magnus Lian) |
| Q34 | Godkjennes tuning-forslaget for `K`, `H`, `B`, `CT`, `L` per forhåndsvalg (`docs/plans/core.md`, vedlegg) som startpunkt? | Eier | M1 | Besvart | Godkjent som startpunkt med planene (D-046, 2026-10-21, Magnus Lian) |
| Q35 | Skal Companion kjøre som Windows-tjeneste uten skrivebord, eller i kiosk-brukerens økt? | Tekniker | M2 | Delvis | Companion installeres på samme PC (D-062, 2026-10-22, Magnus Lian). Om den kjører som tjeneste eller i kiosk-brukerens økt, avgjøres ved installasjonen i studioperioden (`docs/studio/tjenester.md`) |
| Q36 | Godkjennes forslagene PL-01–PL-08 i `docs/plans/README.md` (blant annet ADR-0012, 0013 og 0014 bekreftet)? | Eier | M1 | Besvart | Godkjent (D-046, 2026-10-21, Magnus Lian). Endring: ingen skyggerunde som milepæl (D-049) |
| Q37 | Inngangskart på HD8 ISO: hvilken inngang er programleder, gjest 1–3, fugleperspektiv (inngang 6 «Camera 6»?), laptop og eventuelt halvtotal? Inngang 5 og 8 vises ikke i multiview i dag | Rutekart, `devices.yaml`, Companion | Tekniker | M2 (studiotest) | Besvart | Camera 1 = programleder, Camera 2–4 = gjest 1–3, Camera 6 = oversikt, Camera 7 = laptop; inngang 5 og 8 brukes ikke (D-054, 2026-10-21, Magnus Lian). Lagt inn i `site/multimediesenteret/` |
| Q38 | Får CutCut endre ATEM-oppsettet (multiview-ruter, korte navn, safe area av, SuperSource i en rute), eller brukes studioet også av andre slik det står i dag? Og er OBSBOT-kameraene og laptopen koblet via HDMI-til-SDI-omformere? | Rutekart, videolag, oppsett-veiviser | Eier / tekniker | M2–M3 | Delvis | Kameraene er koblet til mikseren; HDMI eller HD-SDI varierer mellom studioer og har ingen betydning (D-054). Åpent: om dere vil slå av safe area og bruke det anbefalte oppsettet for rute 7–8 (D-055). CutCut virker uten |
| Q39 | Mediaspiller 1 har «Podkast Akrinn»-grafikken. Skal «Kun lyd»-grafikken (modus `A`) ligge på mediaspiller 2? | Modus A, Companion side 11 | Eier | M2 | Besvart | Mediaspilleren er intern og brukes ikke i studio, så «Kun lyd» kan ligge på mediaspiller 1 som i spesifikasjonen (D-054) |
| Q40 | Hvilket SMTP-relé kan regi-PC-en sende varsler gjennom (adresse, port, om det trenger brukernavn og passord), og hvilken avsenderadresse skal brukes? | Varsling (HS-3) | IT-avdelingen | Etter idriftsetting (D-065) | Åpen | Varslingen er av som standard; da er `H-VARSEL-1` grønn med «av», og varslene vises bare i teknikervinduet |
