# LiberAstra HTTP API

The CLI and MCP server use the same HTTP API. Use it directly only for capabilities the CLI does not wrap yet.

## Base URL and auth

- Base URL: the server root, for example `http://127.0.0.1:8000`.
- Auth: `Authorization: Bearer astra_...`.
- API tokens are created in the Web UI or by `astra login`.
- Interactive OpenAPI docs: `GET /docs` on the server.

Most generation endpoints return `202` with a job object:

```json
{
  "id": "0f1c...",
  "kind": "image.generate",
  "status": "queued",
  "progress": 0,
  "created_at": "..."
}
```

Poll `GET /api/v1/jobs/{id}` until `status` is `succeeded`, `failed`, or `canceled`. Succeeded jobs list outputs under `outputs`; assets have `asset_id` and are downloaded from `/api/v1/assets/{asset_id}/content`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/healthz` | Health and version |
| `POST` | `/api/v1/auth/login` | Username/password login |
| `GET` | `/api/v1/auth/me` | Current user |
| `GET` | `/api/v1/providers` | List providers |
| `POST` | `/api/v1/providers` | Create provider |
| `POST` | `/api/v1/providers/{id}/test` | Test provider |
| `GET` | `/api/v1/providers/{id}/models` | List provider models |
| `GET` | `/api/v1/workflows` | List workflow packs |
| `POST` | `/api/v1/images/generate` | Text-to-image |
| `POST` | `/api/v1/images/edit` | Image-to-image / multi-reference (multipart, field `images`) |
| `POST` | `/api/v1/images/depth` | Depth map |
| `POST` | `/api/v1/tts` | Text-to-speech (`options` JSON object) |
| `POST` | `/api/v1/asr` | Speech-to-text (multipart, field `file`, optional `options` JSON) |
| `POST` | `/api/v1/videos/quick` | Quick video |
| `POST` | `/api/v1/videos/i2v` | Image-to-video (multipart) |
| `POST` | `/api/v1/videos/avatar` | Digital human |
| `POST` | `/api/v1/videos/motion` | Motion transfer |
| `GET` | `/api/v1/jobs` | List jobs (`status_filter`, `kind`, `limit`) |
| `GET` | `/api/v1/jobs/{id}` | Get job |
| `POST` | `/api/v1/jobs/{id}/cancel` | Cancel job |
| `POST` | `/api/v1/jobs/{id}/retry` | Retry job |
| `GET` | `/api/v1/assets` | List assets |
| `GET` | `/api/v1/assets/{id}` | Get asset metadata |
| `GET` | `/api/v1/assets/{id}/content` | Download asset |
| `DELETE` | `/api/v1/assets/{id}` | Delete asset |
| `GET` | `/api/v1/voices` | List saved voices |
| `POST` | `/api/v1/voices` | Create a cloned voice |
| `GET` | `/api/v1/characters` | List characters |
| `POST` | `/api/v1/characters` | Create character |
| `GET` | `/api/v1/canvases` | List canvases |
| `POST` | `/api/v1/canvases` | Create canvas |
| `POST` | `/api/v1/tools/concat` | Concatenate media |
| `POST` | `/api/v1/vc` | Voice conversion (multipart, optional `options` JSON) |

## Examples

Text-to-image:

```bash
curl -s http://127.0.0.1:8000/api/v1/images/generate \
  -H "Authorization: Bearer $LIBERASTRA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"一只橘猫，逆光","workflow":"qwen_image_21","width":1024,"height":1024}'
```

Image edit:

```bash
curl -s http://127.0.0.1:8000/api/v1/images/edit \
  -H "Authorization: Bearer $LIBERASTRA_TOKEN" \
  -F images=@input.png \
  -F prompt='把背景换成海滩' \
  -F workflow=qwen_image_21_edit
```

Speech-to-text:

```bash
curl -s http://127.0.0.1:8000/api/v1/asr \
  -H "Authorization: Bearer $LIBERASTRA_TOKEN" \
  -F file=@talk.wav \
  -F formats=srt \
  -F language=zh
```

Speech `options` (TTS JSON body, ASR/VC multipart field) are model-specific and only supported by `liber_speech` providers. Examples: TTS `{"speed":0.9,"exaggeration":0.7}`; ASR `{"timestamps":"word","vad_filter":true,"hotwords":"LiberAstra 张三"}`; VC `{"convert_all":true,"denoise":true,"diffusion_steps":10}`. The speech service validates keys, ranges, and model support, and returns structured `invalid_parameters` errors.

## Notes

- ComfyUI providers need a workflow pack for image/video/ComfyUI-speech jobs. Pass `workflow` explicitly when more than one pack has the same capability.
- OpenAI-compatible cloud models can be used by omitting `workflow` and setting `model` (and a provider).
- Download outputs by asset id; do not assume a file path from the job params.
