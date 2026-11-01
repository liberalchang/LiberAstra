---
name: liberastra
description: 不动画布，直接用服务端工具出图、出视频、配音和转写；结果显示在对话里。Use when the user wants a quick image, video, speech, transcription, or character generation without building a canvas.
license: MIT
compatibility: 需要已配置的图像、视频或语音服务商；生成类操作会经过安全路由确认。
metadata:
  author: LiberAstra
  version: "2.0"
allowed-tools: list_assets read_asset_text list_workflows list_characters generate_image edit_image generate_video tts asr create_character
---

# LiberAstra 服务端创作

这个技能不修改画布。适合用户只想快速出一张图、一段视频、一段语音，或把音频转成文字。

**按需读取：**

- 调用生成工具前，读 `references/tool-parameters.md` 确认必填参数和返回结构。
- 任务失败或超时时，读 `references/error-recovery.md`。

## 出图

调用 `generate_image`：

- 必填 `prompt`
- 可选 `provider_id`、`model`、`workflow`、`size`、`n`
- 使用 ComfyUI 时必须给 `workflow`（先 `list_workflows` 查可用的包）
- 调用前说明将使用哪个服务商、模型和工作流，等用户确认

结果返回 `job_id`、`status`、`outputs`。`outputs` 里的 `asset_id` 可以在消息里预览。

## 改图

调用 `edit_image`：

- 必填 `prompt` 和 `asset_ids`（图片资产 id，先用 `list_assets` 查）
- 使用 ComfyUI 时同样需要 `workflow`
- 先说明会改哪张图、用什么风格

## 出视频

调用 `generate_video`：

- 必填 `prompt`、`workflow`
- `asset_ids` 放首帧图片；没有首帧时用文生视频包
- 说明预计时长和分辨率

## 配音与转写

- `tts`：必填 `text`；可选 `voice`、`model`、`workflow`、`format`。
- `asr`：必填 `asset_id`（音频资产）；可选 `language`。

## 规则

- 所有生成类工具调用前都要向用户说明将占用 GPU；安全路由会暂停等待确认。
- 任务失败时把 `error` 原样转述，并建议换模型、换工作流或检查服务商配置。
- 不要把服务端生成和画布节点混在一起说，除非用户要求把结果继续做进画布。
- 生成完成后告诉用户结果在消息里可以直接点开预览，也可以去任务中心查看。

## Gotchas

- 没配置对应能力的服务商时，先提示用户去服务商设置，不要反复重试。
- ComfyUI 工作流名必须与 `list_workflows` 返回的一致。
- `asset_ids` 是资源库资产 id，不是文件路径。
- 不要伪造 `job_id` 或生成结果；任务状态以工具返回为准。
