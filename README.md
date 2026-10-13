# LiberAstra

自托管 AIGC 聚合编排平台。对接局域网或本地的 ComfyUI、Ollama、OpenAI 兼容服务，以及云端模型 API，提供文字转语音、语音转文字、图片生成和视频生成。

平台本身不做模型推理。协议为 MIT。

## 开发

```bash
# 后端（Python 3.11+）
cd backend
uv venv .venv && uv pip install -e ".[dev]"
uv run pytest                 # 测试
uv run ruff check .           # lint
uv run astra serve --reload   # 启动 API（http://localhost:8000，文档在 /docs）

# 前端（Node 20+，另开一个终端）
cd frontend
npm install
npm run dev                   # http://localhost:5173（代理 /api 到 8000）
npm run build                 # 产物 dist/ 由后端托管
```

首次访问会进入初始化向导，创建管理员账号。配置见 `.env.example`。

## Docker

```bash
docker compose up -d --build          # http://localhost:8000，数据在 ./data
docker compose --profile ollama up -d # 可选：一键带 Ollama / comfyui / postgres
```

## 仓库结构

- `backend/` — FastAPI 后端、`astra` CLI、Alembic 迁移（`liberastra/` 包）
- `frontend/` — React 19 + Vite + Tailwind v4 + shadcn 风格组件
- `docker/` — 单镜像 Dockerfile（前端构建 + Python 运行时 + ffmpeg）
- `docker-compose.yml` — 主服务 + 可选 profile（ollama / comfyui / postgres）
- `.github/workflows/ci.yml` — lint、测试、前端构建、镜像构建
