# Qwen-Image-2.1：真人参考图 + 线稿/深度图改动作 — Comfy 生态调研

- 调研日期：2026-10-30（Asia/Shanghai）
- 补充核对：同日针对用户澄清的 **「双人身份参考 + 双人控制图合图」** 需求（见文首专节）
- 目标：本地 ComfyUI / 无审查栈优先；是否可用 **1 张或多张人物真实照片** + **动作线稿（OpenPose/Canny/Scribble 等）或深度图（Depth）**，把人物动作改成控制图中的姿态
- 结论摘要（单人改姿）：**有（明确支持 2.1）**。最对口的是 Alibaba PAI **Qwen-Image-2.1 Fun ControlNet Union** + T8 社区「参考图编辑 + Pose/Depth」工作流；官方原生多图 Edit 可做「用第二张图当姿态参考」，但**没有**结构控制网那么硬。本调研**未在本机实测**跑通。
- 结论摘要（双人合图按控制图）：**不原生支持**用户精确需求（图一=人物1、图二=人物2、另附双人线稿/深度图 → 两人合进同一输出并按该控制图摆姿）。可有「软合图 / 自拼近似 / 其他人偶栈」绕路，见下节。

---

## 0. 双人身份参考 + 双人线稿/深度图（用户澄清需求）

### 0.1 需求精确描述

| 输入 | 含义 |
| --- | --- |
| 图一 | **人物1** 的真人参考（身份/外观） |
| 图二 | **人物2** 的真人参考（身份/外观） |
| 线稿或深度图 | **同一张图里两人**的目标动作/构图（双人 Pose / Depth / Lineart） |
| 目标输出 | 两人按各自身份合进同一画面，并按该双人控制图摆姿 |

这与「一张单人照 + 一张单人姿态图改动作」不是同一问题；也与「多张同一人的多角度参考」不同。

### 0.2 一句话结论

**现有公开 Comfy / Qwen-Image-2.1 工作流不原生支持该精确流水线**（没有现成 JSON/文档声明：两个对等身份槽 + 一张双人结构控制图 → 合图并硬跟姿势）。  
**结构侧**：Fun ControlNet Union 的单张 `control_image` **可以**是含两人的 DWPose/Depth/Lineart（模型卡未禁止多人控制图）。  
**身份侧**：T8 的 3 个参考槽**不是**「人物1 / 人物2 / 人物3」对等绑定；`reference_image` 是**编辑目标画布**，`_2`/`_3` 是附加外观/风格参考；README 写明结构控制**不保证**把另一人的脸/衣服精确拷过来。官方多图 Edit 可做**软**多主体合图，但**无**硬 ControlNet。本结论基于公开仓库/文档交叉核对，**未本机出图实测**。

### 0.3 关键证据

| 来源 | 证据 |
| --- | --- |
| [T8 `qwen21_union_pose_reference_edit.json`](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8/blob/main/workflows/qwen21_union_pose_reference_edit.json) | 画布只接 **1** 个 `LoadImage`→`reference_image` + **1** 个控制图；**未接线** `reference_image_2`/`_3`。默认 prompt：「Edit the reference image to follow the pose while preserving its **subject**…」——单主体改姿，非双人合图 |
| [T8 README / README_CN](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8) | `reference_image` = **图1：要编辑的原图，决定输出画布**；`reference_image_2`/`_3` = **附加外观或风格参考**。明确：「姿态等结构控制不保证把另一个人的五官或服装精准迁移过来。」无双人场景示例 |
| [T8 `__init__.py` · `QwenImage21UnionReferenceEncode`](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8/blob/main/__init__.py) | 把三张图映射为 `image_1`…`image_3` 交给原生 `TextEncodeQwenImage21`；节点说明：image_1 = edit target and canvas；可选 image_2/3 = visual references。v1.0.3 发布说明仅为「Multiple image references」，非「multi-character identity slots」 |
| [alibaba-pai Fun ControlNet Union](https://huggingface.co/alibaba-pai/Qwen-Image-2.1-Fun-Controlnet-Union) | 单路 `control_image` + 文本（及可选 inpaint）；八种控制含 Pose/Depth/Lineart；示例与脚本均为「一张控制图 + prompt 描述整图」，**无**双身份参考接口 |
| [Comfy 官方 Qwen-Image-2.1 Image Edit](https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1) | 最多 16 参考槽；`image_1` = 被编辑图，其余供内容；官方模板**未**接 Fun ControlNet |
| [QwenLM 多参考编辑例](https://github.com/QwenLM/Qwen-Image-2.1) | `image=[ref_0,ref_1,ref_2]` + 「These three characters are sitting around a campfire…」——**软**多主体合图，无 Pose/Depth ControlNet |
| [SpicyAPI 双人 Edit](https://spicyapi.ai/workflows/comfyui-qwen-multi-character-edit) | 两张身份参考 → Qwen Image 2.1 Edit 合场景；靠 prompt 指定左右；**无**线稿/深度硬控；且为托管 API 模板 |
| [Fisher Pose（双人）](https://github.com/Work-Fisher/ComfyUI-Fisher-Pose) | 产品化「人物1 + 人物2 + 双人摆姿」最接近；路径是 **VNCCS PoseStudio QI2.1 LoRA + 3D 人偶**，不是 Fun ControlNet Union；身份对应「依赖模型理解提示词，并非人脸锁定」；导入 OpenPose 时多人**只取身形最大者** |

### 0.4 T8「约 3 槽参考」语义（专项核对）

| 问题 | 答案 |
| --- | --- |
| 是「多张同一人」还是「可绑定不同人物身份」？ | **接口上**可塞不同照片；**语义上**设计为：槽1 = **被编辑的那张图（画布）**，槽2/3 = **附加外观/风格参考**（服装、发型、风格等）。**不是**「人物1身份 / 人物2身份」对等角色槽。README 用词是 appearance/style references，并警告无法保证把「另一个人」的脸精确迁过来 |
| 控制图是单人还是支持双人构图？ | **一张** `control_image`。Pose/Depth/Lineart 像素里可以画/检出**两个**人（DWPose 多人骨架常见）；Union **没有**「每人一张控制图」或「骨架ID↔身份槽」的绑定 API。文档/示例**未**给出双人控制场景 |
| 有无文档/示例明确双人场景？ | **无**。T8 workflows 目录无 dual/two-person/双人 命名；pose_reference_edit 为单参考；官方 Union 模型卡无双人合图例 |

### 0.5 最接近可行方案（按推荐排序，均非「原生一键」）

1. **自拼 T8 Union（硬结构近似）**  
   - 控制：双人 DWPose / Depth / Lineart → `QwenImage21UnionApply`（mode=Pose/Depth/Lineart）  
   - 身份：`QwenImage21UnionReferenceEncode` — 建议用**场景底板/空白/粗排版**作 `reference_image`（定画布），人物1→`reference_image_2`，人物2→`reference_image_3`；prompt 写清「左侧人物取自 `<image2>`，右侧取自 `<image3>`，姿态跟随控制图」  
   - **勿**把人物1单人照直接当 `reference_image` 还指望自然「长出」第二人——槽1是编辑目标，默认工作流是在**一张已有主体图**上改姿势  
   - 缺口：无现成 JSON；左右身份靠 VL+提示词软绑定；脸一致性无硬锁；未实测

2. **Fisher Pose 双人工作流（产品化双人摆姿，栈不同）**  
   - [【Work-Fisher】无限姿势+无限视角（支持双人）.json](https://raw.githubusercontent.com/Work-Fisher/ComfyUI-Fisher-Pose/main/workflows/%E3%80%90Work-Fisher%E3%80%91%E6%97%A0%E9%99%90%E5%A7%BF%E5%8A%BF%2B%E6%97%A0%E9%99%90%E8%A7%86%E8%A7%92%EF%BC%88%E6%94%AF%E6%8C%81%E5%8F%8C%E4%BA%BA%EF%BC%89.json)：默认「人物1」「人物2」两张单人照，或一张合照  
   - 在编辑器里摆双人姿势（可识别动作照 / 点 OpenPose）；生成靠 VNCCS LoRA，**不是**用户自备线稿接 Fun ControlNet  
   - 若用户坚持「自己的线稿/深度图」：可用编辑器导出的人偶/骨骼作参考，或把用户骨架尽量导入（OpenPose 入口；多人图只取最大身形——双人线稿需谨慎）  
   - 缺口：身份非硬锁；复杂双人姿势不如单人稳；与 Fun Union 线不完全等同

3. **分步软硬结合**  
   - 步 A：官方 Image Edit / SpicyAPI 双参考 → 软合成双人同框（保留脸，姿势可先松）  
   - 步 B：合成图作 T8 `reference_image`，用户双人 Pose/Depth 作 `control_image` → `pose_reference_edit` 再硬拧姿势  
   - 或反过来：先 Union 纯控制出双人结构占位，再 Edit 多参考换脸/换衣服  
   - 缺口：两步误差叠加；仍无骨架↔身份硬绑定

### 0.6 明确缺口清单

1. **无**「人物1槽 + 人物2槽 + 双人控制图」现成 Comfy JSON（T8 / 官方 / Union 模型卡均无）。  
2. T8 三槽**不对称**：槽1=画布/编辑目标，不是对等身份。  
3. **无**控制骨架实例与身份参考的左右硬绑定（无 IP-Adapter FaceID 类硬锁）。  
4. README 明确：**结构控制 ≠ 精确换脸/换装**。  
5. 官方多主体合图是 **Edit 软路径**，与 Fun ControlNet **未**官方绑成一条模板。  
6. Fisher 虽支持双人，但是 **人偶+LoRA** 栈，且不把用户双人线稿/深度当作 Union ControlNet 一等公民输入。

---

## 1. 总答

| 问题 | 结论 |
| --- | --- |
| 2.1 是否有 Pose / Depth / 线稿 ControlNet？ | **有**。Fun ControlNet Union 单文件覆盖 Canny、Depth、Grayscale、HED、Lineart、MLSD、**Pose**、Scribble，并可与 inpaint 同开 |
| 能否 1 张真人照 + 控制图改动作？ | **有现成 JSON**：`qwen21_union_pose_reference_edit.json`（参考照 + Pose 控制图） |
| 能否多张人物参考？ | **部分有**。T8 `Qwen 2.1 UNION Image Reference Encode` 支持 `reference_image` + `_2` + `_3`（约 3 槽）；官方原生 Edit 文本编码器可到 **16** 槽（`image_1`…`image_16`），但官方模板**未**把 16 槽与 Fun ControlNet 绑成一条现成「多图身份 + Pose」模板 |
| 多图身份 + 姿态控制能否同开？ | **文档/工作流设计上可以同开**（参考 Encode + Apply UNION）；T8 README 写明结构控制**不保证**把另一人的脸/衣服精确拷过来。**未实测** |
| 是否必须在线 API？ | **否**。权重可本地下载；Comfy Cloud / RunningHub 仅为可选托管 |
| 权重许可 | Fun ControlNet Union：基于 Qwen Research License，**默认非商用**（除非另行授权） |

---

## 2. Qwen-Image-2.1 官方能力（与控姿相关）

### 2.1 基座（Comfy 原生）

来源：[ComfyUI 文档 · Qwen-Image-2.1](https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1)、[QwenLM/Qwen-Image-2.1](https://github.com/QwenLM/Qwen-Image-2.1)

- 单权重覆盖 **文生图 + 指令编辑**；原生约 2K；VAE 四通道（含 alpha）
- **多图编辑**：`Text Encode Qwen Image 2.1` 最多 **16** 个参考槽；`image_1` 为被编辑图，其余供内容；提示词用 `<image1>`… 引用
- 官方模板：T2I、Image Edit、去背、Turbo T2I/Edit（Template Library 搜 `Qwen-Image-2.1`）
- **官方 2.1 教程页未附带 ControlNet 模板**；控姿需另接 Fun ControlNet Union

常用本地模型文件（Comfy-Org）：

| 用途 | 文件名 | 目录 |
| --- | --- | --- |
| DiT（省显存） | `qwen_image_2.1_int8_convrot.safetensors` | `models/diffusion_models/` |
| DiT（全精） | `qwen_image_2.1_bf16.safetensors` | 同上 |
| Turbo DiT | `qwen_image_2.1_turbo_int8_convrot.safetensors` 等 | 同上 |
| 文本编码 | `qwen3vl_8b_int8_convrot.safetensors` / `qwen3vl_8b_bf16.safetensors` | `models/text_encoders/` |
| VAE | `qwen_image_2.1_vae_bf16.safetensors` | `models/vae/` |

下载：https://huggingface.co/Comfy-Org/Qwen-Image-2.1

采样（官方模板）：steps 25（Turbo 8）、cfg **1**、euler + simple。cfg=1 时负向提示无效。

### 2.2 Fun ControlNet Union（2.1 专用，最相关）

来源：

- 权重：[alibaba-pai/Qwen-Image-2.1-Fun-Controlnet-Union](https://huggingface.co/alibaba-pai/Qwen-Image-2.1-Fun-Controlnet-Union)
- ModelScope：`PAI/Qwen-Image-2.1-Fun-Controlnet-Union`
- 新闻整理：[ComfyUI Wiki 2026-09-24](https://comfyui-wiki.com/en/news/2026-09-24-qwen-image-2-1-fun-controlnet-union)
- Comfy 合并：PR [#16519](https://github.com/Comfy-Org/ComfyUI/pull/16519)（约 2026-09-28）

控制类型（单文件约 **7.55 GB**）：

- **Canny / Depth / Grayscale / HED / Lineart / MLSD / Pose / Scribble**
- 同支路支持 **masked inpainting**（白=重绘，黑=保留）

技术要点：

- 仅含 control 分支（`control_img_in` + 16×`control_blocks`），叠在冻结的 2.1 transformer 上
- `control_in_dim=129`（64 控制 latent + 1 mask + 64 掩码图 latent）
- 示例脚本 `guidance_scale=1.0`；`control_context_scale=1.0` 最强，可调弱

Comfy 加载路径有两条：

1. **原生（PR #16519）**：`Load Model Patch` → `Apply Qwen Image DiffSynth ControlNet` → Sampler；Kijai 转换补丁：
   - `qwen_image_2.1_fun_controlnet_union_bf16.safetensors`
   - `qwen_image_2.1_fun_controlnet_union_int8_convrot.safetensors`
   - 目录：`models/model_patches/`（Kijai：`Kijai/QwenImage_experimental`）
   - Wiki 注明：**尚无**官方 `workflow_templates` 专用模板
2. **T8 自定义节点（推荐拿现成 JSON）**：见下一节

预处理：模式下拉**只是标签**，不会自动从照片抽线；需先用 **DWPose / Depth Anything / Canny / Lineart** 等（常用 `comfyui_controlnet_aux` 或 AIO Aux Preprocessor）生成控制图，再接入。

---

## 3. 最对口工作流 / 方案（2.1）

### A. 【首选】T8：参考图编辑 + Pose（明确 2.1）

- 仓库：https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8
- Registry：`comfy node install qwen-image-2-1-fun-controlnet-union-t8` / Manager 搜 *Qwen Image 2.1 Fun ControlNet Union (T8)*
- 工作流 JSON：
  - [qwen21_union_pose_reference_edit.json](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8/blob/main/workflows/qwen21_union_pose_reference_edit.json) — **真人参考照 + Pose 控制图改动作**
  - [qwen21_union_pose_reference_inpaint.json](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8/blob/main/workflows/qwen21_union_pose_reference_inpaint.json) — 同上 + 蒙版局部重绘
  - [qwen21_union_pose.json](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8/blob/main/workflows/qwen21_union_pose.json) — 纯 Pose 条件生图（无「编辑某张真人照」）
  - [qwen21_union_depth.json](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8/blob/main/workflows/qwen21_union_depth.json) — Depth
  - 另有 canny / lineart / scribble / hed / mlsd / grayscale / inpaint_pose

图接法（与用户需求对齐）：

| 输入 | 含义 |
| --- | --- |
| `control_image` | 预处理后的 Pose 骨架 / Depth / 线稿 |
| `reference_image` | **Image 1**：要改动作的真人照（定画布比例） |
| `reference_image_2` / `_3` | 额外外观/风格参考（提示词写 `<image2>` `<image3>`） |
| `inpaint_image` + `mask` | 可选局部重绘 |

节点：`QwenImage21UnionLoader` → `QwenImage21UnionApply`（mode=Pose/Depth/…）+ `QwenImage21UnionReferenceEncode`

Union 权重（T8 转换，放 `models/controlnet/`）：

- https://huggingface.co/t8star/Qwen-Image-2.1-Fun-Controlnet-Union-Comfy
- 文件名须以 `Qwen-Image-2.1-Fun-Controlnet-Union` 开头，例如 `Qwen-Image-2.1-Fun-Controlnet-Union-ComfyUI.safetensors`（改名会导致下拉消失）

要求：ComfyUI **≥ 0.37.0**；本地离线可跑；**不需**在线 API。

注意（README / 节点说明）：

- 控制图与输出画布**纵横比一致**更稳（社区视频也强调这一点）
- 「不会克隆另一人的精确脸/服装」；难姿势可降 strength（如 0.8）并在 prompt 描述姿态
- 示例采样：40 steps、euler/simple、CFG 1.0

### B. YouTube 实测向教程（明确 2.1 + Pose/Depth）

- [Qwen Image 2.1 Finally Has ControlNet: Pose, Depth and Inpainting Tested](https://www.youtube.com/watch?v=JNLbghoDCuc)
- 内容：Union 一文件八控制；AIO Aux 预处理 DWPose / Depth；**一张角色图 + 第二张姿态源图 → 抽骨架后控姿**；强调两图同分辨率；难姿势降 strength + 文案描述手部
- 作者提到约 **32 GB RAM** 场景下可对输入做放大；显存侧建议用 int8_convrot 基座
- **未提供**独立 GitHub JSON；与 T8 / 原生 Apply 节点同族

### C. 官方原生多图 Edit（无 ControlNet，软姿态迁移）

- 文档：https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1
- Template：`Qwen Image 2.1 Image Edit` / Turbo Edit
- 做法：`image_1`=人物照，`image_2`=姿态参考照（或再加骨架图作 `image_3`），提示词如：把 `<image1>` 人物改成 `<image2>` 的姿势，保留脸/发型/服装
- **优点**：官方、多图到 16、本地
- **缺点**：无 Pose/Depth 硬约束；难姿势成功率不如 ControlNet（社区对 **Qwen Edit 2509/2511** 的经验可作参考，但那是**另一代 Edit 模型**，见 §5）

### D. 原生 ModelPatch 路径（明确 2.1，无官方模板）

- ComfyUI ≥ 含 PR #16519 的版本
- `ModelPatchLoader` 加载 Kijai `qwen_image_2.1_fun_controlnet_union_*.safetensors` → `Apply Qwen Image DiffSynth ControlNet`
- 需自拼：参考图 Encode + 预处理 + Apply；**无**现成「人物多图 + Pose」官方 JSON

---

## 4. 多图人物参考 × 姿态控制

> **双人澄清**：若需求是「人物1照 + 人物2照 + 一张双人 Pose/Depth 合图」，见文首 **§0**；本节原表主要描述「多参考外观 × 单路控制」的设计能力，**不等于**已有双人对等身份工作流。

| 路径 | 人物参考槽 | 与 Pose/Depth 同开 | 说明 |
| --- | --- | --- | --- |
| T8 Reference Encode + UNION Apply | 1～3 | **设计上同开**（已有 pose_reference_edit 工作流） | 最贴近「真人照 + 动作图」；脸一致性无 IP-Adapter 级保证 |
| 官方 TextEncodeQwenImage21 Edit | 最多 16 | 官方模板**未**接 Fun ControlNet | 可自拼：多图 Encode + ModelPatch Apply（社区未给标准 JSON） |
| 经典 IP-Adapter | — | 2.1 生态**不以** SD IP-Adapter 为主 | 身份靠 VL 多图槽 + 提示词 |

**实测状态（本调研）**：文档与工作流 JSON 已核对；**未在本机 GPU 上跑图验证**脸稳度与难姿势成功率。

实用建议（综合 T8 README + 社区视频，非实测）：

1. 人物主图与控制图画到**同一分辨率/比例**
2. Pose：DWPose；Depth：Depth Anything / MiDaS
3. strength 难姿势试 0.7～0.8；简单姿势可 1.0
4. 多参考时 prompt 明确 `<image1>` 保脸、`<image2>` 仅取服装/发型等
5. 需要局部不动：加 mask + `pose_reference_inpaint`

---

## 5. 近似 / 降级方案（非 2.1 或未写明 2.1）

下列针对 **原版 Qwen-Image / Qwen Image Edit 2509·2511**，**不要**与 2.1 Fun Union 权重混用。

| 方案 | 链接 | 控制 | 备注 |
| --- | --- | --- | --- |
| InstantX Union ControlNet | [HF InstantX/Qwen-Image-ControlNet-Union](https://huggingface.co/InstantX/Qwen-Image-ControlNet-Union)；[Comfy 教程](https://docs.comfy.org/tutorials/image/qwen/qwen-image)；模板搜 *Qwen-Image InstantX ControlNet* | canny / soft edge / **depth** / **pose** | **原版 Qwen-Image**；文件 `Qwen-Image-InstantX-ControlNet-Union.safetensors` → `models/controlnet/` |
| DiffSynth Model Patches | 同上官方 Qwen-Image 文档 | 分文件 canny / depth / inpaint | `models/model_patches/` |
| DiffSynth Union LoRA | `qwen_image_union_diffsynth_lora.safetensors` | canny, depth, pose, lineart, softedge, normal, openpose | `models/loras/` |
| OpenArt InstantX 流程 | [Qwen+Image+InstantX+Controlnet深度控制V1](https://openart.ai/workflows/t8star/qwenimageinstantxcontrolnetv1/RYODhE9ZZkiFV14tdMkq) | 深度等 | 标题为 InstantX，属**旧栈** |
| Civitai：Edit + OpenPose | [Qwen Image Edit + OpenPose CtrlNet](https://civitai.com/models/1966651/qwen-image-edit-openpose-ctrlnet) | OpenPose + Edit | 发布 2025-09；Base=Qwen；**非 2.1** |
| MyAIForce：Edit 2511 姿势迁移 | https://myaiforce.com/qwen-image-edit-pose-transfer/ | 人像 + 清洗后姿态照 + DWPose 三图 | **Qwen Edit 2511**，非 2.1；思路可借鉴到 2.1 多图 Edit |

---

## 6. 节点包与模型文件速查

### 节点 / 包

| 名称 | 作用 | 是否需联网跑图 |
| --- | --- | --- |
| ComfyUI 原生 Qwen Image 2.1 | T2I / Edit / Cache | 否（下好权重后） |
| `qwen-image-2-1-fun-controlnet-union-t8` | UNION Loader / Apply / Reference Encode | 否 |
| `comfyui_controlnet_aux`（或 AIO Aux） | DWPose、Depth、Canny、Lineart… | 否 |
| VideoX-Fun 脚本 | 非 Comfy 推理备选 | 否 |

### 模型文件

| 文件 | 放置 |
| --- | --- |
| `Qwen-Image-2.1-Fun-Controlnet-Union.safetensors`（官方）或 `…-ComfyUI.safetensors`（T8）或 Kijai `qwen_image_2.1_fun_controlnet_union_*.safetensors` | `controlnet/` 或 `model_patches/`（视加载器） |
| `qwen_image_2.1_int8_convrot.safetensors` | `diffusion_models/` |
| `qwen3vl_8b_int8_convrot.safetensors` | `text_encoders/` |
| `qwen_image_2.1_vae_bf16.safetensors` | `vae/` |

---

## 7. 硬件粗要求（文档/社区口径）

- Fun ControlNet 模型卡：transformer + Qwen3-VL **难以整模塞进单张消费级 GPU**；推荐 `model_group_offload` 或 `model_cpu_offload_and_qfloat8`（VideoX-Fun 路径）
- Comfy int8_convrot 栈：权重约十余 GB 量级；社区称 **24GB（如 4090）可跑** 约 1K 档；**32GB（5090）** 更宽裕，2K 更吃显存
- 官方 Edit 文档举例：RTX 5090 上大参考图 `resolution=0` 可达约 12MP、约 6 s/it；`resolution=1024` 可到约 0.3 s/it — 说明**分辨率是成本主因**
- T8 说明：int8_convrot 使 **30 系**也能跑（无 fp8 路径时）
- 本调研**未**做本地压测

---

## 8. 推荐落地路径（本地）

1. 更新 ComfyUI ≥ 0.37.0  
2. 下载 Comfy-Org 2.1 int8 DiT + VL + VAE  
3. 安装 T8 节点；下载 `Qwen-Image-2.1-Fun-Controlnet-Union-ComfyUI.safetensors` → `models/controlnet/`  
4. 安装 `comfyui_controlnet_aux`；从姿态照片抽 DWPose 或 Depth  
5. 拖入 `qwen21_union_pose_reference_edit.json`：参考槽接真人照，控制槽接骨架/深度图  
6. 需要第二张服装/多角度脸：接到 `reference_image_2`，prompt 写清 `<image1>`/`<image2>`  
7. 难姿势：strength 0.7～0.8 + 文案描述；必要时换 Depth 或加 inpaint mask  

若暂时只要「改姿势、接受软控制」：官方 **Image Edit** 多图模板即可，免下 7.5GB Union。

---

## 9. 来源索引

1. https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1  
2. https://docs.comfy.org/tutorials/image/qwen/qwen-image  
3. https://huggingface.co/alibaba-pai/Qwen-Image-2.1-Fun-Controlnet-Union  
4. https://huggingface.co/t8star/Qwen-Image-2.1-Fun-Controlnet-Union-Comfy  
5. https://huggingface.co/Comfy-Org/Qwen-Image-2.1  
6. https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8  
7. https://comfyui-wiki.com/en/news/2026-09-24-qwen-image-2-1-fun-controlnet-union  
8. https://github.com/Comfy-Org/ComfyUI/pull/16519  
9. https://www.youtube.com/watch?v=JNLbghoDCuc  
10. https://huggingface.co/InstantX/Qwen-Image-ControlNet-Union  
11. https://civitai.com/models/1966651/qwen-image-edit-openpose-ctrlnet  
12. https://myaiforce.com/qwen-image-edit-pose-transfer/  
13. https://openart.ai/workflows/t8star/qwenimageinstantxcontrolnetv1/RYODhE9ZZkiFV14tdMkq  
14. https://registry.comfy.org/nodes/qwen-image-2-1-fun-controlnet-union-t8
15. https://github.com/Work-Fisher/ComfyUI-Fisher-Pose  
16. https://spicyapi.ai/workflows/comfyui-qwen-multi-character-edit  
17. https://github.com/QwenLM/Qwen-Image-2.1（多参考多主体合图示例）  
18. https://comfy.icu/node/QwenImage21UnionReferenceEncode    

---

*全文基于公开网页/仓库/文档交叉核对；未宣称本机出图实测。*
