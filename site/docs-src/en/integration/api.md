---
title: API
---

# API

OpenAI-compatible `/v1`. See `docs/api.md`.

Example:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{ "model": "your-provider:your-model", "messages":[{"role":"user","content":"hi"}] }'
```
