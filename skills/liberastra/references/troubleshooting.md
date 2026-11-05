# Troubleshooting

## Exit codes

| Code | Meaning | What to do |
| --- | --- | --- |
| `0` | Success | — |
| `2` | Bad arguments | Check `--help`; Typer prints the offending option |
| `3` | Server unreachable | Check `--server`, the server process, and `astra doctor` |
| `4` | Job failed or timed out | Run `astra job get <id>` and read `error`; retry with new parameters |

With `--json`, errors are on stderr:

```json
{"ok": false, "error": {"type": "ServiceUnavailable", "message": "无法连接服务端: ...", "exit_code": 3}}
```

## Common problems

**`凭据无效，请先 astra login`**

The token is missing, expired, or belongs to another server. Run:

```bash
astra login --server http://127.0.0.1:8000 --username admin --password '***'
astra config
```

**`无法连接服务端` (exit 3)**

- Confirm the server is running: `curl http://127.0.0.1:8000/healthz`.
- If using Docker, publish the port and use the host URL, not `localhost` from inside another container.
- `astra doctor` prints the resolved server and health result.

**`HTTP 404: 任务不存在`**

The job id is wrong or belongs to another user. `astra job list` shows your jobs.

**Job fails with `没有可用的 ... 服务` or `无 ... 工作流包`**

- Add and enable a provider in Settings → Providers.
- Import a matching workflow pack in Settings → Workflow Packs.
- Use `astra workflow list --capability <cap>` to see what is available.

**Image/video job fails while loading a model**

The selected model files are missing on the ComfyUI host. Check the pack's model dropdowns and the ComfyUI model directories. The Web UI shows a yellow warning for missing files before submission.

**`文件不存在`**

The CLI checks local input paths before submitting. Use an absolute path or run from the correct directory.

**Long video times out**

Use `--no-wait` to get the job id, then:

```bash
astra job wait <job_id> --timeout 7200
```

The server-side ComfyUI timeout is set in Settings → System Settings → Run parameters. Raise it for H3 / long jobs.

**Windows: `astra` is not recognized**

Use the install directory's embedded runtime:

```powershell
runtime\python.exe -m liberastra.cli.main --help
```

Or add the directory containing `astra.exe` to PATH.

**Config file location**

`~/.liberastra/config.toml`. It contains the server URL and token. Do not commit it. `astra logout` deletes it.

## MCP-specific

- If the MCP client cannot start `astra`, use the absolute path in `command`.
- If tools return `{"ok": false, "error": ...}`, read `message` and `exit_code`; the same exit-code table applies.
- The MCP server runs on the same machine as the agent. File paths passed to `transcribe` / `submit_transcription` must exist on that machine.
