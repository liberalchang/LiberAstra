# 部署

## Docker（推荐）

```bash
cp .env.example .env   # 按需设置 LIBERASTRA_SECRET_KEY、LIBERASTRA_PUBLISH_PORT
docker compose up -d --build
# 默认 http://localhost:8000，数据在 ./data
```

若宿主机 **8000 已被占用**，在 `.env` 中设置：

```bash
LIBERASTRA_PUBLISH_PORT=18000
```

则访问 `http://<主机>:18000`（容器内仍监听 8000）。

### 分置部署（LiberAstra 与 Ollama/Comfy/Speech 不在同一台机器）

见 **[分置部署教程](./分置部署教程.md)**：应用主机只起 LiberAstra、显卡主机分别部署推理服务、data/数据库迁移、局域网 Provider 配置。

### 可选本地全栈 profile

```bash
docker compose --profile ollama up -d     # + Ollama
docker compose --profile comfyui up -d    # + ComfyUI（需 NVIDIA Container Toolkit）
docker compose --profile postgres up -d   # + PostgreSQL（需同时设 LIBERASTRA_DATABASE_URL）
docker compose --profile speech up -d     # + 语音服务（需 NVIDIA Container Toolkit）
```

语音服务在 `services/speech`，和 Ollama、ComfyUI 一样是可选进程。把它单独放到显卡主机：

```bash
cd services/speech && docker compose up -d --build
```

服务监听 `0.0.0.0:5555`。在 LiberAstra「服务提供方」添加类型 Liber Speech API，Base URL 填 `http://<显卡主机IP>:5555`。音色名填语言代码，例如 `zh`。需要鉴权时，主机和 LiberAstra 填同一个 `LIBER_SPEECH_API_KEY`。

容器访问宿主机/局域网服务（如宿主机上的 ComfyUI）：地址用 `host.docker.internal`（compose 已配置 extra_hosts）；访问**其它机器**则用对方局域网 IP。

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
| `LIBERASTRA_SECRET_KEY` | 自动生成到 `data/.secret_key` | JWT 签名与密钥加密的主密钥，生产必设；迁库须一并迁移 `.secret_key` |
| `LIBERASTRA_DATABASE_URL` | SQLite `data/liberastra.db` | PostgreSQL：`postgresql+psycopg://...`（需 `pip install 'liberastra[postgres]'`） |
| `LIBERASTRA_DATA_DIR` | `./data`（容器内 `/data`） | 数据目录（outputs/uploads/voices/workflows/logs） |
| `LIBERASTRA_PUBLISH_PORT` | `8000` | **宿主机**映射端口（compose）；与容器内监听端口分离 |
| `LIBERASTRA_HOST` / `LIBERASTRA_PORT` | `0.0.0.0` / `8000` | 容器/进程内监听地址 |
| `LIBERASTRA_CLEANUP_RETENTION_DAYS` | `0`（关闭） | 已结束任务与产物的保留天数 |

## 运维

- 健康检查：`GET /healthz`
- 日志：`data/logs/app.log`（50MB 轮转 × 5）
- 备份：`GET /api/v1/system/backup`（管理员，zip 导出数据目录，不含日志）
- 首次启动进入初始化向导创建管理员账号；若已迁移 `data/`，则沿用原账号
