---
title: Providers
---

# Providers

A provider is one external service connection. Each type declares capability tags (`llm`, `tts`, `asr`, `image`, `video`); calls route by capability, not by vendor.

| Type | Capability | Notes | Default base URL |
| --- | --- | --- | --- |
| `openai_compatible` | llm | vLLM, LM Studio, DeepSeek, Qwen, Volcengine, Kimi, Zhipu, SiliconFlow, OpenRouter | `http://localhost:8000/v1` |
| `ollama` | llm | Local Ollama (`/api/tags`, chat through `/v1`) | `http://localhost:11434` |
| `openai_tts` | tts | OpenAI / Kokoro-FastAPI / Speaches / SiliconFlow | `http://localhost:8880/v1` |
| `edge_tts` | tts | Microsoft online TTS, mp3 only | - |
| `openai_stt` | asr | OpenAI / Groq / Speaches / faster-whisper-server | `http://localhost:8100/v1` |
| `comfyui` | image, video | LAN ComfyUI, driven by workflow packs | `http://localhost:8188` |
| `openai_images` | image | OpenAI gpt-image and compatible gateways | `https://api.openai.com/v1` |

## Add a provider

Use Settings -> Providers, or the CLI:

```bash
astra provider add --name home-ollama --type ollama --base-url http://192.168.1.10:11434
astra provider test 1
astra provider models 1
```

`api_key` is encrypted before storage and the API returns only `has_api_key`. `concurrency` limits parallel jobs (default 2). Put defaults such as `{"model": "qwen3:8b"}` in `extra`.

## ComfyUI workflow packs

A ComfyUI provider is driven by workflow packs. A pack is `workflow.json` (ComfyUI -> Save (API Format)) plus `manifest.yaml`:

```yaml
name: my_t2i
capability: t2i            # t2i / i2i / upscale / t2v / i2v / avatar / motion / tts
inputs:
  prompt: { node: "6", field: inputs.text, type: str, required: true }
  image:  { node: "1", field: inputs.image, type: image }
  seed:   { node: "3", field: inputs.seed, type: int, default: -1 }
outputs: { node: "9", key: images }
requirements:
  nodes: [KSampler]
```

Import through Settings -> Workflow Packs. LiberAstra packs, ComfyUI API Format, and canvas JSON are supported; same-name user packs override built-ins.

## Add a new provider type (development)

Register a provider type under `backend/liberastra/providers` with its capability tags and add it to the capability registry. The Providers page and workflow pages use those tags to decide where the provider appears.
