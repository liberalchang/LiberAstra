# CLI 文档

`astra` 是 LiberAstra 的命令行客户端。默认通过 HTTP 调用已经启动的服务，不在本进程里跑模型。

全局选项写在子命令前面：

```bash
astra --server http://127.0.0.1:8000 --token astra_... --json job list
```

| 选项 | 作用 |
|------|------|
| `--server` | 服务地址。默认读 `~/.liberastra/config.toml` |
| `--token` | API Token。也可用 `astra login` 保存 |
| `--json` | 输出机器可读 JSON |

退出码：`0` 成功，`2` 参数错误，`3` 服务不可用，`4` 任务失败。`--wait`（默认）等到任务结束；`--no-wait` 只提交并返回任务 id。复杂参数可写成 `@file.json`，或用 `-` 从标准输入读 JSON。

## 本机

```bash
astra serve                 # 启动 API 和页面，默认 0.0.0.0:8000
astra serve --reload        # 开发时自动重载
astra doctor                # 检查配置、数据库、ffmpeg、服务连通性
astra version
astra login --server http://127.0.0.1:8000 --username admin --password '***'
astra config                # 显示当前 server 与是否已保存 token
```

Windows 安装包从开始菜单启动的是同一套服务。命令行需在安装目录执行 `runtime\python.exe -m liberastra.cli.main`，或自行把 `astra` 加到 PATH。

## 服务提供方

```bash
astra provider list
astra provider add --name 家里Ollama --type ollama --base-url http://192.168.1.10:11434
astra provider test 1
astra provider models 1
```

`--type` 与网页「服务提供方」一致，例如 `ollama`、`openai_compatible`、`openai_tts`、`edge_tts`、`comfyui`、`liber_speech`。

## 语音、图像、视频

```bash
astra tts "你好" --voice zh-CN-XiaoxiaoNeural -o hello.mp3
astra asr ./talk.wav -f srt -o talk.srt --language zh
astra image gen --prompt "一只橘猫" --workflow qwen_image_21 -o ./out
astra video quick --topic "三个提高效率的小技巧" --voice zh-CN-XiaoxiaoNeural -o v.mp4
```

`image gen` 还可加 `--width`、`--height`、`--seed`、`--provider-id`、`--params`。`video quick` 用 `--topic` 或 `--script` 二选一，`--aspect` 默认 `9:16`。

## 任务与工作流

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

以 stdio 启动 MCP Server，把能力暴露给 Agent。需要额外安装：`pip install "liberastra[mcp]"`。
