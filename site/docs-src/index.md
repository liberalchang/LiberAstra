---
title: 介绍
---

# LiberAstra 编排台

**口号**：只编排，不推理  
LiberAstra 是自托管的 AIGC 编排台（orchestration desk，编排台）。它将 ComfyUI、Ollama、语音服务与 OpenAI 兼容接口统一到一张「桌面」之上：

- **访问方式**：Web UI、`astra` CLI、MCP、OpenAI 兼容 `/v1`（英文：OpenAI-compatible API）
- **重要前提**：LiberAstra 不运行模型，只负责编排；模型实际在 ComfyUI / Ollama / 语音服务中运行
- **品牌基调**：深+浅色主题双一等；中英双一等；诚实、工具化的语气

## 适用对象

- 需要在本地或私有环境中，将图像 / 视频 / 语音能力统一到同一工作台的开发者和创作者
- 需要 **Web/CLI/API** 多入口协同编排的团队

## 非目标

- 不追求成为模型运行容器；不重新发明推理执行器
- 不制造虚假的「案例、用户、分数或下载量」

## 进一步阅读

- 快速开始：见「[快速开始](./quickstart.md)」
- 安装 / 下载：见「[安装](./install.md)」
- 指南：图像 / 视频 / 语音 / 作品与任务
- 集成：[`astra` CLI](./integration/cli.md) / [API](./integration/api.md) / [MCP](./integration/mcp.md)
- 服务提供方：[Providers](./providers.md)
- 关于与安全：[About](./about.md)

> 备注：网络中存在「`liberastra.com.br`」的导师网站，与本项目无关。仓库为 `github.com/liberalchang/LiberAstra`。
