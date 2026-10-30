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
| `LIBER_SPEECH_MODELS_DIR` | 宿主机权重目录，挂到容器 `/models` |
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

也可以不用缓存结构，直接放平铺目录：

- `/models/faster-whisper-large-v3/model.bin`
- `/models/faster-whisper-large-v3-turbo/model.bin`
- `/models/Qwen3-ASR-1.7B/config.json`
- `/models/Qwen3-ForcedAligner-0.6B/config.json`

## 接口

- `GET /api/v1/models`：返回 `tts_models`（11 个合成包）、`asr_models`、`default_tts_model`、`default_asr_model`
- `POST /api/v1/tts/synthesize`：表单字段 `text`、`model`、`language`、`format`，参考音频字段名是 `prompt`
- `POST /api/v1/asr/transcribe`：上传音频，可选 `model`、`language`、`task`

返回的 `chunks` 都是句子级：`start`、`end`、`text`。Qwen3-ASR 原始结果是字或词，服务会按标点或超过 0.6 秒的停顿收成句子，主服务导出 SRT / VTT 不用另写解析。

## 显存

每次合成或转写结束都会丢掉当前模型，并调用 `gc.collect()` 与 `torch.cuda.empty_cache()`。同一次请求里不会让 Chatterbox 和识别模型一起留在显存上。Qwen3-ASR 使用 Transformers 后端，不会按 vLLM 的方式预占整张卡。
