# LiberAstra skills

Two external-use skills live here. They point at different services; do not mix their base URLs.

| Skill | Service | Style | Use when |
| --- | --- | --- | --- |
| [`liberastra`](./liberastra/SKILL.md) | LiberAstra main server, default `http://localhost:8000` | Asynchronous jobs; images, video, speech, assets, canvas | You want the full orchestration platform, image/video generation, or job management |
| [`speechapi`](./speechapi/SKILL.md) | Liber Speech service, default `http://localhost:5555` | Synchronous ASR/TTS; Chatterbox models, voice cloning | You only need speech-to-text or text-to-speech against a speech service |

## How they relate

- `liberastra` calls the main API at `:8000`. Generation is queued as jobs; TTS/ASR may be routed to a speech provider, but the CLI/MCP surface is the main server.
- `speechapi` calls the speech service's own `/api/v1` at `:5555`. It does not use the main job queue.
- Both are external skills: copy the skill directory into your agent's skills directory, or point the agent at the `SKILL.md`.

## Install

Copy the whole skill directory (not just `SKILL.md`) so the agent can read `references/` and run `scripts/`.

- `liberastra`: requires the `astra` CLI (`pip install ./backend` or the Windows installer's embedded runtime).
- `speechapi`: requires Python 3.10+ and `pip install -r skills/speechapi/requirements.txt`.

## MCP

The main server's MCP is exposed by `astra mcp`; see [`liberastra/references/mcp.md`](./liberastra/references/mcp.md). The speechapi skill is script-based and does not start an MCP server.

## Security

- Never commit `.env`, API tokens, or `data.json` containing credentials.
- `speechapi/.env` is gitignored. If you keep a local PicGo/cloud config in the skill directory, keep it out of version control.
- Do not print API keys in logs or agent output.
