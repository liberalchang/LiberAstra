# LiberAstra 架构

LiberAstra 是单用户自托管的 AIGC 聚合编排平台：**只编排，不推理**。所有推理交给外部服务（局域网 ComfyUI / Ollama / OpenAI 兼容服务，或云端 API）。

## 分层

```
Clients（Web UI / astra CLI / MCP / OpenAI 兼容 /v1）
  └── REST /api/v1（FastAPI）
        ├── services/    能力服务（llm / tts / asr / image）
        ├── pipelines/   视频流水线（quick / i2v / avatar / motion / assets）
        ├── jobs/        SQLite 持久化队列 + asyncio worker + SSE
        ├── providers/   适配器（每种能力一个 Protocol）
        ├── media/       ffmpeg 合成、字幕导出
        └── storage/     本地文件系统（data/），预留 S3
```

## 核心概念

- **Provider**：外部服务配置（类型、base_url、加密 API Key、并发上限、能力标签）。密钥 Fernet 加密落库，主密钥来自 `LIBERASTRA_SECRET_KEY`（缺省自动生成到 `data/.secret_key`）。
- **Job**：统一任务模型。所有生成走 Job（pending/running/succeeded/failed/canceled + progress + steps + outputs）；同步接口是“提交后等待”的语法糖（`?wait=true`）。
- **Asset**：产物统一载体（image/audio/video/subtitle/text），关联来源 Job，落盘 `data/outputs/{job_id}/`。
- **WorkflowPack**：ComfyUI 工作流包 = `workflow.json`（API Format）+ `manifest.yaml`（参数 → `node.inputs.field` 映射）。内置在 `backend/workflows/`，用户导入在 `data/workflows/`，同名覆盖。

## 扩展一个新能力

1. `providers/<cap>/` 写适配器（实现 `providers/base.py` 中的 Protocol）。
2. `providers/__init__.py` 的 `PROVIDER_TYPES` 注册类型与能力标签。
3. `services/providers.py build_adapter` 增加分发分支。
4. 写 Job runner 并 `register_*_jobs` 挂到 `main.py` lifespan。
5. `api/routes/` 加路由。

## 并发与取消

JobManager 按 Provider 限制并发（`Provider.concurrency`，默认 2），全局上限 4。取消为协作式：pending 立即取消，running 在 runner 下一个检查点生效。

## 部署形态

单镜像（多阶段：Node 构建前端 → python:3.11-slim + ffmpeg + 中文字体）。`docker-compose.yml` 可选 profile：ollama / comfyui（GPU）/ postgres。
