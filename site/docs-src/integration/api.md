---
title: API
---

# API（OpenAI 兼容 /v1）

LiberAstra 提供 OpenAI 兼容（OpenAI-compatible，兼容 OpenAI 接口）的 `/v1` 入口。  
请参考仓库文档：

- `docs/api.md`

占位示例（伪代码）：

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{ "model": "your-provider:your-model", "messages":[{"role":"user","content":"hi"}] }'
```

> 注意：LiberAstra 不提供模型本身；`model` 对应已对接的服务提供方与其模型命名。
