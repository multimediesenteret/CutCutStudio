# Runbook: Kamera beveger seg ikke

- **Sjekk-ID / regel:** `H-CAM-<kamera>` (for eksempel `H-CAM-C2`), `H-CAM-MOVE`; I2
- **Alvor:** gul (bildet kommer, styringen mangler); `H-CAM-MOVE` er rød
- **Vises på touch:** nei
- **Sist testet:** 2026-10-21 mot falske kameraer over UDP i CI, ikke i studio ennå

## Hva brukeren merker

Ofte ingenting: bildet fra kameraet går fortsatt over SDI/HDMI til ATEM. Et preset hentes ikke, eller utsnittet blir ikke justert.

## Hva CutCut gjør selv

CutCut flytter aldri et kamera som er på program eller preview (I2), så «kameraet beveger seg ikke» er ofte riktig oppførsel. Svarer kameraet ikke tre ganger på rad, venter CutCut 10 s før det prøver igjen, og `H-CAM-<kamera>` blir gul. Posisjonen leses hvert 2. sekund; flytter kameraet seg uten at CutCut ba om det, blir `H-CAM-MOVE` rød.

## Sjekk først (under 2 minutter)

1. Er kameraet på program eller preview? Da er det riktig at det står stille.
2. Teknikervinduet → **Helse**: hva står ved `H-CAM-<kamera>`: svarer ikke, tregt, eller ikke manuell?
3. Lyser kameraet, og står nettverkskabelen i (PoE-lampa på svitsjen)?

## Løs det

1. Svarer ikke: sjekk strøm og nett. Kameraets IP står under **Oppsett → Utstyr og nettverk**.
2. Ikke manuell: sett manuell hvitbalanse og eksponering i kameraets meny eller app.
3. `H-CAM-MOVE` rød: noen har dyttet eller snudd kameraet, eller AI-tracking er slått på utenfor CutCut. Slå tracking av under **Kameraer** (eller i kameraets app), og hent riktig preset. Tracking som er slått på fra CutCut, gir ikke `H-CAM-MOVE`.
4. Feil IP: rett den under **Oppsett → Utstyr og nettverk**. Den tas i bruk uten omstart.
5. Bekreft at sjekken er grønn i 30 s.

## Hvis det ikke hjelper

- Kjør maskintesten `uv run cutcut hwtest camera --site C:\CutCut\site --camera C2` når kameraet ikke er på lufta.
- Last ned **feilsøkingspakke** (Logg → Feilsøkingspakke) og send den til Magnus Lian, magnus.lian@ntnu.no.

## Bakgrunn

Spesifikasjonen 7.3, 8.5 (`H-CAM-*`, `H-CAM-MOVE`) og 9.1. `docs/plans/devices-cameras.md`, `docs/studio/maskintest.md`.
