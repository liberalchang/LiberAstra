# Workflows

## Mode 1: Telegram/openclaw voice workflow

1. Receive or download the Telegram voice/audio file.
2. Run ASR:
   - v2: upload the file, then `file_id`, `language`, `task=transcribe`
   - extract `text`
3. Send the transcript to openclaw.
4. Generate the full textual reply.
5. Compress it for voice:
   - keep the direct answer and essential facts
   - remove markdown, code, tables, and repeated explanation
6. Run TTS:
   - `format=ogg_opus`
   - `model` / `language` from config
   - optional reference audio
7. Return the audio URL or saved file to Telegram.

## Mode 2: Direct text-to-speech

Use when the user explicitly asks to turn text into audio.

- default format: `wav`
- default model: `multilingual_v3`
- use clone audio only when enabled and the file exists
- v2 advanced parameters are optional; omitted values use server defaults
- do not force summarization unless a short spoken version is requested

## Mode 3: Direct speech-to-text

Use when the user explicitly asks to turn audio into text.

- default output: structured JSON
- plain text only when explicitly requested
- `timestamps=word` for word-level output
- use `vad_filter`, `initial_prompt`, and `hotwords` only for faster-whisper models
- Qwen3-ASR cannot translate or use VAD/beam/hotwords

## Mode 4: Voice conversion

Use when the user asks to replace the voice in audio/video.

1. Validate source and reference files.
2. Choose `chatterbox` or `seed-vc`.
3. Choose either:
   - `convert_all=true` for the whole track
   - `segments=[{start,end}]` for selected ranges
4. Optional v2 parameters:
   - Seed-VC: `seed`, `diffusion_steps`, `inference_cfg_rate`, `n_quantizers`, `temperature`
   - common: `denoise`, `normalize_loudness`, `target_lufs`, `output_sample_rate`
5. Download `audio_url` and return the local path.
6. VC requires `/api/v2`; v1 servers are rejected with a clear error.

## Failure strategy

### ASR failure

- return plain error text
- ask the user to resend clearer audio if needed

### Summarization failure

- conservatively trim text to the configured limit

### TTS or VC failure

- return a plain text error or fall back to the original reply
- do not block the surrounding chatbot workflow

### Clone audio missing

- continue without cloning
