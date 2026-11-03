---
title: 关于 / MIT / 安全
---

# 关于

- 许可证：MIT
- 仓库：<https://github.com/liberalchang/LiberAstra>
- 品牌与语气：深/浅主题都为一等公民；中英双一等；诚实的工具化基调。

## 安全

不要在公开 Issue、Discussion 或 Pull Request 里粘贴：

- Provider 的 API Key
- LiberAstra 的 API Token（`astra_...`）或登录密码
- `data/.secret_key`
- 数据库文件或 `data/` 备份

发现漏洞请使用 GitHub 私人通报：<https://github.com/liberalchang/LiberAstra/security/advisories/new>。说明影响版本、复现步骤，以及是否已经有公开利用。维护者确认后再决定是否公开。

LiberAstra 只编排外部服务。ComfyUI、Ollama、语音插件和云端 API 的进程安全、模型文件来源，按那些组件自己的方式处理。

## 运行边界

- LiberAstra 不下载、不运行模型权重；模型在 ComfyUI / Ollama / 语音服务或云端 API 中运行。
- 每次生成都是任务；任务、产物与参数保存在本地 `data/`，不依赖第三方托管。
- `astra` CLI、MCP 和 OpenAI 兼容 `/v1` 共用同一套 Provider、工作流与任务队列。

## 常见问题

**为什么页面里没有模型？**

模型由外部服务提供。请先在「设置 → 服务提供方」里配置 ComfyUI、Ollama、语音服务或 OpenAI 兼容 API，再导入对应工作流包。

**可以直接用 OpenAI SDK 吗？**

可以，把 base URL 指向 LiberAstra 的 `/v1`，并使用已配置的 Provider 模型名。详见 [API](/integration/api)。

**数据放在哪？**

默认在仓库根目录的 `data/`；容器内是 `/data`。迁移时连同 `data/.secret_key` 一起迁移。
