# Configuration

## 配置文件结构

Liber SpeechAPI skill 使用两种配置方式：

1. **`.env` 文件** - 存放核心认证和服务器配置（必填）
2. **`speechapi_config.json` 文件** - 存放详细的 ASR、TTS 和全局默认配置（可选，支持 `default` 值）

---

## 1. .env 文件（核心配置）

### 必填变量

| 变量名 | 描述 | 示例 |
|--------|------|------|
| `LIBER_API_BASE_URL` | Liber SpeechAPI 服务器地址 | `http://127.0.0.1:5555/api/v1` |
| `LIBER_API_KEY` | API 访问密钥（Bearer Token） | `your_api_key_here` |

### 示例 .env 文件

```env
LIBER_API_BASE_URL=http://127.0.0.1:5555/api/v1
LIBER_API_KEY=your_api_key_here
```

说明：
- `.env` 只负责服务地址和鉴权信息
- ASR/TTS 默认参数主要来自 `speechapi_config.json`
- 如果 skill 目录和当前工作目录都存在 `.env`，优先使用 skill 目录内的 `.env`

---

## 2. speechapi_config.json 文件（详细参数）

### 完整配置示例

```json
{
    "asr": {
        "language": "zh",
        "task": "transcribe",
        "model": "default"
    },
    "tts": {
        "model": "multilingual_v3",
        "language": "zh",
        "format": "wav",
        "audio_prompt_path": "default"
    },
    "global": {
        "voice_summary_limit": 100,
        "default_clone_audio": "tmp/clone.wav",
        "telegram_tts_format": "ogg_opus",
        "asr_output": "json"
    }
}
```

### default 值处理

- 参数值为 `"default"` 表示使用后端默认值，请求时不传递该字段
- 参数值为 `null` 或未定义也会使用后端默认值
- 所有参数都有合理默认值，用户只需覆盖需要自定义的参数

---

## 3. 默认行为

### 通用文字转语音

- 默认输出格式：`wav`
- 默认参数来源：`tts` 配置段

### Telegram/openclaw 语音回复

- 强制输出格式：`ogg_opus`
- 默认参数来源：`tts` 配置段 + `global.telegram_tts_format`

### 通用语音转文字

- 默认输出模式：`json`
- 若显式要求纯文本，再返回 `text`
- 默认输出模式来源：`global.asr_output`

---

## 4. ASR 参数

| 参数名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `language` | string | `"zh"` | 输入音频语言。请求留空时由模型识别 |
| `task` | string | `"transcribe"` | `transcribe` 或 `translate`。`qwen3-asr-1.7b` 不支持 `translate` |
| `model` | string | `"default"` | `large-v3`、`large-v3-turbo` 或 `qwen3-asr-1.7b`。`default` 或不传时用服务端 `LIBER_SPEECH_ASR_MODEL` |

`model` 填模型别名，不填 `/models/...` 路径。`qwen3-asr-1.7b` 的字词时间戳会收成句子级 `chunks`。请求不传说话人分割。每次转写结束后服务释放模型和显存。

---

## 5. TTS 参数（Chatterbox）

| 参数名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `model` | string | `"multilingual_v3"` | 11 个模型包之一。`multilingual` 仍等同 `multilingual_v2` |
| `language` | string | `"zh"` | 输出语言 |
| `format` | string | `"wav"` | `wav` 或 `ogg_opus`。`ogg` 等同 `ogg_opus` |
| `audio_prompt_path` | string | `"default"` | 本机参考音频路径。上传时的表单字段名是 `prompt` |

`mp3`、`mp4` 以及温度、`cfg_weight` 等采样参数不是当前接口字段。

---

## 6. 全局参数

| 参数名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `voice_summary_limit` | number | 100 | 语音回复文本长度限制 |
| `default_clone_audio` | string | `"tmp/clone.wav"` | 默认声音克隆参考音频路径 |
| `telegram_tts_format` | string | `"ogg_opus"` | Telegram 语音回复格式 |
| `asr_output` | string | `"json"` | 通用 ASR 默认输出模式 |

---

## 7. 配置优先级

1. 命令行参数
2. 函数参数
3. `speechapi_config.json`
4. 后端默认值

说明：
- `.env` 不参与 ASR/TTS 参数优先级比较，只负责服务地址和 API Key
- `default` 值会被忽略，最终由后端补默认值

---

## 8. 快速开始

优先读取 `~/.openclaw/workspace/config/speechapi_config.json`。没有该文件时，使用技能目录里的 `speechapi_config.json`。

### 运行健康检查

```bash
python scripts/liber_speech_client.py health
```

### 通用文字转语音（默认 wav）

```bash
python scripts/liber_speech_client.py tts "你好，欢迎使用 Liber SpeechAPI"
```

### 通用语音转文字（默认 json）

```bash
python scripts/liber_speech_client.py asr demo.wav
```

### 仅返回文本

```bash
python scripts/liber_speech_client.py asr demo.wav --output text
```

### Telegram 语音格式

```bash
python scripts/liber_speech_client.py tts "这是一条 Telegram 语音回复" --telegram
```
