---
title: 安装 / 下载
---

# 安装 / 下载

本页为安装与部署的简版指引；更完整的部署说明请参考仓库文档：

- `docs/deployment.md`
- `docs/deployment.en.md`
- `docs/分置部署教程.md`

## Docker（推荐）

在仓库根目录运行：

```bash
docker compose up -d --build
```

随后访问 `http://localhost:8000`，首次进入请创建管理员账户，并在「设置 → 服务提供方（Providers）」中配置你的 ComfyUI / Ollama / 语音服务地址。

提示：LiberAstra 不运行模型，模型实际运行在上述服务中。

## Windows 安装包

- 访问 Releases 下载：`https://github.com/liberalchang/LiberAstra/releases`

## 分置部署

若前后端 / 服务需要分置部署，请参考 `docs/分置部署教程.md`，该文档包含端口、反向代理与多节点的注意事项。
