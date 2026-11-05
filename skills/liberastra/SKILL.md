---
name: liberastra
description: 调用 LiberAstra 自托管 AIGC 平台：文字转语音、语音转文字、文生图、图生图、短视频创作、任务与资产查询。Use when the user asks to generate speech, transcribe audio, create images or short videos with a self-hosted LiberAstra server, or manage asynchronous jobs through the astra CLI or MCP.
---

# LiberAstra

LiberAstra 是本地自托管的 AIGC 编排台。`astra` CLI 和 MCP 工具都通过 HTTP 调用已经启动的服务；模型仍在 ComfyUI、Ollama 或语音服务里运行。

## 准备

```bash
astra login --server http://localhost:8000 --username admin --password '<密码>'
# 或使用 API Token
astra login --server http://localhost:8000 --token astra_...

astra doctor          # 数据库、ffmpeg、服务端连通性
astra doctor --json   # 机器可读检查结果
```

Windows 安装包没有把 `astra` 自动加到 PATH 时，在安装目录执行 `runtime\python.exe -m liberastra.cli.main`，或把 `astra` 加入 PATH。源码环境的 CLI 随 `backend` 包安装。

## Agent 约定

- 全局选项 `--json`、`--server`、`--token` 可以放在子命令前或后；需要机器可读输出时一律加 `--json`。
- 退出码：`0` 成功、`2` 参数错误、`3` 服务不可用、`4` 任务失败。`--json` 模式下错误以 `{ok:false,error:{type,message,exit_code}}` 写到 stderr。
- 生图、生视频、语音合成、转写都是异步任务。长任务优先用 `--no-wait` 拿 `job_id`，再 `astra job wait <id> --timeout 7200`；短任务可以直接用默认 `--wait`。
- 复杂参数用 `--params @file.json`、`--params -`（stdin）或内联 JSON。
- 不要打印或记录 API Token。

## 常用命令

```bash
# 文字转语音
astra tts "你好，世界" --voice zh-CN-XiaoxiaoNeural -o hello.mp3

# 语音转文字
astra asr input.wav -f srt -o out.srt --language zh

# 文生图
astra image gen --prompt "一只橘猫，逆光" --workflow qwen_image_21 -o ./out

# 图生图 / 多图编辑（--image 可重复）
astra image edit --image input.png --prompt "把背景换成海滩" --workflow qwen_image_21_edit -o ./out

# 图生视频（首帧 / 首尾帧）
astra video i2v --image first.png --image-2 last.png --sub-capability i2v_flf \
  --workflow minimax_h3_i2v --prompt "镜头缓慢推进" -o video.mp4

# 一句话出短视频
astra video quick --topic "三个提高效率的小技巧" --voice zh-CN-XiaoxiaoNeural -o video.mp4

# 任务
astra job list --status failed --kind image.generate
astra job get <job_id>
astra job wait <job_id> --timeout 7200
astra job retry <job_id>
astra job cancel <job_id>

# 发现与资产
astra workflow list --capability t2v
astra voices list
astra asset list --kind image --limit 20
astra asset download 123 -o ./out
astra asset delete 123 --yes
```

完整命令和参数见 [references/cli.md](references/cli.md)。

## 典型工作流

**语音消息转文字后回复语音**

1. `astra asr input.wav -f txt` 获取文本。
2. 组织回复文本。
3. `astra tts "回复内容" --voice <音色> -o reply.mp3`。

**一句话出短视频**

1. `astra --json video quick --topic "..." --voice <音色> --no-wait` 拿 `job_id`。
2. `astra --json job wait <job_id> --timeout 7200`（或 `job get` 轮询）。
3. 产物在 `outputs` 里引用 asset；完成后用 `astra job get <id>` 查看资产，或直接 `astra video quick ... --wait -o video.mp4`。

**先发现再生成**

1. `astra workflow list --capability t2i` 选包。
2. `astra image gen --prompt "..." --workflow <包名>`。
3. `astra asset list --kind image` 确认产物。

## MCP

`astra mcp` 以 stdio 启动 MCP Server。工具分三类：

- 阻塞便捷：`generate_image`、`synthesize_speech`、`transcribe`、`create_video`、`get_job`
- 异步提交：`submit_image`、`submit_speech`、`submit_transcription`、`submit_video`
- 发现与控制：`list_voices`、`list_workflows`、`list_providers`、`list_assets`、`get_asset`、`wait_job`、`cancel_job`、`retry_job`

凭据同 CLI：环境变量 `LIBERASTRA_SERVER` / `LIBERASTRA_TOKEN` 优先，其次 `~/.liberastra/config.toml`。详见 [references/mcp.md](references/mcp.md)。

## 参考

- [CLI 命令与参数](references/cli.md)
- [HTTP API 直连](references/api.md)
- [MCP 工具](references/mcp.md)
- [排错与退出码](references/troubleshooting.md)
