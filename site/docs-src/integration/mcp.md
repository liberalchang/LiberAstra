---
title: MCP
---

# MCP 与 Agent

LiberAstra 通过 MCP（Model Context Protocol，模型上下文协议）把生成能力暴露给 Agent。传输方式是 stdio；生成仍然是异步任务，推理在已接入的 ComfyUI、Ollama 或语音服务里完成。

## 准备

1. LiberAstra 已在本机或局域网运行。
2. 在「设置 → 服务提供方」里配置好实际执行推理的服务。
3. 安装 MCP 额外依赖：

```bash
pip install "liberastra[mcp]"
```

源码环境可以用 `uv pip install -e ".[mcp]"`。

先登录并体检：

```bash
astra login --server http://127.0.0.1:8000 --username admin --password '<密码>'
astra doctor
```

`astra doctor` 会检查数据库、ffmpeg 和服务连通性。

## 启动

```bash
astra mcp
```

凭据顺序：环境变量 `LIBERASTRA_SERVER` / `LIBERASTRA_TOKEN`，然后才读 `~/.liberastra/config.toml`。

## Cursor / Claude 配置

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

把 `command` 换成你机器上的 `astra` 可执行文件路径。Token 可以在界面里签发 API Token，或使用登录后的配置。不要把 Token 提交进仓库。

## 工具

| 工具 | 作用 |
| --- | --- |
| `generate_image` | 文生图，返回本地文件路径 |
| `synthesize_speech` | 文字转语音；`voice` 例如 `zh-CN-XiaoxiaoNeural` |
| `transcribe` | 语音转文字 |
| `create_video` | 一句话生成短视频 |
| `get_job` | 查询任务状态与产物 |

## Skill

仓库内提供 Agent Skill：`skills/liberastra/SKILL.md`。它覆盖文字转语音、语音转文字、文生图和「一句话出短视频」。把 Skill 文件放到 Agent 的 skills 目录，或在对话中直接引用即可。

Skill 只是在 Agent 侧描述调用方式；实际执行仍走本页的 MCP 或 [CLI](/integration/cli)。
