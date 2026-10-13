# 部署

## Docker（推荐）

```bash
cp .env.example .env   # 设置 LIBERASTRA_SECRET_KEY
docker compose up -d --build
# http://localhost:8000，数据在 ./data
```

可选本地全栈：

```bash
docker compose --profile ollama up -d     # + Ollama
docker compose --profile comfyui up -d    # + ComfyUI（需 NVIDIA Container Toolkit）
docker compose --profile postgres up -d   # + PostgreSQL（需同时设 LIBERASTRA_DATABASE_URL）
```

容器访问宿主机/局域网服务（如宿主机上的 ComfyUI）：地址用 `host.docker.internal`（compose 已配置 extra_hosts）。

## 源码运行

```bash
cd backend && uv venv .venv && uv pip install -e ".[dev]"
cd ../frontend && npm install && npm run build   # 产物由后端托管
cd ../backend && uv run astra serve
```

开发模式：后端 `uv run astra serve --reload`，前端 `npm run dev`（5173 代理 /api 到 8000）。

## 配置

优先级：环境变量 > `.env` > 默认值。见 `.env.example`。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LIBERASTRA_SECRET_KEY` | 自动生成到 `data/.secret_key` | JWT 签名与密钥加密的主密钥，生产必设 |
| `LIBERASTRA_DATABASE_URL` | SQLite `data/liberastra.db` | PostgreSQL：`postgresql+psycopg://...`（需 `pip install 'liberastra[postgres]'`） |
| `LIBERASTRA_DATA_DIR` | `./data` | 数据目录（outputs/uploads/voices/workflows/logs） |
| `LIBERASTRA_CLEANUP_RETENTION_DAYS` | `0`（关闭） | 已结束任务与产物的保留天数 |
| `LIBERASTRA_HOST` / `PORT` | `0.0.0.0:8000` | 监听地址 |

## 运维

- 健康检查：`GET /healthz`
- 日志：`data/logs/app.log`（50MB 轮转 × 5）
- 备份：`GET /api/v1/system/backup`（管理员，zip 导出数据目录，不含日志）
- 首次启动进入初始化向导创建管理员账号
