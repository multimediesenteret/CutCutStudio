# CutCut som Windows-tjeneste (SO-2)

CutCut kjører som Windows-tjenesten **CutCut Studio** (`CutCut`). Tjenesten starter `cutcut supervisor`, som starter og passer på `core`, `atem-bridge` og `audio-capture`. Ansvaret er delt slik:

| Hvis | Så |
| --- | --- |
| En av prosessene krasjer eller henger | Supervisor starter den på nytt etter 1–30 s, og Helse viser `H-PROC-*` |
| Supervisor selv krasjer | Windows starter tjenesten på nytt etter 5, 10 og 30 s. Barna stoppes alltid sammen med den |
| PC-en starter på nytt | Tjenesten starter automatisk, uten at noen logger inn |

## Første installasjon (som administrator)

```powershell
# 1. Kode og avhengigheter (til pakken i SO-3 finnes)
git clone https://github.com/multimediesenteret/CutCutStudio C:\CutCut\current
cd C:\CutCut\current
uv sync --locked --extra silero
uv run python tools/fetch_models.py
pnpm install --filter @cutcut/atem-bridge        # atem-bridge
pnpm --filter "./ui/**" build                     # skjermene

# 2. Studio-oppsettet
git clone <studio-repo> C:\CutCut\site            # eller kopier site\ntnu-studio dit

# 3. Tjenesten
.\installer\install-services.ps1 -Root C:\CutCut -UiDir C:\CutCut\current\ui\dist
```

Sjekk:
- `Get-Service CutCut` skal vise **Running**.
- `http://127.0.0.1:8080/tech/` åpner teknikervinduet. Under **Helse → Prosesser** skal alle prosessene kjøre.

## Hverdagsbruk

- **Stoppe og starte:** `Stop-Service CutCut` og `Start-Service CutCut`. Opptak på Pearl stoppes aldri av dette (I7), men motoren klipper ikke mens tjenesten står.
- **Logg:** tjenestens egen logg ligger i `C:\CutCut\data\logs\service`, og CutCut-loggen i `C:\CutCut\data\logs`.
- **Kopi av databasen:** hver natt i `C:\CutCut\data\backup\` (de 7 nyeste). Slik settes en kopi tilbake: `Stop-Service CutCut`, kopier filen til `C:\CutCut\data\cutcut.db`, `Start-Service CutCut`.
- **Fjerne:** `.\installer\install-services.ps1 -Root C:\CutCut -Uninstall`.

## Companion (Q35)

Companion skal også starte selv. `-Companion -CompanionExe <sti>` installerer den som tjenesten `CutCut-Companion`. Companion sin Windows-utgave er laget for å kjøre med skjerm. Derfor avgjøres på test-PC-en om den skal være tjeneste, eller startes ved innlogging av kiosk-brukeren (SO-6). Til da startes Companion som før.
