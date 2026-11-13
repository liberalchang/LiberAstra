# liber-speechapi 技能使用说明

`liber-speechapi` 直连 Liber Speech 服务，提供 TTS、ASR、VC 和 Telegram 语音工作流。

- TTS：Chatterbox 11 个模型包，支持语速、语气强度、节奏等 v2 参数
- ASR：faster-whisper 和 Qwen3-ASR，支持词级时间戳、VAD、热词
- VC：Chatterbox VC、Seed-VC，支持分段、seed、diffusion steps
- API：优先 `/api/v2` JSON，旧服务自动回退 `/api/v1`

## 前置条件

- 语音服务已在显卡主机运行，默认端口 `5555`
- Python 3.10+
- `pip install -r skills/speechapi/requirements.txt`

## 配置

优先级：

1. 环境变量 `LIBER_API_BASE_URL`、`LIBER_API_KEY`
2. `~/.openclaw/.env`
3. 技能目录 `.env`
4. 当前工作目录 `.env`

`LIBER_API_BASE_URL` 可以写：

- `http://host:5555`
- `http://host:5555/api/v1`
- `http://host:5555/api/v2`

可选 `LIBER_API_VERSION=auto|v1|v2`，默认 `auto`。

详细参数放在 `speechapi_config.json` 的 `asr`、`tts`、`vc`、`global` 段；每段支持 `options` 对象。

不要把密钥写进文档或日志。

## 使用示例

```bash
# 健康检查 / 模型 / 参数帮助
python scripts/liber_speech_client.py health
python scripts/liber_speech_client.py models
python scripts/liber_speech_client.py help
python scripts/liber_speech_client.py help tts turbo
python scripts/liber_speech_client.py help asr large-v3
python scripts/liber_speech_client.py help vc seed-vc --format markdown

# TTS
python scripts/liber_speech_client.py tts "你好世界" --language zh --format wav
python scripts/liber_speech_client.py tts "你好世界" --speed 0.9 --exaggeration 0.7
python scripts/liber_speech_client.py tts "你好世界" --params '{"cfg_weight":0.3}'

# ASR
python scripts/liber_speech_client.py asr audio.wav --language zh
python scripts/liber_speech_client.py asr audio.wav --timestamps word
python scripts/liber_speech_client.py asr audio.wav --vad-filter --initial-prompt "术语"
python scripts/liber_speech_client.py asr audio.wav --output srt

# VC
python scripts/liber_speech_client.py vc source.wav --prompt ref.wav --model seed-vc --convert-all
python scripts/liber_speech_client.py vc source.wav --prompt ref.wav --segments '[{"start":0,"end":3.2}]'
python scripts/liber_speech_client.py vc source.wav --prompt ref.wav --seed 42 --diffusion-steps 20
```

## 常用选项

所有子命令支持：

- `--base-url` / `--api-key`：本次调用覆盖配置
- `--api-version v1|v2|auto`
- `--timeout`：默认 120 秒；TTS/ASR/VC 默认 600 秒
- `--retries`：只重试连接错误、超时和 HTTP 5xx

退出码：

| 退出码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 配置、参数或输入文件错误 |
| `3` | 网络或服务不可达 |
| `4` | 服务返回 API 错误 |

## 和 `liberastra` skill 的区别

- 本 skill 直连语音服务 `:5555` 的 `/api/v2`（回退 `/api/v1`），同步返回结果。
- `liberastra` skill 调用主平台 `:8000`，生成走异步任务。
- 两者不要混用 `LIBER_API_BASE_URL` 和 `LIBERASTRA_SERVER`。
