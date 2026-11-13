# Liber SpeechAPI Reference

## Base URL and auth

`LIBER_API_BASE_URL` can be:

- `http://host:5555`
- `http://host:5555/api/v1`
- `http://host:5555/api/v2`

The client splits the origin and probes `/api/v2/help`. If unavailable, it falls back to `/api/v1`.

Bearer token:

```http
Authorization: Bearer LIBER_API_KEY
```

Never hardcode or print the token.

## API versions

| Version | Style | Notes |
|---|---|---|
| v2 | upload file → JSON request | preferred; full parameter set |
| v1 | multipart request | legacy; only basic fields |

v2-only parameters on a v1 server return a clear client error instead of being silently ignored.

---

## v2 files

```http
POST /api/v2/files
Content-Type: multipart/form-data
```

Field: `file`.

Response:

```json
{"file_id":"f_xxx","filename":"input.wav","size":1234,"sha256":"...","expires_at":"..."}
```

Delete with `DELETE /api/v2/files/{file_id}`. The client uploads automatically for TTS reference audio, ASR input, and VC source/prompt.

---

## v2 help

```http
GET /api/v2/help
GET /api/v2/help/{function}
GET /api/v2/help/{function}/{model}
```

Query: `include=common,model,examples,errors,unsupported`, `format=json|markdown`.

Use this as the source of truth for defaults, ranges, model differences, and unsupported parameters.

---

## v2 TTS

```http
POST /api/v2/tts/synthesize
Content-Type: application/json
```

Common fields:

- `text` required
- `model`
- `language`
- `format`: `wav` or `ogg_opus`
- `prompt_file_id`
- `speed`
- `normalize_loudness`, `target_lufs`
- `ref_start`, `ref_duration`

Model fields:

- multilingual/standard/language packs: `exaggeration`, `cfg_weight`, `temperature`, `repetition_penalty`, `min_p`, `top_p`
- turbo/nano: `temperature`, `repetition_penalty`, `top_p`, `top_k`, `norm_loudness`

Response:

```json
{"audio_url":"/api/v1/results/tts-xxx.wav","meta":{"format":"wav","sample_rate":24000,"parameters":{},"warnings":[]}}
```

Download `audio_url` with the same bearer token. `speed` uses ffmpeg atempo and keeps pitch; `normalize_loudness` uses loudnorm.

### v1 TTS compatibility

v1 accepts multipart fields `text`, `model`, `language`, `format`, and optional file field `prompt`. It does not accept sampling parameters. `ogg` is treated as `ogg_opus`; `mp3`/`mp4` are rejected.

---

## v2 ASR

```http
POST /api/v2/asr/transcribe
Content-Type: application/json
```

Common fields:

- `file_id` required
- `model`
- `language`
- `task`: `transcribe` or `translate`
- `timestamps`: `none`, `segment`, `word`
- `response_format`: `json`, `verbose_json`, `text`, `srt`, `vtt`

faster-whisper fields:

`beam_size`, `best_of`, `patience`, `length_penalty`, `repetition_penalty`, `no_repeat_ngram_size`, `temperature`, `compression_ratio_threshold`, `log_prob_threshold`, `no_speech_threshold`, `condition_on_previous_text`, `initial_prompt`, `prefix`, `hotwords`, `vad_filter`, `vad_parameters`, `max_new_tokens`, and related decoding options.

Qwen3-ASR fields:

`max_new_tokens`, `max_inference_batch_size`, `timestamps`. It does not support `task=translate`, VAD, beam, hotwords, or `initial_prompt`.

Response:

```json
{"text":"...","chunks":[{"start":0.0,"end":1.0,"text":"..."}],"words":[],"language":"zh","model":"large-v3","meta":{}}
```

`timestamps=word` adds top-level `words`. `response_format=text|srt|vtt` returns plain text instead of JSON.

### v1 ASR compatibility

v1 accepts multipart `file`, `language`, `task`, `model` and returns JSON with `text` and sentence-level `chunks`. It does not accept word timestamps or advanced decoding parameters.

---

## v2 VC

```http
POST /api/v2/vc/convert
Content-Type: application/json
```

Common fields:

- `file_id` required
- `prompt_file_id` required
- `model`: `chatterbox` or `seed-vc`
- `segments`: `[{start, end}]`
- `convert_all`
- `segment_padding`, `merge_gap`, `min_segment`
- `ref_start`, `ref_duration`
- `denoise`, `normalize_loudness`, `target_lufs`, `output_sample_rate`

Seed-VC fields:

`seed`, `diffusion_steps`, `inference_cfg_rate`, `n_quantizers`, `temperature`, `max_window`, `context`, `fade`, `ref_max_len`, `length_adjust`, `overlap_frame_len`.

Chatterbox VC has no model-level sampling parameters. Its reference audio uses the first 10 seconds; Seed-VC defaults to 25 seconds.

Response:

```json
{"audio_url":"/api/v1/results/vc-xxx.wav","meta":{"format":"wav","sample_rate":24000,"parameters":{},"warnings":[]}}
```

`dereverb`, pitch/F0 controls, and speaker diarization are not supported in v1 of the service.

## Error handling

- `400`: parameter or file validation error; the response contains `detail.errors[]`
- `401/403`: bad key
- `404`: missing file or endpoint
- `410`: expired file
- `500`: synthesis/transcription/conversion failure or ffmpeg failure
- `503`: missing model dependency or weights

Retry only connection errors, timeouts, and 5xx; do not retry 4xx.
