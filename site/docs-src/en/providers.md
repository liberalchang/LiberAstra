---
title: Providers
---

# Provider integration guide

## Concepts

A provider is the connection configuration for one external service. Each type declares capability tags (`llm` / `tts` / `asr` / `image` / `video`); calls are routed by tag, not by vendor.

## Built-in types

| Type | Capability | Description | Default base_url |
| --- | --- | --- | --- |
| `openai_compatible` | llm | vLLM / LM Studio / DeepSeek / Qwen / Volcano Ark / Kimi / Zhipu / SiliconFlow / OpenRouter | `http://localhost:8000/v1` |
| `ollama` | llm | Local Ollama (models from `/api/tags`, chat via `/v1`) | `http://localhost:11434` |
| `openai_tts` | tts | OpenAI / Kokoro-FastAPI / Speaches / SiliconFlow | `http://localhost:8880/v1` |
| `edge_tts` | tts | Microsoft online TTS, zero-config fallback (mp3 only) | — |
| `openai_stt` | asr | OpenAI / Groq / Speaches / faster-whisper-server | `http://localhost:8100/v1` |
| `comfyui` | image, video | LAN ComfyUI, driven by workflow packs | `http://localhost:8188` |
| `openai_images` | image | OpenAI gpt-image and compatible gateways | `https://api.openai.com/v1` |

## Add a provider

In the Web UI under **Settings → Providers**, or with the CLI:

```bash
astra provider add --name home-ollama --type ollama --base-url http://192.168.1.10:11434
astra provider test 1
astra provider models 1
```

- `api_key` is Fernet-encrypted before storage; the API only returns `has_api_key`.
- `concurrency` limits concurrent jobs for that provider (default 2).
- Extra configuration (such as a default model) goes in `extra`: `{"model": "qwen3:8b"}`.

## ComfyUI workflow packs

A ComfyUI provider is driven by workflow packs. A pack is a `workflow.json` (ComfyUI → Save (API Format)) plus a `manifest.yaml`:

```yaml
name: my_t2i
capability: t2i            # canonical: t2i / i2i / upscale / t2v / i2v / avatar / motion / tts
inputs:
  prompt: { node: "6", field: inputs.text, type: str, required: true }
  image:  { node: "1", field: inputs.image, type: image }   # image/video/audio inputs are uploaded to ComfyUI automatically
  seed:   { node: "3", field: inputs.seed, type: int, default: -1 }  # -1 = random
outputs: { node: "9", key: images }   # images / videos / gifs
# Optional: acceleration LoRA (removed when disabled; downstream reconnects to bypass_input)
# accel:
#   node: "200"
#   bypass_input: model
#   lora: { field: inputs.lora_name, options_from: loras, match: "minimax_h3", recommended: "xxx.safetensors" }
#   strength: { field: inputs.strength_model, default: 1.0 }
#   preset: { steps: 8 }
requirements:
  nodes: [KSampler]        # used by import preflight
```

Import options: Web UI **Settings → Workflow packs** (LiberAstra packs, API Format, and canvas JSON with `nodes`/`links` converted automatically), or write to `data/workflows/<name>/` (a user pack with the same name overrides the built-in one). Video examples: built-in packs `minimax_h3_i2v`, `minimax_h3_i2v_uncensored`, `minimax_h3_i2v_enhancer`.

## Add a provider type (development)

Register capability tags in `backend/liberastra/providers` following the existing provider types, and add the type to the capability registry. The Web UI **Providers** page uses capability tags to decide which pages and workflows are available.
