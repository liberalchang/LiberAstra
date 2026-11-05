---
title: About / MIT / Security
---

# About

- License: MIT
- Repository: <https://github.com/liberalchang/LiberAstra>
- Brand and tone: dark/light themes are first-class; Chinese and English are first-class; honest, tool-like voice.

## Security

Do not paste the following into public issues, discussions, or pull requests:

- Provider API keys
- LiberAstra API tokens (`astra_...`) or login passwords
- `data/.secret_key`
- Database files or `data/` backups

To report a vulnerability, use GitHub private reporting: <https://github.com/liberalchang/LiberAstra/security/advisories/new>. Include the affected version, reproduction steps, and whether there is already public exploitation. The maintainers will decide whether to disclose after confirming.

LiberAstra only orchestrates external services. Process security and model-file provenance for ComfyUI, Ollama, speech plugins, and cloud APIs are handled by those components themselves.

## Runtime boundaries

- LiberAstra does not download or run model weights; models run in ComfyUI / Ollama / speech services or cloud APIs.
- Every generation is a job; jobs, outputs, and parameters are stored locally in `data/`, with no third-party hosting dependency.
- The `astra` CLI, MCP, and OpenAI-compatible `/v1` share the same providers, workflows, and job queue.

## FAQ

**Why are there no models on the page?**

Models come from external services. Configure ComfyUI, Ollama, a speech service, or an OpenAI-compatible API under **Settings → Providers**, then import the matching workflow packs.

**Can I use the OpenAI SDK directly?**

Yes. Point the base URL at LiberAstra's `/v1` and use the model name of a configured provider. See [API](/en/integration/api).

**Where is the data stored?**

By default in `data/` in the repository root; in the container it is `/data`. Migrate `data/.secret_key` together with the rest of the data.
