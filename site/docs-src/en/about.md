---
title: About / MIT / Security
---

# About

- License: MIT
- Repository: <https://github.com/liberalchang/LiberAstra>
- Light and dark themes are both first-class; Chinese and English are both first-class.

## Security

Never paste provider API keys, LiberAstra tokens (`astra_...`), passwords, `data/.secret_key`, database files, or `data/` backups into public issues, discussions, or pull requests.

Report vulnerabilities privately through GitHub Security Advisories: <https://github.com/liberalchang/LiberAstra/security/advisories/new>. Include the affected version, reproduction steps, and whether a public exploit exists.

LiberAstra only orchestrates external services. Hardening ComfyUI, Ollama, speech plugins, and cloud APIs is handled by those components.

## Boundaries

- LiberAstra does not download or run model weights.
- Every generation is a job; jobs, outputs, and parameters live in local `data/`.
- CLI, MCP, and the OpenAI-compatible `/v1` share providers, workflows, and the job queue.

## FAQ

**Where are the models?**
They are supplied by external services. Add ComfyUI, Ollama, speech, or an OpenAI-compatible API in Settings -> Providers, then import a workflow pack.

**Can I use the OpenAI SDK?**
Yes. Point the base URL at LiberAstra `/v1` and use a model name from a configured provider. See [API](/en/integration/api).

**Where is data stored?**
`data/` under the repo root by default, or `/data` in Docker. Move `data/.secret_key` with the data directory.
