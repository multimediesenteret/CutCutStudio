# Touch-skjermen som kiosk (SO-6)

Touch-skjermen ved bordet er Microsoft Edge i kiosk-modus på regi-PC-en. Den skal alltid komme tilbake av seg selv. Ansvaret er delt slik:

| Hvis | Så |
| --- | --- |
| PC-en starter på nytt | Windows logger inn kiosk-brukeren `cutcut-kiosk` automatisk |
| Kiosk-brukeren logger inn | Oppgaveplanlegger starter kiosk-vakten, og vakten starter Edge med touch-siden |
| Edge lukkes eller krasjer | Vakten starter Edge igjen innen 5 s |
| Siden henger eller er svart (ingen hjerteslag på 30 s) | Vakten lukker og starter Edge. Helse viser `H-PROC-touch` gult imens |
| CutCut starter på nytt | Siden kobler seg til igjen selv. Vakten venter |
| Natt (kl. 03, ingen økt) | Siden laster seg selv på nytt, så minnet ikke vokser over uker |

Tjenesten CutCut (`docs/studio/tjenester.md`) kjører uavhengig av kiosken, også før noen er logget inn.

## Oppsett (som administrator, i servicevinduet)

```powershell
.\installer\kiosk\setup-kiosk.ps1 -Password (Read-Host -AsSecureString "Passord for cutcut-kiosk") -AutoLogon
```

- `-DryRun` viser hva som ville blitt gjort.
- `-Remove` fjerner oppgaven og den automatiske innloggingen.
- Passordet velges på stedet og legges aldri i git.
- Med `-AutoLogon` ligger passordet i Windows-registeret. PC-en er vanlig Windows uten sentral administrasjon (D-062, Q8); vil dere ikke ha passordet i registeret, brukes Sysinternals Autologon i stedet.

Vaktens logg: `C:\Users\cutcut-kiosk\AppData\Local\CutCut\kiosk-vakt.log`. Prøv vakten for hånd med `.\installer\kiosk\kiosk-vakt.ps1 -Once -DryRun`.

## Prøves i studioperioden (`testdag.md` 1.7)

- **Windows tilordnet tilgang (Assigned Access):** den låser kiosk-brukeren til bare Edge, og prøves på regi-PC-en. Vakten virker med og uten.
- **Touch-innstillinger:** skru av sveipebevegelser fra kanten og tastatur på skjermen for kiosk-brukeren.
- **BIOS:** «Power on after AC loss» skal være på, så PC-en starter selv etter strømbrudd.
