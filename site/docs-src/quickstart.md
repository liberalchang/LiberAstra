---
title: 快速开始
---

# 快速开始

1. 启动服务

```bash
docker compose up -d --build
```

2. 打开 `http://localhost:8000`，创建管理员账号
3. 前往「设置 → 服务提供方（Providers）」配置 ComfyUI / Ollama / 语音
4. 在首页 `PromptField` 提交一个图像 / 视频 / 语音任务，查看任务队列与结果

## 小贴士

- Web / CLI / MCP / OpenAI 兼容 `/v1` 入口可以混合使用
- 模型的下载与运行由 ComfyUI / Ollama / 语音服务负责，LiberAstra 仅进行「编排」
