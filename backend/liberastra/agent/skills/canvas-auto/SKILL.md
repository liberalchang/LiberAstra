---
name: canvas-auto
description: 自动搭画布：节点种类、变量名、绑定、提示词写法和先预检再执行的约定。Use when the user asks to build or restructure a LiberAstra canvas, connect nodes, bind inputs, or turn a creative goal into a node graph.
license: MIT
compatibility: 需要 LiberAstra 画布读写工具；生成与删除操作会经过安全路由确认。
metadata:
  author: LiberAstra
  version: "2.1"
allowed-tools: ask_user list_canvas_menu list_workflows list_execution_specs canvas_get_graph canvas_get_node canvas_get_node_schema canvas_add_node canvas_update_node canvas_connect canvas_disconnect canvas_set_binding canvas_layout canvas_delete_nodes canvas_run_nodes
---

# 自动画布

## 核心流程

1. `canvas_get_graph` 看现状，确认已有节点、变量名和连线。
2. 需要功能入口时 `list_canvas_menu`，看用户菜单里启用项、可用目标和默认目标；需要工作流槽位时 `list_workflows`。
3. 功能节点先保持空白创建：`canvas_add_node` 的 `kind=function`，不要传 `pack`、`outputKind` 或 `menu`。
4. 优先用 `canvas_apply_menu` 套用功能菜单项（例如 `preset_t2i`、`preset_i2i`），它会自动解析到已启用的工作流或支持模型。已经有上游节点时，把槽位→变量名写进 `bindings`，避免自动补建空输入节点。
5. 没有合适功能菜单时，再用 `list_workflows` 找包名，并用 `canvas_apply_pack` 绑定工作流。仍没有目标时问用户，不要猜一个包。
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
- 合成：`output_image_storyboard_1`

变量名是画布级命名空间，不能重复。新增节点时自动分配，改名前先确认不冲突。

## 提示词

- 文本变量用 `{{变量名}}` 引用，提交时会替换成文本输入的内容。
- 图片引用写成 `<Picture 1>`、`<Picture 2>`，与槽位顺序一致。
- 引用角色时说明「保持同一人物，五官、发型、服装一致」。

## Gotchas

- 不要用同一个变量名重复建节点；工具会复用或拒绝，先看返回值。
- 不要直接给功能节点写 `pack` 或 `outputKind`，必须走 `canvas_apply_menu` / `canvas_apply_pack`，否则会绕过功能菜单和自动补建输入。
- 执行合成节点时只传合成节点 id；不要为了“保险”把上游关键帧节点一起传，否则会重新提交上游任务。
- 连线被拒绝通常是自环、重复边、成环或目标节点没有输入口；先检查节点类型。
- 图片合成节点只收同类型媒体；产物类型未知时先完成上游节点。
- 图片网格是行优先：要 2 行 N 列（每列一个分镜的首尾帧），先连全部首帧，再连全部尾帧，`columns=N`。
- 图生视频 / 图生增强目标只有一个图片槽时只接首帧；尾帧不要硬连。图生增强节点内部会优化提示词，不要再写一份增强提示词。
- `canvas_update_node` 的 `values` 是整份替换；先读完整值，改目标键后再整份写回。
- 套用菜单时优先用 `bindings` 绑定已有上游，避免自动补建空输入节点；自动补建的空文本输入把正文写进输入节点后再让功能节点引用 `{{变量名}}`。
- 功能节点要引用文本输入时，`prompt` 只写 `{{变量名}}`；不要把正文复制进去，否则修改文本节点不会同步。
- 删除节点、提交生成、运行脚本会经过安全确认；失败时向用户说明，不要靠重复建点绕过。
- 改完画布提醒用户保存；不要假设未保存的节点会持久化。
