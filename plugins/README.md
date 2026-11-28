# LiberAstra Plugins

本目录存放面向外部编排框架 / Agent 宿主的独立扩展插件（与仓库根目录下的 [`skills/`](../skills/README.md) 同级）。

| 插件目录 | 包名 | 宿主 | 说明 |
| --- | --- | --- | --- |
| [`comfy-provider-plus`](./comfy-provider-plus/) | `@openclaw/comfy-provider-plus` | OpenClaw | 基于官方 `@openclaw/comfy-provider` 二次开发的 ComfyUI 图像插件（插件 id：`comfy-plus`），支持 Qwen-Image 2.1 文生图、1–16 张多图参考与提示词槽位规范化，并预留调色/换姿评估门禁 |

## 开发约定

- 仓库 `backend/workflows/` 中的工作流包属于 LiberAstra 专用变体（`manifest.yaml` + 运行时图改写），仅作为节点拓扑与模型配对参考，**不能直接拷贝到 OpenClaw / 原生 ComfyUI 使用**。
- 严禁提交包含密钥、令牌或本机绝对路径的运行配置文件。
