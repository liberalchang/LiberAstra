# astra CLI reference

`astra` calls a running LiberAstra server over HTTP. It does not run models in the CLI process.

## Global options

Global options can be placed before or after the subcommand.

| Option | Meaning |
| --- | --- |
| `--server URL` | Server URL. Defaults to `~/.liberastra/config.toml` |
| `--token TOKEN` | API token (`astra_...`). Or save one with `astra login` |
| `--json` | Machine-readable JSON output |
| `--version` | Print the version |

Exit codes: `0` success, `2` bad arguments, `3` server unreachable, `4` job failed. With `--json`, errors are written to stderr as `{ok:false,error:{type,message,exit_code}}`.

## Local commands

```bash
astra serve [--host 0.0.0.0] [--port 8000] [--reload]
astra doctor [--json]
astra version
astra logout
astra login --server http://127.0.0.1:8000 --username admin --password '***'
astra login --server http://127.0.0.1:8000 --token astra_...
astra config
```

`doctor` checks the data directory, database, ffmpeg, and server health. `logout` removes `~/.liberastra/config.toml`.

## Providers

```bash
astra provider list
astra provider add --name home-ollama --type ollama --base-url http://192.168.1.10:11434
astra provider test 1
astra provider models 1
```

`--type` matches the Providers page: `ollama`, `openai_compatible`, `openai_tts`, `edge_tts`, `openai_stt`, `comfyui`, `openai_images`, `liber_speech`.

## Speech

```bash
astra tts "你好" --voice zh-CN-XiaoxiaoNeural -o hello.mp3
astra tts "你好" --voice zh-CN-XiaoxiaoNeural --options '{"speed":0.9,"exaggeration":0.7}' -o hello.mp3
astra tts "你好" --voice zh-CN-XiaoxiaoNeural --no-wait
astra asr ./talk.wav -f srt -o talk.srt --language zh
astra asr ./talk.mp4 -f txt --options '{"vad_filter":true,"hotwords":"LiberAstra 张三"}'
```

`tts` flags: `--voice`, `--format`, `--provider-id`, `--options` (JSON), `--wait/--no-wait`, `-o/--out`.
`asr` flags: `-f/--format` (`txt`/`srt`/`vtt`/`json`), `--language`, `--provider-id`, `--options` (JSON), `--wait/--no-wait`, `-o/--out`.

`--options` passes model-specific speech parameters through to a Liber Speech provider. Unknown or unsupported keys are rejected by the speech service with a structured error.

## Image

```bash
astra image gen --prompt "一只橘猫" --workflow qwen_image_21 -o ./out
astra image gen --prompt "一只橘猫" --width 1024 --height 1024 --seed -1 --no-wait
astra image edit --image input.png --prompt "把背景换成海滩" --workflow qwen_image_21_edit -o ./out
astra image edit --image first.png --image second.png --workflow qwen_image_21_edit_multi -o ./out
```

`image gen` flags: `--prompt`, `--workflow`, `--width`, `--height`, `--seed`, `--provider-id`, `--params`, `--wait/--no-wait`, `-o/--out`.
`image edit` flags: `--image` (repeatable, required), `--prompt`, `--workflow`, `--provider-id`, `--params`, `--wait/--no-wait`, `-o/--out`.

`--params` accepts inline JSON, `@file.json`, or `-` for stdin. It is merged into the workflow inputs / request body.

## Video

```bash
astra video quick --topic "三个提高效率的小技巧" --voice zh-CN-XiaoxiaoNeural -o v.mp4
astra video quick --script script.txt --voice zh-CN-XiaoxiaoNeural --aspect 9:16 -o v.mp4
astra video i2v --image first.png --sub-capability i2v_first --workflow minimax_h3_i2v -o v.mp4
astra video i2v --image first.png --image-2 last.png --sub-capability i2v_flf \
  --workflow minimax_h3_i2v -o v.mp4
```

`video quick` flags: `--topic` or `--script`, `--voice`, `--aspect`, `--params`, `--wait/--no-wait`, `-o/--out`.
`video i2v` flags: `--image`, `--image-2`, `--prompt`, `--workflow` or `--model`, `--sub-capability` (`i2v_first`, `i2v_flf`, `t2v`), `--provider-id`, `--params`, `--wait/--no-wait`, `-o/--out`.

## Jobs

```bash
astra job list --limit 20 --status failed --kind image.generate
astra job get <job_id>
astra job wait <job_id> --timeout 7200
astra job retry <job_id>
astra job cancel <job_id>
```

`job list` filters use the API's `status_filter` and `kind` query parameters. `job wait` exits with code `4` on failure or timeout.

## Workflows

```bash
astra workflow list
astra workflow list --capability t2i
astra workflow list --capability t2v
```

Capabilities: `t2i`, `i2i`, `upscale`, `v2v`, `t2v`, `i2v`, `avatar`, `motion`, `tts`, `analysis`.

## Assets

```bash
astra asset list --kind image --limit 20 --offset 0
astra asset list --job-kind image.generate
astra asset list --include-hidden
astra asset download 123 -o ./out
astra asset delete 123 --yes
```

`asset download` fetches the asset metadata first, then writes the file. If `-o` is a directory, the server-side basename is used. `asset delete` requires `--yes`.

## Voices

```bash
astra voices list
```

Lists saved voices, whether each is the default, and its provider / external voice id.

## MCP

```bash
astra mcp
```

Starts the MCP server on stdio. Install the extra dependency with `pip install "liberastra[mcp]"`.
