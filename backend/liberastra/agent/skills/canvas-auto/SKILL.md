---
name: canvas-auto
description: 自动搭画布：节点种类、变量名、绑定、提示词写法和先预检再执行的约定。Use when the user asks to build or restructure a LiberAstra canvas, connect nodes, bind inputs, or turn a creative goal into a node graph.
license: MIT
compatibility: 需要 LiberAstra 画布读写工具；生成与删除操作会经过安全路由确认。
metadata:
  author: LiberAstra
  version: "2.3"
allowed-tools: ask_user list_canvas_menu list_workflows list_execution_specs canvas_get_graph canvas_get_node canvas_get_node_schema canvas_add_node canvas_update_node canvas_connect canvas_disconnect canvas_set_binding canvas_layout canvas_delete_nodes canvas_discard_nodes canvas_run_nodes
---

# 自动画布

## 核心流程

1. `canvas_get_graph` 看现状，确认已有节点、变量名和连线。
2. 需要功能入口时 `list_canvas_menu`，看用户菜单里启用项、可用目标和默认目标；需要工作流槽位时 `list_workflows`。
3. 功能节点先保持空白创建：`canvas_add_node` 的 `kind=function`，不要传 `pack`、`outputKind` 或 `menu`。
4. 优先用 `canvas_apply_menu` 套用功能菜单项（例如 `preset_t2i`、`preset_i2i`），它会自动解析到已启用的工作流或支持模型。**功能在创建时确定**：`canvas_apply_menu` 只用于没有 `presetId`、没有 `pack/target` 的空白节点做首次绑定；已有功能的节点不能再换功能，需要换功能时新建节点。已经有上游节点时，把槽位→变量名写进 `bindings`；工具会自动补上游连线，并返回 `created_edges` / `missing_bindings`。`bindings` 只选槽，不能替代连线。
5. 没有合适功能菜单时，再用 `list_workflows` 找包名，并用 `canvas_apply_pack` 绑定工作流；这样创建的是没有 `presetId` 的通用节点。仍没有目标时问用户，不要猜一个包。已有功能节点只能在当前功能允许的目标里换工作流/模型，不能借 `canvas_apply_pack` 跨功能。
6. 套好目标后先用 `canvas_get_node_schema` 读输入槽、参数规格和完整 `values`，再 `canvas_update_node` 写 prompt、变量名、`bindings` 和整份 `values`，然后 `canvas_connect`。
7. 生成前说明会跑哪些节点，等用户确认后 `canvas_run_nodes`。

**执行规则：**

- `canvas_run_nodes` 的 `node_ids` 只传当前要执行的节点，不要传上游；上游按指纹复用。
- 默认执行当前节点；只有用户明确要求强制时才传 `force=true`。确认卡会让用户再选择“执行当前节点”或“强制执行含上游”。
- 执行前保存画布；预检不过的节点会红框标出，先修配置再跑。

**按需读取：**

- 新增/修改节点、连线、绑定前，读 `references/canvas-schema.md`。
- 需要现成结构时，读 `references/recipes.md`。

## 变量名

- 输入：`input_image_1`、`input_text_script`、`input_character_hero`
- 功能：`output_image_1`、`output_video_1`
- 拼接：`output_image_storyboard_1`

变量名是画布级命名空间，不能重复。新增节点时自动分配，改名前先确认不冲突。

## 提示词

- 文本变量用 `{{变量名}}` 引用，提交时会替换成文本输入的内容。
- 图片引用写成 `<Picture 1>`、`<Picture 2>`，与槽位顺序一致。
- 引用角色时说明「保持同一人物，五官、发型、服装一致」。

## 语音节点（speech）

语音模式在创建时确定，已有语音节点不能改 `mode`。建节点用 `canvas_add_node(kind="speech", data={mode:"tts|asr|vc"})`；需要参数时先 `canvas_get_node_schema` 读完整 data，再整份写回 `ttsTuning`/`asrTuning`/`vcTuning`。

- **TTS**：`text` 支持 `{{变量名}}`；音色库写 `voiceRecordId`，服务原生音色写 `voice`/`model`，Comfy 写 `workflow`。通用字段 `providerId`、`language`、`format`。
  - `ttsTuning`：`{advanced, linked, expressiveness, speed, exaggeration, cfgWeight}`。`linked=true` 时用 `expressiveness` 同时插值语速/语气/节奏；`advanced=false` 使用服务默认值。
  - Turbo/Nano 只支持 `speed`；需要语气或节奏时换多语言/标准模型。
- **ASR**：上游必须接音频或视频；写 `language` 和 `format`（空=自动）。
  - `asrTuning`：`{advanced, timestamps, task, vad, beamSize, bestOf, temperature, noSpeechThreshold, compressionRatioThreshold, conditionOnPreviousText, initialPrompt, hotwords, qwenBatchSize, extraJson}`。
  - `timestamps=none|segment|word`；`task=transcribe|translate`。Qwen3-ASR 不支持 VAD、beam、热词、初始提示词和翻译。
- **VC**：上游接音频或视频；`voiceRecordId` 必填且音色要有参考音频。通用字段 `providerId`、`model`、`separateBgm`、`subtitleAssetId`、`burnSubtitles`、`subtitleSize`、`subtitleColor`、`format`。
  - `vcTuning`：`{advanced, convertAll, segmentPadding, mergeGap, minSegment, normalizeLoudness, targetLufs, denoise, outputSampleRate, refStart, refDuration, seed, diffusionSteps, inferenceCfgRate, nQuantizers, temperature, lengthAdjust, overlapFrameLen, maxWindow, context, fade, refMaxLen, extraJson}`。
  - `convertAll=true` 时整段替换，不再依赖分段。Chatterbox 只用参考音频前 10 秒；Seed-VC 支持 `seed`、`diffusionSteps` 等参数，参考默认最多 25 秒。
- 只有 Liber Speech 支持高级参数；其他 TTS/ASR 服务只写通用字段。上传 srt 属于属性面板的人工操作；Agent 只能复用已有 subtitle 资产，不要伪造 `assetId`。

## Gotchas

- 不要用同一个变量名重复建节点；工具会复用或拒绝，先看返回值。
- 不要直接给功能节点写 `pack` 或 `outputKind`，必须走 `canvas_apply_menu` / `canvas_apply_pack`，否则会绕过功能菜单和自动补建输入。
- 已有 `presetId` 的节点不能再用 `canvas_apply_menu` 换成另一个功能；要换功能就新建节点。`canvas_update_node` 也不能改 speech 的 `mode`。
- 没有 `presetId`、但已有 `pack` 或 `targetType/targetId` 的通用节点可以继续用 `canvas_apply_pack` 换工作流；它没有功能菜单约束，不能再套菜单。
- 执行拼接节点时只传拼接节点 id；不要为了“保险”把上游关键帧节点一起传，否则会重新提交上游任务。
- 连线被拒绝通常是自环、重复边、成环或目标节点没有输入口；先检查节点类型。
- 图片拼接节点只收同类型媒体；产物类型未知时先完成上游节点。
- 图片网格是行优先：要 2 行 N 列（每列一个分镜的首尾帧），先连全部首帧，再连全部尾帧，`columns=N`。
- 图生视频 / 图生增强目标只有一个图片槽时只接首帧；尾帧不要硬连。图生增强节点内部会优化提示词，不要再写一份增强提示词。
- `canvas_update_node` 的 `values` 是整份替换；先读完整值，改目标键后再整份写回。
- `bindings` 只决定槽位，媒体依赖仍必须连到上游；工具会自动补边，`missing_bindings` 非空时先 `canvas_connect`。自动补建的空文本输入把正文写进输入节点后再让功能节点引用 `{{变量名}}`。
- 功能节点要引用文本输入时，`prompt` 只写 `{{变量名}}`；不要把正文复制进去，否则修改文本节点不会同步。
- 换方案时先清理旧草稿：未执行、无产物的旧节点用 `canvas_discard_nodes` 删除，不必逐次确认；有执行记录或产物时用 `canvas_delete_nodes` 并确认。只清理本次被替换的节点，不要删除用户手建节点；自动补建的空输入若已无下游也一并丢弃。
- 删除节点、提交生成、运行脚本会经过安全确认；失败时向用户说明，不要靠重复建点绕过。
- 改完画布提醒用户保存；不要假设未保存的节点会持久化。
- 图片/视频/音频拼接和音频提取是内置工具节点（`kind=concat`），UI 显示为「工具」；它们不走 `canvas_apply_menu`，也不绑定工作流包。音频提取用 `data.toolId=audio_extract`，只接一个视频或音频输入，`audioMode=whole|tail` 控制完整音轨或固定长度尾音。
- 图片增强和视频增强是功能节点，走 `canvas_apply_menu` / `canvas_apply_pack`；视频增强接最终视频，默认不自动加。
- 附件标为「仅节点」时不会发给模型，消息里会给出 `asset_id`；用 `canvas_add_node(kind=input, media_kind=..., data={assetId, assetName, varName})` 或 `canvas_update_node(node_id, patch={assetId, assetName})` 把它绑到输入节点。发给模型的附件同样带 `asset_id`，也可以复用。
