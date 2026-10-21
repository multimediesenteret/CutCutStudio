# Åpne spørsmål

Hver rad har en ID som brukes i issues, planer og commit-meldinger («venter på Q4»). Når et spørsmål er besvart: skriv svaret, dato og hvem, sett status til **Besvart**, og legg svaret inn i spesifikasjonen eller studio-oppsettet. Slett aldri rader.

Status: **Åpen** · **Delvis** · **Besvart**

## Data og beslutninger fra NTNU (spesifikasjonen 13.2)

| ID | Spørsmål / mangler | Trengs til | Ansvar | Blokkerer | Status | Svar |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | Opptak fra 3–5 ekte sendinger: hvert mic-spor som WAV, multiview som video, ATEM ISO-filer. Se `docs/intake/opptak-og-klippeliste.md` | Tuning av lydregler, avspillingstester, videolag | NTNU | Steg 4, 7 | Åpen | |
| Q2 | Menneskelig klippeliste for de samme opptakene (format i `docs/intake/`) | Fasit for «feilkutt per 10 min» (10.4) | NTNU | Akseptanse | Åpen | |
| Q3 | Studiotegning og bilder: bordplan, kameraplassering, lys, bilde av hvert utsnitt | Rutekart, presets, utsnittsregler | NTNU | Steg 6–8 | Åpen | |
| Q4 | NTNU-API: nøkkel, svarformat, eksempelsvar, kortformat (hex, byte-rekkefølge som i Crestron) | Kortinnlogging | NTNU IT | Steg 6 | Åpen | |
| Q5 | Panopto: hvordan opptak havner på brukerens egen konto uten passord | Publisering | NTNU + Panopto-admin | Senere | Åpen | |
| Q6 | Canon XC-kommandoliste fra Canon | Canon-driver | NTNU via Canon | Steg 8 | Åpen | |
| Q7 | ATEM-modell (Extreme ISO eller G2) og bekreftet støtte i `atem-connection` og Companion | Integrasjon | NTNU | Steg 5 | Delvis | Studioet har **ATEM Television Studio HD8 ISO** (foto av multiview 2026-10-21, D-053). Støtte i `atem-connection` og Companion verifiseres i maskintesten (M2) |
| Q8 | Er regi-PC-en NTNU-administrert (Intune/gruppepolicy)? Kan kiosk, tjenester, strømplan og oppdateringstider settes lokalt? | Drift (9) | NTNU IT | Steg 9 | Åpen | |
| Q9 | Nett: VLAN, IP-plan bekreftet, brannmur ut mot NTNU-API og Panopto | Alt | NTNU IT | Steg 5 | Åpen | |
| Q10 | Personvern: behandlingsgrunnlag og lagringstid for brukernavn, økthistorikk, ev. live tekst | Lagring og logg | Personvernombud | Før produksjon | Åpen | |
| Q11 | Lisens for repoet og eierskap til koden | Avhengigheter, deling | NTNU | Steg 1 | Besvart | Apache-2.0, opphavsrett NTNU Multimediesenteret; agenten valgte etter ønske fra produkteier (D-047, 2026-10-21, Magnus Lian) |
| Q12 | Kontaktpersoner: produkteier, tekniker for studiotest, IT-kontakt | Godkjenning | NTNU | Steg 1 | Besvart | Magnus Lian (magnus.lian@ntnu.no) er produkteier, kontakt for studiotest og IT-kontakt inntil annet er sagt (D-048, 2026-10-21) |

## Tekniske spørsmål (spesifikasjonen 11)

| ID | Spørsmål | Ansvar | Status | Svar |
| --- | --- | --- | --- | --- |
| Q13 | Hvilket kamera er fugleperspektiv, og har det IP-styring? | NTNU | Åpen | |
| Q14 | Står laptopen alltid på inngang 6, eller kan det komme flere content-kilder? | NTNU | Åpen | |
| Q15 | Montering og kabellengde til touch-skjermen (trengs forlenger for skjermsignal og USB?) | NTNU | Åpen | |
| Q16 | Virker OSC `SetAiEnable` på studioets OBSBOT-fastvare, og hvor rolig er tracking med fart «lat»? | Tekniker (hw-test) | Åpen | `SetAiEnable` står ikke i OBSBOTs OSC-tabeller i `site/ntnu-studio/equipment/obsbot/`; driveren bruker adressen fra spesifikasjonen til maskintesten (CA-5) har svart |
| Q17 | Hvor lenge skal opptak ligge på Pearl og ATEM-disken før lokal sletting? | NTNU | Åpen | |
| Q18 | Fastvareversjoner på alt utstyr (fylles i `docs/intake/studio-inventar.md`) | Tekniker | Åpen | |
| Q19 | Skal OBSBOT og Canon blandes i samme show? (Avgjør hvor viktig fargematching er) | NTNU | Åpen | |
| Q20 | Hvilken GPU har regi-PC-en? (Avgjør CUDA/TensorRT eller DirectML for videolaget) | NTNU | Åpen | |
| Q21 | Lyd med ASIO på Windows: virker RØDE ASIO via `sounddevice` (`SD_ENABLE_ASIO`) med 20 kanaler, synkront og stabilt? Research: `docs/research/lyd-fra-rodecaster.md`. Bekreftes med `tools/hw-test/audio_rodecaster.py` | Tekniker (hw-test) | Delvis | Research 2026-10-21 anbefaler ASIO i egen prosess (ADR-0014); venter på maskintest |
| Q22 | Vercel: passer Hobby-planen for NTNU-prosjektet? | NTNU | Besvart | Ja. Intern prototyping ved universitet, ikke kommersielt. Bare web-simulatoren publiseres (2026-10-21, Magnus Lian) |
| Q23 | RØDECaster-firmware og faderkart | Claude (valgt) | Besvart | Firmware 1.7.6, fast faderkart med programleder på fader 1. `docs/studio/rodecaster-standardoppsett.md` (2026-10-21) |
| Q24 | Inneholder pre-fader multitrack-sporet lyd fra en mic som er dempet på RØDECaster? Avgjør om regel `S6` trengs eller om post-fader er bedre. Testes i `tools/hw-test/audio_rodecaster.py` | Tekniker (hw-test) | Åpen | `S6` er laget (AU-4) og sammenligner med hovedmiksen, så den virker uansett svar. Maskintesten avgjør om den trengs |
| Q25 | Eksakte fargenavn i RØDECaster-paletten for magenta, cyan, lilla og oransje (noteres i `baseline.yaml`) | Tekniker | Åpen | |
| Q26 | Kamerakart: hvilket kamera ser hvem? Konseptet antar CAM 1 = Canon CR-N300 på programleder, CAM 2–4 = OBSBOT Tail 2 på gjestene, CAM 5 = fast fugleperspektiv, IN 6 = laptop. Stemmer det, og hvor mange OBSBOT finnes? | NTNU | Åpen | |

## Fra implementasjonsplanene (M0, 2026-10-21)

| ID | Spørsmål | Ansvar | Blokkerer | Status | Svar |
| --- | --- | --- | --- | --- | --- |
| Q27 | GitHub og Vercel: beskyttelse av `main` finnes ikke for private repoer på gratis GitHub. Velg A (privat, disiplin), B (GitHub Pro) eller C (offentlig repo). Godkjenn også CI med sti-filtre og `ignoreCommand` i `vercel.json` (se `docs/plans/milestones.md`) | Eier | M1 | Besvart | Alternativ A: privat og gratis, agenten pusher aldri til `main`. Agenten oppretter milepæler, etiketter og issues; `ignoreCommand` i `vercel.json` godkjent (D-050, 2026-10-21, Magnus Lian) |
| Q28 | Finnes en Windows-maskin (gjerne lik regi-PC-en) vi kan teste på før studio, eventuelt som egen GitHub Actions-maskin (gratis minutter, ekte Windows)? | NTNU | M2 | Delvis | Test-PC Dell SFF ordnes av NTNU (D-051, 2026-10-21, Magnus Lian). Modell, CPU, GPU og Windows-oppsett noteres når den er klar |
| Q29 | Varsling utenfor studio ved rødt over 1 min: e-post, Teams eller begge? Hvem skal få det? | NTNU | M3 | Åpen | |
| Q30 | Åpningstider og servicevindu: når kan CutCut gjøre nattlig vedlikehold (forslag 04:00) og når kan Windows og CutCut oppdateres? | NTNU | M2 | Åpen | |
| Q31 | Strøm: finnes UPS for PC, ATEM, RØDECaster og switch? Kan BIOS settes til «power on after AC loss», og er automatisk innlogging for kiosk-brukeren tillatt? | NTNU IT | M3 | Åpen | |
| Q32 | Standardvalg på touch: 2 personer og video (D-036), eller hentes det fra studio-oppsettet? | Eier | M1 | Åpen | |
| Q33 | Hvem står på teknikerlisten (`operator`) og admin-listen, og skal PIN brukes som reserve? | Eier | M1 (fiktivt), M3 (ekte) | Åpen | |
| Q34 | Godkjennes tuning-forslaget for `K`, `H`, `B`, `CT`, `L` per forhåndsvalg (`docs/plans/core.md`, vedlegg) som startpunkt? | Eier | M1 | Besvart | Godkjent som startpunkt med planene (D-046, 2026-10-21, Magnus Lian) |
| Q35 | Skal Companion kjøre som Windows-tjeneste uten skrivebord, eller i kiosk-brukerens økt? | Tekniker | M2 | Åpen | |
| Q36 | Godkjennes forslagene PL-01–PL-08 i `docs/plans/README.md` (blant annet ADR-0012, 0013 og 0014 bekreftet)? | Eier | M1 | Besvart | Godkjent (D-046, 2026-10-21, Magnus Lian). Endring: ingen skyggerunde som milepæl (D-049) |
| Q37 | Inngangskart på HD8 ISO: hvilken inngang er programleder, gjest 1–3, fugleperspektiv (inngang 6 «Camera 6»?), laptop og eventuelt halvtotal? Inngang 5 og 8 vises ikke i multiview i dag | Rutekart, `devices.yaml`, Companion | Tekniker | M2 (studiotest) | Besvart | Camera 1 = programleder, Camera 2–4 = gjest 1–3, Camera 6 = oversikt, Camera 7 = laptop; inngang 5 og 8 brukes ikke (D-054, 2026-10-21, Magnus Lian). Lagt inn i `site/ntnu-studio/` |
| Q38 | Får CutCut endre ATEM-oppsettet (multiview-ruter, korte navn, safe area av, SuperSource i en rute), eller brukes studioet også av andre slik det står i dag? Og er OBSBOT-kameraene og laptopen koblet via HDMI-til-SDI-omformere? | Rutekart, videolag, oppsett-veiviser | Eier / tekniker | M2–M3 | Delvis | Kameraene er koblet til mikseren; HDMI eller HD-SDI varierer mellom studioer og har ingen betydning (D-054). Åpent: om dere vil slå av safe area og bruke det anbefalte oppsettet for rute 7–8 (D-055). CutCut virker uten |
| Q39 | Mediaspiller 1 har «Podkast Akrinn»-grafikken. Skal «Kun lyd»-grafikken (modus `A`) ligge på mediaspiller 2? | Modus A, Companion side 11 | Eier | M2 | Besvart | Mediaspilleren er intern og brukes ikke i studio, så «Kun lyd» kan ligge på mediaspiller 1 som i spesifikasjonen (D-054) |
