# 导演 Skill 视频流程优化

> **历史方案（已归档）**：本文记录当时的开发计划与决策，不代表当前实现。当前功能与文档以 `site/docs-src/` 和代码为准；请勿直接按本文实施。


> 2026-11-02 讨论确认，开发中。
>
> 目标：把导演 skill 从“让用户选择节点实现”改成“先选创作路线，再按目标能力生成资产和视频”。两条路线分别服务连续长镜头和多分镜剪辑。
>
> **进度：** 工作流包和菜单已完成；导演 skill 视频分支和状态结构已重写。Ref2VA 权重尚未下载，60 秒实际生成待下载后验证。
>
> **冒烟结果：** 2026-11-02 用 FL2VA 权重跑通 Extender 2 段 ×4 秒，输出 8.0 秒 / 192 帧 / 640×384，`ref_pack` 导入 2 张参考图，耗时约 4 分 19 秒。
>
> **交互验证：** 2026-11-02 只输入剧本、不预设生成方式，通过 Web UI 走通两条路线，均只建节点、未执行生成。分镜视频路线 16 个节点；一段视频路线 13 个节点，7 张参考图 → 4 张 1×N 合成图 → Extender 4 段（10+15+10+10=45 秒）。`ask_user` 排查确认：后端在提问后立即结束本轮，前端只有点击选项按钮才会发送回答，不存在自动推进；测试中出现的连续回答来自并发的真实界面点击。

## 1. 背景

当前导演 skill 的第 8 步让用户选择「图生视频节点」还是「参考视频节点」，然后进入两条各 6～9 步的实现分支：

- 图生视频：每镜一个节点，绑定首帧/尾帧，逐镜执行，可选视频合成。
- 参考视频：按 15 秒分组，每组合成一张首帧或首尾帧拼图，每组一个视频节点，逐组执行，可选视频合成。

问题不在具体工具，而在职责混在一起：

- 用户被要求选择实现方式，而不是表达创作意图；
- 参考视频分支把“分组、合成、组文本、组视频、再合并”全部暴露给导演；
- 图生视频分支只解决单镜生成，没有定义多镜头的视觉一致性策略；
- 15 秒是模型单段上限，不应该成为用户需要理解和选择的参数。

## 2. 两条创作路线

### A. 关键帧分镜

用途：多分镜剪辑，镜头之间可以硬切，重点是角色、服装、场景和风格一致，不要求运动连续。

流程：

1. 剧本 → 分镜；
2. 用户选择每镜生成几张关键帧；
3. 生成关键帧图片，**不合成**；
4. 每镜一个图生视频节点，传入角色参考图和该镜关键帧；
5. 每镜生成一段视频；
6. 最后用视频合成节点把所有分镜视频按顺序拼成一条。

约束：

- 关键帧数量由用户选择，但必须先读目标视频节点的 schema，不能超过目标实际图片槽位；
- 关键帧图片不合并，不生成统一分镜拼图；
- 角色参考图默认绑定，前提是目标节点有额外的图片/参考槽位；
- 用户不需要角色参考时，由画布技能断开对应连线并清掉槽位绑定；
- 第三方模型的输入槽位可能不同，完全按 `canvas_get_node_schema` 的实际字段映射，不假设固定键名。

### B. 单视频 / 长视频

用途：一条连续成片，镜头之间保持运动、构图、光线和音频连续；总时长可以 ≤15 秒，也可以更长。

流程：

1. 剧本 → 分镜；
2. 每镜生成一张分镜参考图；
3. 按目标单段上限内部切段；
4. 每段把所有该段分镜的参考图合成一张 1×N 参考图；
5. 总时长 ≤15 秒：一个参考视频节点；
6. 总时长 >15 秒：强制走 Extender 时间线，每段一张参考图，内部接力；
7. 直接输出一条成片，不再做多段视频合成。

约束：

- 每镜固定一张参考图，不做首尾帧两行拼图；
- 不向用户暴露“每张合成图放几个分镜”或“15 秒分组”；
- >15 秒必须使用 Extender；未安装时提示安装，不自动退回多组独立视频；
- 60 秒默认按 4 段 × 15 秒处理；15 秒实际是 362 帧 ≈ 15.08 秒，最终可按需裁到 60 秒。

## 3. 新导演流程

### Step 1～4

保持不变：主题、角色、剧本、分镜设计。

### Step 5 选择创作路线

在生成分镜图片前询问：

- **A. 关键帧分镜**：多分镜、可剪辑，重点是视觉一致；
- **B. 单视频 / 长视频**：一条连续成片，重点是运动、光线和音频连续。

这一步替代当前 Step 8 的「图生视频 / 参考视频」选择。节点类型由路线推导，不再让用户选实现。

### Step 6A 关键帧分镜：生成关键帧

1. 先确定图生视频目标（菜单或工作流包），读 `canvas_get_node_schema`；
2. 根据目标实际图片槽位，告诉用户每镜最多可生成几张关键帧；
3. 用户选择每镜关键帧数量；
4. 每镜生成关键帧，变量名 `output_image_kf_<分镜>_<序号>`；
5. 关键帧不合成，保留为独立节点。

### Step 6B 单视频：生成分镜参考图

1. 每镜生成一张参考图，变量名 `output_image_ref_<分镜>`；
2. 读取视频目标单段上限；
3. 按总时长内部切段；
4. 每段生成一个图片合成节点，`layout=grid`、`columns=N`，合成该段全部参考图，变量名 `output_image_ref_group_<段号>`；
5. ≤15 秒时只有一张合成图；>15 秒时每段一张，例如 60 秒四张。

### Step 7A 关键帧分镜：逐镜视频并合成

1. 每镜建 `output_video_<分镜>`；
2. 按目标 schema 绑定：
   - 一个图片槽：绑首帧；
   - 两个图片槽：绑首帧 + 尾帧；
   - 多参考槽：按语义绑全部关键帧；
   - 有余量时默认绑定角色参考图；
3. 写入视频提示词，检查 `created_edges` / `missing_bindings`；
4. 逐镜执行；
5. 最后建「视频合成」节点，按分镜顺序合并。

### Step 7B 单视频：参考视频或 Extender

- 总时长 ≤15 秒：建一个参考视频节点，绑定该段合成图，直接输出。
- 总时长 >15 秒：建一个 Extender 长视频节点，传入时间线 JSON 和参考图包，一次输出整条成片。

### Step 8 收尾

汇总关键帧/参考图、每段视频、最终成片。节点建完后可以自动整理画布；整理后检查分镜视频和合成节点的顺序。

## 4. 状态结构

建议把 `video` 状态改成：

```json
{
  "route": "keyframe",
  "keyframe_count": 2,
  "keyframes": {
    "1": ["output_image_kf_1_1", "output_image_kf_1_2"]
  },
  "reference_images": {
    "1": "output_image_ref_1"
  },
  "segments": [
    {
      "shots": [1, 2, 3],
      "duration_s": 15,
      "composite_var": "output_image_ref_group_1"
    }
  ],
  "videos": [
    {"shot": 1, "video_var": "output_video_1"}
  ],
  "final_video_var": "output_video_final"
}
```

规则：

- `route`：`keyframe` 或 `single_video`；
- `keyframe_count`：仅关键帧路线使用；
- `keyframes`：仅关键帧路线使用，每镜可以有多个变量；
- `reference_images`：仅单视频路线使用，每镜一张；
- `segments`：仅单视频 >15 秒且走 Extender 时使用；
- `videos`：仅关键帧路线记录每镜视频；
- `final_video_var`：最终成片变量；
- 不再保存 `video.mode = i2v/reference` 和 `shots_per_composite`；
- 角色参考图变量可另存 `character_refs`，供两条路线复用。

## 5. Extender 接入结论

已核对 `ComfyUI_MiniMax_H3_Extender` 3.0.14 的节点接口。

### 5.1 节点注册

插件目录在 `/home/ps/workspace/ComfyUI/custom_nodes/ComfyUI_MiniMax_H3_Extender`，实际运行目录是 `/home/ps/workspace/remote_bundle/ComfyUI`（前者是后者的软链接）。

当前 ComfyUI 进程启动于插件安装之前，`object_info` 里还没有 `MiniMaxH3Extender`。需要重启 ComfyUI 后才会注册。

### 5.2 核心输入

`MiniMaxH3Extender` 的关键输入：

- `model`：Ref2VA 模型；
- `clip`：H3 文本编码器；
- `vae` / `audio_vae`：视频/音频 VAE；
- `run_mode`：`clip_by_clip` 或 `full_batch`；
- `clips_json`：**字符串**，传整条时间线；
- `refs_json`：内部参考图描述；
- `ref_pack`：外部参考图包；
- `generation_mode`：`ref2va` 或 `fl2va`；
- `motion_context`：长镜头必须为 `true`；
- `context_length`：默认 22；
- `continue_existing_video`：可选，从已有视频继续。

`clips_json` 结构示例：

```json
{
  "version": 2,
  "generation_mode": "ref2va",
  "motion_context": true,
  "clips": [
    {
      "id": "clip_1",
      "prompt": "第 1 段连续镜头提示词",
      "duration": 15,
      "seed": 123456,
      "seed_mode": "fixed",
      "validated": false
    },
    {
      "id": "clip_2",
      "prompt": "第 2 段连续镜头提示词",
      "duration": 15,
      "seed": 123456,
      "seed_mode": "fixed",
      "validated": false
    }
  ]
}
```

### 5.3 参考图

使用 `MiniMaxH3ReferencePackBridge`：

- 输入 `ref_1`～`ref_9` 共 9 个 IMAGE 槽；
- 输出 `ref_pack`，接到 Extender 的 `ref_pack`；
- Extender 在 Queue 时把已连接的槽导入内部 Ref 1～Ref 9；
- 每条 clip 的 prompt 用 `<Picture N>` 引用对应参考图。

推荐用法：

- Ref 1～Ref 4：60 秒四段的四张分镜合成图；
- Ref 5～Ref 8：角色定妆照三视图或场景参考；
- 每段 clip prompt 只引用本段对应的 `<Picture N>`，并在开头重复 `subject_definitions` 块，明确角色和参考图对应关系。

### 5.4 输出

`MiniMaxH3MotionContextDiskFinalDecode` 接收 Extender 的 `cache`、`vae`、`audio_vae`，输出一条带音轨的 `VIDEO`，再接 `SaveVideo` 保存为 MP4。

### 5.5 建议的工作流包

新增 `minimax_h3_extender` 包，节点大致为：

```text
UNETLoader(Ref2VA) → TurboLoRA → Extender.model
CLIPLoader → Extender.clip
VAELoader(video) → Extender.vae / FinalDecode.vae
VAELoader(audio) → Extender.audio_vae / FinalDecode.audio_vae
ReferencePackBridge(ref_1..ref_9) → Extender.ref_pack
Extender.clips_json
Extender.cache → FinalDecode.cache
FinalDecode.video → SaveVideo
```

工作流包输入：

- `clips_json`：字符串，由导演/后端按分镜生成；
- 固定 9 个图片输入，或按实际使用的参考图数量暴露槽位；
- `width` / `height` / `seed` / `steps` / `sampler_name` / `scheduler`；
- 可选 Turbo/加速设置。

## 6. 导演 Skill 需要改什么

### 6.1 Step 8 改成路线选择

当前：

- 问「图生视频 / 参考视频」；
- 写 `video.mode`。

改为：

- 问「关键帧分镜 / 单视频」；
- 写 `route`；
- 节点类型和视频方式由路线推导。

### 6.2 9A 改成关键帧分镜

- 先读视频目标 schema；
- 再问每镜关键帧数量；
- 生成关键帧不合成；
- 视频节点按 schema 绑定关键帧 + 角色参考；
- 逐镜执行后合并。

### 6.3 9B 改成单视频

- 每镜一张参考图；
- 按单段上限内部切段；
- 每段一张 1×N 合成图；
- ≤15 秒一个参考视频节点；
- >15 秒一个 Extender 节点；
- 不再出现多组独立视频节点和最终 concat。

### 6.4 角色参考的职责边界

导演 skill 只表达“这镜要默认带角色参考”“用户要求去掉角色参考”这类创作意图。

断线、清理 `bindings`、检查上游连线属于画布技能/画布工具职责。当前行为已确认：

- `canvas_disconnect` 只删除边，不会自动删除下游节点的 `bindings`；
- 断线后预检会报“绑定变量 X 不是上游节点，请先连线”；
- 因此画布技能的断线操作需要同时清空对应槽位 binding，或提供 `canvas_unset_binding`；
- 导演 skill 不复制这套底层逻辑，只调用画布技能完成“移除角色参考”。

### 6.5 文字和推荐

- 不再全局写“参考视频优先”；
- 只在单视频/长镜头路线推荐参考视频或 Extender；
- 关键帧分镜路线说明重点是视觉一致，不是运动连续。

## 7. 开发阶段

### P0：Extender 验证

1. 重启 ComfyUI，确认 `MiniMaxH3Extender` 注册；当前已确认 3.0.14 的三个节点均注册；
2. 先做冒烟测试：2 段 ×4 秒、低分辨率、4 步 Turbo，验证 `clips_json`、`ref_pack`、段间接续和 FinalDecode，预计几分钟；
3. 冒烟通过后再做 4 段 ×15 秒的 60 秒验证，可后台或夜间运行；
4. 每段一张合成分镜图 + 一段 prompt；
5. 检查：接缝动作、人物一致性、音频连续性、显存、耗时、取消/续跑。

### P1：Extender 工作流包 + 长镜头路线

1. 新增 `minimax_h3_extender` 包；
2. 把 `clips_json` 和参考图包接入 manifest；
3. 导演 skill 增加单视频 >15 秒分支；
4. 状态结构增加 `segments`。

### P2：关键帧视觉一致性

1. 扩展 `minimax_h3_i2v_ref` 支持多参考图；
2. 导演 skill 支持每镜多个关键帧；
3. 默认绑定角色参考，支持用户移除；
4. 可选：上一镜末帧作为场景/光线参考，不作为首帧。

### P3：文档、测试、回退

1. 更新 `docs/使用文档.md` 和 `docs/画布导演台.md`；
2. 增加导演 skill 路线分支测试；
3. 增加 Extender JSON 构造测试；
4. 保留 ≤15 秒旧参考视频路径；
5. 第三方模型输入变化时，优先通过 schema 适配，不硬编码。

## 8. 待验证 / 风险

- ComfyUI 重启后 Extender 节点是否正常注册；
- `clips_json` 通过 API 提交时，Extender 是否正确解析；
- 每段 15 秒在 Extender 中是否被内部裁到合法帧数；
- 9 张参考图上限下，4 张分段合成图 + 角色参考是否够用；
- 60 秒任务显存、耗时、取消、磁盘缓存续跑；
- `motion_context` 与音频上下文在段间的实际效果；
- 参考图 token 成本是否过高（`ref_image_size` 可调）；
- 断线后 binding 清理是否在画布技能中实现。

## 9. 非目标

- 不新增首尾帧专用 ComfyUI 工作流；
- 不再为 60 秒长镜头使用“全部参考图合成一张”的全局拼图；
- 不把 Extender 的时间线编辑 UI 搬进导演台；
- 不允许 >15 秒长镜头在没有 Extender 时静默退回多段独立视频。
