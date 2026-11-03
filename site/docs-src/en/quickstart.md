---
title: Quick start
---

# Quick start

LiberAstra only orchestrates external services. Four steps: start the app, add providers, import workflow packs, create something.

## 1. Start

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8000`. The first run creates the admin account. See [Install](/en/install) for other methods.

## 2. Add providers

Go to Settings -> Providers and add the services you actually run:

| Use | Type | Example |
| --- | --- | --- |
| LAN ComfyUI | ComfyUI | `http://192.168.1.20:8188` |
| Local Ollama | Ollama | `http://localhost:11434` |
| Liber Speech | Liber Speech API | `http://localhost:5555` |
| Online TTS | Local (Microsoft Edge TTS) | zero config |
| OpenAI-compatible LLM | OpenAI compatible | `http://localhost:8000/v1` |

Only enabled providers with the matching capability appear on each page. Models do not run inside LiberAstra.

## 3. Import workflow packs

Image, video, and ComfyUI speech tasks need a workflow pack. Go to Settings -> Workflow Packs and import a LiberAstra pack, ComfyUI API Format, or canvas JSON. Built-ins such as `qwen_image_21`, `flux3_klein`, and `minimax_h3_avatar` ship with the app.

## 4. Create

Open the Overview command desk, write an intent, and choose image, video, or speech. Or go directly to a studio from the sidebar. Jobs go to the job center and outputs return to the asset library.

## Tips

- Web, CLI, MCP, and OpenAI-compatible `/v1` share one task system.
- Model downloads, VRAM, and process security belong to ComfyUI / Ollama / speech services.
- Development: `uv run astra serve --reload` plus `npm run dev` (5173 proxies `/api` to 8000).
- Docs: [Install](/en/install) . [Providers](/en/providers) . [CLI](/en/integration/cli) . [API](/en/integration/api)
