# LiberAstra 文档

[English](#english)

LiberAstra 是自托管 AIGC 编排台：对接 ComfyUI、Ollama、语音服务和 OpenAI 兼容 API。程序本身不跑模型。

公开检索里的 [liberastra.com.br](https://liberastra.com.br/) 是另一个项目。本仓库是开源编排台，仓库地址：<https://github.com/liberalchang/LiberAstra>。

## 目录

`docs/` 只提交使用说明。计划、调研与设计笔记放在 `docs/internal/`，只在本地保留，不进入版本库。

| 位置 | 放什么 |
|------|--------|
| `manual/` | 部署、接入、接口、架构等使用说明 |
| `images/` | 文档与社交预览用截图 |
| `agents.md` | 在 Claude / Cursor 里用本项目的约定说明 |
| `internal/` | 计划与调研笔记（本地保留，不入库） |

## 使用

| 文档 | 适合谁 |
|------|--------|
| [使用文档](../site/docs-src/quickstart.md) | 站点与应用内共用；中文，英文在 `site/docs-src/en/` |
| [部署](./manual/deployment.md) | Docker、环境变量、可选 profile |
| [Deployment (English)](./manual/deployment.en.md) | Same deploy path in English |
| [分置部署教程](./manual/分置部署教程.md) | 编排机和显卡机分开 |
| [部署相关资源下载](./manual/Liberastra部署相关资源下载.md) | 安装包、Ollama、ComfyUI、模型地址 |
| [CLI](../site/docs-src/integration/cli.md) / [CLI (English)](../site/docs-src/en/integration/cli.md) | `astra` 命令 |
| [在 Claude / Cursor 里用](./agents.md) | Skill 与 MCP |
| [Provider 接入](./manual/providers.md) | 服务提供方类型 |
| [通知](../site/docs-src/guides/notifications.md) | 渠道、规则、进度推送与投递记录 |
| [API](./manual/api.md) | HTTP 接口 |
| [架构](./manual/architecture.md) | 分层和扩展点 |

Windows 主程序看 [最新 Release](https://github.com/liberalchang/LiberAstra/releases/latest) 的 `LiberAstra-Setup.exe`。本地语音和深度图在应用里「资源 → 插件」安装，Release 不再附带 `LiberSpeech-Setup.exe`。只做在线朗读时可以不装语音插件，用 edge-tts。

## 研发

计划与调研笔记写在 `docs/internal/`，只在本机保留，不提交。参与改代码见仓库根目录的 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 维护者

社交预览图原文件是 [images/social-preview.png](./images/social-preview.png)（1280×640）。GitHub 的 Social preview 只能在仓库 Settings → General 里上传，没有公开 API。

一页落地的源文件在仓库 `site/index.html`。发布到 GitHub Pages 之前，About 的 Homepage 先指向 Releases。

## English

User-facing docs are linked in the table above. The in-app manual is generated from `site/docs-src/` and is available in Chinese and English; the Web UI follows the same languages. Deploy steps in English: [deployment.en.md](./manual/deployment.en.md). Agents: [agents.md](./agents.md).

Only usage docs are committed. Planning and research notes live in `docs/internal/` on the author's machine and are not tracked by git.
