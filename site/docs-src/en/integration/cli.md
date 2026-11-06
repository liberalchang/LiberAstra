---
title: CLI
---

# CLI

`astra` is the LiberAstra command-line client. It calls a running server over HTTP and does not run models in this process.

## Connection and global flags

Global flags usually go before the subcommand, but can also be placed after it:

```bash
astra --server http://127.0.0.1:8000 --token astra_... --json job list
```

`--server`, `--token`, and `--json` can also be placed after the subcommand. With `--json`, errors are written to stderr as `{ok:false,error:{type,message,exit_code}}`.

| Flag | Meaning |
|------|---------|
| `--server` | Server URL. Defaults to `~/.liberastra/config.toml` |
| `--token` | API token. Or save one with `astra login` |
| `--json` | Machine-readable JSON output |

Exit codes: `0` success, `2` bad arguments, `3` server unreachable, `4` job failed. `--wait` (default) blocks until the job finishes; `--no-wait` submits and prints the job id. Extra parameters can be `@file.json`, or `-` to read JSON from stdin.

## Command reference

### Local

```bash
astra serve                 # API and web UI, default 0.0.0.0:8000
astra serve --reload        # Reload on code changes
astra doctor                # Config, database, ffmpeg, server reachability
astra version               # or astra --version
astra login --server http://127.0.0.1:8000 --username admin --password '***'
astra config                # Current server and whether a token is saved
astra logout                # Remove saved credentials
```

The Windows setup starts the same server from the Start menu. From a terminal, run `astra.cmd` in the install directory, or `runtime\python.exe -m liberastra.cli.main`; add the install directory to PATH to use `astra` directly.

### Providers

```bash
astra provider list
astra provider add --name home-ollama --type ollama --base-url http://192.168.1.10:11434
astra provider test 1
astra provider models 1
```

`--type` matches the Providers page: `ollama`, `openai_compatible`, `openai_tts`, `edge_tts`, `comfyui`, `liber_speech`.

### Speech, image, video

```bash
astra tts "Hello" --voice zh-CN-XiaoxiaoNeural -o hello.mp3
astra asr ./talk.wav -f srt -o talk.srt --language zh
astra image gen --prompt "an orange cat" --workflow qwen_image_21 -o ./out
astra image edit --image input.png --prompt "replace the background with a beach" --workflow qwen_image_21_edit -o ./out
astra video quick --topic "three productivity tips" --voice zh-CN-XiaoxiaoNeural -o v.mp4
astra video i2v --image first.png --workflow minimax_h3_i2v -o v.mp4
```

`image gen` also accepts `--width`, `--height`, `--seed`, `--provider-id`, and `--params`. `image edit` takes one or more repeatable `--image` inputs. `video quick` needs either `--topic` or `--script`; `--aspect` defaults to `9:16`. `video i2v` takes the first frame with `--image`; add `--image-2` and `--sub-capability i2v_flf` for first/last-frame mode.

### Jobs and workflows

```bash
astra job list --limit 20 --status failed --kind image.generate
astra job get <job_id>
astra job wait <job_id> --timeout 7200
astra job retry <job_id>
astra job cancel <job_id>
astra workflow list --capability t2i
```

### Assets and voices

```bash
astra asset list --kind image --limit 20
astra asset list --include-hidden
astra asset download 123 -o ./out
astra asset delete 123 --yes
astra voices list
```

`asset download` reads the asset metadata first, then downloads the file; when `-o` is a directory, the server-side basename is used. `asset delete` requires `--yes`.

### MCP

```bash
astra mcp
```

Starts the MCP server on stdio so an agent can call LiberAstra. Install the extra dependency with `pip install "liberastra[mcp]"`.

## Troubleshooting

**Server unreachable (exit code 3)?** Check that the server is running, the `--server` URL and port are correct, and the token has not expired. `astra config` shows the current address.

**Job failed (exit code 4)?** Run `astra job get <job_id>` to see the error, then `astra job retry <job_id>` if needed.

**No `astra` in the Windows install?** Run `astra.cmd` in the install directory, or add that directory to PATH. `runtime\python.exe -m liberastra.cli.main` also works.
