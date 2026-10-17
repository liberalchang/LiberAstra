# Third-Party Notices

LiberAstra 以重新实现为主，不直接复制以下项目的代码；仅在工作流 JSON、模板素材等复用时逐项注明。

| 项目 | 协议 | 用途 |
| --- | --- | --- |
| Pixelle-Video | Apache-2.0（保留 NOTICE） | 视频流水线设计参考；`backend/templates/` 全部 31 个分镜模板移植自其 `templates/`（已去除第三方热链图片并做本地化处理）；`backend/workflows/analysis_image_qwenvl/`、`analysis_video_qwenvl/` 的 workflow.json 移植自其 `workflows/selfhost/analyse_image.json` / `analyse_video.json` |
| Dreamifly | MIT | 图像能力设计参考（ComfyUI 工作流模板映射） |
| Liber_SpeechAPI | AGPL-3.0 | **只参考过接口形态**。语音服务是本仓库 `services/speech` 的独立实现，不包含、不打包该项目源码 |

Pixelle-Video 原始协议文本见其仓库 `LICENSE` / `NOTICE`（Copyright 2025 AIDC-AI，Apache License 2.0）。
