# CLI

`astra` is the LiberAstra command-line client. It calls a running server over HTTP and does not run models in this process.

Global flags go before the subcommand:

```bash
astra --server http://127.0.0.1:8000 --token astra_... --json job list
```

| Flag | Meaning |
|------|---------|
| `--server` | Server URL. Defaults to `~/.liberastra/config.toml` |
| `--token` | API token. Or save one with `astra login` |
| `--json` | Machine-readable JSON output |

Exit codes: `0` success, `2` bad arguments, `3` server unreachable, `4` job failed. `--wait` (default) blocks until the job finishes; `--no-wait` submits and prints the job id. Extra parameters can be `@file.json`, or `-` to read JSON from stdin.

## Local

```bash
astra serve                 # API and web UI, default 0.0.0.0:8000
astra serve --reload        # Reload on code changes
astra doctor                # Config, database, ffmpeg, server reachability
astra version
astra login --server http://127.0.0.1:8000 --username admin --password '***'
astra config                # Current server and whether a token is saved
```

The Windows setup starts the same server from the Start menu. From a terminal, run `runtime\python.exe -m liberastra.cli.main` inside the install directory, or put `astra` on PATH yourself.

## Providers

```bash
astra provider list
astra provider add --name home-ollama --type ollama --base-url http://192.168.1.10:11434
astra provider test 1
astra provider models 1
```

`--type` matches the Providers page: `ollama`, `openai_compatible`, `openai_tts`, `edge_tts`, `comfyui`, `liber_speech`.

## Speech, image, video

```bash
astra tts "Hello" --voice zh-CN-XiaoxiaoNeural -o hello.mp3
astra asr ./talk.wav -f srt -o talk.srt --language zh
astra image gen --prompt "an orange cat" --workflow qwen_image_21 -o ./out
astra video quick --topic "three productivity tips" --voice zh-CN-XiaoxiaoNeural -o v.mp4
```

`image gen` also accepts `--width`, `--height`, `--seed`, `--provider-id`, and `--params`. `video quick` needs either `--topic` or `--script`. `--aspect` defaults to `9:16`.

## Jobs and workflows

```bash
astra job list --limit 20
astra job get <job_id>
astra job wait <job_id>
astra job cancel <job_id>
astra workflow list
```

## MCP

```bash
astra mcp
```

Starts the MCP server on stdio so an agent can call LiberAstra. Install the extra dependency with `pip install "liberastra[mcp]"`.
