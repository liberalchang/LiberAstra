# Liber Depth

把图片转成 MiDaS 深度图的独立服务，默认端口 `5556`。越亮表示越近。

## 本机插件

在 LiberAstra「资源 → 插件」里安装并启用「Liber Depth」。启用会用当前 Python 启动 `server.py`（`python -m uvicorn server:app`）。

模型不使用本机其它项目里的目录。约定路径：

- 开发：`data/plugins/depth/models`（相对后端工作目录）
- Windows 安装包：`%LOCALAPPDATA%\LiberAstra\data\plugins\depth\models`

安装时如果这个目录里没有 `.pt` / `.pth`，会自动下载 `dpt_swin2_large_384.pt`。也可以再放入 `dpt_beit_large_512.pt`。环境变量 `LIBER_DEPTH_MODELS_DIR` 可以改目录。

安装插件时会在数据目录建立单独的虚拟环境并安装依赖。有 NVIDIA 显卡时安装 CUDA 版 PyTorch，否则安装 CPU 版。主服务进程不加载这些依赖。

## 局域网显卡主机

```bash
docker compose up -d --build
```

把 `.env.example` 复制为 `.env`，把模型目录挂到 `/models`。LiberAstra「设置 → 服务提供方」新增类型 **Liber Depth API**，Base URL 填 `http://<主机IP>:5556`。

## 接口

- `GET /api/v1/health`：状态、设备、默认模型和已扫描权重。
- `GET /api/v1/models`：模型列表。
- `POST /api/v1/depth/convert`：表单字段 `image`、可选 `model`、`device`。返回 `filename`（`<原名>_depth.png`）和 `png_base64`。
- `GET /api/v1/results/{filename}`：已生成的 PNG。
