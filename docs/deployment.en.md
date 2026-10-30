# Deployment

LiberAstra only installs the orchestration app. Ollama, ComfyUI, and the speech plugin are separate processes. They can run on this machine or on another host. The app does not download or run model weights by itself.

After the app is up: create the admin account, then Settings → Providers, and fill in each service URL.

Chinese deploy notes: [deployment.md](./deployment.md). Split-host walkthrough: [分置部署教程](./分置部署教程.md). Download links: [Liberastra部署相关资源下载](./Liberastra部署相关资源下载.md).

## Docker

From the repository root:

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8000`. Data is stored in `./data`.

If port 8000 is already taken, set `LIBERASTRA_PUBLISH_PORT=18000` in `.env` and open `http://<host>:18000`. The process inside the container still listens on 8000.

Optional profiles (only when you want these processes in the same Compose project):

```bash
docker compose --profile ollama up -d      # Ollama on host port 11434
docker compose --profile comfyui up -d     # ComfyUI on 8188 (NVIDIA Container Toolkit)
docker compose --profile speech up -d      # speech plugin on 5555 (NVIDIA)
docker compose --profile postgres up -d    # PostgreSQL; also set LIBERASTRA_DATABASE_URL
```

The speech plugin can also be copied alone: `services/speech`, then `docker compose up -d --build` in that directory. In LiberAstra set the provider URL to `http://<gpu-host>:5555`.

When the app runs in Docker and ComfyUI or Ollama runs on the **same machine's host network**, use `http://host.docker.internal:<port>`. Do not use `localhost` for that path: inside the container, localhost is the container. Another machine on the LAN is reached by that machine's IP.

| Variable | Default | Role |
|----------|---------|------|
| `LIBERASTRA_PUBLISH_PORT` | `8000` | Host port published by Compose |
| `LIBERASTRA_HOST` / `LIBERASTRA_PORT` | `0.0.0.0` / `8000` | Listen address inside the container |
| `LIBERASTRA_DATA_DIR` | `./data` (`/data` in the container) | Database, assets, uploads, logs |
| `LIBERASTRA_SECRET_KEY` | written to `data/.secret_key` if empty | JWT and provider-key encryption. Copy this file when you move the data directory |
| `LIBERASTRA_DATABASE_URL` | SQLite `data/liberastra.db` | Set a Postgres URL and enable the `postgres` profile to switch |
| `LIBER_SPEECH_DEVICE` | `auto` | `auto` / `cuda` / `cpu` on the speech plugin |
| `LIBER_SPEECH_API_KEY` | empty | Shared by the plugin and the LiberAstra provider |
| `LIBER_SPEECH_TTS_MODEL` | `multilingual` | `turbo` / `standard` / `multilingual` |
| `LIBER_SPEECH_ASR_MODEL` | `large-v3` | Speech-to-text model on the plugin |

Health check: `GET /healthz`.

## Windows installer

Download [LiberAstra-Setup.exe](https://github.com/liberalchang/LiberAstra/releases/latest/download/LiberAstra-Setup.exe) from [Releases](https://github.com/liberalchang/LiberAstra/releases). The installer includes a Python runtime and the built web UI. The target PC does not need a separate Python or Node install. After setup, open `http://127.0.0.1:8000`. Data lives in `%LOCALAPPDATA%\LiberAstra\data`.

The installer allows inbound TCP 8000. Other browsers on the LAN can use `http://<this-pc>:8000`.

Video assembly needs `ffmpeg` on `PATH` (`winget install Gyan.FFmpeg`). The Docker image already includes ffmpeg.

Ollama, ComfyUI, and the speech plugin are not inside this installer.

Rebuild locally (not required to install):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

Output: `packaging\windows\output\LiberAstra-Setup.exe`. The build machine needs Node.js 20+, network access, and [Inno Setup 6](https://jrsoftware.org/isdl.php).

## Speech and depth

Online read-aloud can use edge-tts and skip the speech plugin. Local synthesis, transcription, or depth maps are installed inside the app: Resources → Plugins. Liber Speech listens on port 5555, Liber Depth on 5556. Releases do not include `LiberSpeech-Setup.exe`.

On another GPU host, run `services/speech` or `services/depth` with `docker compose up -d --build`, then set the provider URL to `http://<host>:5555` or `http://<host>:5556`. Weights download on first run.

## Models you bring yourself

Weights go into the ComfyUI `models\` tree (portable installs: `ComfyUI\models\`). They are not stored in this repository.

| Use | Download | Put in |
|-----|----------|--------|
| Qwen-Image 2.1 official (UNET, 8B text encoder, VAE) | https://huggingface.co/Comfy-Org/Qwen-Image-2.1 | `diffusion_models/`, `text_encoders/`, `vae/` |
| Qwen-Image 2.1 optional UNET `qwen-image-2.1-UC-int8_convrot.safetensors` | https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized | `diffusion_models/` |
| MiniMax H3 official | https://huggingface.co/Comfy-Org/MiniMax-H3 | `diffusion_models/`, `text_encoders/`, `vae/` |
| H3 optional text encoder (INT8, enhancer pack) | https://huggingface.co/ethanfel/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot | `text_encoders/` |
| H3 optional text encoder (NVFP4) | https://huggingface.co/sakamakismile/Qwen3-VL-32B-Heretic-MiniMax-H3-NVFP4 | `text_encoders/` |
| H3 Turbo LoRA | https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora and https://huggingface.co/lightx2v/Minimax-h3-Turbo | `loras/` |

Pair official packs with official weights. Filename lists are in the Chinese [使用文档](./使用文档.md). Ollama installers and pull examples are in the [download list](./Liberastra部署相关资源下载.md).

## Run from source

```bash
cd backend && uv venv .venv && uv pip install -e ".[dev]"
cd ../frontend && npm install && npm run build
cd ../backend && uv run astra serve
```

Development: `uv run astra serve --reload` in `backend`, and `npm run dev` in `frontend` (`http://localhost:5173`, `/api` proxied to 8000). See [CONTRIBUTING.md](../CONTRIBUTING.md).
