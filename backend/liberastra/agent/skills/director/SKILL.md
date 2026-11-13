---
name: director
description: 分步完成一条短片：主题、角色、剧本、分镜、关键帧方式、关键帧、视频方式与视频。每一步先问再确认。Use when the user wants to plan or produce a short film, storyboard, shot list, keyframes, or a multi-shot video.
license: MIT
compatibility: 需要 LiberAstra 导演台和画布工具；生成类操作会经过安全路由确认。
metadata:
  author: LiberAstra
  version: "3.2"
allowed-tools: ask_user load_skill read_skill_file list_skill_files update_session_state list_assets get_asset list_characters list_voices list_music list_canvas_menu list_workflows list_execution_specs canvas_get_graph canvas_get_node_schema canvas_add_node canvas_update_node canvas_connect canvas_disconnect canvas_apply_menu canvas_apply_pack canvas_set_binding canvas_layout canvas_delete_nodes canvas_discard_nodes canvas_run_nodes
---

# 导演技能

按阶段推进。每一步先用 `ask_user` 收集信息，把方案说清楚，得到用户确认后再进入下一步，并把当前步骤和已确认内容写进会话状态。第 6 步先选创作路线：分镜视频或整段参考图视频；分镜视频再选逐镜拼接或连续时间线。第 8 步按路线和模式生成视频。

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

**关键帧/参考图提示词只写视觉**，不写台词、口型、字幕或声音。台词只写进视频提示词或独立的音频/TTS 节点（见「语音节点」）；不要把同一段带台词的文本直接接到文生图节点。

先把全部提示词列出来给用户过目，再写入画布节点。

## 6. 选择创作路线（生成分镜图片前确认）

先 `list_canvas_menu`，读取「参考图生视频（单段）」「连续生成（长）」的当前配置和目标；分镜视频路线 A1 复用前者。不要自行新增或修改工作流包。

先向用户说明两条创作路线，等用户选择：

- **A. 分镜视频**：每镜生成关键帧，再生成视频。选 A 后继续问分镜生成方式：
  - **A1. 逐镜拼接（默认）**：每镜一个视频，最后拼接；可单独重试，允许硬切。
  - **A2. 连续时间线**：多个分镜放进一个 Extender 时间线；适合同场景连续镜头，整条重跑，不能单独重试一镜。
- **B. 整段参考图视频**：每镜生成一张参考图，拼成整段参考，生成一条连续成片。重点是运动、光线和整段音频连续。

选 A1 后继续问音频连续性，全部用画布节点和连线表达：

- `native`：模型原生，默认，不建音频节点；
- `previous_tail`：参考上一镜尾音，问参考长度（默认 5 秒，2–15 秒）。第 1 镜原生；第 2 镜起，上一镜视频 → 音频提取节点（`audio_extract`，`tail`）→ 当前镜的 `ref_audio` 槽；
- `global_bed`：全片氛围底，问选择/上传。建一个音频输入节点，接到所有分镜的 `ref_audio` 槽。H3 把参考音频当条件，不按时间轴自动切片；需要逐镜精确对齐时要向用户说明这个限制。

接缝淡化写在视频拼接节点的 `audioFadeMs`（0–200，默认 60），不要再靠运行级音频参数。

选 A2 时确认总时长、clip 数和 `audio_context_length`（默认 0）；P1 再问可选 `ref_audio`。
选 B 时确认总时长：≤15 秒走单段 `i2v_ref`，>15 秒走 Extender；长视频问 `audio_context_length`（默认 0），P1 再问可选 `ref_audio`。

汇总路线、模式、音频方案、镜头数/段数，等用户确认后写入会话状态 `route`、`storyboard_mode`、`audio_strategy` 等字段。**用户确认前不要创建任何 `output_video_*` 节点。** 节点类型由路线和模式决定，不再让用户选择「图生视频 / 参考视频」。

## 7A. 分镜视频：关键帧

1. 先解析「参考图生视频（单段）」目标（默认是 `i2v_ref` 多参考图包），用 `canvas_get_node_schema` 读实际图片槽、数量上限和 `duration_limits`。写 `length` 前按 `duration_limits` 的 `fps`、`align_base`、`align_offset` 换算：先 `ceil(秒 × fps)`，再向上吸到 `align_base × k + align_offset`，最后夹在 min/max。H3 的 10 秒是 243 帧，不是 240 或 241。
2. 问用户每镜生成几张关键帧；数量不能超过目标可用参考槽，扣除角色/场景参考后至少保留 1 张技能帧。默认 1～2 张。
3. 每镜生成关键帧，变量名 `output_image_kf_<分镜>_<序号>`，关键帧不拼接。
4. 角色参考按视角分开建节点（正面、侧面、背面、面部），一个节点只输出一个视角；场景参考单独节点。这些节点会被所有分镜视频节点共享。
5. A2 连续时间线：每镜至少保留 1 张主关键帧；生成前计算 Extender 的 9 个图片槽预算。超预算时先减少每镜关键帧，仍不足就把同一段的多张关键帧拼成 1×N 参考图；不要重复绑定同一源节点。
6. 把 `keyframe_count`、`keyframes` 写入会话状态；A2 还要记录 `segments`（`shots`、`duration_s`、`clip_index`、`ref_vars`，用了拼接图时加 `composite_var`）。

功能节点先空白创建（`canvas_add_node` 的 `kind=function`，不传 `pack`/`outputKind`/`menu`），再用：

1. `list_canvas_menu` 找对应功能入口（文生图 `preset_t2i`、图生图 `preset_i2i`）。
2. `canvas_apply_menu` 套用菜单，让它解析到已启用工作流或支持模型。**功能在创建时确定**：这个工具只用于空白节点的首次绑定；已有 `presetId` 的节点不能换功能，要换功能就新建节点。
3. 没有合适菜单时 `list_workflows` + `canvas_apply_pack`，创建没有 `presetId` 的通用节点；仍没有目标就问用户，不要猜包。已有功能节点只能在当前功能允许的目标里换工作流，不能跨功能。
4. 用 `canvas_get_node_schema` 读目标参数规格，写 prompt、变量名和 `bindings`。`canvas_update_node` 不能改 speech 的 `mode`。
5. `bindings` 只决定多个上游如何填槽，媒体依赖仍必须有真实连线。`canvas_apply_menu` / `canvas_apply_pack` 会自动补边；返回的 `created_edges` 应包含参考变量。`missing_bindings` 非空时先 `canvas_connect` 补线，再继续。

建视频节点并套用菜单时，**apply_menu 时一并传 bindings**（槽位→变量名）；不要先套菜单再 `canvas_set_binding`，否则必填槽会被自动补建一个空输入节点。A2 的 Extender、A1 的每镜 `i2v_ref`、B 的单段视频节点都按这个顺序做。

### 关键帧/参考图的控制与增强（可选）

默认用 `preset_t2i` / `preset_i2i`，不要给每张图都加控制节点。用户明确要求锁定姿势或构图时，先 `list_canvas_menu` 看当前可用项，再按控制图选择：

- 人物照 + 姿势图/线稿，且要保留人物身份：`preset_depth_pose`「人物换姿势」。目标通常是 PoseStudio，需要人物照和姿势图两个图片槽，分别连线；线稿保持原始画幅，不裁白边，输出画幅取姿势参考图比例，分辨率取两图较大者（长边上限 2048）。
- 只有姿势图/线稿，不需要固定人物身份：`preset_depth_gen`「姿势生成人物」。
- 只有深度图：`preset_depth_gen` 里的 Union Depth 目标。先从 `available_targets` 确认，再用 `canvas_apply_pack` 绑定具体包；不要把控制图当成普通首帧。
- 控制图的画幅会覆盖用户选的画幅；使用前确认，否则生成后按目标画幅补边或重新生成。
- 关键帧/参考图清晰度不足时，可加 `preset_upscale`「图片修复放大」。默认目标是 RealESRGAN；SeedVR2 属于生成式修复，可能改变人物细节，先向用户说明，不要默认用在一致性关键帧上。

7B 的每镜参考图也适用以上规则。

提交生成前先列出将执行的节点和数量。生成类工具会进入安全确认，不要自行绕过。

## 7B. 整段参考图视频：分镜参考图与拼接

1. 每镜生成一张参考图，变量名 `output_image_ref_<分镜>`；不做首尾帧。参考图提示词只写视觉，不写台词、口型或字幕；台词留到视频提示词。
2. 读「参考图生视频（单段）」或「连续生成（长）」目标的单段上限（H3 通常 15 秒 / 362 帧）。单段 `i2v_ref` 的 `length` 按 `duration_limits` 换算，不要按 24fps 直接乘后取整。
3. 按总时长内部切段：不超过单段上限就一段；超过就按上限切段，60 秒默认 4 段。
4. 每段建一个图片拼接工具节点（`canvas_add_node` 的 `kind=concat`、`media_kind=image`），`layout=grid`、`columns=N`，拼接该段全部参考图，变量名 `output_image_ref_group_<段号>`；拼接图始终是一行 N 张。
5. 确认后先执行拼接节点，给用户看每段拼接图。
6. 把 `reference_images`、`segments` 写入会话状态。

## 8A. 分镜视频：按分镜生成方式执行

### A1 逐镜拼接

1. 按分镜剧本估算每镜时长：中文约 4 字/秒，英文约 2.5 词/秒，最短 3 秒。先列表给用户确认。
2. 每镜建 `output_video_<分镜>`，套用「参考图生视频（单段）」目标（`i2v_ref` 多参考图包）。
3. 用 `canvas_get_node_schema` 看实际图片槽，按连续顺序绑定：
   - `image`：本镜关键帧 1，主参考；
   - `image_2` 起：本镜其余关键帧（如果有），再往后才是角色三视图、面部、场景；
   - 不要跳过已填槽；`image_6` 空着却填 `image_7` 会让 `<Picture N>` 编号错位；
   - 同一角色的不同视角必须是不同源节点；一个源节点不能重复连到同一个目标节点；
   - 实际 `<Picture N>` 按已填槽位顺序编号，视频 prompt 必须以 `subject_definitions` 开头，逐行写清每个 `<Picture N>` 对应关键帧、角色还是场景；
   - 角色参考默认绑定，前提是目标有槽；用户要求去掉时，让画布技能断线并清掉对应 binding。
4. 检查 `created_edges` / `missing_bindings`，缺边用 `canvas_connect` 补上。
5. 建音频节点并连线（按第 6 步选择）：
   - `native`：不建音频节点。
   - `previous_tail`：第 1 镜不建；第 2..N 镜各建一个 `output_audio_tail_<分镜>`，用 `canvas_add_node` 的 `kind=concat`、`media_kind=audio`，`data` 写 `toolId=audio_extract`、`audioMode=tail`、`tailSeconds=<参考秒数>`。连线：上一镜 `output_video_<i-1>` → `output_audio_tail_<i>` → 当前镜 `output_video_<i>`。音频产物会自动填进当前镜的 `ref_audio` 槽。
   - `global_bed`：建一个音频输入节点（变量名 `input_audio_bed`，`assetId` 来自 `list_assets` 或用户上传），连接到所有 `output_video_<i>` 的 `ref_audio` 槽。H3 只把它当参考，不按时间轴切片。
   音频关系全部用节点和连线表达，执行顺序由连线决定。建完后用 `canvas_get_graph` 核对尾音链：上一镜视频 → 提取节点 → 当前镜视频，两段边都必须存在；缺哪段就用 `canvas_connect` 补上。
6. 建「视频拼接」工具节点（`canvas_add_node` 的 `kind=concat`、`media_kind=video`），按分镜顺序依次连接所有视频节点；连接顺序就是拼接顺序。节点 `data` 写 `audioFadeMs`（0–200，默认 60）。
7. 逐镜执行：按分镜顺序运行视频节点；音频提取节点是它们的上游，会随执行范围自动执行。不要用运行级参数注入音频。
8. 把 `videos`、`audio_nodes`、`final_video_var` 写入会话状态。

### A2 连续时间线

1. 把分镜合并成 clip：单 clip ≤15 秒，总时长可超过 15 秒；记录每个 clip 的分镜号、时长、参考变量。
2. 只建一个 `output_video_long`，套用「连续生成（长）」目标（`minimax_h3_extender`）。
3. `clips_json` 写 `{"version":2,"generation_mode":"ref2va","motion_context":true,"clips":[...]}`；每段一个 clip，包含 prompt、duration、固定 seed。
4. `ref_1..ref_N` 依次绑定各 clip 的主关键帧或分段拼接图，剩余槽位绑定角色/场景参考；每段 prompt 只引用本段对应的 `<Picture N>`。套用「连续生成（长）」菜单时就**apply_menu 时一并传 bindings**，不要先 apply 再补绑定，否则菜单会自动补建一个空的参考图输入节点。
5. 第 1 段写起始状态；后续每段重复上一段结尾的动作、镜头方向、光线和同一 `overall_soundscape`。
6. 写 `audio_context_length`（默认 0）；P1 可选 `ref_audio`。用户选了参考音频时，用 `list_assets` 找到音频资产，建音频输入节点并连到 Extender 的 `ref_audio` 槽，不要伪造路径。不要暴露 A1 的上一镜尾音/全片氛围底三选一。
7. 用 `full_batch` 一次执行，输出一条成片；**不要**创建视频拼接节点，也不要创建 `output_video_<分镜>` 单镜节点。
8. 把 `segments`、`final_video_var` 写入会话状态。

## 8B. 整段参考图视频

1. 总时长不超过单段上限：建一个 `output_video_single`，套用「参考图生视频（单段）」目标，**apply_menu 时一并传 bindings**（`image` → 该段拼接图），直接执行。`length` 按节点 schema 的 `duration_limits` 换算；H3 的 10 秒是 243 帧，不要写 240 或 241。
2. 总时长超过单段上限：建一个 `output_video_long`，套用「连续生成（长）」目标（`minimax_h3_extender`）。
   - `clips_json` 写 `{"version":2,"generation_mode":"ref2va","motion_context":true,"clips":[...]}`；
   - 每段一个 clip，包含 prompt、duration、固定 seed；每段不超过 15 秒；
   - 段间 prompt 重复上一段结尾的动作、镜头方向、光线和同一 `overall_soundscape`；
   - `ref_1..ref_N` 依次绑定各段拼接图，剩余槽位绑定角色/场景参考；每段 prompt 只引用本段对应的 `<Picture N>`；
   - 写 `audio_context_length`（默认 0）；P1 可选 `ref_audio` 和 `audio_ref_strategy`（默认 `context`）。选了参考音频时建音频输入节点并连到 Extender 的 `ref_audio` 槽；
   - 不出现 A1 的上一镜尾音/全片氛围底/接缝淡化；
   - 用 `full_batch` 一次执行，输出一条成片；
   - **不要**再建视频拼接节点。
3. 把 `segments`、`single_video_var` 或 `final_video_var` 写入会话状态。

## 9. 收尾

汇总关键帧/参考图、每镜视频或成片、输出变量，告诉用户怎么预览、怎么保存到资源库。节点建完后可以调用 `canvas_layout` 整理画布；整理后检查分镜视频和拼接节点的顺序，避免视频节点混进分镜图。

成片需要提升清晰度时，先问用户是否做最终增强，不要默认加：

- `preset_video_enhance`「视频增强」使用 SeedVR2，接最终视频节点，保留原 fps 和音频；耗时较长，用户确认后再建节点和执行。
- 分镜视频路线接视频拼接的输出（A1）或 `final_video_var`（A2）；整段参考图视频路线接 `single_video_var` 或 `final_video_var`。
- 增强是生成式修复，可能改变细节；已经满意的成片不要强行加。

## 可选：语音节点（TTS / ASR / VC）

语音模式在创建时确定，`canvas_update_node` 不能改 `mode`。先 `list_canvas_menu` 看对应入口；建节点用 `canvas_add_node(kind="speech", data={mode:"tts|asr|vc"})`，需要参数时先 `canvas_get_node_schema` 读完整字段，再整份写回。

**TTS（mode=tts）**

- `text` 支持 `{{变量名}}`。音色库写 `voiceRecordId`；服务原生音色写 `voice`/`model`；Comfy 写 `workflow`。
- 通用字段：`providerId`、`language`、`format`（mp3 / wav / ogg_opus）。
- 高级参数写 `ttsTuning`：`{advanced, linked, expressiveness, speed, exaggeration, cfgWeight}`。`linked=true` 时由 `expressiveness`（0–1）同时插值语速、语气和节奏；`linked=false` 时用独立值。`advanced=false` 表示全部用服务默认值。
- Turbo/Nano 只支持 `speed`，不要承诺语气或节奏；需要语气时改用多语言或标准模型。

**ASR（mode=asr）**

- 上游必须接音频或视频。写 `language`（空=自动）、`format`（空=自动，或 txt/json/srt/vtt）。
- 高级参数写 `asrTuning`：`{advanced, timestamps, task, vad, beamSize, bestOf, temperature, noSpeechThreshold, compressionRatioThreshold, conditionOnPreviousText, initialPrompt, hotwords, qwenBatchSize, extraJson}`。
- `timestamps` 可取 `none|segment|word`；`task` 可取 `transcribe|translate`。
- Qwen3-ASR 不支持 VAD、beam、热词、初始提示词和翻译；不要给 Qwen 写这些参数，也不要声称能词级对齐之外的 Whisper 专属能力。

**VC（mode=vc）**

- 上游接音频或视频；`voiceRecordId` 必填，音色必须有参考音频。输出类型随输入变化。
- 通用字段：`providerId`、`model`、`separateBgm`、`subtitleAssetId`、`burnSubtitles`、`subtitleSize`、`subtitleColor`、`format`（wav/mp3）。
- 高级参数写 `vcTuning`：`{advanced, convertAll, segmentPadding, mergeGap, minSegment, normalizeLoudness, targetLufs, denoise, outputSampleRate, refStart, refDuration, seed, diffusionSteps, inferenceCfgRate, nQuantizers, temperature, lengthAdjust, overlapFrameLen, maxWindow, context, fade, refMaxLen, extraJson}`。
- `convertAll=true` 表示整段替换，不再依赖识别分段。Chatterbox 只用参考音频前 10 秒；Seed-VC 支持 `seed`、`diffusionSteps` 等生成参数，参考默认最多 25 秒。
- 需要自定义字幕时让用户在属性面板上传 srt；Agent 不伪造 `subtitleAssetId`。没有 srt 时自动 ASR。

只有 Liber Speech 支持这些高级参数；其他 TTS/ASR 服务只写通用字段。向用户说明会产出音频、字幕或视频，确认后再 `canvas_run_nodes`；不要默认自动换音。

## 推进规则

- 不要把多个步骤合并成一次长回复。
- 每次只问当前步骤真正需要的信息。
- 用户说「你决定」时，给出一个明确方案并说明理由，仍要等一句确认。
- 每步确认后调用 `update_session_state`，把 `step`、`topic`、`characters`、`script`、`shots`、`route`、`storyboard_mode`、`audio_strategy`、`audio_nodes`、`keyframes`、`reference_images`、`segments`、`videos`、`final_video_var` 写进会话状态。刷新后先读系统提示里的「当前会话状态」，从中断处继续，不要重做已完成步骤。

## Gotchas

- 文本输入节点被下游引用时，用 `{{变量名}}`；不要写成裸变量名。
- 功能节点先建空白，再套功能菜单/工作流；不要直接写 `pack` 或 `outputKind`。
- 执行单个节点时只传该节点 id，不要传上游；否则会把上游重新提交一遍。
- 画布变量名是全局命名空间，新增节点前先看是否重名。
- 换方案时先清理旧草稿：旧节点未执行、无产物时用 `canvas_discard_nodes` 删除，不必逐次确认；有执行记录或产物时用 `canvas_delete_nodes` 并让用户确认。只清理本次为被替换方案创建的节点，不要删除用户手建的节点。自动补建的空输入若已无下游，也一并丢弃。
- 删除节点、提交生成、运行脚本等高风险操作会被安全路由暂停；向用户说明将执行什么，不要重复创建节点来绕过失败。
- 预检失败时先修节点配置，不要直接强行执行。
- 不要在没有用户确认的情况下连续生成大量关键帧或视频。
- 创建视频节点前必须先让用户选 A/B；选 A 后再选 A1/A2。用户确认前不要建任何 `output_video_*` 节点。
- A1 每镜一个 `i2v_ref` 视频节点，关键帧不拼接；A2 只建一个 Extender（「连续生成（长）」菜单），不建单镜视频和拼接节点。
- `<Picture N>` 按实际已填槽位顺序编号；连续填槽，删掉参考后重新计算后面的编号。
- B 不超过单段上限时用「参考图生视频（单段）」；超过时用「连续生成（长）」，不要拆成多个独立视频再拼接。
- 长视频 `clips_json` 每段不超过 15 秒；60 秒默认 4 段；`motion_context=true`；段间 prompt 重复上一段结尾的动作、镜头方向、光线和同一 `overall_soundscape`。
- A1 `previous_tail` 用 `audio_extract` 节点：上一镜视频 → 提取节点（`tail`）→ 当前镜 `ref_audio`；第 1 镜不建提取节点。`global_bed` 用一个音频输入节点连到所有分镜，不要把音频路径写死在各节点里。建完必须用 `canvas_get_graph` 核对两段边都存在；只设置 `ref_audio` 绑定不算完成。
- A2 不暴露逐镜音频三选一；B 不出现 A1 的 `previous_tail` / `global_bed` / 接缝淡化。A2/B 的 `audio_context_length` 默认 0。
- 视频节点套菜单时，**apply_menu 时一并传 bindings**；先 apply 再 `canvas_set_binding` 会多建一个空输入节点。
- 关键帧/参考图提示词只写视觉，不写台词、口型、字幕或声音；台词只进视频提示词或音频节点。
- 写 `length` 前读 `duration_limits`，按 `fps`、`align_base`、`align_offset` 换算并夹在 min/max，不要按 24fps 直接乘或沿用默认帧数。
- 角色参考默认绑定，前提是目标有额外图片槽；用户要求去掉时，让画布技能断线并清掉对应 binding。
- 关键帧数量受目标参考槽限制，不要生成目标用不上的关键帧。
- 可以自动整理画布；整理后检查分镜视频和拼接节点的顺序，避免视频节点混进分镜图。
- 改 `values` 前先 `canvas_get_node_schema` 读完整值，整份写回，不要只传要改的键。
- `bindings` 只决定槽位，不替代上游依赖；套用菜单或 `canvas_set_binding` 后检查 `created_edges` / `missing_bindings`，缺边用 `canvas_connect` 补上，否则预检会报“不是上游节点”。
- 长视频每个 clip 的 prompt 只引用本段对应的 `<Picture N>`，不要把所有参考图都写进同一段。
- 图片/视频拼接和音频提取是画布内置工具节点（`kind=concat`），不是功能菜单项；不要对它们调用 `canvas_apply_menu`。音频提取设 `data.toolId=audio_extract`，只接一个视频或音频输入，`audioMode=whole|tail` 控制完整音轨或固定长度尾音。UI 里的「工具」「拼接」和内部 `concat` 指同一类节点。
- `preset_depth_pose` 需要人物照 + 姿势图两个图片槽，只有一个姿势图时改用 `preset_depth_gen`；`preset_depth_gen` 默认可能解析到姿势生成人物，要 Union Depth 时先看 `available_targets`，再用 `canvas_apply_pack` 绑具体包。
- 线稿保持原始画幅，不裁白边；人物换姿势按姿势参考图比例、两图较大边长生成（长边上限 2048），姿势生成人物跟姿势参考图原尺寸。用之前先确认，避免成片画幅和主题设定不一致。
- 图片修复放大和视频修复放大是可选步骤，必须用户确认后再加；SeedVR2 会生成式改变细节，视频增强还更耗时。
