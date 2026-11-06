---
title: CLI
---

# CLI 文档

`astra` 是 LiberAstra 的命令行客户端。默认通过 HTTP 调用已经启动的服务，不在本进程里跑模型。

## 连接与全局选项

全局选项通常写在子命令前面，也可以放在后面：

```bash
astra --server http://127.0.0.1:8000 --token astra_... --json job list
```

`--server`、`--token`、`--json` 也可以放在子命令后面；`--json` 模式下错误写到 stderr，格式为 `{ok:false,error:{type,message,exit_code}}`。

| 选项 | 作用 |
|------|------|
| `--server` | 服务地址。默认读 `~/.liberastra/config.toml` |
| `--token` | API Token。也可用 `astra login` 保存 |
| `--json` | 输出机器可读 JSON |

退出码：`0` 成功，`2` 参数错误，`3` 服务不可用，`4` 任务失败。`--wait`（默认）等到任务结束；`--no-wait` 只提交并返回任务 id。复杂参数可写成 `@file.json`，或用 `-` 从标准输入读 JSON。

## 命令参考

### 本机

```bash
astra serve                 # 启动 API 和页面，默认 0.0.0.0:8000
astra serve --reload        # 开发时自动重载
astra doctor                # 检查配置、数据库、ffmpeg、服务连通性
astra version               # 或 astra --version
astra login --server http://127.0.0.1:8000 --username admin --password '***'
astra config                # 显示当前 server 与是否已保存 token
astra logout                # 删除本地保存的凭据
```

Windows 安装包从开始菜单启动的是同一套服务。命令行在安装目录执行 `astra.cmd`，或 `runtime\python.exe -m liberastra.cli.main`；把安装目录加入 PATH 后可直接用 `astra`。

### 服务提供方

```bash
astra provider list
astra provider add --name 家里Ollama --type ollama --base-url http://192.168.1.10:11434
astra provider test 1
astra provider models 1
```

`--type` 与网页「服务提供方」一致，例如 `ollama`、`openai_compatible`、`openai_tts`、`edge_tts`、`comfyui`、`liber_speech`。

### 语音、图像、视频

```bash
astra tts "你好" --voice zh-CN-XiaoxiaoNeural -o hello.mp3
astra asr ./talk.wav -f srt -o talk.srt --language zh
astra image gen --prompt "一只橘猫" --workflow qwen_image_21 -o ./out
astra image edit --image input.png --prompt "把背景换成海滩" --workflow qwen_image_21_edit -o ./out
astra video quick --topic "三个提高效率的小技巧" --voice zh-CN-XiaoxiaoNeural -o v.mp4
astra video i2v --image first.png --workflow minimax_h3_i2v -o v.mp4
```

`image gen` 还可加 `--width`、`--height`、`--seed`、`--provider-id`、`--params`。`image edit` 用可重复的 `--image` 传 1～4 张图。`video quick` 用 `--topic` 或 `--script` 二选一，`--aspect` 默认 `9:16`。`video i2v` 用 `--image` 传首帧，首尾帧再加 `--image-2` 和 `--sub-capability i2v_flf`。

### 任务与工作流

```bash
astra job list --limit 20 --status failed --kind image.generate
astra job get <job_id>
astra job wait <job_id> --timeout 7200
astra job retry <job_id>
astra job cancel <job_id>
astra workflow list --capability t2i
```

### 资产与音色

```bash
astra asset list --kind image --limit 20
astra asset list --include-hidden
astra asset download 123 -o ./out
astra asset delete 123 --yes
astra voices list
```

`asset download` 先读资产元数据再下载；`-o` 是目录时用服务端文件名。`asset delete` 需要 `--yes`。

### MCP

```bash
astra mcp
```

以 stdio 启动 MCP Server，把能力暴露给 Agent。需要额外安装：`pip install "liberastra[mcp]"`。

## 故障排查

**提示服务不可用（退出码 3）？** 确认服务已经启动，`--server` 地址和端口正确，并且 token 没有过期。可以先跑 `astra config` 看当前地址。

**任务失败（退出码 4）？** 用 `astra job get <job_id>` 看错误；需要重试时用 `astra job retry <job_id>`。

**Windows 安装包里没有 `astra`？** 在安装目录运行 `astra.cmd`，或把安装目录加入 PATH。直接调用 `runtime\python.exe -m liberastra.cli.main` 也可以。
