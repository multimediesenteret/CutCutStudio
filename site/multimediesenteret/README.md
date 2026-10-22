# site/multimediesenteret

Alt som er spesielt for studioet. Kan senere flyttes til et eget repo (`cutcut-site-multimediesenteret`, spesifikasjonen 12.2).

`devices.yaml` (utstyr, med IP-adresser som bare er eksempler), `shows/` (1–4 personer, inngangskart D-054), `staff.yaml` (tom) og `equipment/`.

**Det som er hemmelig eller personlig, ligger ikke her.** Virkelige IP-adresser, teknikerlisten og mottakere av varsler legges inn i appen på studio-PC-en og lagres i databasen der. «Lagre oppsett» (Innstillinger → Oppsett) gir en fil med alt sammen, som kan hentes inn igjen på samme eller en ny PC. Kommer: `setup/`, `baseline.yaml`. Ingen passord eller nøkler her.

Prøv oppsettet i simulatoren: `uv run cutcut sim --site site/multimediesenteret`.

| Mappe | Innhold |
| --- | --- |
| `equipment/obsbot/` | OSC-definisjon for Tail 2 og OBSBOT Center (fra OBSBOT). VISCA-tabellen ligger i Google Sheets (lenke i teknisk referanse) og skal lastes ned hit |
| `equipment/canon/` | XC-kommandoliste når den kommer (Q6) |
| `equipment/atem/` | Eksportert ATEM-oppsett og makroer (ATEM Television Studio HD8 ISO, D-053) |
| `equipment/multiview_map.yaml` | Rutekart for videolaget fra foto, inngangskart bekreftet (D-054) |
| `equipment/companion_map.yaml` | Companion side 10, peker på kamera-ID-er |
| `equipment/companion/` | `cutcut-pages.companionconfig` og eksisterende eksport |
