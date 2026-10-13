---
name: liberastra
description: 调用 LiberAstra 自托管 AIGC 平台：文字转语音、语音转文字、文生图、短视频创作。当用户需要生成语音/图片/视频，或要求"一句话出短视频"、"语音消息转文字后回复语音"时使用。
---

# LiberAstra Skill

LiberAstra 是本地自托管的 AIGC 聚合平台。通过 `astra` CLI（或 MCP 工具）调用，所有生成走异步任务。

## 准备

```bash
astra login --server http://localhost:8000 --username admin --password <密码>
# 或使用 API Token：astra login --token astra_...
astra doctor    # 体检：数据库 / ffmpeg / 服务端连通性
```

## 常用命令

```bash
# 文字转语音
astra tts "你好，世界" --voice zh-CN-XiaoxiaoNeural -o hello.mp3

# 语音转文字（含字幕）
astra asr input.wav -f srt -o out.srt

# 文生图
astra image gen --prompt "一只橘猫，逆光" --width 1024 --height 1024 -o ./out

# 一句话出短视频（LLM 写文案与分镜，逐帧合成）
astra video quick --topic "三个提高效率的小技巧" --voice zh-CN-XiaoxiaoNeural -o video.mp4

# 任务管理
astra job list
astra job wait <job_id>
```

## Agent 约定

- 所有命令支持 `--json` 输出机器可读结果；**全局选项（`--json` / `--server` / `--token）放在子命令之前**，如 `astra --json job list`。
- 退出码：0 成功、2 参数错误、3 服务不可用、4 任务失败。
- 生成命令默认 `--wait` 等待完成；`--no-wait` 只拿 job_id 后用 `astra job wait` 跟进。
- 复杂参数用 `--params @file.json` 或 `--params -`（stdin）。

## 典型工作流

**语音消息转文字后回复语音**
1. `astra asr input.wav -f txt` 获取文本
2. 组织回复文本
3. `astra tts "回复内容" --voice <音色> -o reply.mp3`

**一句话出短视频**
1. `astra --json video quick --topic "..." --voice <音色> --no-wait` 拿 job_id
2. `astra --json job wait <job_id>` 轮询
3. 产物在 outputs 中引用 asset，或直接加 `--wait -o video.mp4`

## MCP

`astra mcp` 以 stdio 启动 MCP Server，工具：generate_image / synthesize_speech / transcribe / create_video / get_job。凭据同 CLI（环境变量 LIBERASTRA_SERVER / LIBERASTRA_TOKEN 优先）。
