# Configuration

## `.env`

| Variable | Description |
|---|---|
| `LIBER_API_BASE_URL` | `http://host:5555`, `.../api/v1`, or `.../api/v2` |
| `LIBER_API_KEY` | Bearer token; same as server `LIBER_SPEECH_API_KEY` |
| `LIBER_API_VERSION` | optional `auto` / `v1` / `v2` |

```env
LIBER_API_BASE_URL=http://127.0.0.1:5555
LIBER_API_KEY=your_api_key_here
LIBER_API_VERSION=auto
```

The client strips `/api/v1` or `/api/v2` to obtain the origin, then uses that origin for both versions.

## `speechapi_config.json`

```json
{
  "asr": {
    "language": "zh",
    "task": "transcribe",
    "model": "default",
    "options": {}
  },
  "tts": {
    "model": "multilingual_v3",
    "language": "zh",
    "format": "wav",
    "audio_prompt_path": "default",
    "options": {}
  },
  "vc": {
    "model": "seed-vc",
    "convert_all": true,
    "options": {}
  },
  "global": {
    "voice_summary_limit": 100,
    "default_clone_audio": "tmp/clone.wav",
    "telegram_tts_format": "ogg_opus",
    "asr_output": "json",
    "api_version": "auto"
  }
}
```

### `options`

`options` is flattened into the v2 JSON request. Examples:

```json
{
  "tts": {
    "options": {
      "speed": 0.9,
      "exaggeration": 0.7,
      "cfg_weight": 0.3
    }
  },
  "asr": {
    "options": {
      "timestamps": "word",
      "vad_filter": true,
      "initial_prompt": "LiberAstra、Chatterbox"
    }
  },
  "vc": {
    "options": {
      "seed": 42,
      "diffusion_steps": 20,
      "denoise": true
    }
  }
}
```

CLI `--params '{"...":...}'` has the highest priority.

### Default values

- `"default"` or `null` → omit the field and use the server default.
- Missing key → use the client default config.
- Explicit `false` / `0` are kept.

## Priority

1. CLI arguments (`--base-url`, `--api-key`, `--api-version`, `--params`, parameter flags)
2. `speechapi_config.json`
3. server defaults

`.env` only provides origin and API key; it does not participate in parameter precedence.

## Version selection

- Base URL ending in `/api/v2` → v2
- Base URL ending in `/api/v1` → v1
- Bare origin → probe `/api/v2/help`; fallback v1
- `--api-version` / `LIBER_API_VERSION` overrides detection

v2-only parameters on a v1 server raise a configuration error.

## Quick start

```bash
python scripts/liber_speech_client.py health
python scripts/liber_speech_client.py help tts multilingual_v3
python scripts/liber_speech_client.py tts "你好，欢迎使用" --speed 0.9
python scripts/liber_speech_client.py asr demo.wav --timestamps word
python scripts/liber_speech_client.py vc demo.wav --prompt ref.wav --convert-all
```
