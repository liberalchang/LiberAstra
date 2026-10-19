# LiberAstra

[English](#english) | 自托管 AIGC 聚合编排平台 · MIT

对接局域网或本地的 ComfyUI、Ollama、OpenAI 兼容服务，以及云端模型 API，提供语音、图像、视频三大能力。**平台本身不做模型推理**，只做编排。

## 功能

- **语音**：文字转语音（OpenAI 兼容 TTS、edge-tts 兜底）、声音克隆音色库、语音转文字（txt/srt/vtt/json 字幕导出）
- **图像**：ComfyUI 工作流驱动的文生图 / 图生图 / 修复放大，在线图像 API（gpt-image 及兼容网关），统一 PromptField + 场景模板库的 LLM 提示词优化
- **视频**：快速创作（一句话出短视频：LLM 脚本 → 分镜 → 逐帧 TTS+图像 → 字幕 → 拼接+BGM）、自定义素材成片、数字人口播、图生视频、动作迁移、分镜编辑器
- **平台**：单用户 + API Token、持久化任务队列（SSE 进度、取消/重试）、Provider 密钥加密、工作流包导入向导、中英文界面、明暗主题
- **接入**：Web UI、`astra` CLI、MCP Server、OpenAI 兼容 `/v1`（chat/audio/images）

## 快速开始

```bash
docker compose up -d --build     # http://localhost:8000，数据在 ./data
```

首次访问创建管理员账号，然后到「设置 → 服务提供方」添加服务（如 Ollama、ComfyUI、或只加一个 edge_tts 即可立即体验 TTS）。

源码运行与开发指南见下文；详细文档在 [docs/](docs/)：架构、API、Provider 接入、[部署](docs/deployment.md)、[分置部署教程](docs/分置部署教程.md)。

## 开发

```bash
# 后端（Python 3.11+）
cd backend
uv venv .venv && uv pip install -e ".[dev]"
uv run pytest                 # 测试（55+）
uv run ruff check .           # lint
uv run astra serve --reload   # 启动 API（http://localhost:8000，文档在 /docs）

# 前端（Node 20+，另开一个终端）
cd frontend
npm install
npm run dev                   # http://localhost:5173（代理 /api 到 8000）
npm run build                 # 产物 dist/ 由后端托管
```

CLI（需先 `astra login`）：

```bash
astra tts "你好" --voice zh-CN-XiaoxiaoNeural -o hello.mp3
astra image gen --prompt "一只橘猫" -o ./out
astra video quick --topic "三个提高效率的小技巧" --voice zh-CN-XiaoxiaoNeural -o v.mp4
astra mcp                     # MCP Server（stdio）
```

## 仓库结构

- `backend/` — FastAPI 后端、`astra` CLI、MCP、Alembic 迁移、内置工作流包（`workflows/`）
- `frontend/` — React 19 + Vite + Tailwind v4 + i18next
- `docker/`、`docker-compose.yml` — 单镜像（ffmpeg + 中文字体）与可选 profile（ollama/comfyui/postgres）
- `skills/liberastra/` — Agent Skill
- `docs/` — 架构 / API / Provider 接入 / 部署
- `.github/workflows/ci.yml` — lint、测试、前端构建、镜像构建

## 参考项目

LiberAstra 以重新实现为主；下列上游仓库是设计与部分素材的参考来源。协议与移植范围见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

| 项目 | 原 GitHub | 协议 | 本仓库如何参考 |
|------|-----------|------|----------------|
| [Pixelle-Video](https://github.com/AIDC-AI/Pixelle-Video) | https://github.com/AIDC-AI/Pixelle-Video | Apache-2.0 | 视频流水线设计；分镜模板与素材分析工作流移植自其仓库 |
| [Dreamifly](https://github.com/LastLighter/Dreamifly) | https://github.com/LastLighter/Dreamifly | MIT | 图像能力与 ComfyUI 工作流模板映射的设计参考 |
| [Liber_SpeechAPI](https://github.com/liberalchang/Liber_SpeechAPI) | https://github.com/liberalchang/Liber_SpeechAPI | AGPL-3.0 | **仅参考接口形态**；本仓库 `services/speech` 为独立实现，不打包其源码 |

功能迁移方法见 [docs/功能迁移优化方法.md](docs/功能迁移优化方法.md)。

---

## English

LiberAstra is a self-hosted, single-user AIGC orchestration hub (MIT). It orchestrates external inference services — ComfyUI, Ollama, OpenAI-compatible servers, and cloud APIs — for speech, image, and video generation. It never runs models itself.

- **Speech**: TTS (OpenAI-compatible, edge-tts fallback), voice library with cloning metadata, ASR with srt/vtt/txt/json export
- **Image**: ComfyUI workflow-pack-driven T2I / I2I / upscale, online image APIs, LLM prompt optimization
- **Video**: one-topic short-video pipeline (LLM script → storyboard → per-frame TTS+image → subtitles → concat+BGM), custom assets, digital human, I2V, motion transfer, storyboard editor
- **Clients**: Web UI (zh/en), `astra` CLI, MCP server, OpenAI-compatible `/v1` endpoints

Run with Docker: `docker compose up -d --build` → http://localhost:8000. See [docs/](docs/) for details.

### Reference projects

Upstream repos LiberAstra drew from (re-implementation first; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for licenses and what was ported):

| Project | Original GitHub | License | How we use it |
|---------|-----------------|---------|---------------|
| [Pixelle-Video](https://github.com/AIDC-AI/Pixelle-Video) | https://github.com/AIDC-AI/Pixelle-Video | Apache-2.0 | Video pipeline design; storyboard templates and analysis workflows ported |
| [Dreamifly](https://github.com/LastLighter/Dreamifly) | https://github.com/LastLighter/Dreamifly | MIT | Image UX / ComfyUI workflow-mapping design reference |
| [Liber_SpeechAPI](https://github.com/liberalchang/Liber_SpeechAPI) | https://github.com/liberalchang/Liber_SpeechAPI | AGPL-3.0 | **API shape only**; `services/speech` is an independent implementation |
