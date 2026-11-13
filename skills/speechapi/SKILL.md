---
name: liber-speechapi
description: Use Liber SpeechAPI for speech workflows: Telegram/openclaw voice-message handling with ASR and OGG/Opus TTS, direct text-to-speech, direct speech-to-text, and voice conversion. Prefer /api/v2 JSON with /api/v1 fallback, expose parameter Help, support environment-based configuration and reference-audio cloning.
---

# Liber SpeechAPI

Use this skill for four related tasks:

- handle Telegram/openclaw voice-message workflows end to end
- convert user-provided text to speech on demand
- convert user-provided audio to text on demand
- replace the voice in audio/video with a target voice (VC)

## Follow this workflow

1. Read `references/config.md` to resolve `.env` and `speechapi_config.json`.
2. Read `references/workflow.md` for Telegram and voice-conversion workflows.
3. Read `references/api.md` for v2/v1 endpoint details.
4. Read `references/parameters.md` for TTS/ASR/VC parameter meanings and defaults.
5. Use `scripts/liber_speech_client.py` for deterministic calls instead of rewriting HTTP logic.
6. Use `/api/v2/help` when you need the authoritative parameter list for a model.

## API version

- New deployments support `/api/v2`: file upload → JSON request.
- Old deployments only support `/api/v1`: multipart request.
- The client defaults to `auto`: probe `/api/v2/help`, then fall back to `/api/v1`.
- Force a version with `--api-version v1|v2` or `LIBER_API_VERSION`.
- v2-only parameters on a v1 server fail with a clear error instead of being silently ignored.

## Configuration

`.env`:

- `LIBER_API_BASE_URL`: `http://host:5555`, `.../api/v1`, or `.../api/v2`
- `LIBER_API_KEY`: same value as the server's `LIBER_SPEECH_API_KEY`
- `LIBER_API_VERSION`: optional `auto` / `v1` / `v2`

`speechapi_config.json`:

- `asr`, `tts`, `vc`, `global` sections
- `options` object inside each section for model-specific parameters
- values `"default"` or `null` are omitted from requests

Never print or log API keys.

## Health, models, and help

```bash
python scripts/liber_speech_client.py health
python scripts/liber_speech_client.py models
python scripts/liber_speech_client.py help
python scripts/liber_speech_client.py help tts turbo
python scripts/liber_speech_client.py help asr large-v3 --include model
python scripts/liber_speech_client.py help vc seed-vc --format markdown
```

`models` uses v2 `/api/v2/models` when available and falls back to `/api/v1/models`.

## Direct text-to-speech

```bash
python scripts/liber_speech_client.py tts "你好世界" --language zh --format wav
python scripts/liber_speech_client.py tts "你好世界" --speed 0.9 --exaggeration 0.7 --cfg-weight 0.3
python scripts/liber_speech_client.py tts "你好世界" --params '{"temperature":0.8,"top_p":0.9}'
```

- Default output: `wav`; Telegram voice: `ogg_opus`.
- v2 supports `speed`, `exaggeration`, `cfg_weight`, `temperature`, `repetition_penalty`, `min_p`, `top_p`, `top_k`, `norm_loudness`, `normalize_loudness`, `target_lufs`, `ref_start`, `ref_duration`.
- Model differences:
  - multilingual / standard / language packs: `exaggeration`, `cfg_weight`, `speed`
  - turbo / nano: `speed`, `temperature`, `top_p`, `top_k`; no `exaggeration`/`cfg_weight`
  - v1 servers: only `model`, `language`, `format`, and reference audio
- Reference audio is uploaded as `prompt_file_id` on v2 and as form field `prompt` on v1.
- Return the result URL and saved local path.

## Direct speech-to-text

```bash
python scripts/liber_speech_client.py asr audio.wav --language zh
python scripts/liber_speech_client.py asr audio.wav --timestamps word
python scripts/liber_speech_client.py asr audio.wav --vad-filter --initial-prompt "术语"
python scripts/liber_speech_client.py asr audio.wav --output srt
```

- Default output: structured JSON; `text`, `srt`, `vtt` are available.
- v2 supports `timestamps=none|segment|word`, VAD, `initial_prompt`, `hotwords`, `beam_size`, `condition_on_previous_text`, and other Whisper parameters.
- Qwen3-ASR supports `timestamps`, `max_new_tokens`, and `max_inference_batch_size`; it does not support VAD, beam, hotwords, `initial_prompt`, or `task=translate`.
- Batch transcription writes results next to each input; `--output` is only valid for a single input.

## Voice conversion

```bash
python scripts/liber_speech_client.py vc source.wav --prompt ref.wav --model seed-vc --convert-all
python scripts/liber_speech_client.py vc source.wav --prompt ref.wav --segments '[{"start":0,"end":3.2}]'
python scripts/liber_speech_client.py vc source.wav --prompt ref.wav --seed 42 --diffusion-steps 20
```

- VC requires v2.
- Seed-VC supports `seed`, `diffusion_steps`, `inference_cfg_rate`, `n_quantizers`, `temperature`, `max_window`, `context`, `fade`, `ref_max_len`, `length_adjust`, `overlap_frame_len`.
- Chatterbox VC has no model-level sampling parameters; reference audio uses the first 10 seconds.
- Common options: `convert_all`, `segments`, `segment_padding`, `merge_gap`, `min_segment`, `ref_start`, `ref_duration`, `denoise`, `normalize_loudness`, `target_lufs`, `output_sample_rate`.
- `dereverb`, pitch/F0 controls, and speaker diarization are not supported in v1 of the service.

## Telegram/openclaw workflow

1. Download or locate the voice/audio file.
2. Run ASR and extract `text`.
3. Send the transcript to openclaw.
4. Shorten the reply if needed.
5. Synthesize with `ogg_opus`.
6. Return the audio URL or saved file path.

For Telegram voice replies, force `ogg_opus`, keep spoken output concise, and avoid reading markdown/code/tables verbatim.

## Safety and robustness

- Never print or log API keys.
- Validate input files and non-empty text before calls.
- Use timeouts; default 120s, synthesis/transcription/VC 600s.
- Retry only connection errors, timeouts, and HTTP 5xx; do not retry 4xx.
- Exit codes: `0` success, `2` config/input, `3` network/service unreachable, `4` API error.
- If clone audio is configured but missing, continue without cloning.
- Use `/api/v2/help` rather than hardcoding parameter ranges or model capabilities.

## Expected outputs

Depending on the task, return one of:

- structured ASR JSON, plain transcript, SRT/VTT
- TTS result URL and saved audio path
- VC result URL and saved audio path
- a structured JSON object containing transcript, summary, and synthesis result
- the server model catalog or parameter help
- a list of batch ASR results
