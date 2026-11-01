---
name: director
description: 分步完成一条短片：主题、角色、剧本、分镜、关键帧方式、关键帧、视频方式与视频。每一步先问再确认。Use when the user wants to plan or produce a short film, storyboard, shot list, keyframes, or a multi-shot video.
license: MIT
compatibility: 需要 LiberAstra 导演台和画布工具；生成类操作会经过安全路由确认。
metadata:
  author: LiberAstra
  version: "3.0"
allowed-tools: ask_user load_skill read_skill_file list_skill_files update_session_state list_assets get_asset list_characters list_voices list_music list_canvas_menu list_workflows list_execution_specs canvas_get_graph canvas_get_node_schema canvas_add_node canvas_update_node canvas_connect canvas_set_binding canvas_layout canvas_delete_nodes canvas_run_nodes
---

# 导演技能

按阶段推进。每一步先用 `ask_user` 收集信息，把方案说清楚，得到用户确认后再进入下一步，并把当前步骤和已确认内容写进会话状态。第 9 步分两条路：9A 图生视频 / 图生增强，9B 参考图。

**按需读取：**

- 写分镜提示词或关键帧提示词前，读 `references/shot-prompt-template.md`。
- 每步确认后更新状态前，读 `references/state-schema.md`。

## 1. 主题

问清：

- 想讲什么（一句话）
- 成片用途和平台（短视频、广告、故事片段）
- 画面风格（写实、动画、胶片、赛博等）
- 画幅比例和大致时长

确认后，把主题整理成 3–5 句创作说明。

## 2. 角色设计

先 `list_characters` 看角色库，给出三种路径：

1. 复用已有角色（推荐）
2. 用文生图/图生图创建新角色
3. 用画布「角色输入」节点引用角色库

需要新角色时，先问清外貌、服装、气质、年龄段，再生成正面、侧面、背面三视图，保持同一人物。确认角色形象后再继续。

## 3. 剧本内容

根据主题写分场剧本。每场包含：场景、发生什么、人物动作、情绪、镜头意图。

- 先给 3–5 个版本的一句话梗概让用户选，再展开。
- 剧本确认后，在画布上新建「文本输入」节点保存正文，变量名如 `input_text_script`。

## 4. 分镜数量

根据时长和节奏建议分镜数（通常 4–8 个）。问用户是否采用，允许调整。确认后列出每个分镜的一句话内容。

## 5. 分镜提示词

为每个分镜写完整提示词。读取 `references/shot-prompt-template.md`，按模板固定包含：

1. 主题与场景限制
2. 角色图引用和人物一致性说明
3. 镜头说明：场景、内容、景别、光影、镜头语言、动作、材质、风格
4. 视频运动约束和不要出现的元素

先把全部提示词列出来给用户过目，再写入画布节点。

## 6. 关键帧生成方式与提示词

在生成分镜图片前先问用户：

- **只生成首帧**：每个分镜 1 张。图生视频 / 图生增强只用首帧；参考图模式合成图只有一行。
- **生成首尾帧**：每个分镜 2 张（首帧 + 尾帧）。当前图生视频 / 图生增强仍只接首帧，尾帧用于参考图合成，不接入这两个节点。

按选择自动适配关键帧提示词：

- 首帧：分镜提示词 + `[首帧]` 开场画面、动作起点、构图。
- 尾帧：分镜提示词 + `[尾帧]` 收束画面、动作终点、与首帧的衔接。
- 只生成首帧时不要生成尾帧提示词。

详细写法见 `references/shot-prompt-template.md`。把模式写进会话状态 `keyframe_mode`：`first` 或 `first_last`。

## 7. 生成关键帧图片

用画布节点搭：

- 文生图节点（无角色参考）或图生图节点（引用角色输入节点）
- 首帧模式每镜一个功能节点，变量名 `output_image_kf_<分镜>_1`
- 首尾帧模式每镜两个功能节点，变量名 `output_image_kf_<分镜>_1`、`output_image_kf_<分镜>_2`

功能节点先空白创建（`canvas_add_node` 的 `kind=function`，不传 `pack`/`outputKind`/`menu`），再用：

1. `list_canvas_menu` 找对应功能入口（文生图 `preset_t2i`、图生图 `preset_i2i`）。
2. `canvas_apply_menu` 套用菜单，让它解析到已启用工作流或支持模型。
3. 没有合适菜单时 `list_workflows` + `canvas_apply_pack`；仍没有目标就问用户，不要猜包。
4. 用 `canvas_get_node_schema` 读目标参数规格，写 prompt、变量名和 `bindings`。
5. `bindings` 只决定多个上游如何填槽，媒体依赖仍必须有真实连线。`canvas_apply_menu` / `canvas_apply_pack` 会自动补边；返回的 `created_edges` 应包含参考变量。`missing_bindings` 非空时先 `canvas_connect` 补线，再继续。

提交生成前先列出将执行的节点和数量。生成类工具会进入安全确认，不要自行绕过。

## 8. 选择视频生成方式

先 `list_canvas_menu`，找到「图生视频」「图生增强」「参考视频」菜单项，确认：

- 菜单项是否启用；
- 目标有几个图片槽；
- 默认工作流是否可用；
- 参考视频目标的最大时长。

向用户报告当前配置，然后问：

- **A. 图生视频 / 图生增强**：当前目标只有一个图片槽时只用首帧；尾帧图片保留但不接入。
- **B. 参考图**：多个分镜合成一张参考图，用参考视频节点生成。

把选择写进 `video.mode`。

## 9A. 图生视频 / 图生增强

1. 问用户用图生视频还是图生增强。
2. 图生增强节点内部已有 LLM 优化：只写正常的视频运动提示词，不要另写“增强提示词”，也不要设置 `promptOptimized`。
3. 按分镜剧本估算时长：中文约 4 字/秒，英文约 2.5 词/秒，最短 3 秒。先列表给用户确认。
4. 读目标规格：本地包常用 `length` 帧数，按 `fps`、`min`、`max`、`align_base`、`align_offset` 对齐；云端模型常用 `duration` 秒。不要写死参数名。
5. 建 `output_video_<分镜>`：
   - 套用菜单时把首帧变量写进 `canvas_apply_menu` 的 `bindings`（键名以目标 inputs 为准，通常是 `image` 或 `first_frame`），并把视频提示词写进 `data.prompt`；工具会自动补上游连线，检查返回的 `created_edges` / `missing_bindings`；
   - 目标只有一个图片槽：只绑首帧，尾帧不连；如果用户之前选了首尾帧，明确告诉用户尾帧不会用于这条视频，只保留在画布上；
   - 目标有两个图片槽：才绑首帧 + 尾帧，`bindings` 里同时给 `first_frame`/`last_frame`；
   - 先 `canvas_get_node_schema` 读完整 `values`，改时长后再整份写回。
6. 列出节点和时长，确认后逐段执行。
7. 可选最后加「视频合成」节点，把各分镜视频按顺序拼成一条。
8. 把 `video.variant`、`video.shot_durations` 和视频节点写入会话状态。

## 9B. 参考图

1. 读取参考视频目标的最大时长。问每张合成图放几个分镜，默认 3；总时长必须不超过目标上限，超了就减少每组数量或拆更多组。
2. 按关键帧方式建合成图：
   - 只生成首帧：一行 N 张，第 N 张对应第 N 个分镜；按分镜顺序连线。
   - 首尾帧：2 行 N 列，第一行是各分镜首帧，第二行是尾帧；先连该组全部首帧，再连全部尾帧，`columns=N`。每列上下两张属于同一个分镜。
3. 每组一个图片合成节点，`layout=grid`，`columns=N`，默认间隔 4px、白色；变量名 `output_image_storyboard_group_<组号>`。
4. 确认后只执行合成节点，给用户看合成图。
5. **询问用户是否继续创建视频节点**。
6. 每组建 `input_text_group_<组号>`，内容是：
   - 合成图布局说明：首帧模式写“一行 N 张，第 i 张对应分镜 i”；首尾帧模式写“2 行 N 列，第 i 列对应分镜 i，上方首帧、下方尾帧”；
   - 该组各分镜的剧本内容；
   - 该组总时长。
7. 建 `output_video_group_<组号>`，套参考视频菜单时同时传：
   - `bindings: {image: 合成图变量}`（槽名以目标 inputs 为准）；
   - `data.prompt: "{{input_text_group_<组号>}}"`，引用组文本，不要内联复制正文；
   - 时长设为该组总秒数并按目标规格对齐。
   套用后确认 `created_edges` 包含合成图变量；缺边用 `canvas_connect` 补上。
8. 确认后逐段执行；可选最后加视频合成节点。
9. 把 `video.shots_per_composite` 和 `video.groups` 写入会话状态。

## 10. 收尾

汇总每段视频、合成图和输出变量，告诉用户怎么预览、怎么保存到资源库。**不要自动整理画布**；按分镜组把节点放在关键帧右侧，避免视频节点混进分镜图。

## 推进规则

- 不要把多个步骤合并成一次长回复。
- 每次只问当前步骤真正需要的信息。
- 用户说「你决定」时，给出一个明确方案并说明理由，仍要等一句确认。
- 每步确认后调用 `update_session_state`，把 `step`、`topic`、`characters`、`script`、`shots`、`keyframes`、`keyframe_mode`、`video` 写进会话状态。刷新后先读系统提示里的「当前会话状态」，从中断处继续，不要重做已完成步骤。

## Gotchas

- 文本输入节点被下游引用时，用 `{{变量名}}`；不要写成裸变量名。
- 功能节点先建空白，再套功能菜单/工作流；不要直接写 `pack` 或 `outputKind`。
- 执行单个节点时只传该节点 id，不要传上游；否则会把上游重新提交一遍。
- 画布变量名是全局命名空间，新增节点前先看是否重名。
- 删除节点、提交生成、运行脚本等高风险操作会被安全路由暂停；向用户说明将执行什么，不要重复创建节点来绕过失败。
- 预检失败时先修节点配置，不要直接强行执行。
- 不要在没有用户确认的情况下连续生成大量关键帧或视频。
- 当前图生视频 / 图生增强工作流只接首帧时，不要连接尾帧；目标 `media_slots` 有两个图片槽才接首尾。
- 图生增强内部会优化提示词，不要再写一份增强提示词，也不要设置 `promptOptimized`。
- 参考图首帧模式只有一行，第 i 张对应分镜 i；首尾帧模式才是 2 行 N 列，先连首帧再连尾帧。
- 不要自动整理画布；整理会按依赖分层，视频节点可能混进分镜图。
- 改 `values` 前先 `canvas_get_node_schema` 读完整值，整份写回，不要只传要改的键。
- `bindings` 只决定槽位，不替代上游依赖；套用菜单或 `canvas_set_binding` 后检查 `created_edges` / `missing_bindings`，缺边用 `canvas_connect` 补上，否则预检会报“不是上游节点”。
- 参考图模式的视频节点 `prompt` 必须用 `{{input_text_group_<组号>}}` 引用组文本，不要把正文内联复制；否则改组文本不会生效。
