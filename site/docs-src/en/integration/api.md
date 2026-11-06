---
title: API
---

# LiberAstra API reference

## Conventions

- All endpoints except `/healthz` and `/auth/*` require `Authorization: Bearer <JWT or astra_ token>`.
- Interactive docs: open `/docs` (Swagger UI) after the app starts.
- Generation endpoints return `202` + a Job by default; add `?wait=true` to wait for the terminal state.
- Subscribe to job progress with SSE at `/api/v1/jobs/{id}/events`.

## Auth

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/auth/status` | Whether the instance has been initialized |
| POST | `/api/v1/auth/setup` | Create the first administrator |
| POST | `/api/v1/auth/login` | Log in and return a JWT |
| GET/POST/DELETE | `/api/v1/tokens[/{id}]` | Issue, list, and revoke API tokens |

## Providers and capabilities

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/capabilities` | Provider type registry and capability tags |
| GET/POST | `/api/v1/providers` | List / create providers (`api_key` stored encrypted) |
| PATCH/DELETE | `/api/v1/providers/{id}` | Update / delete |
| POST | `/api/v1/providers/{id}/test` | Test the connection |
| GET | `/api/v1/providers/{id}/models` | Fetch and cache the live model list |

## Jobs

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/jobs` | List jobs (`status_filter`, `kind`, `limit`) |
| GET | `/api/v1/jobs/{id}` | Job detail |
| GET | `/api/v1/jobs/{id}/events` | SSE progress stream (snapshot + deltas + heartbeat) |
| POST | `/api/v1/jobs/{id}/cancel` / `retry` | Cancel / retry |

## Generation endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/llm/chat` | LLM chat (Job) |
| POST | `/api/v1/tts` | Text to speech (`voice` or `voice_record_id`) |
| POST | `/api/v1/asr` | Speech to text (multipart; export txt/srt/vtt/json) |
| GET/POST/DELETE | `/api/v1/voices` | Voice library (reference audio + `voice_id` + default voice) |
| POST | `/api/v1/images/generate` / `edit` | Text-to-image / image edit (ComfyUI requires a workflow pack name) |
| POST | `/api/v1/images/optimize-prompt` | Expand a prompt with the LLM |
| GET/POST/DELETE | `/api/v1/workflows[/{name}]`, `/workflows/import` | Workflow pack management |
| POST | `/api/v1/videos/quick` | Quick Create (`topic`/`script`/`storyboard`) |
| POST | `/api/v1/videos/i2v` / `avatar` / `motion` / `assets` | Image-to-video / digital human / motion transfer / custom assets (multipart) |
| POST | `/api/v1/uploads` | General uploads referenced by parameters such as BGM |
| GET | `/api/v1/assets[/{id}[/content]]` | Asset list / detail / content download |
| GET | `/api/v1/system/info`, POST `cleanup`, GET `backup` | System info / cleanup / backup export (administrator) |

## OpenAI-compatible subset (/v1)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/chat/completions` | Proxy the default LLM (streaming is not supported yet) |
| POST | `/v1/audio/speech` | Default TTS provider |
| POST | `/v1/audio/transcriptions` | Default ASR provider (json/text/srt/vtt) |
| POST | `/v1/images/generations` | Online image provider (b64_json/url; use `/api/v1/images/generate` for ComfyUI providers) |
