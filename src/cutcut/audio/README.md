# `cutcut.audio` – `audio-capture`

Egen prosess (ADR-0014, PL-02) som leser multitrack fra RØDECaster og sender bare målinger til `core`. Rå lyd går aldri på bussen eller til disk.

| Fil | Innhold |
| --- | --- |
| `channels.py` | Kanalkart: mic N på multitrack-kanal `2 × N + 1` (D-032), hovedmiks på 1–2 |
| `dsp.py` | Nivå (RMS i dB) og 48 → 16 kHz nedsampling som strømmer mellom blokker |
| `vad.py` | Silero VAD (studio, ekstra `silero` + `models/silero_vad.onnx`) og energi-VAD (tester, reserve) |
| `analyzer.py` | 10 ms-blokker → `audio.frame`: `vad`, `level_db`, `dominance_db`, `pause_ms`, `phrase_end`, `pitch_falling`, `leak`, `in_main_mix` per mic |
| `phrase.py` | Frasegrenser (AU-3, spesifikasjonen 5.10): tonehøyde med YIN (64–500 Hz, bare mens mic-en snakker), energifall og pause. `phrase_end` etter 250 ms pause, eller 150 ms når tonen falt eller stemmen døde ut |
| `leak.py` | Lekkasje (AU-4): en aktiv mic som ikke er minst 6 dB over lekkasjen forutsagt fra en høyere, aktiv mic, merkes `leak`. Matrisen måles i setup steg 5 (`cutcut.setup.mic_check`, Oppsett → Mikrofoner), lagres i `baseline.yaml` (`audio.leak_db`) og kommer som `audio.config` til en `audio-capture` som kjører; før det brukes −18 dB. **P13 `AdaptiveLeak`:** når én mic er minst 10 dB over alle andre, måles lekkasjen derfra på nytt (glattet over ca. 30 s slik tale, innenfor ±6 dB fra fasit, nullstilt ved ny økt). Bryteren `audio_adapt` kommer med `audio.config` (`adapt`: off/shadow/on, `session`); i skygge sendes den andre vurderingen som `leak_other`, på bytter den plass med fasit. `audio.status.adapt` har matrisen, tid talt alene og talenivå per person |
| `mainmix.py` | `S6` (AU-4): hovedmiksen (kanal 1–2) sammenlignes med hver mic på nivåkurven over 0,5 s. Følger ikke hovedmiksen stavelsene i 0,5 s, er mic-en dempet (`in_main_mix = false`); ett godt vindu gir den tilbake. Ingenting dømmes før hovedmiksen har hatt lyd |
| `backend.py` | `fake` spiller en 48 kHz multitrack-WAV (tester, demo) |
| `device.py` | Lydkortet (AU-5). Se detaljene under tabellen |
| `process.py`, `main.py` | Løkka og `cutcut audio --wav fil.wav` |

```bash
uv sync --extra silero && uv run python tools/fetch_models.py   # Silero-modellen, sjekket med SHA-256
uv run cutcut audio --site site/multimediesenteret                      # RØDECaster (ASIO, ellers WASAPI)
uv run cutcut audio --wav opptak.wav --site site/multimediesenteret     # spill av til en kjørende core
```

Tester (`tests/unit/audio/`) bruker syntetiske signaler, aldri ekte opptak av personer. Frasegrensene sjekkes mot den gylne fila `tests/fixtures/audio/phrases.json`: påstand, spørsmål, nøling, stemme som dør ut, og dyp stemme. Fila oppdateres med vilje med `CUTCUT_UPDATE_GOLDEN=1`. En test viser at målingene får den ekte motoren til å klippe til den som snakker.

## Lydkortet (`device.py`, AU-5)

- **Kobling:** RØDECaster-multitracken leses via PortAudio med `sounddevice`, med ASIO først og WASAPI eksklusiv som reserve.
- **Ingen blokkering:** PortAudio sin tråd kopierer bare inn i en kø, og analysen får 10 ms-blokker.
- **Åpnes på nytt:** når lydkortet mangler eller strømmen stopper (USB trukket ut, ingen lyd på 1 s), prøver `audio-capture` å åpne det igjen hvert 5. sekund, uten slutt. Imens går motoren over til `S4`.
- **`audio.status`** sendes hvert sekund, også mens kortet er borte. Den har backend, enhet, buffer, over- og underflyt, tapte rammer og siste feil. Helsesjekken `H-AUD-1` viser feilen.
- **Oppsett** i `devices.yaml` under `audio`:
  - `backend` (`asio` eller `wasapi`);
  - `device`, en del av navnet, standard «RODECaster»;
  - `channels`, standard 20;
  - `buffer`, standard 256 sampler. Øk den ved dropouts.
- **Krav:** `sounddevice` installeres bare på Windows (PortAudio med ASIO følger med).
- **Tester:** de bruker en falsk PortAudio. Windows-CI laster ekte PortAudio uten lydkort. Ekte ASIO testes på test-PC-en (AU-6).

Maskintesten for RØDECaster (AU-6) er `uv run cutcut hwtest audio --site …` (`src/cutcut/hwtest/audio.py`, `docs/studio/maskintest.md`). Rapporten svarer på Q21 og Q24.
