---
title: MCP
---

# MCP and agents

LiberAstra exposes generation capabilities to agents through MCP (Model Context Protocol). The transport is stdio; generation stays asynchronous, and inference runs in the configured ComfyUI, Ollama, or speech services.

## Preparation

1. LiberAstra is running locally or on the LAN.
2. Configure the service that actually performs inference under Settings -> Providers.
3. Install the MCP extra:

```bash
pip install "liberastra[mcp]"
```

Source environments can use `uv pip install -e ".[mcp]"`.

Log in and check the environment first:

```bash
astra login --server http://127.0.0.1:8000 --username admin --password '<password>'
astra doctor
```

`astra doctor` checks the database, ffmpeg, and service connectivity.

## Start

```bash
astra mcp
```

Credential order: the environment variables `LIBERASTRA_SERVER` / `LIBERASTRA_TOKEN`, then `~/.liberastra/config.toml`.

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

Replace `command` with the path to the `astra` executable on your machine. Issue an API token in the UI, or use the credentials saved by `astra login`. Do not commit the token to a repository.

## Tools

| Tool | Purpose |
| --- | --- |
| `generate_image` / `submit_image` | Text-to-image; `submit_*` returns a job immediately |
| `synthesize_speech` / `submit_speech` | Text-to-speech |
| `transcribe` / `submit_transcription` | Speech-to-text |
| `create_video` / `submit_video` | Quick video |
| `get_job` / `wait_job` | Read / wait for a job |
| `cancel_job` / `retry_job` | Cancel / retry a job |
| `list_voices` / `list_workflows` / `list_providers` | Discover voices, workflow packs, and providers |
| `list_assets` / `get_asset` | List / read assets |

`generate_image`, `synthesize_speech`, `transcribe`, and `create_video` are blocking convenience tools for single-call workflows. For video and long jobs, prefer `submit_*` to get a `job_id`, then follow it with `wait_job` so one tool call does not time out.

Use `list_workflows` and `list_voices` to discover valid names; built-in packs vary by installation.

Resources: `liberastra://skill` returns the skill instructions, and `liberastra://workflows` returns the workflow pack catalog.

Tool failures return a structured object instead of raising:

```json
{"ok": false, "error": {"type": "SecurityError", "message": "凭据无效，请先 astra login", "exit_code": 1}}
```

## Skill

The repository includes an Agent Skill at `skills/liberastra/SKILL.md`. It covers text to speech, speech to text, text to image, and "one-line short video". Put the skill file in the agent's skills directory, or reference it directly in the conversation.

A skill only describes how to call LiberAstra on the agent side; execution still goes through MCP on this page or [CLI](/en/integration/cli).
