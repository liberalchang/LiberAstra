# 服务端工具参数

## `list_assets`

```json
{"kind": "image|video|audio|text", "include_hidden": false, "limit": 30}
```

返回资产 `id`、类型、路径和名称。隐藏资产默认不列出。

## `read_asset_text`

```json
{"asset_id": 12}
```

只读取文本资产正文，最多返回 60000 字。

## `list_workflows`

无参数。返回工作流包名称、能力、说明和输入槽。ComfyUI 生成必须使用返回的包名。

## `generate_image`

```json
{"prompt": "提示词", "provider_id": 1, "model": "", "workflow": "", "size": "1024x1024", "n": 1}
```

返回 `job_id`、`status`、`outputs`；`outputs[].asset_id` 可预览。

## `edit_image`

```json
{"prompt": "修改要求", "asset_ids": [12, 13], "provider_id": 1, "workflow": "", "size": ""}
```

`asset_ids` 是原图或参考图资产 id。

## `generate_video`

```json
{"prompt": "运动描述", "asset_ids": [12], "provider_id": 1, "workflow": "包名", "model": ""}
```

没有首帧时用文生视频包；有首帧时用图生视频包。

## `tts`

```json
{"text": "要朗读的文本", "voice": "", "provider_id": 1, "model": "", "workflow": "", "format": "mp3"}
```

## `asr`

```json
{"asset_id": 12, "language": "zh", "provider_id": 1}
```

## `create_character`

```json
{"name": "角色名", "description": "外貌与服装", "tags": ["标签"], "ref_asset_ids": [12], "provider_id": 1, "workflow": ""}
```

创建角色并生成定妆照，耗时较长。

## 选择服务商

- 不传 `provider_id` 时使用系统默认或第一个具备该能力的已启用服务商。
- 同一能力有多个服务商时，先说明默认选择，用户要求再换。
- 任务返回 `error` 时按原文转述，不要编造结果。
