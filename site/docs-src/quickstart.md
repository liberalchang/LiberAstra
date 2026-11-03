---
title: 快速开始
---

# 快速开始

LiberAstra 只编排外部服务。第一次跑起来需要四步：启动编排台、接服务、导入工作流包、开始创作。

## 1. 启动

在仓库根目录：

```bash
cp .env.example .env
docker compose up -d --build
```

打开 `http://localhost:8000`。首次进入会引导创建管理员账号。更多安装方式见 [安装 / 下载](/install)。

## 2. 接入服务提供方

进入「设置 → 服务提供方」，按你实际运行的服务添加：

| 场景 | 类型 | 地址示例 |
| --- | --- | --- |
| 局域网 ComfyUI | ComfyUI | `http://192.168.1.20:8188` |
| 本地 Ollama | Ollama | `http://localhost:11434` |
| Liber Speech | Liber Speech API | `http://localhost:5555` |
| 在线 TTS | 本地（微软 Edge TTS） | 零配置 |
| OpenAI 兼容 LLM | OpenAI 兼容服务 | `http://localhost:8000/v1` |

只列出已启用、且具备对应能力的 Provider。模型不在 LiberAstra 内运行。

## 3. 导入工作流包

图像 / 视频 / ComfyUI 语音任务需要工作流包。进入「设置 → 工作流包」，可以导入：

- LiberAstra 工作流包
- ComfyUI API Format
- 含 `nodes` / `links` 的画布 JSON（自动转换）

内置包（如 `qwen_image_21`、`flux3_klein`、`minimax_h3_avatar`）随应用分发；同名用户包会覆盖内置包。

## 4. 开始创作

回到「总览」指挥台，写一句创作意图，选择图像、视频或语音，进入对应工作室。也可以直接从左侧菜单进入：

- 图像：文生图、图生图与编辑、修复与放大、深度图
- 视频：快速创作、数字人口播、图生视频、动作迁移
- 语音：文字转语音、语音转文字、音色库、音乐库
- 画布：节点、绑定、导演台与运行

任务会进入任务中心，产物回到资产库。每个任务都保留 Provider、工作流与参数。

## 小贴士

- Web、CLI、MCP 和 OpenAI 兼容 `/v1` 共用同一套任务系统。
- 模型下载、显存和进程安全由 ComfyUI / Ollama / 语音服务负责。
- 本地开发：后端 `uv run astra serve --reload`，前端 `npm run dev`（5173，代理 `/api` 到 8000）。
- 文档：[安装 / 下载](/install) · [服务提供方](/providers) · [CLI](/integration/cli) · [API](/integration/api)
