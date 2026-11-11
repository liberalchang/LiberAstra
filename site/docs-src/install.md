---
title: 安装 / 下载
---

# 安装 / 下载

LiberAstra 的模型不在本进程里运行。安装好编排台后，还需要接入你自己的 ComfyUI、Ollama、语音服务或 OpenAI 兼容 API。各工作流与语音服务的权重下载地址见 [模型相关资源](/models)。

## 安装方式

三种方式选一种即可：

| 场景 | 推荐方式 |
| --- | --- |
| Windows 桌面使用，不想装 Python/Docker | [Windows 安装包](#windows-installer) |
| 服务器长期运行、局域网共享 | [Docker 部署](#docker) |
| 改代码、调试、参与开发 | [源码运行](#source) |

### Windows 安装包 {#windows-installer}

从 [GitHub Releases](https://github.com/liberalchang/LiberAstra/releases/latest) 下载 `LiberAstra-Setup.exe`（Windows 10/11 x64）。

1. 运行安装包，按向导完成安装。默认装到 `C:\Program Files\LiberAstra`，安装程序会放行本机防火墙的 TCP 8000。
2. 从开始菜单或桌面启动 `LiberAstra`。启动器常驻托盘，服务就绪后自动打开 `http://127.0.0.1:8000`。
3. 首次进入创建管理员，然后在「设置 → 服务提供方」里添加实际执行推理的服务。

| 项目 | 位置 / 操作 |
| --- | --- |
| 程序目录 | `C:\Program Files\LiberAstra` |
| 数据目录 | `%LOCALAPPDATA%\LiberAstra\data` |
| 日志 | `%LOCALAPPDATA%\LiberAstra\logs` |
| 系统日志 | 右键托盘中的 LiberAstra 图标 → 系统日志 |
| 退出 | 右键托盘中的 LiberAstra 图标 → 退出 |
| 卸载 | Windows 设置 → 应用 → LiberAstra；卸载不会删除数据目录 |

命令行在安装目录执行 `astra.cmd`，或 `runtime\python.exe -m liberastra.cli.main`；把安装目录加入 PATH 后可直接用 `astra`。网页出帧优先使用系统 Microsoft Edge/Chrome；系统没有 Edge 时先安装 Edge。

### Docker 部署 {#docker}

在仓库根目录：

```bash
cp .env.example .env
docker compose up --build -d
```

默认访问 `http://localhost:8000`，数据保存在 `./data`。首次进入会引导创建管理员账号，然后在「设置 → 服务提供方」里添加实际执行推理的服务。

如果宿主机 8000 端口已被占用，在 `.env` 中设置：

```bash
LIBERASTRA_PUBLISH_PORT=18000
```

访问 `http://<主机>:18000`；容器内部仍监听 8000。

构建默认通过清华 PyPI 安装 Python 依赖。需要换源或换基础镜像 registry 时，在 `.env` 设置 `LIBERASTRA_PIP_INDEX_URL`、`LIBERASTRA_PYTHON_IMAGE`、`LIBERASTRA_NODE_IMAGE` 后重新构建。

### 源码运行 {#source}

```bash
cd backend && uv venv .venv && uv pip install -e ".[dev]"
cd ../frontend && npm install && npm run build
cd ../backend && uv run astra serve
```

开发模式：后端 `uv run astra serve --reload`，前端 `npm run dev`（5173，代理 `/api` 到 8000）。

## Docker 进阶

### 常用环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LIBERASTRA_SECRET_KEY` | 自动生成到 `data/.secret_key` | JWT 签名与密钥加密主密钥，生产必须显式设置；迁移数据时一并迁移 |
| `LIBERASTRA_DATABASE_URL` | SQLite `data/liberastra.db` | PostgreSQL：`postgresql+psycopg://...`，需安装 `liberastra[postgres]` |
| `LIBERASTRA_DATA_DIR` | `./data`（容器内 `/data`） | outputs / uploads / voices / workflows / prompts / logs |
| `LIBERASTRA_PUBLISH_PORT` | `8000` | 宿主机映射端口 |
| `LIBERASTRA_HOST` / `LIBERASTRA_PORT` | `0.0.0.0` / `8000` | 容器或进程监听地址 |
| `LIBERASTRA_CLEANUP_RETENTION_DAYS` | `0`（关闭） | 已结束任务与产物的保留天数 |

优先级：环境变量 > `.env` > 默认值。完整示例见仓库根目录的 `.env.example`。

### 可选的全栈 profile

如果想把 Ollama、ComfyUI、PostgreSQL 或语音服务也放在同一台机器上：

```bash
docker compose --profile ollama up -d
docker compose --profile comfyui up -d
docker compose --profile postgres up -d
docker compose --profile speech up -d
docker compose --profile depth up -d
```

ComfyUI / 语音 / 深度服务需要 NVIDIA Container Toolkit。更推荐把推理服务放到显卡主机，应用主机只跑 LiberAstra。

### 分置部署

适用场景：应用主机只跑 Web/API 与 `data/`，显卡主机分别跑 Ollama、ComfyUI、Liber Speech，通过局域网互联。

```text
应用主机 LiberAstra :18000  ──LAN──▶  显卡主机 Ollama :11434
                                      ComfyUI :8188
                                      Liber Speech :5555
```

在「服务提供方」中填写显卡主机的局域网 IP：

| 名称 | 类型 | Base URL |
| --- | --- | --- |
| comfy | ComfyUI | `http://<显卡主机>:8188` |
| ollama | Ollama | `http://<显卡主机>:11434` |
| speech | Liber Speech API | `http://<显卡主机>:5555` |

访问同一台宿主机上的服务用 `host.docker.internal`；访问另一台机器用对方局域网 IP，不要用 `localhost`。

#### 迁移已有数据

1. 旧实例停止写入，避免 SQLite 出现半截写入。
2. 打包整个数据目录，保留 `.secret_key`、数据库、outputs、uploads、voices、workflows、prompts。
3. 解压到新机器仓库根目录的 `data/`，与 compose 的 `./data:/data` 对齐。
4. 启动后登录原管理员账号，检查 Provider 地址并试跑一个任务。

不要把 `data/` 放在网盘同步目录里。

## 数据与运维

### 数据目录

后端从 `backend` 启动时：

| 内容 | 路径 |
|------|------|
| 数据库 | `backend/data/liberastra.db` |
| 生成物 | `backend/data/outputs/` |
| 上传 | `backend/data/uploads/` |
| 用户工作流包 | `backend/data/workflows/` |
| 用户模板 | `backend/data/templates/` |
| 提示词模板 | `backend/data/prompts/` |
| 音乐库 | `backend/data/bgm/` |
| 角色图片 | `backend/data/characters/` |
| 插件状态 | `backend/data/plugins.json` |
| 插件模型 | `backend/data/plugins/speech/models`、`backend/data/plugins/depth/models` |
| 插件共用环境 | `%LOCALAPPDATA%\LiberAstra\plugin-runtime`（安装包则在数据目录的 `plugins\runtime`） |

画布的节点图和每次执行记录写在数据库里，没有单独的画布目录。节点产物在 `outputs/`，未「保存到资源库」时资产列表默认不显示。

Windows 安装包的数据目录不是程序目录，而是 `%LOCALAPPDATA%\LiberAstra\data`。上表里的 `backend/data` 换成这个目录。插件模型同样在其中的 `plugins\speech\models` 与 `plugins\depth\models`。

`backend/data` 不要放进网盘/同步目录，否则可能锁库报 `disk I/O error`。

### 运维

- 健康检查：`GET /healthz`
- 日志：`data/logs/app.log`（50MB 轮转 × 5）；Windows 安装包的启动器日志在 `%LOCALAPPDATA%\LiberAstra\logs\server.log`
- 备份：`GET /api/v1/system/backup`（管理员，zip 导出数据目录，不含日志）
- 容器日志：`docker compose logs -f --tail 100`
- 停止：`docker compose down`（不会删除 `./data`）；Windows 安装包右键托盘图标 → 退出

## 下一步

- [快速开始](/quickstart)
- [模型相关资源](/models)
