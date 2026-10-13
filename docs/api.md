# LiberAstra API 参考

所有接口（除 `/healthz` 与 `/auth/*`）需要 `Authorization: Bearer <JWT 或 astra_ Token>`。

交互式文档：运行后访问 `/docs`（Swagger UI）。

## 鉴权

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/auth/status` | 是否已初始化 |
| POST | `/api/v1/auth/setup` | 首次创建管理员 |
| POST | `/api/v1/auth/login` | 登录，返回 JWT |
| GET/POST/DELETE | `/api/v1/tokens[/{id}]` | API Token 签发/列表/吊销 |

## Provider 与能力

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/capabilities` | Provider 类型注册表与能力标签 |
| GET/POST | `/api/v1/providers` | 列表 / 创建（api_key 加密存储） |
| PATCH/DELETE | `/api/v1/providers/{id}` | 更新 / 删除 |
| POST | `/api/v1/providers/{id}/test` | 测试连接 |
| GET | `/api/v1/providers/{id}/models` | 实时拉取并缓存模型列表 |

## 任务

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/jobs` | 列表（`status_filter`、`kind`、`limit`） |
| GET | `/api/v1/jobs/{id}` | 详情 |
| GET | `/api/v1/jobs/{id}/events` | SSE 进度推送（快照 + 增量 + 心跳） |
| POST | `/api/v1/jobs/{id}/cancel` / `retry` | 取消 / 重试 |

所有生成接口默认 202 返回 Job；加 `?wait=true` 同步等待终态。

## 能力

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/llm/chat` | LLM 聊天（Job） |
| POST | `/api/v1/tts` | 文字转语音（voice 或 voice_record_id） |
| POST | `/api/v1/asr` | 语音转文字（multipart，导出 txt/srt/vtt/json） |
| GET/POST/DELETE | `/api/v1/voices` | 音色库（参考音频 + voice_id + 默认音色） |
| POST | `/api/v1/images/generate` / `edit` | 文生图 / 图生图（comfyui 需 workflow 包名） |
| POST | `/api/v1/images/optimize-prompt` | LLM 扩写提示词 |
| GET/POST/DELETE | `/api/v1/workflows[/{name}]`、`/workflows/import` | 工作流包管理 |
| POST | `/api/v1/videos/quick` | 快速创作（topic/script/storyboard） |
| POST | `/api/v1/videos/i2v` / `avatar` / `motion` / `assets` | 图生视频 / 数字人 / 动作迁移 / 自定义素材（multipart） |
| POST | `/api/v1/uploads` | 通用上传（BGM 等参数引用） |
| GET | `/api/v1/assets[/{id}[/content]]` | 资产列表 / 详情 / 内容下载 |
| GET | `/api/v1/system/info`，POST `cleanup`，GET `backup` | 系统信息 / 清理 / 备份导出（管理员） |

## OpenAI 兼容子集（/v1）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/v1/chat/completions` | 代理默认 LLM（暂不支持 stream） |
| POST | `/v1/audio/speech` | 默认 TTS Provider |
| POST | `/v1/audio/transcriptions` | 默认 ASR Provider（json/text/srt/vtt） |
| POST | `/v1/images/generations` | 在线图像 Provider（b64_json/url；comfyui 类型请走 `/api/v1/images/generate`） |
