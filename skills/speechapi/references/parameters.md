# Liber SpeechAPI 参数说明文档

## 概述

Liber SpeechAPI skill 提供三类能力：

1. **Telegram/openclaw 语音工作流**：语音输入 → ASR → 回复压缩 → Telegram OGG/Opus TTS
2. **通用文字转语音**：显式把文本合成为音频，默认输出 `wav`
3. **通用语音转文字**：显式把音频转为结构化识别结果，默认输出 `json`

配置支持 `config.json` 中的 `default` 值，表示使用后端默认参数，不在请求中传递该字段。

---

## 配置文件结构

### config.json 格式

```json
{
    "asr": {
        "language": "zh",
        "task": "transcribe"
    },
    "tts": {
        "model": "multilingual",
        "language": "zh",
        "format": "wav",
        "audio_prompt_path": "default"
    },
    "global": {
        "voice_summary_limit": 100,
        "telegram_tts_format": "ogg_opus",
        "asr_output": "json"
    }
}
```

### 默认值处理规则

- 如果参数值为 `default` 或 `null`，请求时不传递该字段
- 使用后端服务器默认值
- `tts.format` 用于通用 TTS 默认输出格式
- `global.telegram_tts_format` 用于 Telegram 场景语音格式
- `global.asr_output` 用于通用 ASR 默认输出模式

---

## ASR 参数（faster-whisper）

服务端用 faster-whisper。模型名来自服务环境变量 `LIBER_SPEECH_ASR_MODEL`，默认 `large-v3`，请求里不能改。

| 参数名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `file` | file | 必填 | 本地音频文件 |
| `language` | string | `zh` | 留空时由模型自动识别 |
| `task` | string | `transcribe` | `transcribe` 或 `translate` |

当前接口不接收 `url`、`timestamps`、`batch_size`、`flash`、说话人分割或 Hugging Face token。客户端也不再转发这些字段。

### 输出模式

| 模式 | 默认值 | 描述 |
|------|--------|------|
| `json` | 是 | 返回完整 ASR JSON：`text`、`chunks`、`meta` |
| `text` | 否 | 仅返回识别文本 |

`chunks` 的每一项是 `{start, end, text}`。`meta` 含 `language` 和 `task`。

---

## TTS 参数（Chatterbox）

### 请求字段

| 参数名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `text` | string | 必填 | 要合成的文本 |
| `model` | string | `multilingual` | 11 个模型包之一。`multilingual` 等同 `multilingual_v2` |
| `language` | string | `zh` | 语言代码。多语言模型必须是它支持的 23 种之一 |
| `format` | string | `wav` | `wav` 或 `ogg_opus`。`ogg` 会被改写成 `ogg_opus` |
| `prompt` | file | 不传 | 音色克隆参考音频，后缀 `.wav`、`.mp3`、`.ogg`、`.flac` |

`mp3` 和 `mp4` 会返回 HTTP 400，详情是「格式只支持 wav 或 ogg_opus」。主服务可以把 wav 再转成 mp3；这个 skill 直连语音服务，不做这步转码。

`temperature`、`top_p`、`top_k`、`cfg_weight`、`exaggeration`、`repetition_penalty`、`norm_loudness` 都不是当前合成接口的字段，客户端不会发送。

### 模型包

| id | 语言 |
|----|------|
| `multilingual_v3` | ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh |
| `multilingual_v2` | 同上。请求里的 `multilingual` 会解析成这个 id |
| `turbo` | en。参考音频须长于 5 秒 |
| `nano` | en。参考音频须长于 5 秒 |
| `standard` | en |
| `zh-cmn` | zh |
| `es-mx` | es |
| `es-es` | es |
| `pt-br` | pt |
| `pt-pt` | pt |
| `hi` | hi |

权重不在服务器上时，首次合成该包会失败。`GET /models` 可查看 `tts_models` 和 `default_tts_model`。

### 输出格式规则

| 场景 | 默认输出 |
|------|----------|
| 直接文字转语音 | `wav` |
| Telegram 语音回复 | `ogg_opus`，文件后缀是 `.ogg` |
| 显式指定格式 | `wav`、`ogg` 或 `ogg_opus` |

实测短句在 `model=multilingual`、`language=zh` 下，wav 与 ogg_opus 都返回 200，`sample_rate` 为 24000。wav 以 `RIFF`/`WAVE` 开头，ogg 以 `OggS` 开头。

---

## 全局参数

| 参数名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `voice_summary_limit` | integer | 100 | 语音回复文本长度限制 |
| `default_clone_audio` | string | `tmp/clone.wav` | 默认声音克隆参考音频路径 |
| `telegram_tts_format` | string | `ogg_opus` | Telegram 语音输出格式 |
| `asr_output` | string | `json` | 通用 ASR 默认输出模式 |

---

## 常见配置场景

### 场景 1: 通用文字转语音

```json
{
    "tts": {
        "model": "multilingual",
        "language": "zh",
        "format": "wav"
    }
}
```

### 场景 2: Telegram/openclaw 语音回复

```json
{
    "tts": {
        "model": "multilingual",
        "language": "zh",
        "format": "wav"
    },
    "global": {
        "telegram_tts_format": "ogg_opus",
        "voice_summary_limit": 100
    }
}
```

### 场景 3: 通用语音转文字

```json
{
    "asr": {
        "language": "zh",
        "task": "transcribe"
    },
    "global": {
        "asr_output": "json"
    }
}
```

### 场景 4: 语音克隆

```json
{
    "tts": {
        "model": "zh-cmn",
        "language": "zh"
    },
    "global": {
        "default_clone_audio": "tmp/clone.wav"
    }
}
```

参考音频通过表单字段 `prompt` 上传。文件不存在时继续普通合成。

---

## 使用注意

- 多语言包的 `language` 必须是 23 种语言代码之一。
- Turbo 和 Nano 的参考音频要长于 5 秒。
- 服务器上没有对应权重时，该模型包会在合成时失败。
- 首次加载模型可能需要一两分钟，客户端超时是 600 秒。
