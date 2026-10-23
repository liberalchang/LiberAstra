# Liber SpeechAPI Reference

## Base URL

Default example:

```text
http://localhost:5555/api/v1
```

Set the actual base URL through `.env`:

- `LIBER_API_BASE_URL`

## Authentication

Use bearer token authentication:

```http
Authorization: Bearer YOUR_API_KEY
```

Read the token from:

- `LIBER_API_KEY`

Do not hardcode tokens in scripts.

---

## Health check

```http
GET /health
```

Use this to verify service availability before ASR/TTS when needed.

---

## ASR

### Endpoint

```http
POST /asr/transcribe
```

### Form fields

The current service accepts only:

- `file`: local audio file upload. Required.
- `language`: for example `zh` or `en`. Omit it to let faster-whisper detect the language.
- `task`: `transcribe` or `translate`. Default is `transcribe`.

The ASR model comes from the server environment variable `LIBER_SPEECH_ASR_MODEL` (default `large-v3`). The request cannot select a model, word timestamps, a remote `url`, batch size, or speaker diarization.

### Expected response fields

- `text`: recognized text
- `chunks`: list of `{start, end, text}`
- `meta.language`: detected or requested language
- `meta.task`: `transcribe` or `translate`

### Output modes in this skill

- direct ASR default: return full JSON
- explicit text-only mode: return `text` only
- Telegram/openclaw mode: extract `text` and pass it into the chatbot workflow

### Notes

- Prefer file upload for Telegram voice processing.
- Validate that the input file exists and is readable.
- Fail clearly if no `text` is returned.

---

## TTS

### Endpoint

```http
POST /tts/synthesize
```

### Form fields

- `text`: text to synthesize. Required.
- `model`: one of the 11 Chatterbox packs. `multilingual` is an alias of `multilingual_v2`.
- `language`: language id, for example `zh` or `en`. A multilingual pack requires one of its 23 languages. A single-language pack rejects any other language.
- `format`: `wav` or `ogg_opus`. `ogg` is rewritten to `ogg_opus`. Default is `wav`.
- `prompt`: optional reference audio for voice cloning. Allowed suffixes are `.wav`, `.mp3`, `.ogg`, and `.flac`.

This endpoint rejects `mp3` and `mp4`. It also does not accept `temperature`, `cfg_weight`, `exaggeration`, or the other old sampling fields. A `mp3` request returns HTTP 400 with `格式只支持 wav 或 ogg_opus`. LiberAstra's main service can convert a wav response to mp3; this skill calls the speech service directly and does not do that conversion.

### Models

| id | Languages | Notes |
| --- | --- | --- |
| `multilingual_v3` | 23 languages, including `zh` | Chatterbox-Multilingual V3 |
| `multilingual_v2` | same 23 languages | alias: `multilingual` |
| `turbo` | `en` | reference audio must be longer than 5 seconds |
| `nano` | `en` | reference audio must be longer than 5 seconds |
| `standard` | `en` | Chatterbox English |
| `zh-cmn` | `zh` | Chinese pack |
| `es-mx` | `es` | Latam Spanish |
| `es-es` | `es` | Spain Spanish |
| `pt-br` | `pt` | Brazilian Portuguese |
| `pt-pt` | `pt` | Portugal Portuguese |
| `hi` | `hi` | Hindi |

The 23 language ids are `ar`, `da`, `de`, `el`, `en`, `es`, `fi`, `fr`, `he`, `hi`, `it`, `ja`, `ko`, `ms`, `nl`, `no`, `pl`, `pt`, `ru`, `sv`, `sw`, `tr`, `zh`.

`GET /models` returns `models`, `tts_models`, and `default_tts_model`. A pack loads on the first synthesis that uses it. Synthesis fails when that pack's weights are not on the server.

### Expected response fields

- `audio_url`: path such as `/api/v1/results/<id>.wav` or `/api/v1/results/<id>.ogg`
- `meta.format`: `wav` or `ogg_opus`
- `meta.sample_rate`: Chatterbox sample rate. A short Chinese sentence returned `24000`

Download `audio_url` with the same bearer token. `ogg_opus` files use the `.ogg` suffix and start with `OggS`.

### Output format rules in this skill

- direct TTS default: `wav`
- Telegram voice reply: force `ogg_opus`
- explicit caller override: honor `wav`, `ogg`, or `ogg_opus`

### Notes

- For Telegram voice notes, use `format=ogg_opus`.
- Only send `prompt` when clone audio is enabled and the file exists.
- The first synthesis after a restart loads the model. The client timeout is 600 seconds.

---

## Telegram compatibility

The upstream project explicitly recommends `OGG/Opus` for Telegram voice-note delivery.

Use:
- `format=ogg_opus`

---

## Error handling guidance

Handle these cases explicitly:
- network timeout
- 401/403 authentication failure
- 404 wrong base URL or endpoint
- 422 invalid form fields
- empty ASR text
- empty TTS audio_url

Return actionable messages so the calling workflow can decide whether to retry, downgrade, or fall back to plain text.
