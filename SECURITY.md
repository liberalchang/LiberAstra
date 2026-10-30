# 安全问题

[English](#english)

不要在公开 Issue、Discussion 或 Pull Request 里粘贴：

- Provider 的 API Key
- LiberAstra 的 API Token（`astra_...`）或登录密码
- `data/.secret_key`
- 数据库文件、`data/` 备份

请用 GitHub 私人通报：<https://github.com/liberalchang/LiberAstra/security/advisories/new>

说明影响版本、复现步骤，以及是否已经有公开利用。维护者确认后再决定是否公开。

本仓库只编排外部服务。ComfyUI、Ollama、语音插件和云端 API 的进程安全、模型文件来源，按那些组件自己的方式处理。

## English

Do not paste provider API keys, LiberAstra tokens, passwords, `data/.secret_key`, or database files into public issues or pull requests.

Report vulnerabilities privately: <https://github.com/liberalchang/LiberAstra/security/advisories/new>

Include the version, how to reproduce, and whether a public exploit already exists. LiberAstra orchestrates external inference services; hardening ComfyUI, Ollama, or the speech plugin is outside this repository.
