---
title: API
---

# API

All endpoints except `/healthz` and `/auth/*` require `Authorization: Bearer <JWT or astra_ token>`. Interactive Swagger UI is available at `/docs` after the app starts.

## Auth

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/auth/status` | Whether setup is complete |
| POST | `/api/v1/auth/setup` | Create the first admin |
| POST | `/api/v1/auth/login` | Return a JWT |
| GET/POST/DELETE | `/api/v1/tokens[/{id}]` | Issue, list, revoke API tokens |

## Providers and jobs

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/capabilities` | Provider registry and capability tags |
| GET/POST | `/api/v1/providers` | List / create providers |
| PATCH/DELETE | `/api/v1/providers/{id}` | Update / delete |
| POST | `/api/v1/providers/{id}/test` | Test connection |
| GET | `/api/v1/providers/{id}/models` | Fetch and cache models |
| GET | `/api/v1/jobs` | List jobs (`status_filter`, `kind`, `limit`) |
| GET | `/api/v1/jobs/{id}` | Job detail |
| GET | `/api/v1/jobs/{id}/events` | SSE progress |
| POST | `/api/v1/jobs/{id}/cancel` / `retry` | Cancel / retry |

Generation endpoints return `202` with a Job by default. Add `?wait=true` to wait for the terminal state.

## Capabilities

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/llm/chat` | LLM chat job |
| POST | `/api/v1/tts` | Text to speech |
| POST | `/api/v1/asr` | Speech to text (multipart; txt/srt/vtt/json) |
| GET/POST/DELETE | `/api/v1/voices` | Voice library |
| POST | `/api/v1/images/generate` / `edit` | Text-to-image / edit |
| POST | `/api/v1/images/optimize-prompt` | LLM prompt expansion |
| GET/POST/DELETE | `/api/v1/workflows[/{name}]`, `/workflows/import` | Workflow packs |
| POST | `/api/v1/videos/quick` | Quick Create |
| POST | `/api/v1/videos/i2v` / `avatar` / `motion` / `assets` | Video modes |
| POST | `/api/v1/uploads` | Uploads for workflow parameters |
| GET | `/api/v1/assets[/{id}[/content]]` | Assets and content |
| GET | `/api/v1/system/info`, POST `cleanup`, GET `backup` | System operations |

## OpenAI-compatible subset

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/chat/completions` | Default LLM (no streaming yet) |
| POST | `/v1/audio/speech` | Default TTS provider |
| POST | `/v1/audio/transcriptions` | Default ASR provider |
| POST | `/v1/images/generations` | Online image provider |
