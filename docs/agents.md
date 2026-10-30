# 在 Claude / Cursor 里用 LiberAstra

[English](#english)

LiberAstra 已经在本机或局域网跑起来，并且完成过一次 `astra login` 之后，Agent 可以用 CLI 或 MCP（Model Context Protocol，模型上下文协议）调用它。生成都是异步任务，推理仍在你配置的 ComfyUI、Ollama 或语音服务上。

## Skill

仓库内说明：[`skills/liberastra/SKILL.md`](../skills/liberastra/SKILL.md)。

Cursor 里把该文件放到本机 skills 目录，或在对话中直接引用。Skill 覆盖文字转语音、语音转文字、文生图，以及「一句话出短视频」。

先登录并体检：

```bash
astra login --server http://127.0.0.1:8000 --username admin --password '<密码>'
astra doctor
```

`astra doctor` 检查数据库、ffmpeg 和服务连通性。

## MCP

额外依赖：`pip install "liberastra[mcp]"`（或在 backend 里 `uv pip install -e ".[mcp]"`）。

```bash
astra mcp
```

stdio 传输。凭据顺序：环境变量 `LIBERASTRA_SERVER` / `LIBERASTRA_TOKEN`，然后是 `~/.liberastra/config.toml`。

工具：

| 工具 | 作用 |
|------|------|
| `generate_image` | 文生图，返回本地路径 |
| `synthesize_speech` | 文字转语音。`voice` 例如 `zh-CN-XiaoxiaoNeural` |
| `transcribe` | 语音转文字 |
| `create_video` | 一句话出短视频 |
| `get_job` | 查询任务 |

Cursor 的 MCP 配置可以写成：

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

把 `astra` 换成你机器上的可执行文件路径。Token 来自登录后的配置，或在界面里签发的 API Token。不要把 Token 提交进仓库。

命令行等价用法见 [cli.md](./cli.md)。全局选项放在子命令前面，例如 `astra --json job list`。

## English

Point an agent at [`skills/liberastra/SKILL.md`](../skills/liberastra/SKILL.md) after `astra login` against your own server. `astra doctor` checks the database, ffmpeg, and connectivity.

MCP (stdio): install `liberastra[mcp]`, then run `astra mcp`. Tools: `generate_image`, `synthesize_speech`, `transcribe`, `create_video`, `get_job`. Credentials: `LIBERASTRA_SERVER` and `LIBERASTRA_TOKEN`, else `~/.liberastra/config.toml`.

The JSON block above is a Cursor-style MCP entry. Keep the token out of git. CLI details: [cli.en.md](./cli.en.md).
