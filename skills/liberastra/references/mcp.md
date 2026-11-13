# LiberAstra MCP

`astra mcp` starts a stdio MCP server. The server exposes LiberAstra generation, discovery, and job control as tools.

Install the extra dependency:

```bash
pip install "liberastra[mcp]"
```

## Client configuration

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

Replace `command` with the absolute `astra` path if it is not on PATH. Credentials resolve in this order: environment variables, then `~/.liberastra/config.toml`.

## Tools

### Blocking convenience

| Tool | Main parameters | Returns |
| --- | --- | --- |
| `generate_image` | `prompt`, `width`, `height`, `workflow` | Local file path |
| `synthesize_speech` | `text`, `voice`, `fmt`, `provider_id`, `options` | Local file path |
| `transcribe` | `file_path`, `language`, `model`, `formats`, `options` | Transcript text |
| `create_video` | `topic` or `script`, `voice`, `aspect` | Local file path |
| `get_job` | `job_id` | Job object |

### Asynchronous submit

`submit_image`, `submit_speech`, `submit_transcription`, and `submit_video` return a job object immediately. Use `wait_job` to follow it. This is the preferred path for long videos and batch work.

| Tool | Main parameters |
| --- | --- |
| `submit_image` | `prompt`, `width`, `height`, `workflow`, `provider_id` |
| `submit_speech` | `text`, `voice`, `fmt`, `provider_id`, `options` |
| `submit_transcription` | `file_path`, `language`, `model`, `formats`, `options` |
| `submit_video` | `voice`, `topic` or `script`, `aspect` |

### Discovery and job control

| Tool | Main parameters |
| --- | --- |
| `list_voices` | none |
| `list_workflows` | `capability` (`t2i`, `i2i`, `i2v`, `t2v`, `avatar`, `motion`, `upscale`, `v2v`, ...) |
| `list_providers` | none |
| `list_assets` | `kind`, `job_id`, `limit`, `include_hidden` |
| `get_asset` | `asset_id` |
| `wait_job` | `job_id`, `timeout` |
| `cancel_job` | `job_id` |
| `retry_job` | `job_id` |

## Resources

| URI | Content |
| --- | --- |
| `liberastra://skill` | The LiberAstra skill instructions (Markdown) |
| `liberastra://workflows` | Workflow pack catalog (JSON) |

## Errors

Tool failures return a structured object instead of raising:

```json
{
  "ok": false,
  "error": {
    "type": "SecurityError",
    "message": "凭据无效，请先 astra login",
    "exit_code": 1
  }
}
```

If you see an auth error, run `astra login` or set `LIBERASTRA_TOKEN`. If the server is unreachable, check `LIBERASTRA_SERVER` and `astra doctor`.

## Notes

- MCP tools use the same job system as the CLI and Web UI.
- `transcribe` and `submit_transcription` read a local file path on the MCP server host.
- Use `list_workflows` before passing a `workflow` name; pack names vary by installation.
