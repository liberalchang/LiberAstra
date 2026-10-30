# LiberAstra 文档

[English](#english)

LiberAstra 是自托管 AIGC 编排台：对接 ComfyUI、Ollama、语音服务和 OpenAI 兼容 API。程序本身不跑模型。

公开检索里的 [liberastra.com.br](https://liberastra.com.br/) 是另一个项目。本仓库是开源编排台，仓库地址：<https://github.com/liberalchang/LiberAstra>。

## 使用

| 文档 | 适合谁 |
|------|--------|
| [使用文档](./使用文档.md) | 装好之后的界面、工作流包和模型怎么配对（中文） |
| [部署](./deployment.md) | Docker、环境变量、可选 profile |
| [Deployment (English)](./deployment.en.md) | Same deploy path in English |
| [分置部署教程](./分置部署教程.md) | 编排机和显卡机分开 |
| [部署相关资源下载](./Liberastra部署相关资源下载.md) | 安装包、Ollama、ComfyUI、模型地址 |
| [CLI](./cli.md) / [CLI (English)](./cli.en.md) | `astra` 命令 |
| [在 Claude / Cursor 里用](./agents.md) | Skill 与 MCP |
| [Provider 接入](./providers.md) | 服务提供方类型 |
| [API](./api.md) | HTTP 接口 |
| [架构](./architecture.md) | 分层和扩展点 |

Windows 主程序看 [最新 Release](https://github.com/liberalchang/LiberAstra/releases/latest) 的 `LiberAstra-Setup.exe`。`v1.0.3` 没有附带语音安装包；本地语音插件用 [v1.0.2 的 LiberSpeech-Setup.exe](https://github.com/liberalchang/LiberAstra/releases/download/v1.0.2/LiberSpeech-Setup.exe)。只做在线朗读时可以不装，用 edge-tts。

## 研发

设计过程写在 [internal/](./internal/README.md)，不作为上手入口。

参与改代码见仓库根目录的 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 维护者

社交预览图原文件是 [images/social-preview.png](./images/social-preview.png)（1280×640）。GitHub 的 Social preview 只能在仓库 Settings → General 里上传，没有公开 API。

一页落地的源文件在仓库 `site/index.html`。发布到 GitHub Pages 之前，About 的 Homepage 先指向 Releases。

## English

User-facing docs are linked in the table above. The long in-app manual (`使用文档.md`) is Chinese; the Web UI is Chinese and English. Deploy steps in English: [deployment.en.md](./deployment.en.md). Agents: [agents.md](./agents.md).
