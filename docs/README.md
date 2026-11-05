# LiberAstra 文档

[English](#english)

LiberAstra 是自托管 AIGC 编排台：对接 ComfyUI、Ollama、语音服务和 OpenAI 兼容 API。程序本身不跑模型。

公开检索里的 [liberastra.com.br](https://liberastra.com.br/) 是另一个项目。本仓库是开源编排台，仓库地址：<https://github.com/liberalchang/LiberAstra>。

## 使用

| 文档 | 适合谁 |
|------|--------|
| [使用文档](../site/docs-src/quickstart.md) | 站点与应用内共用；中文，英文在 `site/docs-src/en/` |
| [部署](./deployment.md) | Docker、环境变量、可选 profile |
| [Deployment (English)](./deployment.en.md) | Same deploy path in English |
| [分置部署教程](./分置部署教程.md) | 编排机和显卡机分开 |
| [部署相关资源下载](./Liberastra部署相关资源下载.md) | 安装包、Ollama、ComfyUI、模型地址 |
| [CLI](../site/docs-src/integration/cli.md) / [CLI (English)](../site/docs-src/en/integration/cli.md) | `astra` 命令 |
| [在 Claude / Cursor 里用](./agents.md) | Skill 与 MCP |
| [Provider 接入](./providers.md) | 服务提供方类型 |
| [API](./api.md) | HTTP 接口 |
| [架构](./architecture.md) | 分层和扩展点 |

Windows 主程序看 [最新 Release](https://github.com/liberalchang/LiberAstra/releases/latest) 的 `LiberAstra-Setup.exe`。本地语音和深度图在应用里「资源 → 插件」安装，Release 不再附带 `LiberSpeech-Setup.exe`。只做在线朗读时可以不装语音插件，用 edge-tts。

## 研发

设计过程写在 [internal/](./internal/README.md)，不作为上手入口。

参与改代码见仓库根目录的 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 维护者

社交预览图原文件是 [images/social-preview.png](./images/social-preview.png)（1280×640）。GitHub 的 Social preview 只能在仓库 Settings → General 里上传，没有公开 API。

一页落地的源文件在仓库 `site/index.html`。发布到 GitHub Pages 之前，About 的 Homepage 先指向 Releases。

## English

User-facing docs are linked in the table above. The in-app manual is generated from `site/docs-src/` and is available in Chinese and English; the Web UI follows the same languages. Deploy steps in English: [deployment.en.md](./deployment.en.md). Agents: [agents.md](./agents.md).
