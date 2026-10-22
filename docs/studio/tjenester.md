# CutCut som Windows-tjeneste (SO-2)

CutCut kjører som Windows-tjenesten **CutCut Studio** (`CutCut`). Tjenesten starter `cutcut supervisor`, som starter og passer på `core`, `atem-bridge`, `audio-capture` og `vision` (videolaget, når studioet har rutekart og capture-kort). Ansvaret er delt slik:

| Hvis | Så |
| --- | --- |
| En av prosessene krasjer eller henger | Supervisor starter den på nytt etter 1–30 s, og Helse viser `H-PROC-*` |
| Supervisor selv krasjer | Windows starter tjenesten på nytt etter 5, 10 og 30 s. Barna stoppes alltid sammen med den |
| PC-en starter på nytt | Tjenesten starter automatisk, uten at noen logger inn |

## Første installasjon (som administrator)

Last ned `cutcut-<versjon>-win64.zip` og `.sha256` fra GitHub-releasen (Releases), og legg dem i samme mappe.

```powershell
# 1. Studio-oppsettet
# kopier site\multimediesenteret fra repoet til C:\CutCut\site (bare utgangspunkt; det ekte legges inn i appen)

# 2. Pakken: pakkes ut, prøves mot oppsettet, og tjenesten installeres og startes
Expand-Archive .\cutcut-1.0.0-win64.zip -DestinationPath $env:TEMP\cutcut-pkg   # bare for å få tak i install.ps1
& "$env:TEMP\cutcut-pkg\cutcut-1.0.0\installer\install.ps1" -Zip .\cutcut-1.0.0-win64.zip
```

Pakken har sin egen Python, Node og skjermene; ingenting annet trenger å være installert. Resultatet blir:

```text
C:\CutCut\
  versions\1.0.0\    pakken (de tre nyeste beholdes)
  current          → versions\1.0.0  (lenke; tjenesten starter alltid denne)
  site\  data\  services\
```

Sjekk:
- `Get-Service CutCut` skal vise **Running**.
- `http://127.0.0.1:8080/tech/` åpner teknikervinduet. Under **Helse → Prosesser** skal alle prosessene kjøre.

## Første oppsett i appen

Det som er spesielt for studioet (IP-adresser, teknikere, varsling), legges inn i appen og lagres på PC-en, ikke i noe repo (D-060).

1. Åpne teknikervinduet og logg inn med et brukernavn og **admin-PIN**. Så lenge teknikerlisten er tom, slipper admin-PIN inn.
2. **Innstillinger → Teknikere** (valgfritt, D-065): legg inn teknikere og deg selv som admin. Da slipper bare de inn. Uten liste gir admin-PIN-en tilgang.
3. **Oppsett → Utstyr og nettverk:** IP-adressene.
4. **Innstillinger → Varsling:** support-e-post (vises på touch ved «Hjelp»). E-postvarsling er av og settes opp etter at studioet er tatt i bruk (D-065).
5. **Innstillinger → Oppsett → Lagre oppsett:** ta en kopi av filen og legg den et trygt sted.

Ny PC eller tilbake til et tidligere oppsett: **Innstillinger → Oppsett → Hent oppsett** viser hva filen endrer, og «Bruk oppsettet» tar den i bruk. CutCut tar også en kopi selv ved hver endring, i `C:\CutCut\data\oppsett\` (de 20 nyeste og `oppsett-siste.yaml`).

## Ny versjon (servicevindu, aldri under opptak)

```powershell
& C:\CutCut\current\installer\install.ps1 -Zip D:\cutcut-1.1.0-win64.zip
```

Skriptet sjekker sjekksummen, pakker ut ved siden av, prøver den nye versjonen mot studio-oppsettet, bytter `current` og starter tjenesten. Svarer ikke den nye versjonen innen 120 s, går den selv tilbake til forrige versjon og sier fra. Opptak på Pearl påvirkes ikke, men motoren klipper ikke de ca. 10 sekundene tjenesten står. Loggen er `C:\CutCut\data\logs\install.log`.

**Tilbake til forrige versjon for hånd:** kjør `install.ps1` med den forrige pakken og `-Force`.

**Fra git-utsjekk:** var `C:\CutCut\current` en vanlig mappe (installert med git før pakkene fantes), flyttes den til `versions\git-<dato>` og brukes som versjonen å gå tilbake til.

## Utvikling fra git (uten pakke)

```powershell
git clone https://github.com/multimediesenteret/CutCutStudio C:\CutCut\current
cd C:\CutCut\current
uv sync --locked --extra silero --extra vision
uv run python tools/fetch_models.py
pnpm install --filter @cutcut/atem-bridge
pnpm --filter "./ui/**" build
.\installer\install-services.ps1 -Root C:\CutCut -UiDir C:\CutCut\current\ui\dist
```

## Hverdagsbruk

- **Stoppe og starte:** `Stop-Service CutCut` og `Start-Service CutCut`. Opptak på Pearl stoppes aldri av dette (I7), men motoren klipper ikke mens tjenesten står.
- **Logg:** tjenestens egen logg ligger i `C:\CutCut\data\logs\service`, og CutCut-loggen i `C:\CutCut\data\logs`.
- **Varsel på e-post:** av som standard. Slås på under Innstillinger → Varsling. Trenger SMTP-reléet passord, legges det som `smtp_password` i Credential Manager. Trykk «Send testvarsel» etter endringer.
- **Kopi av databasen:** hver natt i `C:\CutCut\data\backup\` (de 7 nyeste). Slik settes en kopi tilbake: `Stop-Service CutCut`, kopier filen til `C:\CutCut\data\cutcut.db`, `Start-Service CutCut`.
- **Fjerne:** `.\installer\install-services.ps1 -Root C:\CutCut -Uninstall`.

## Companion (Q35)

Companion skal også starte selv. `-Companion -CompanionExe <sti>` installerer den som tjenesten `CutCut-Companion`. Companion sin Windows-utgave er laget for å kjøre med skjerm. Derfor avgjøres ved installasjonen i studioperioden (`testdag.md` 1.8) om den skal være tjeneste, eller startes ved innlogging av kiosk-brukeren (SO-6). Til da startes Companion som før.
