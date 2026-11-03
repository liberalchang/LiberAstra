---
title: Install / Download
---

# Install / Download

LiberAstra installs the orchestration app only. Ollama, ComfyUI, speech services, and model weights are separate. After the app starts, create the admin account and add providers in Settings.

## Docker (recommended)

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8000`. Data is stored in `./data`. If port 8000 is taken, set `LIBERASTRA_PUBLISH_PORT=18000` in `.env` and open `http://<host>:18000`.

### Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `LIBERASTRA_SECRET_KEY` | `data/.secret_key` | JWT and provider-key encryption. Set explicitly in production; move it with the data directory |
| `LIBERASTRA_DATABASE_URL` | SQLite `data/liberastra.db` | PostgreSQL URL; install `liberastra[postgres]` |
| `LIBERASTRA_DATA_DIR` | `./data` (`/data` in Docker) | Database, outputs, uploads, voices, workflows, prompts, logs |
| `LIBERASTRA_PUBLISH_PORT` | `8000` | Host port published by Compose |
| `LIBERASTRA_HOST` / `LIBERASTRA_PORT` | `0.0.0.0` / `8000` | Listen address inside the container/process |
| `LIBERASTRA_CLEANUP_RETENTION_DAYS` | `0` (off) | Retention for finished jobs and outputs |

### Optional local profiles

```bash
docker compose --profile ollama up -d
docker compose --profile comfyui up -d
docker compose --profile speech up -d
docker compose --profile postgres up -d
```

ComfyUI and the speech plugin need the NVIDIA Container Toolkit. A separate GPU host is usually better.

## Split-host deployment

Run LiberAstra on the app host and inference services on a GPU host:

```text
App host LiberAstra :18000 ---LAN---> GPU host Ollama :11434
                                      ComfyUI :8188
                                      Liber Speech :5555
```

Add providers with the GPU host's LAN IP:

| Name | Type | Base URL |
| --- | --- | --- |
| comfy | ComfyUI | `http://<gpu-host>:8188` |
| ollama | Ollama | `http://<gpu-host>:11434` |
| speech | Liber Speech API | `http://<gpu-host>:5555` |

Use `host.docker.internal` only for services on the same Docker host. Do not use `localhost` for another machine.

### Move existing data

Stop the old instance, copy the whole `data/` directory (including `data/.secret_key`, the database, outputs, uploads, voices, workflows, and prompts), place it under the new repo root, and restart. Log in with the old admin account and verify the provider URLs.

## Run from source

```bash
cd backend && uv venv .venv && uv pip install -e ".[dev]"
cd ../frontend && npm install && npm run build
cd ../backend && uv run astra serve
```

Development: `uv run astra serve --reload` in `backend`, `npm run dev` in `frontend` (5173 proxies `/api` to 8000).

## Operations

- Health: `GET /healthz`
- Logs: `data/logs/app.log`
- Backup: `GET /api/v1/system/backup` (admin)
- Stop: `docker compose down` (keeps `./data`)

## Windows

Download the installer from GitHub Releases. It includes Python and the built web UI; the target PC needs no separate Node or Python install. ffmpeg is required for video assembly.
