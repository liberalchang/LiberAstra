# Liber Speech

独立语音服务。文字转语音用 Chatterbox，语音转文字用 faster-whisper 或 Qwen3-ASR。主服务只发 HTTP 请求，不在自己的进程里加载这些权重。

## 本机插件

在 LiberAstra「资源 → 插件」里安装并启用「Liber Speech」时：

- 仓库里的 `services/speech` 由插件页安装后启动：`python -m uvicorn server:app`，端口 `5555`。语音和深度共用一份 Python 环境（含 PyTorch）。开发时在 `%LOCALAPPDATA%\LiberAstra\plugin-runtime`，安装包在 `%LOCALAPPDATA%\LiberAstra\data\plugins\runtime`。已经装过就不再重装。权重目录是 `data/plugins/speech/models`（Windows 安装包是 `%LOCALAPPDATA%\LiberAstra\data\plugins\speech\models`）。第一次合成时由服务自己下载到这个目录。
- 已发布的 LiberSpeech 安装包在 `C:\Program Files\LiberSpeech`，用 `docker compose` 启动，权重留在安装包自己的 Docker 卷里。

## 启动

在显卡主机上进入本目录，先复制环境变量：

```bash
cp .env.example .env
```

装过 `qwen-asr` 之后需要重新构建镜像，再启动：

```bash
docker compose build
docker compose up -d
```

`docker-compose.yml` 把宿主机的 `server.py` 和 `engine.py` 只读挂进容器。改这两个文件后重启容器即可，不必每次重建镜像。改 `Dockerfile` 或 `requirements.txt` 才需要 `docker compose build`。

默认端口是 `5555`。`NVIDIA_VISIBLE_DEVICES` 决定容器能看见哪一张卡。

## 环境变量

| 变量 | 作用 |
| --- | --- |
| `LIBER_SPEECH_API_KEY` | 接口密钥。留空则不校验 |
| `LIBER_SPEECH_DEVICE` | `cuda` 或 `cpu` |
| `LIBER_SPEECH_ASR_MODEL` | 请求不传 `model` 时的识别模型。可选 `large-v3`、`large-v3-turbo`、`qwen3-asr-1.7b` |
| `LIBER_SPEECH_QWEN_ALIGNER_MODEL` | Qwen3-ASR 时间戳模型路径或仓库名。留空则自动查找本地缓存 |
| `LIBER_SPEECH_TTS_MODEL` | 请求不传 `model` 时的合成模型，默认 `multilingual_v3` |
| `LIBER_SPEECH_VC_MODEL` | 请求不传 `model` 时的换音模型，默认 `chatterbox`；可选 `seed-vc` |
| `LIBER_SPEECH_SEEDVC_DIR` | Seed-VC 主权重目录，默认 `/models/Seed-VC` |
| `LIBER_SPEECH_WHISPER_SMALL_DIR` | Seed-VC 的 Whisper 编码器目录，默认 `/models/whisper-small` |
| `LIBER_SPEECH_CAMPPLUS_DIR` | CAMPPlus 说话人编码器目录，默认 `/models/campplus` |
| `LIBER_SPEECH_BIGVGAN_DIR` | BigVGAN 声码器目录，默认 `/models/bigvgan_v2_22khz_80band_256x` |
| `LIBER_SPEECH_DEMUCS_DIR` | Demucs 权重目录，默认 `/models/demucs` |
| `LIBER_SPEECH_MODELS_DIR` | 宿主机权重目录，挂到容器 `/models` |
| `TORCH_HOME` | 设为 `/models`，Demucs 的本地缓存也会落在 `/models/hub` |
| `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` | 设为 `1` 时不再联网下载 |

请求里的 `model` 会覆盖上面的默认值。`multilingual` 仍然是 `multilingual_v2` 的别名，只有不传 `model` 时才读 `LIBER_SPEECH_TTS_MODEL`。

识别模型别名不区分大小写。`turbo`、`faster-whisper-large-v3-turbo` 都会变成 `large-v3-turbo`。`qwen3-asr` 和 `Qwen/Qwen3-ASR-1.7B` 都会变成 `qwen3-asr-1.7b`。以 `/` 开头的路径按本地目录加载：目录里有 `model.bin` 走 faster-whisper，有 `config.json` 走 Qwen3-ASR。

`qwen3-asr-1.7b` 不支持 `task=translate`。语音翻译请改用 `large-v3`。

## 离线权重

把下载好的 Hugging Face 缓存目录放进宿主机 `models`，容器里就是 `/models`。

| 缓存目录 | 用途 |
| --- | --- |
| `models--ResembleAI--*` | Chatterbox 的 11 个模型包 |
| `models--Systran--faster-whisper-large-v3` | `large-v3` |
| `models--mobiuslabsgmbh--faster-whisper-large-v3-turbo` | `large-v3-turbo`。Systran 没有发布这个仓库 |
| `models--Qwen--Qwen3-ASR-1.7B` | `qwen3-asr-1.7b` |
| `models--Qwen--Qwen3-ForcedAligner-0.6B` | Qwen3-ASR 的字词时间戳 |
| `models--ResembleAI--chatterbox/snapshots/*/s3gen.safetensors` | Chatterbox VC 声码器；同目录的 `conds.pt` 可选，本服务每次都会传参考音频 |
| `/models/Seed-VC/` | Seed-VC V1 主权重和配置 yml |
| `/models/whisper-small/` | Seed-VC 的 Whisper 编码器 |
| `/models/campplus/campplus_cn_common.bin` | Seed-VC 的说话人编码器 |
| `/models/bigvgan_v2_22khz_80band_256x/` | Seed-VC 的 BigVGAN 声码器 |
| `/models/demucs/htdemucs-*.th` | Demucs 背景音分离；启动时会归一化到 `$TORCH_HOME/hub/checkpoints/` |

也可以不用缓存结构，直接放平铺目录：

- `/models/faster-whisper-large-v3/model.bin`
- `/models/faster-whisper-large-v3-turbo/model.bin`
- `/models/Qwen3-ASR-1.7B/config.json`
- `/models/Qwen3-ForcedAligner-0.6B/config.json`

## 接口

- `GET /api/v1/models`：返回 `tts_models`（11 个合成包）、`asr_models`、`vc_models`、`default_tts_model`、`default_asr_model`、`default_vc_model`、`separate_available`
- `POST /api/v1/tts/synthesize`：表单字段 `text`、`model`、`language`、`format`，参考音频字段名是 `prompt`
- `POST /api/v1/asr/transcribe`：上传音频，可选 `model`、`language`、`task`
- `POST /api/v1/vc/convert`：表单字段 `file`（音频）、`prompt`（目标音色参考音频）、`model`（`chatterbox` / `seed-vc`）、`segments`（JSON `[{start, end}]`，可选）；返回 `audio_url`
- `POST /api/v1/audio/separate`：上传音频，返回 `vocals_url`、`accompaniment_url`

返回的 `chunks` 都是句子级：`start`、`end`、`text`。Qwen3-ASR 原始结果是字或词，服务会按标点或超过 0.6 秒的停顿收成句子，主服务导出 SRT / VTT 不用另写解析。

## v2 JSON 接口

v2 用于新接入：先上传文件拿 `file_id`，再用 JSON 调用。旧的 `/api/v1` multipart 接口继续保留。

- `POST /api/v2/files`：multipart 上传，返回 `file_id`、`filename`、`size`、`sha256`、`expires_at`。分块写盘，默认不限制大小。
- `DELETE /api/v2/files/{file_id}`：删除上传文件。
- `GET /api/v2/help`：全部功能、端点、错误码和运行时版本。
- `GET /api/v2/help/{function}`：功能级参数（`tts` / `asr` / `vc`）。
- `GET /api/v2/help/{function}/{model}`：模型级参数、默认值、范围、不支持原因和示例。支持 `?include=common,model,examples,errors,unsupported` 和 `?format=markdown`。
- `GET /api/v2/models`：模型目录，含 `params_url`、`supports`、`unsupported`。
- `POST /api/v2/tts/synthesize`：JSON，字段见 `/api/v2/help/tts/{model}`。
- `POST /api/v2/asr/transcribe`：JSON，字段见 `/api/v2/help/asr/{model}`。
- `POST /api/v2/vc/convert`：JSON，字段见 `/api/v2/help/vc/{model}`。

示例：

```bash
# 1. 上传
curl -X POST http://speech:5555/api/v2/files -F file=@input.wav

# 2. TTS
curl -X POST http://speech:5555/api/v2/tts/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"你好","model":"multilingual_v3","language":"zh","exaggeration":0.7,"speed":0.9}'

# 3. ASR
curl -X POST http://speech:5555/api/v2/asr/transcribe \
  -H 'Content-Type: application/json' \
  -d '{"file_id":"f_xxx","model":"large-v3","timestamps":"word","vad_filter":true}'

# 4. VC
curl -X POST http://speech:5555/api/v2/vc/convert \
  -H 'Content-Type: application/json' \
  -d '{"file_id":"f_xxx","prompt_file_id":"f_ref","model":"seed-vc","diffusion_steps":20,"seed":42}'
```

服务端默认不限制音频时长或上传大小；`LIBER_SPEECH_MAX_UPLOAD_BYTES` 与 `LIBER_SPEECH_MAX_MEDIA_SECONDS` 只在运维显式设置时生效（默认 0 = 不限制）。参考音频上限、Qwen `max_new_tokens` 等模型限制写在 `/api/v2/help` 的 `model_limits` 里。

`timestamps=word` 时 ASR 返回顶层 `words` 数组；`response_format` 支持 `json`、`text`、`srt`、`vtt`。

## 显存

每次合成或转写结束都会丢掉当前模型，并调用 `gc.collect()` 与 `torch.cuda.empty_cache()`。同一次请求里不会让 Chatterbox 和识别模型一起留在显存上。Qwen3-ASR 使用 Transformers 后端，不会按 vLLM 的方式预占整张卡。换音/分离同样在请求结束后释放模型。

## Seed-VC 许可证

`services/speech/third_party/seed_vc/` 来自 [Plachtaa/Seed-VC](https://github.com/Plachtaa/Seed-VC)，按 GPL-3.0 引入，许可证和上游 commit 见该目录的 `LICENSE` / `UPSTREAM.md`。分发安装包时需要一并提供许可证和源码说明；模型权重不随仓库分发。
