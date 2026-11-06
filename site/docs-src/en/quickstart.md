---
title: Quick start
---

# Quick start

LiberAstra is a local orchestration UI. Image, audio, and video generation are all handed to configured external services; no models run in this process.

Getting started for the first time takes four steps: start the desk, connect services, import workflow packs, and start creating.

## Four steps

### 1. Start the desk

#### Docker

In the repository root:

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8000`. The first visit walks you through creating an administrator account. See [Install / Download](/en/install) for more installation options.

#### Windows installer

On Windows you can install the [LiberAstra installer](/en/install#windows-installer) instead; it opens `http://127.0.0.1:8000` the same way.

#### Local run and development mode

Production only starts the backend. Build the frontend once, then start the backend:

```powershell
uv run astra serve --reload
```

Open `http://127.0.0.1:8000/`. The API and the packaged UI share the same port.

When changing the UI, start the frontend dev server at `http://127.0.0.1:5173/`; `/api` requests are proxied to 8000. Pages served from 8000 only pick up source changes after another `npm run build`.

One account can sign in from several browsers at the same time. Each token lasts about 12 hours; sign in again after it expires.

Download links for the installer, Ollama, ComfyUI, and workflow model files are in [model resources](/en/models).

### 2. Connect service providers

Go to **Settings → Providers** and add the services you actually run:

| Scenario | Type | Example address |
| --- | --- | --- |
| LAN ComfyUI | ComfyUI | `http://192.168.1.20:8188` |
| Local Ollama | Ollama | `http://localhost:11434` |
| Liber Speech | Liber Speech API | `http://localhost:5555` |
| Online TTS | Local (Microsoft Edge TTS) | Zero configuration |
| OpenAI-compatible LLM | OpenAI-compatible service | `http://localhost:8000/v1` |

Only providers that are enabled and have the matching capability are listed. Models do not run inside LiberAstra.

### 3. Import workflow packs

Image / video / ComfyUI speech jobs need workflow packs. Go to **Settings → Workflow packs** and import:

- A LiberAstra workflow pack
- ComfyUI API Format
- A canvas JSON containing `nodes` / `links` (converted automatically)

Built-in packs (such as `qwen_image_21`, `flux3_klein`, `minimax_h3_avatar`) ship with the app; a user pack with the same name overrides the built-in one.

### 4. Start creating

Go back to the **Overview** desk, write a creation intent, choose image, video, or speech, and enter the matching studio. You can also go directly from the left sidebar:

- Image: text-to-image, image-to-image and edit, depth map
- Video: quick create, digital human, image-to-video, motion transfer, custom assets
- Speech: text-to-speech, speech-to-text, voice conversion
- Tools: image concat, video concat, audio concat, image enhance, video enhance
- Canvas: nodes, bindings, director, and runs

Jobs go to the job center and outputs go to the asset library. Every job keeps its provider, workflow, and parameters.

## Understand the three layers

The UI often shows "Service / Provider", "Workflow pack", "Main model / Text encoder / VAE" dropdowns at the same time. They mean different things:

| Layer | Where to choose | What it decides | What it does not decide |
|----|--------|----------|------------|
| **Service provider (Provider)** | Settings → Providers; the "Image/Video/Speech service" on each feature page | **Which machine** receives the request (address, key, enabled) | Which model set or compute graph to use |
| **Workflow pack** | Settings → Workflow packs; the "Workflow / Illustration workflow / Video workflow" dropdowns on each feature page | **Which Comfy compute graph**, parameter mapping, capability (`t2i`/`t2v`/`i2v`/`v2v`…), optional Turbo | Service address |
| **Model file** | After a pack is selected, the parameter area expands from the manifest's `options_from` | **Which exact weight file** on that Comfy machine | The graph structure (decided by the graph) |

### Which layer to change

Therefore:

- Change to another Comfy machine → change the provider.
- Change "official / uncensored / prompt enhancer / Turbo" → mostly by **switching packs**, or by switching to a **matched set of model files** inside the same pack (see the package tables below).
- Feature pages and function nodes on the sidebar **Canvas** all end up using a workflow pack (or a cloud model). The Comfy web UI is used to export workflow packs; use **Canvas** to chain several packs into one flow.
- Image concat, video concat, and audio concat under the sidebar **Tools** are **native local tools**. They do not go through a provider or workflow pack. Image enhance and video enhance do need the ComfyUI `upscale` / `v2v` packs.

### When the capability does not match

When the capability does not match, the dropdown is empty or shows "no xxx workflow pack". Quick create → Generate video lists only packs with `capability: t2v` by default; after a character is selected, `i2v` packs are added. The workflow-pack dropdown shows the capability name and a one-line pack description first; uncensored packs are marked "uncensored". The lightbulb on the right opens the full description from the manifest.

## Interface overview

### Overview page

The sidebar **Overview** is a quick entry point. The three mode cards at the top switch between image, video, and speech: write a prompt in the input, click **Start**, and the matching feature page opens (image → text-to-image, video → quick create, speech → text-to-speech) with the prompt carried over.

The **Tools** section below lists common entry points in four groups:

- Image: text-to-image, image-to-image and edit, depth map.
- Video: quick create, image-to-video, digital human, motion transfer.
- Speech: text-to-speech, speech-to-text, voice conversion.
- Tools: image concat, video concat, audio concat, image enhance, video enhance.

These entries only navigate; actual generation still depends on the provider and workflow pack selected on each feature page.

### Choose from the asset library

Image edit, image enhance, depth map, video enhance, speech-to-text, character library, image-to-video, digital human, motion transfer, and custom assets all have a **Choose from asset library** action below the upload area. You can pick an existing image, video, or audio file instead of uploading it again. Single-select pages apply it immediately; multi-select pages let you check items and click **Confirm selection**. Selected media appears in the thumbnail strip exactly like a local upload and can be removed one by one.

After selection, the task uses the newly uploaded file; the original asset is not affected.

## Tips and next steps

- Web, CLI, MCP, and the OpenAI-compatible `/v1` share the same job system.
- Model downloads, VRAM, and process safety are handled by ComfyUI / Ollama / the speech service.
- Local development: backend `uv run astra serve --reload`, frontend `npm run dev` (5173, proxying `/api` to 8000).
- Docs: [Install / Download](/en/install) · [Providers](/en/providers) · [CLI](/en/integration/cli) · [API](/en/integration/api)
