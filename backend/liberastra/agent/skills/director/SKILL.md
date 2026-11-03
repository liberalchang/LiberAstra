---
name: director
description: 分步完成一条短片：主题、角色、剧本、分镜、关键帧方式、关键帧、视频方式与视频。每一步先问再确认。Use when the user wants to plan or produce a short film, storyboard, shot list, keyframes, or a multi-shot video.
license: MIT
compatibility: 需要 LiberAstra 导演台和画布工具；生成类操作会经过安全路由确认。
metadata:
  author: LiberAstra
  version: "3.1"
allowed-tools: ask_user load_skill read_skill_file list_skill_files update_session_state list_assets get_asset list_characters list_voices list_music list_canvas_menu list_workflows list_execution_specs canvas_get_graph canvas_get_node_schema canvas_add_node canvas_update_node canvas_connect canvas_disconnect canvas_apply_menu canvas_apply_pack canvas_set_binding canvas_layout canvas_delete_nodes canvas_run_nodes
---

# 导演技能

按阶段推进。每一步先用 `ask_user` 收集信息，把方案说清楚，得到用户确认后再进入下一步，并把当前步骤和已确认内容写进会话状态。第 6 步先选创作路线：分镜视频或一段视频；第 8 步按路线生成视频。

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

## 6. 选择创作路线（生成分镜图片前确认）

先 `list_canvas_menu`，读取「分镜视频」「参考图生视频」「参考图生成视频（长）」的当前配置和目标。不要自行新增或修改工作流包。

向用户说明区别，等用户选择：

- **A. 分镜视频**：每镜生成关键帧，逐镜生成视频后拼接。重点是人物、服装、场景和风格一致，允许硬切。
- **B. 一段视频**：每镜生成一张分镜参考图，拼接参考图后生成一条连续成片。重点是运动、光线和音频连续。

写入会话状态 `route`：`storyboard` 或 `single_video`。**用户确认前不要创建任何 `output_video_*` 节点。** 节点类型由路线决定，不再让用户选择「图生视频 / 参考视频」。

## 7A. 分镜视频：关键帧

1. 先解析「分镜视频」目标（默认是 `i2v_ref` 多参考图包），用 `canvas_get_node_schema` 读实际图片槽和数量上限。
2. 问用户每镜生成几张关键帧；数量不能超过目标可用参考槽，扣除角色/场景参考后至少保留 1 张技能帧。默认 1～2 张。
3. 每镜生成关键帧，变量名 `output_image_kf_<分镜>_<序号>`，关键帧不拼接。
4. 角色参考按视角分开建节点（正面、侧面、背面、面部），一个节点只输出一个视角；场景参考单独节点。这些节点会被所有分镜视频节点共享。
5. 把 `keyframe_count`、`keyframes` 写入会话状态。

功能节点先空白创建（`canvas_add_node` 的 `kind=function`，不传 `pack`/`outputKind`/`menu`），再用：

1. `list_canvas_menu` 找对应功能入口（文生图 `preset_t2i`、图生图 `preset_i2i`）。
2. `canvas_apply_menu` 套用菜单，让它解析到已启用工作流或支持模型。
3. 没有合适菜单时 `list_workflows` + `canvas_apply_pack`；仍没有目标就问用户，不要猜包。
4. 用 `canvas_get_node_schema` 读目标参数规格，写 prompt、变量名和 `bindings`。
5. `bindings` 只决定多个上游如何填槽，媒体依赖仍必须有真实连线。`canvas_apply_menu` / `canvas_apply_pack` 会自动补边；返回的 `created_edges` 应包含参考变量。`missing_bindings` 非空时先 `canvas_connect` 补线，再继续。

### 关键帧/参考图的控制与增强（可选）

默认用 `preset_t2i` / `preset_i2i`，不要给每张图都加控制节点。用户明确要求锁定姿势或构图时，先 `list_canvas_menu` 看当前可用项，再按控制图选择：

- 人物照 + 姿势图/线稿，且要保留人物身份：`preset_depth_pose`「姿势换姿」。目标通常是 PoseStudio，需要人物照和姿势图两个图片槽，分别连线；线稿保持原始画幅，不裁白边，输出画幅取姿势参考图比例，分辨率取两图较大者（长边上限 2048）。
- 只有姿势图/线稿，不需要固定人物身份：`preset_depth_gen`「姿势生图」。
- 只有深度图：`preset_depth_gen` 里的 Union Depth 目标。先从 `available_targets` 确认，再用 `canvas_apply_pack` 绑定具体包；不要把控制图当成普通首帧。
- 控制图的画幅会覆盖用户选的画幅；使用前确认，否则生成后按目标画幅补边或重新生成。
- 关键帧/参考图清晰度不足时，可加 `preset_upscale`「图片增强」。默认目标是 RealESRGAN；SeedVR2 属于生成式修复，可能改变人物细节，先向用户说明，不要默认用在一致性关键帧上。

7B 的每镜参考图也适用以上规则。

提交生成前先列出将执行的节点和数量。生成类工具会进入安全确认，不要自行绕过。

## 7B. 一段视频：分镜参考图与拼接

1. 每镜生成一张参考图，变量名 `output_image_ref_<分镜>`；不做首尾帧。
2. 读「参考图生视频」或「参考图生成视频（长）」目标的单段上限（H3 通常 15 秒 / 362 帧）。
3. 按总时长内部切段：不超过单段上限就一段；超过就按上限切段，60 秒默认 4 段。
4. 每段建一个图片拼接工具节点（`canvas_add_node` 的 `kind=concat`、`media_kind=image`），`layout=grid`、`columns=N`，拼接该段全部参考图，变量名 `output_image_ref_group_<段号>`；拼接图始终是一行 N 张。
5. 确认后先执行拼接节点，给用户看每段拼接图。
6. 把 `reference_images`、`segments` 写入会话状态。

## 8A. 分镜视频：逐镜生成并拼接

1. 按分镜剧本估算每镜时长：中文约 4 字/秒，英文约 2.5 词/秒，最短 3 秒。先列表给用户确认。
2. 每镜建 `output_video_<分镜>`，套用「分镜视频」目标（`i2v_ref` 参考图生视频）。
3. 用 `canvas_get_node_schema` 看实际图片槽，按连续顺序绑定：
   - `image`：本镜关键帧 1，主参考；
   - `image_2` 起：本镜其余关键帧（如果有），再往后才是角色三视图、面部、场景；
   - 不要跳过已填槽；`image_6` 空着却填 `image_7` 会让 `<Picture N>` 编号错位；
   - 同一角色的不同视角必须是不同源节点；一个源节点不能重复连到同一个目标节点；
   - 实际 `<Picture N>` 按已填槽位顺序编号，视频 prompt 必须以 `subject_definitions` 开头，逐行写清每个 `<Picture N>` 对应关键帧、角色还是场景；
   - 角色参考默认绑定，前提是目标有槽；用户要求去掉时，让画布技能断线并清掉对应 binding。
4. 检查 `created_edges` / `missing_bindings`，缺边用 `canvas_connect` 补上。
5. 逐镜执行。
6. 建「视频拼接」工具节点（`canvas_add_node` 的 `kind=concat`、`media_kind=video`），按分镜顺序依次连接所有视频节点；连接顺序就是拼接顺序。
7. 把 `videos`、`final_video_var` 写入会话状态。

## 8B. 一段视频：参考图生视频或长视频

1. 总时长不超过单段上限：建一个 `output_video_single`，套用「参考图生视频」目标，绑定该段拼接图，直接执行。
2. 总时长超过单段上限：建一个 `output_video_long`，套用「参考图生成视频（长）」目标（`minimax_h3_extender`）。
   - `clips_json` 写 `{"version":2,"generation_mode":"ref2va","motion_context":true,"clips":[...]}`；
   - 每段一个 clip，包含 prompt、duration、固定 seed；每段不超过 15 秒；
   - 段间 prompt 重复上一段结尾的动作和镜头方向，保持运动连续；
   - `ref_1..ref_N` 依次绑定各段拼接图，剩余槽位绑定角色/场景参考；每段 prompt 只引用本段对应的 `<Picture N>`；
   - 用 `full_batch` 一次执行，输出一条成片；
   - **不要**再建视频拼接节点。
3. 把 `segments`、`single_video_var` 或 `final_video_var` 写入会话状态。

## 9. 收尾

汇总关键帧/参考图、每镜视频或成片、输出变量，告诉用户怎么预览、怎么保存到资源库。节点建完后可以调用 `canvas_layout` 整理画布；整理后检查分镜视频和拼接节点的顺序，避免视频节点混进分镜图。

成片需要提升清晰度时，先问用户是否做最终增强，不要默认加：

- `preset_video_enhance`「视频增强」使用 SeedVR2，接最终视频节点，保留原 fps 和音频；耗时较长，用户确认后再建节点和执行。
- 分镜视频路线接视频拼接的输出；一段视频路线接 `single_video_var` 或 `final_video_var`。
- 增强是生成式修复，可能改变细节；已经满意的成片不要强行加。

## 推进规则

- 不要把多个步骤合并成一次长回复。
- 每次只问当前步骤真正需要的信息。
- 用户说「你决定」时，给出一个明确方案并说明理由，仍要等一句确认。
- 每步确认后调用 `update_session_state`，把 `step`、`topic`、`characters`、`script`、`shots`、`route`、`keyframes`、`reference_images`、`segments`、`videos`、`final_video_var` 写进会话状态。刷新后先读系统提示里的「当前会话状态」，从中断处继续，不要重做已完成步骤。

## Gotchas

- 文本输入节点被下游引用时，用 `{{变量名}}`；不要写成裸变量名。
- 功能节点先建空白，再套功能菜单/工作流；不要直接写 `pack` 或 `outputKind`。
- 执行单个节点时只传该节点 id，不要传上游；否则会把上游重新提交一遍。
- 画布变量名是全局命名空间，新增节点前先看是否重名。
- 删除节点、提交生成、运行脚本等高风险操作会被安全路由暂停；向用户说明将执行什么，不要重复创建节点来绕过失败。
- 预检失败时先修节点配置，不要直接强行执行。
- 不要在没有用户确认的情况下连续生成大量关键帧或视频。
- 创建视频节点前必须先让用户选「分镜视频」还是「一段视频」；用户确认前不要建任何 `output_video_*` 节点。
- 分镜视频每镜一个 `i2v_ref` 视频节点，关键帧不拼接；共享角色/场景参考用独立源节点，一个源节点不能重复连到同一个视频节点。
- `<Picture N>` 按实际已填槽位顺序编号；连续填槽，删掉参考后重新计算后面的编号。
- 一段视频不超过单段上限时用「参考图生视频」；超过时用「参考图生成视频（长）」，不要拆成多个独立视频再拼接。
- 长视频 `clips_json` 每段不超过 15 秒；60 秒默认 4 段；`motion_context=true`；段间 prompt 重复上一段结尾的动作和镜头方向。
- 角色参考默认绑定，前提是目标有额外图片槽；用户要求去掉时，让画布技能断线并清掉对应 binding。
- 关键帧数量受目标参考槽限制，不要生成目标用不上的关键帧。
- 可以自动整理画布；整理后检查分镜视频和拼接节点的顺序，避免视频节点混进分镜图。
- 改 `values` 前先 `canvas_get_node_schema` 读完整值，整份写回，不要只传要改的键。
- `bindings` 只决定槽位，不替代上游依赖；套用菜单或 `canvas_set_binding` 后检查 `created_edges` / `missing_bindings`，缺边用 `canvas_connect` 补上，否则预检会报“不是上游节点”。
- 长视频每个 clip 的 prompt 只引用本段对应的 `<Picture N>`，不要把所有参考图都写进同一段。
- 图片/视频拼接是画布内置工具节点（`kind=concat`），不是功能菜单项；不要对拼接节点调用 `canvas_apply_menu`。UI 里的「工具」「拼接」和内部 `concat` 指同一类节点。
- `preset_depth_pose` 需要人物照 + 姿势图两个图片槽，只有一个姿势图时改用 `preset_depth_gen`；`preset_depth_gen` 默认可能解析到姿势生图，要 Union Depth 时先看 `available_targets`，再用 `canvas_apply_pack` 绑具体包。
- 线稿保持原始画幅，不裁白边；姿势换姿按姿势参考图比例、两图较大边长生成（长边上限 2048），姿势生图跟姿势参考图原尺寸。用之前先确认，避免成片画幅和主题设定不一致。
- 图片增强和视频增强是可选步骤，必须用户确认后再加；SeedVR2 会生成式改变细节，视频增强还更耗时。
