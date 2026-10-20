# LiberAstra

[English](#english) | 自托管 AIGC 聚合编排平台 · MIT

对接局域网或本地的 ComfyUI、Ollama、OpenAI 兼容服务，以及云端模型 API，提供语音、图像、视频三大能力。**平台本身不做模型推理**，只做编排。

## 功能

平台本身不做模型推理。界面按侧栏分组；出图、出声、出视频都交给已配置的外部服务。各页提示词共用 **PromptField**（原始稿 / 优化稿、场景模板、✨ 提交优化任务，刷新后仍可接着看）。

### 首页

工作台：按图像 / 视频 / 语音切换，写一句提示词即可进入对应功能。下方是常用入口。

![首页](docs/images/home.png)

### 图像生成

- **文生图**：选图像服务与 `t2i` 工作流包。内置 Qwen-Image 2.1（官方 / 越狱）与传统 checkpoint 包。参数区可换 UNET、文本编码器、VAE；越狱包可开关 Uncensored LoRA。也支持在线图像 API。
- **图生图与编辑**：整图编辑、多参考（最多 4 张，提示词用 image 1 / image 2 指代）、局部重绘（原图 + 蒙版）。官方包与越狱包成对。
- **修复与放大**：走 Upscale 模型，不是重新生图。

![文生图](docs/images/image-generate.png)

![图生图与编辑](docs/images/image-edit.png)

### 视频生成

- **快速创作**：AI 创作 / 固定文案 / 批量。口播拆成多镜，再按分镜模板出画面：静态排版、逐镜插图或逐镜文生视频，最后配音、字幕、BGM 拼接。是否用 LLM 写画面提示词由开关决定；工作流包里的 Guide 增强只跟所选包有关，两者互不关闭。包声明了 Turbo 时可开关加速 LoRA。
- **自定义素材**：已有图片或视频做成口播短片。可选素材分析、静图动画（`i2v`）、配音与 BGM。
- **数字人口播**：人物图 + 口播文案 → TTS → avatar 工作流（需自备并导入工作流包）。
- **图生视频**：首帧 + 提示词，走 `i2v`。内置 MiniMax H3 官方、越狱、越狱+提示词增强三套，可开 Turbo。
- **动作迁移**：参考视频 + 目标图（需自备 motion 工作流包）。
- **模板管理**：上传或覆盖分镜模板（`static_` / `image_` / `video_`）。

![快速创作](docs/images/video-quick.png)

![自定义素材](docs/images/video-assets.png)

![图生视频](docs/images/video-i2v.png)

### 语音服务

- **文字转语音**：按服务类型切换控件。edge-tts、OpenAI 兼容 TTS、Liber Speech 音色库，或 Comfy `tts` 工作流。
- **语音转文字**：导出 txt / srt / vtt / json。
- **音色库**：登记可复用的克隆音色。
- **音乐库**：上传 BGM，供快速创作与自定义素材选用。

![文字转语音](docs/images/speech-tts.png)

### 平台与接入

- **作品**、**任务**：生成结果与任务进度（SSE、取消 / 重试）。
- **设置**：服务提供方（地址与密钥）、工作流包导入、默认 LLM 与运行参数。
- **接入**：Web UI（中英文、明暗主题）、`astra` CLI、MCP Server、OpenAI 兼容 `/v1`（chat / audio / images）。单用户，API Token；Provider 密钥加密保存。

模型怎么配对、内置包名单见 [docs/使用文档.md](docs/使用文档.md)。

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

### 功能

The app does not run models. Prompt fields share one control: raw and optimized drafts, scene presets, and a sparkle action that keeps running if you refresh.

**Home.** Pick image, video, or speech and jump in with one line.

![Home](docs/images/home.png)

**Images.** Text-to-image (Qwen-Image 2.1 official or uncensored packs, or a classic checkpoint; uncensored packs can toggle an Uncensored LoRA). Image edit: full-frame, up to four references, or inpaint with a mask. Upscale uses an upscale model, not a new generation. Online image APIs are supported.

![Text to image](docs/images/image-generate.png)

![Image edit](docs/images/image-edit.png)

**Video.** Quick create turns a topic or a fixed script into a short: storyboard, per-shot stills or text-to-video, TTS, subtitles, and BGM. The LLM visual-prompt switch and a pack’s built-in Guide enhancer are independent. Custom assets reuse your clips (optional analysis and image-to-video). Also: talking avatar, image-to-video (MiniMax H3 official / uncensored / enhancer, optional Turbo LoRA), motion transfer, and storyboard templates.

![Quick create](docs/images/video-quick.png)

![Custom assets](docs/images/video-assets.png)

![Image to video](docs/images/video-i2v.png)

**Speech.** Text-to-speech (edge-tts, OpenAI-compatible, Liber Speech, or a Comfy TTS pack), speech-to-text (txt/srt/vtt/json), a voice library, and a music library for BGM.

![Text to speech](docs/images/speech-tts.png)

**Platform.** Asset library, job queue (SSE, cancel/retry), providers, workflow-pack import, default LLM. Clients: Web UI (zh/en, light/dark), `astra` CLI, MCP server, OpenAI-compatible `/v1`.

Model pairing is in [docs/使用文档.md](docs/使用文档.md).

Run with Docker: `docker compose up -d --build` → http://localhost:8000. See [docs/](docs/) for details.

### Reference projects

Upstream repos LiberAstra drew from (re-implementation first; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for licenses and what was ported):

| 项目                                                                 | Original GitHub                                 | License    | How we use it                                                             |
| ------------------------------------------------------------------ | ----------------------------------------------- | ---------- | ------------------------------------------------------------------------- |
| [Pixelle-Video](https://github.com/AIDC-AI/Pixelle-Video)          | https://github.com/AIDC-AI/Pixelle-Video        | Apache-2.0 | Video pipeline design; storyboard templates and analysis workflows ported |
| [Dreamifly](https://github.com/LastLighter/Dreamifly)              | https://github.com/LastLighter/Dreamifly        | MIT        | Image UX / ComfyUI workflow-mapping design reference                      |
| [Liber_SpeechAPI](https://github.com/liberalchang/Liber_SpeechAPI) | https://github.com/liberalchang/Liber_SpeechAPI | AGPL-3.0   | **API shape only**; `services/speech` is an independent implementation    |
