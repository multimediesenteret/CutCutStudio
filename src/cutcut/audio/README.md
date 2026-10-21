# `cutcut.audio` – `audio-capture`

Egen prosess (ADR-0014, PL-02) som leser multitrack fra RØDECaster og sender bare målinger til `core`. Rå lyd går aldri på bussen eller til disk.

| Fil | Innhold |
| --- | --- |
| `channels.py` | Kanalkart: mic N på multitrack-kanal `2 × N + 1` (D-032), hovedmiks på 1–2 |
| `dsp.py` | Nivå (RMS i dB) og 48 → 16 kHz nedsampling som strømmer mellom blokker |
| `vad.py` | Silero VAD (studio, ekstra `silero` + `models/silero_vad.onnx`) og energi-VAD (tester, reserve) |
| `analyzer.py` | 10 ms-blokker → `audio.frame`: `vad`, `level_db`, `dominance_db`, `pause_ms`, `phrase_end`, `pitch_falling` per mic. Lekkasje (AU-4) kommer |
| `phrase.py` | Frasegrenser (AU-3, spesifikasjonen 5.10): tonehøyde med YIN (64–500 Hz, bare mens mic-en snakker), energifall og pause. `phrase_end` etter 250 ms pause, eller 150 ms når tonen falt eller stemmen døde ut |
| `backend.py` | Hvor lyden kommer fra: `fake` spiller en 48 kHz WAV; ASIO/WASAPI kommer i AU-5 |
| `process.py`, `main.py` | Løkka og `cutcut audio --wav fil.wav` |

```bash
uv sync --extra silero && uv run python tools/fetch_models.py   # Silero-modellen, sjekket med SHA-256
uv run cutcut audio --wav opptak.wav                             # spill av til en kjørende core
```

Tester (`tests/unit/audio/`) bruker syntetiske signaler, aldri ekte opptak av personer. Frasegrensene sjekkes mot den gylne fila `tests/fixtures/audio/phrases.json`: påstand, spørsmål, nøling, stemme som dør ut, og dyp stemme. Fila oppdateres med vilje med `CUTCUT_UPDATE_GOLDEN=1`. En test viser at målingene får den ekte motoren til å klippe til den som snakker.
