---
title: MCP
---

# MCP and agents

LiberAstra exposes generation through MCP (Model Context Protocol) over stdio. Jobs stay asynchronous; inference runs in the configured ComfyUI, Ollama, or speech services.

## Setup

1. Start LiberAstra locally or on the LAN.
2. Configure providers under Settings -> Providers.
3. Install the extra:

```bash
pip install "liberastra[mcp]"
```

Log in and check the environment:

```bash
astra login --server http://127.0.0.1:8000 --username admin --password '<password>'
astra doctor
```

Start the server with `astra mcp`. Credentials come from `LIBERASTRA_SERVER` / `LIBERASTRA_TOKEN`, then `~/.liberastra/config.toml`.

## Cursor / Claude config

```json
{
  "mcpServers": {
    "liberastra": {
      "command": "astra",
      "args": ["mcp"],
      "env": {
        "LIBERASTRA_SERVER": "http://127.0.0.1:8000",
        "LIBERASTRA_TOKEN": "astra_..."
      }
    }
  }
}
```

Keep the token out of git.

## Tools

| Tool | Purpose |
| --- | --- |
| `generate_image` | Text to image; returns a local path |
| `synthesize_speech` | Text to speech |
| `transcribe` | Speech to text |
| `create_video` | One-line short video |
| `get_job` | Job status and outputs |

## Skill

The repository includes an Agent Skill at `skills/liberastra/SKILL.md` covering TTS, transcription, text-to-image, and one-line video. Put it in the agent's skills directory or reference it in the conversation. Execution still goes through MCP or [CLI](/en/integration/cli).
