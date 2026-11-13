# Liber SpeechAPI 参数说明

## 能力

1. Telegram/openclaw 语音工作流：ASR → 回复压缩 → OGG/Opus TTS
2. 通用文字转语音（TTS）
3. 通用语音转文字（ASR）
4. 换音（VC）

服务端优先使用 `/api/v2`；客户端自动探测并回退 `/api/v1`。v2 参数在 v1 服务上不会静默忽略，会直接报错。

配置里的 `"default"` 或 `null` 表示不传该字段，使用服务端默认值。

---

## 配置文件

```json
{
  "asr": {
    "language": "zh",
    "task": "transcribe",
    "model": "default",
    "options": {}
  },
  "tts": {
    "model": "multilingual_v3",
    "language": "zh",
    "format": "wav",
    "audio_prompt_path": "default",
    "options": {}
  },
  "vc": {
    "model": "seed-vc",
    "convert_all": true,
    "options": {}
  },
  "global": {
    "telegram_tts_format": "ogg_opus",
    "asr_output": "json",
    "api_version": "auto"
  }
}
```

`options` 里的字段会平铺到 v2 JSON 请求。CLI 的 `--params` 优先级最高。

---

## TTS 通用参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `text` | string | 必填 | 要合成的文本 |
| `model` | string | `multilingual_v3` | 11 个模型包之一 |
| `language` | string | `zh` | 语言代码 |
| `format` | string | `wav` | `wav` 或 `ogg_opus` |
| `prompt_file_id` | string | 无 | v2 参考音频 file_id |
| `speed` | number | 1.0 | 0.5–2.0；ffmpeg atempo，保持音高 |
| `normalize_loudness` | bool | false | ffmpeg loudnorm |
| `target_lufs` | number | -16 | -40 到 -5 |
| `ref_start` | number | 0 | 参考音频起始秒 |
| `ref_duration` | number | 0 | 参考音频时长；0 表示完整 |

## TTS 模型差异

| 参数 | multilingual/standard/语言包 | turbo/nano |
|---|---|---|
| `exaggeration` | ✅ 0–2，默认 0.5 | ❌ |
| `cfg_weight` | ✅ 0–1，默认 0.5 | ❌ |
| `temperature` | ✅ 0.05–2，默认 0.8 | ✅ |
| `repetition_penalty` | ✅ 1–2，默认 1.2 | ✅ |
| `min_p` | ✅ 0–1，默认 0.05 | ❌ |
| `top_p` | ✅ 默认 1.0 | ✅ 默认 0.95 |
| `top_k` | ❌ | ✅ 默认 1000 |
| `norm_loudness` | ❌ | ✅ 默认 true |

Chatterbox TTS 没有 `seed`、`pitch` 或离散情绪标签参数。`exaggeration` 是语气强度，不是“开心/悲伤”。

模型包：

`multilingual_v3`、`multilingual_v2`、`standard`、`turbo`、`nano`、`zh-cmn`、`es-mx`、`es-es`、`pt-br`、`pt-pt`、`hi`。

---

## ASR 通用参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `file_id` | string | 必填（v2） | 输入音频/视频 |
| `model` | string | 服务端默认 | `large-v3`、`large-v3-turbo`、`qwen3-asr-1.7b` |
| `language` | string | 自动 | 语言代码 |
| `task` | string | `transcribe` | `transcribe` 或 `translate` |
| `timestamps` | string | `segment` | `none` / `segment` / `word` |
| `response_format` | string | `json` | `json` / `verbose_json` / `text` / `srt` / `vtt` |

### faster-whisper 专属

`beam_size`、`best_of`、`patience`、`length_penalty`、`repetition_penalty`、`no_repeat_ngram_size`、`temperature`、`compression_ratio_threshold`、`log_prob_threshold`、`no_speech_threshold`、`condition_on_previous_text`、`prompt_reset_on_temperature`、`initial_prompt`、`prefix`、`hotwords`、`suppress_blank`、`suppress_tokens`、`max_initial_timestamp`、`prepend_punctuations`、`append_punctuations`、`multilingual`、`vad_filter`、`vad_parameters`、`chunk_length`、`clip_timestamps`、`hallucination_silence_threshold`、`language_detection_threshold`、`language_detection_segments`、`max_new_tokens`。

### Qwen3-ASR 专属

`max_new_tokens`（默认 512）、`max_inference_batch_size`（默认 4）、`timestamps`。

Qwen 不支持：`task=translate`、`vad_filter`、`beam_size`、`initial_prompt`、`hotwords`、`temperature`、各种 threshold、language detection、suppress/punctuation、clip/chunk。

`timestamps=word` 时返回顶层 `words`；`chunks` 仍是句子级。

---

## VC 通用参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `file_id` | string | 必填 | 源音频/视频 |
| `prompt_file_id` | string | 必填 | 目标音色参考音频 |
| `model` | string | `chatterbox` | `chatterbox` 或 `seed-vc` |
| `segments` | array | 无 | `[{start,end}]` |
| `convert_all` | bool | true（配置） | 忽略 segments，整段替换 |
| `segment_padding` | number | 0 | 段前后扩展秒数 |
| `merge_gap` | number | 0.05 | 相邻段合并间隔 |
| `min_segment` | number | 0.02 | 最短段 |
| `ref_start` | number | 0 | 参考音频起始秒 |
| `ref_duration` | number | 0 | 参考音频时长；0 表示完整 |
| `denoise` | bool | false | ffmpeg afftdn 去底噪 |
| `normalize_loudness` | bool | false | 输出响度归一 |
| `target_lufs` | number | -16 | 响度目标 |
| `output_sample_rate` | number | 0 | 0 跟随源；8000–192000 |
| `max_window` | number | 20 | 外层分段窗口 5–30 秒 |
| `context` | number | 0.15 | 接缝上下文 0–0.5 秒 |
| `fade` | number | 0.02 | 接缝淡化 0–0.1 秒 |

### Seed-VC 专属

`seed`、`diffusion_steps`（默认 10）、`inference_cfg_rate`（默认 0.7）、`n_quantizers`（默认 3）、`temperature`（默认 1.0）、`ref_max_len`（默认 25）、`length_adjust`（默认 1.0）、`overlap_frame_len`（默认 16）。

### Chatterbox VC

没有模型级采样参数。参考音频固定使用前 10 秒；用 `ref_start`/`ref_duration` 选择片段。

### 不支持

`dereverb`、`pitch`、`semi_tone_shift`、`auto_f0_adjust`、`f0_condition`、说话人分离。当前 Seed-VC V1 的 `f0_condition=false`，不能做变调。

---

## 服务限制

服务端默认不限制音频时长、上传大小或文本长度：

- `LIBER_SPEECH_MAX_UPLOAD_BYTES=0`
- `LIBER_SPEECH_MAX_MEDIA_SECONDS=0`

模型限制写在 `/api/v2/help` 的 `model_limits`：

- Chatterbox VC 参考音频 10 秒
- Seed-VC 参考音频 25 秒
- Qwen3-ASR `max_new_tokens=512`、`max_inference_batch_size=4`

长音频由 ASR 分块和 VC 窗口处理；资源不足时返回 `resource_exhausted` / `model_limit_exceeded`。
