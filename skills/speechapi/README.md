# liber-speechapi 技能使用说明

## 功能和目的

`liber-speechapi` 是一个集成了ASR（自动语音识别）和TTS（文本转语音）功能的语音处理工具。该技能提供了：

- **ASR（语音转文字）**：`large-v3`、`large-v3-turbo`、`qwen3-asr-1.7b`。不传 `model` 或传 `default` 时用服务端 `LIBER_SPEECH_ASR_MODEL`（默认 `large-v3`）。每次转写结束后服务会释放模型和显存
- **TTS（文字转语音）**：Chatterbox 的 11 个模型包。默认 `multilingual_v3`。`multilingual` 仍等同 `multilingual_v2`。可用参考音频做音色克隆。每次合成结束后服务会释放模型和显存
- **输出格式**：
  - ASR：JSON 或纯文本
  - TTS：`wav`、`ogg_opus`（`ogg` 与 `ogg_opus` 相同）。语音服务不直接生成 `mp3` 或 `mp4`
- **调用方式**：`scripts/liber_speech_client.py` 调用已部署的 LiberAstra Speech 服务
- **API 鉴权**：Bearer Token，对应服务端 `LIBER_SPEECH_API_KEY`

## 前置条件

### 部署后端要求

使用此技能前，语音服务需要已经在显卡主机上运行：

- 服务代码在仓库 `services/speech`，默认端口 `5555`
- 服务端需要 FFmpeg，用来把 wav 转成 ogg_opus
- 客户端需要 Python 3.10+ 和 `requests`（见技能目录 `requirements.txt`）

### 配置优先级

环境配置按以下优先级顺序加载：

1. **环境变量**：`LIBER_API_BASE_URL` 和 `LIBER_API_KEY`（最高优先级）
2. **全局配置文件**：`~/.openclaw/.env`（用于跨项目共享配置）
3. **项目内配置**：技能目录下的 `.env` 文件
4. **当前工作目录**：当前工作目录下的 `.env` 文件（最低优先级）

这样可以灵活地在不同层级进行配置，满足全局、项目和个人需求。

### 配置文件存储

为了防止在更新技能时丢失用户配置，详细的配置参数存储在以下位置：

1. **首选位置**：`~/.openclaw/workspace/config/speechapi_config.json`（防止更新时被覆盖）
2. **备用位置**：技能目录里的 `speechapi_config.json`

### 后端

这个 skill 不单独安装 Liber SpeechAPI。它调用 LiberAstra 的 `services/speech`，默认监听 `5555`。`LIBER_API_BASE_URL` 形如 `http://<主机>:5555/api/v1`，`LIBER_API_KEY` 与服务端 `LIBER_SPEECH_API_KEY` 相同。不要把密钥写进文档或日志。

## 使用示例

在技能目录下执行。首次合成会加载模型，客户端超时是 600 秒。

### 健康检查

```bash
python scripts/liber_speech_client.py health
```

### TTS

```bash
python scripts/liber_speech_client.py tts "你好世界" --language zh --model multilingual_v3 --format wav
python scripts/liber_speech_client.py tts "你好世界" --format ogg_opus --output hello.ogg
```

`mp3` 会得到 HTTP 400。Telegram 语音用 `--telegram`，输出 `ogg_opus`。

### ASR

```bash
python scripts/liber_speech_client.py asr audio.wav --language zh
python scripts/liber_speech_client.py asr audio.wav --output text
```

模型列表、语言代码和字段说明见 `references/api.md`。

### 模型列表

```bash
python scripts/liber_speech_client.py models
```

直接读取服务端 `GET /api/v1/models`，返回可用的 ASR/TTS 包和默认模型。优先用它确认模型名，不要硬编码。

### 批量转写

```bash
# 多个文件
python scripts/liber_speech_client.py asr a.wav b.mp3 --output json
# 整个目录
python scripts/liber_speech_client.py asr ./recordings --output text
```

批量模式下，结果写在每个输入文件旁边：结构化输出写同名 `.json`，纯文本写同名 `.txt`。`--output` 只对单个输入生效。

### 临时覆盖与重试

所有子命令都支持：

- `--base-url` / `--api-key`：覆盖本次调用的服务地址和密钥
- `--timeout`：请求超时（默认 120 秒；合成/转写默认 600 秒）
- `--retries`：连接错误、超时和 HTTP 5xx 的指数退避重试次数；4xx 不重试

### 退出码

| 退出码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 配置、参数或输入文件错误 |
| `3` | 网络或服务不可达 |
| `4` | 服务返回 API 错误 |

### 和 `liberastra` skill 的区别

- 本 skill 直接调用语音服务 `:5555` 的 `/api/v1`，同步返回 ASR/TTS 结果，不经过主平台的任务队列。
- `liberastra` skill 调用主平台 `:8000`，生成走异步任务，适合图片、视频和需要任务管理的场景。
- 两者不要混用 `LIBER_API_BASE_URL` 和 `LIBERASTRA_SERVER`。