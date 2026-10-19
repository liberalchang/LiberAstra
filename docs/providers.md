# Provider 接入指南

## 概念

Provider = 一个外部服务的连接配置。每种类型声明自己的能力标签（`llm` / `tts` / `asr` / `image` / `video`），能力调用按标签路由，不按厂商。

## 内置类型

| 类型 | 能力 | 说明 | 默认 base_url |
| --- | --- | --- | --- |
| `openai_compatible` | llm | vLLM / LM Studio / DeepSeek / 通义 / 火山方舟 / Kimi / 智谱 / SiliconFlow / OpenRouter | `http://localhost:8000/v1` |
| `ollama` | llm | 本地 Ollama（`/api/tags` 拉模型，chat 走 `/v1`） | `http://localhost:11434` |
| `openai_tts` | tts | OpenAI / Kokoro-FastAPI / Speaches / SiliconFlow | `http://localhost:8880/v1` |
| `edge_tts` | tts | 微软在线 TTS，零配置兜底（仅 mp3） | — |
| `openai_stt` | asr | OpenAI / Groq / Speaches / faster-whisper-server | `http://localhost:8100/v1` |
| `comfyui` | image, video | 局域网 ComfyUI，工作流包驱动 | `http://localhost:8188` |
| `openai_images` | image | OpenAI gpt-image 及兼容网关 | `https://api.openai.com/v1` |

## 添加

Web UI「设置 → 服务提供方」，或 CLI：

```bash
astra provider add --name 家里Ollama --type ollama --base-url http://192.168.1.10:11434
astra provider test 1
astra provider models 1
```

- `api_key` 以 Fernet 加密后落库，API 只回显 `has_api_key`。
- `concurrency` 限制该 Provider 的任务并发（默认 2）。
- 额外配置（如默认模型）写入 `extra`：`{"model": "qwen3:8b"}`。

## ComfyUI 工作流包

ComfyUI 类型 Provider 通过工作流包驱动。包 = `workflow.json`（ComfyUI → Save (API Format)）+ `manifest.yaml`：

```yaml
name: my_t2i
capability: t2i            # 规范：t2i / i2i / upscale / t2v / i2v / avatar / motion / tts
inputs:
  prompt: { node: "6", field: inputs.text, type: str, required: true }
  image:  { node: "1", field: inputs.image, type: image }   # image/video/audio 输入会自动上传 ComfyUI
  seed:   { node: "3", field: inputs.seed, type: int, default: -1 }  # -1 = 随机
outputs: { node: "9", key: images }   # images / videos / gifs
# 可选：加速 LoRA（关闭时摘掉节点，下游改接 bypass_input 来源）
# accel:
#   node: "200"
#   bypass_input: model
#   lora: { field: inputs.lora_name, options_from: loras, match: "minimax_h3", recommended: "xxx.safetensors" }
#   strength: { field: inputs.strength_model, default: 1.0 }
#   preset: { steps: 8 }
requirements:
  nodes: [KSampler]        # 导入预检查用
```

导入方式：Web UI「设置 → 工作流包」（支持 LiberAstra 包、API Format、以及含 `nodes`/`links` 的画布 JSON 自动转换），或写入 `data/workflows/<name>/`（同名覆盖内置包）。视频示例见内置包 `minimax_h3_i2v`、`minimax_h3_i2v_uncensored`、`minimax_h3_i2v_enhancer`。

## 新增 Provider 类型（开发）

见 `docs/architecture.md`「扩展一个新能力」。
