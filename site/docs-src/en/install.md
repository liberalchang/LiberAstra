---
title: Install / Download
---

# Install / Download

LiberAstra's models do not run in this process. After installing the orchestration desk, connect your own ComfyUI, Ollama, speech service, or OpenAI-compatible API. Weight download links for the built-in workflows and speech services are in [Model resources](/en/models).

## Docker (recommended)

In the repository root:

```bash
cp .env.example .env
docker compose up --build -d
```

By default the app is available at `http://localhost:8000`, and data is stored in `./data`. The first visit walks you through creating an administrator account; then add the services that actually run inference under **Settings → Providers**.

If port 8000 is already in use on the host, set this in `.env`:

```bash
LIBERASTRA_PUBLISH_PORT=18000
```

Open `http://<host>:18000`; the container still listens on 8000 internally.

## Common environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `LIBERASTRA_SECRET_KEY` | Generated automatically at `data/.secret_key` | Master key for JWT signing and secret encryption. Set it explicitly in production; migrate it together with your data. |
| `LIBERASTRA_DATABASE_URL` | SQLite `data/liberastra.db` | PostgreSQL: `postgresql+psycopg://...`; install `liberastra[postgres]`. |
| `LIBERASTRA_DATA_DIR` | `./data` (`/data` in the container) | outputs / uploads / voices / workflows / prompts / logs |
| `LIBERASTRA_PUBLISH_PORT` | `8000` | Host port mapping |
| `LIBERASTRA_HOST` / `LIBERASTRA_PORT` | `0.0.0.0` / `8000` | Container or process listen address |
| `LIBERASTRA_CLEANUP_RETENTION_DAYS` | `0` (disabled) | Days to keep finished jobs and outputs |

Priority: environment variables > `.env` > defaults. See `.env.example` in the repository root for the full example.

## Optional full-stack profiles

If you want to run Ollama, ComfyUI, PostgreSQL, or the speech service on the same machine:

```bash
docker compose --profile ollama up -d
docker compose --profile comfyui up -d
docker compose --profile postgres up -d
docker compose --profile speech up -d
docker compose --profile depth up -d
```

ComfyUI / speech / depth services need the NVIDIA Container Toolkit. It is usually better to put inference services on a GPU host and run only LiberAstra on the application host.

## Split deployment

Use this when the application host runs only Web/API and `data/`, while the GPU host runs Ollama, ComfyUI, and Liber Speech over the LAN.

```text
Application host LiberAstra :18000  ──LAN──▶  GPU host Ollama :11434
                                              ComfyUI :8188
                                              Liber Speech :5555
```

Set the GPU host's LAN IP in **Providers**:

| Name | Type | Base URL |
| --- | --- | --- |
| comfy | ComfyUI | `http://<gpu-host>:8188` |
| ollama | Ollama | `http://<gpu-host>:11434` |
| speech | Liber Speech API | `http://<gpu-host>:5555` |

For services on the same host, use `host.docker.internal`; for another machine, use its LAN IP, not `localhost`.

### Migrate existing data

1. Stop writes on the old instance to avoid a half-written SQLite file.
2. Archive the entire data directory, keeping `.secret_key`, the database, outputs, uploads, voices, workflows, and prompts.
3. Extract it into `data/` in the new machine's repository root, matching compose's `./data:/data`.
4. Start the app, sign in with the original administrator account, check provider addresses, and run one test job.

Do not put `data/` in a cloud-sync directory.

## Run from source

```bash
cd backend && uv venv .venv && uv pip install -e ".[dev]"
cd ../frontend && npm install && npm run build
cd ../backend && uv run astra serve
```

Development mode: backend `uv run astra serve --reload`, frontend `npm run dev` (5173, proxying `/api` to 8000).

## Where files live

When the backend is started from `backend`:

| Content | Path |
|------|------|
| Database | `backend/data/liberastra.db` |
| Outputs | `backend/data/outputs/` |
| Uploads | `backend/data/uploads/` |
| User workflow packs | `backend/data/workflows/` |
| User templates | `backend/data/templates/` |
| Prompt templates | `backend/data/prompts/` |
| Music library | `backend/data/bgm/` |
| Character images | `backend/data/characters/` |
| Plugin state | `backend/data/plugins.json` |
| Plugin models | `backend/data/plugins/speech/models`, `backend/data/plugins/depth/models` |
| Shared plugin runtime | `%LOCALAPPDATA%\LiberAstra\plugin-runtime` (the installer uses `plugins\runtime` under the data directory) |

Canvas graphs and each execution record are stored in the database; there is no separate canvas directory. Node outputs are in `outputs/` and are hidden from the asset list until **Save to asset library** is clicked.

The Windows installer stores data in `%LOCALAPPDATA%\LiberAstra\data`, not the program directory. Replace `backend/data` in the table above with that directory. Plugin models are under `plugins\speech\models` and `plugins\depth\models` there.

Do not put `backend/data` in a cloud-sync or sync directory, or the database may fail with `disk I/O error`.

## Operations

- Health check: `GET /healthz`
- Logs: `data/logs/app.log` (50MB rotation × 5)
- Backup: `GET /api/v1/system/backup` (administrator; zips the data directory, excluding logs)
- Container logs: `docker compose logs -f --tail 100`
- Stop: `docker compose down` (does not delete `./data`)

## Windows installer

Download the installer from [GitHub Releases](https://github.com/liberalchang/LiberAstra/releases). The Start-menu entry starts the same service as Docker. For the command line, run `runtime\python.exe -m liberastra.cli.main` in the install directory, or add `astra` to PATH.
