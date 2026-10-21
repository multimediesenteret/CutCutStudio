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
| Q7 | ATEM-modell (Extreme ISO eller G2) og bekreftet støtte i `atem-connection` og Companion | Integrasjon | NTNU | Steg 5 | Åpen | |
| Q8 | Er regi-PC-en NTNU-administrert (Intune/gruppepolicy)? Kan kiosk, tjenester, strømplan og oppdateringstider settes lokalt? | Drift (9) | NTNU IT | Steg 9 | Åpen | |
| Q9 | Nett: VLAN, IP-plan bekreftet, brannmur ut mot NTNU-API og Panopto | Alt | NTNU IT | Steg 5 | Åpen | |
| Q10 | Personvern: behandlingsgrunnlag og lagringstid for brukernavn, økthistorikk, ev. live tekst | Lagring og logg | Personvernombud | Før produksjon | Åpen | |
| Q11 | Lisens for repoet og eierskap til koden | Avhengigheter, deling | NTNU | Steg 1 | Åpen | |
| Q12 | Kontaktpersoner: produkteier, tekniker for studiotest, IT-kontakt | Godkjenning | NTNU | Steg 1 | Åpen | |

## Tekniske spørsmål (spesifikasjonen 11)

| ID | Spørsmål | Ansvar | Status | Svar |
| --- | --- | --- | --- | --- |
| Q13 | Hvilket kamera er fugleperspektiv, og har det IP-styring? | NTNU | Åpen | |
| Q14 | Står laptopen alltid på inngang 6, eller kan det komme flere content-kilder? | NTNU | Åpen | |
| Q15 | Montering og kabellengde til touch-skjermen (trengs forlenger for skjermsignal og USB?) | NTNU | Åpen | |
| Q16 | Virker OSC `SetAiEnable` på studioets OBSBOT-fastvare, og hvor rolig er tracking med fart «lat»? | Tekniker (hw-test) | Åpen | |
| Q17 | Hvor lenge skal opptak ligge på Pearl og ATEM-disken før lokal sletting? | NTNU | Åpen | |
| Q18 | Fastvareversjoner på alt utstyr (fylles i `docs/intake/studio-inventar.md`) | Tekniker | Åpen | |
| Q19 | Skal OBSBOT og Canon blandes i samme show? (Avgjør hvor viktig fargematching er) | NTNU | Åpen | |
| Q20 | Hvilken GPU har regi-PC-en? (Avgjør CUDA/TensorRT eller DirectML for videolaget) | NTNU | Åpen | |
| Q21 | Lyd med ASIO på Windows: virker RØDE ASIO via `sounddevice` (`SD_ENABLE_ASIO`) med 20 kanaler, synkront og stabilt? Research: `docs/research/lyd-fra-rodecaster.md`. Bekreftes med `tools/hw-test/audio_rodecaster.py` | Tekniker (hw-test) | Delvis | Research 2026-10-21 anbefaler ASIO i egen prosess (ADR-0014); venter på maskintest |
| Q22 | Vercel: passer Hobby-planen for NTNU-prosjektet? | NTNU | Besvart | Ja. Intern prototyping ved universitet, ikke kommersielt. Bare web-simulatoren publiseres (2026-10-21, Magnus Lian) |
| Q23 | RØDECaster-firmware og faderkart | Claude (valgt) | Besvart | Firmware 1.7.6, fast faderkart med programleder på fader 1. `docs/studio/rodecaster-standardoppsett.md` (2026-10-21) |
| Q24 | Inneholder pre-fader multitrack-sporet lyd fra en mic som er dempet på RØDECaster? Avgjør om regel `S6` trengs eller om post-fader er bedre. Testes i `tools/hw-test/audio_rodecaster.py` | Tekniker (hw-test) | Åpen | |
| Q25 | Eksakte fargenavn i RØDECaster-paletten for magenta, cyan, lilla og oransje (noteres i `baseline.yaml`) | Tekniker | Åpen | |
| Q26 | Kamerakart: hvilket kamera ser hvem? Konseptet antar CAM 1 = Canon CR-N300 på programleder, CAM 2–4 = OBSBOT Tail 2 på gjestene, CAM 5 = fast fugleperspektiv, IN 6 = laptop. Stemmer det, og hvor mange OBSBOT finnes? | NTNU | Åpen | |
