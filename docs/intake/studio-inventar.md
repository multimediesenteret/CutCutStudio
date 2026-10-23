# Studioinventar

Fylles ut av tekniker i studio. Agenten trenger dette for å skrive `site/multimediesenteret/devices.yaml` og maskintestene. Ikke skriv passord her.

## Utstyr

| Enhet | Modell | Fastvare | IP / port | Inngang på ATEM | Merknad |
| --- | --- | --- | --- | --- | --- |
| Miksere | ATEM Television Studio HD8 ISO (foto 2026-10-21, D-053) | | | – | 8 SDI-innganger; se `docs/studio/multiview.md` |
| Opptaker | Epiphan Pearl Nexus | (≥ 4.24.1 for REST) | | – | |
| Lydmikser | RØDECaster Pro II | | USB | – | USB 1 multitrack på? |
| Kamera 1 | | | | | Rolle: |
| Kamera 2 | | | | | Rolle: |
| Kamera 3 | | | | | Rolle: |
| Kamera 4 | | | | | Rolle: |
| Fugleperspektiv | | | | | |
| Laptop-inngang | – | – | – | | |
| Capture-kort | INOGENI 4KXUSB3 | | USB | multiview-utgang | |
| Kortleser | ELATEC TWN3 MIFARE USB | | COM? | – | Modus og skript |
| Touch-skjerm | iiyama T2254MSC-B2AG | – | – | – | Kabellengde |
| Regi-PC | | Windows-versjon | | – | CPU, GPU, RAM |
| Companion | Bitfocus Companion | versjon | :8000 | – | |
| Stream Deck | | | | – | Hvilke sider brukes i dag |

## Mikrofoner

Faderkartet er bestemt (`docs/studio/rodecaster-standardoppsett.md`, D-032). Fyll inn mic-modell og bekreft kameraene.

| Fader / kanal | Deltaker og farge | Mic-modell | Kamera som ser personen |
| --- | --- | --- | --- |
| 1 / 3–4 | Programleder · magenta | | CAM 1 (OBSBOT Tail 2, D-070) |
| 2 / 5–6 | Gjest 1 · cyan | | CAM 2 (OBSBOT Tail 2) |
| 3 / 7–8 | Gjest 2 · lilla | | CAM 3 (OBSBOT Tail 2) |
| 4 / 9–10 | Gjest 3 · oransje | | CAM 4 (OBSBOT Tail 2) |
| 5 / 11–12 | Laptop (USB 2) | – | IN 6 |

## Filer som legges i `site/multimediesenteret/equipment/`

- [ ] ATEM-oppsett eksportert fra ATEM Software Control (`atem/`)
- [ ] Companion-eksport av eksisterende sider (`companion/`)
- [ ] Canon XC-kommandoliste når den kommer (`canon/`)
- [ ] OBSBOT VISCA-tabell lastet ned som xlsx fra Google Sheets (`obsbot/`) – OSC-filene ligger der allerede
- [ ] Bilder av hvert kamerautsnitt og av studioet (`photos/`)
- [ ] Bordplan med kameraplassering (skisse eller foto av tegning er nok)
