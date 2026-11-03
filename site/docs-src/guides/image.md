---
title: 图像
---

# 图像

从文生图、编辑、修复放大到深度图；先选服务与工作流包，再写提示词。

当前仓库主推 **Qwen-Image 2.1** 系列（与视频用的 MiniMax H3 **不是同一套模型**）。另有 **FLUX.3 Image Klein** 蒸馏三包，以及传统 SD checkpoint 包作备用。换下拉里的文件名时，按下面「成套」选，不要混系列、混量化、混 GGUF。

## 当前生图系列一览

| 系列 | 能力 | 工作流包 | 模型怎么选 |
|------|------|----------|------------|
| **官方** | `t2i` | `qwen_image_21` | UNET + TE + VAE；默认官方 INT8 |
| **越狱** | `t2i` | `qwen_image_21_uncensored` | 默认 UC UNET；另有 **Uncensored LoRA** 开关（同视频 Turbo 控件） |
| **官方** | `i2i` 整图 | `qwen_image_21_edit` | 三件套 + 1 张原图 |
| **越狱** | `i2i` 整图 | `qwen_image_21_edit_uncensored` | UC + LoRA 开关 |
| **官方** | `i2i` 多参考 | `qwen_image_21_edit_multi` | 三件套；2～4 张参考图 |
| **越狱** | `i2i` 多参考 | `qwen_image_21_edit_multi_uncensored` | UC + LoRA 开关 |
| **官方** | `i2i` 重绘 | `qwen_image_21_inpaint` | 三件套；原图 + 蒙版 |
| **越狱** | `i2i` 重绘 | `qwen_image_21_inpaint_uncensored` | UC + LoRA 开关 |
| **FLUX.3 Klein** | `t2i` | `flux3_klein` | 蒸馏 INT8 + Qwen3-VL-4B + w4a8 扩展器 + flux2-vae |
| **FLUX.3 Klein** | `i2i` 单图 | `flux3_klein_edit` | 同上四件套；1 张原图 |
| **FLUX.3 Klein** | `i2i` 多参考 | `flux3_klein_edit_multi` | 同上；2～4 张参考图 |
| **传统 SD** | `t2i` | `t2i_basic` | 只选 `checkpoints/` 一个整包，无 UNET/TE/VAE |
| **参考图调色** | `i2i` | `qwen_edit_2511_color_grade` | Edit-2511 + 调色 LoRA；原图 + 参考图。见下文 |
| **Union 深度生图** | `i2i` | `qwen_image_21_union_depth` | 2.1 三件套 + Fun ControlNet Union；只上传深度图 |
| **Union 参考改姿** | `i2i` | `qwen_image_21_union_reference` | 同上；第 1 张人物照，第 2 张深度图 |
| **换衣** | `i2i` | `qwen_image_21_outfit_swap` | 官方三件套 + Outfit Swap LoRA；第 1 张人物照，第 2 张衣服 |
| 放大 | `upscale` | `upscale_basic` | `upscale_models/`，非生图 |

官方四包与越狱四包**图结构对应**；差别是默认 UNET 与是否声明 `accel`（LoRA）。不要在官方包里只改 UNET 却指望出现 LoRA 开关——要挂 LoRA 请选 `*_uncensored` 包。

## FLUX.3 Image Klein

三个包都是蒸馏版，图内已经接好 prompt upsampler（提示词扩展器）。ComfyUI 需要 **≥ 0.41**。采样固定 CFG 1、euler、simple，步数 16。24GB 用下面这一套，不要换成 bf16 或 NVFP4：

| 槽位 | 目录 | 文件 |
|------|------|------|
| UNET | `diffusion_models/` | `flux3-image-klein-int8-convrot.safetensors` |
| 文本编码器 | `text_encoders/` | `qwen3vl_4b_int8_convrot.safetensors` |
| 扩展器 | `text_encoders/` | `qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors` |
| VAE | `vae/` | `flux2-vae.safetensors` |

CLIPLoader 的 type 保持 `flux3`。这套没有公开的图像底模越狱版，不要把 Qwen 的 UC UNET 或 LoRA 换进来。

### 文生图：`flux3_klein`

侧栏「图像 → 文生图」。图像服务选 ComfyUI，工作流包选 `flux3_klein`。

1. 四个模型保持上表。扩展器会把短提示词扩成英文长描述，不要把它换成 Qwen-Image 的 8B 或视频用的 32B。
2. 提示词写画面内容即可，例如「窗边的陶瓷杯，柔和侧光」。
3. 宽高默认 1024，长边不超过 1536。页面上的步数会覆盖包内默认值，蒸馏版改回 **16**。CFG 固定为 1，页面上没有这项。
4. 24GB 显存张数保持 1。扩展器本身占显存。

### 单图编辑：`flux3_klein_edit`

侧栏「图像 → 图生图与编辑」。只上传 **1 张**原图。

1. 提示词写改什么、保留什么，例如「把背景换成海滩，人脸和姿势保持不变」。
2. 没有宽高控件。输出尺寸跟原图，编码前参考图缩到约 1MP。
3. 步数 16，权重与文生图同一套。
4. 这个包没有画框。要涂抹局部重绘，改用 `qwen_image_21_inpaint`。

### 多图编辑：`flux3_klein_edit_multi`

同一页，工作流包换成 `flux3_klein_edit_multi`。

1. 至少 2 张、最多 4 张。第 1 张是主图，决定输出尺寸（先缩到约 2MP，再按约 1MP 编码）。第 3、4 张可以不传；没传的槽会断开，不会拿占位图去跑。
2. 提示词按上传顺序写「第一张」「第二张」，例如「第一张里的人站在第二张的秋日森林观景台前」。这里不用 Qwen 多图包的 `` `<image1>` ``、`` `<image2>` ``。
3. 步数 16，CFG 固定为 1。

## 参考图调色

包名 `qwen_edit_2511_color_grade`，能力 `i2i`。侧栏「图像 → 图生图与编辑」。

它只换颜色：Qwen-Image-Edit-2511 加 Color Grade Transfer LoRA 生成约 1MP 的调色结果，再由 KJNodes 的 ColorMatch 把颜色贴回全尺寸原图，不重绘像素。

Comfy 环境需要：

- 节点包 [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)（提供 `ColorMatch`）
- 在 Comfy 的 Python 环境执行 `pip install color-matcher`

| 槽位 | 目录 | 文件 |
|------|------|------|
| UNET | `diffusion_models/` | `qwen_image_edit_2511_fp8mixed.safetensors` |
| 文本编码器 | `text_encoders/` | `qwen_2.5_vl_7b_fp8_scaled.safetensors` |
| VAE | `vae/` | `qwen_image_vae.safetensors` |
| 调色 LoRA | `loras/` | `QIE-2511-Color-Grade-Transfer-LoRA.safetensors` |

页面上：

1. 工作流包选 `qwen_edit_2511_color_grade`。
2. 第 1 张是要保留内容和分辨率的摄影原图，第 2 张是只借用颜色的参考图。顺序不要反。
3. **提示词留空**。留空会使用包内触发句 `Transfer ONLY the color grading from Image 2 onto Image 1`。写成普通修图指令（例如换背景、换衣服）会离开这条调色链路。
4. 步数 **20**，CFG **4**。这是不开 Lightning 时的官方模板。LoRA 强度默认 1。
5. 颜色迁移算法默认 `hm-mvgd-hm`，也可填 `mkl`、`hm`、`reinhard`、`mvgd`、`hm-mkl-hm`。调色强度 1 为完全套用参考色，0.7 更淡，0 等于原图。

这四件权重和 Qwen-Image 2.1 不是一套。下拉里如果出现 `qwen_image_2.1*`、`qwen3vl_8b*`、`qwen_image_2.1_vae*`，不要选。CLIPLoader 的 type 保持 `qwen_image`。24GB 用 fp8mixed；显存够可换同代 bf16，文本编码器仍用 `qwen_2.5_vl_7b`，VAE 仍用 `qwen_image_vae`。

## Qwen-Image 2.1：成套选模型（不要混搭）

选中包后，参数区有 UNET / TE / VAE 下拉。界面允许单独改名，但**必须按套餐整组选**。

### 套餐表（推荐）

| 套餐 | 主模型 UNET（`diffusion_models/`） | 文本编码器 TE（`text_encoders/`） | VAE（`vae/`） | LoRA（`loras/`，仅越狱包） |
|------|-------------------------------------|-----------------------------------|---------------|---------------------------|
| **官方 INT8** | `qwen_image_2.1_int8_convrot.safetensors` | `qwen3vl_8b_int8_convrot.safetensors` | `qwen_image_2.1_vae_bf16.safetensors` | 无（官方包无 accel） |
| **越狱 UC INT8** | `qwen-image-2.1-UC-int8_convrot.safetensors` | **同上** `qwen3vl_8b_*` | **同上** | 推荐 `qwen-image-2.1-uncensored-lora.safetensors`（可关） |
| **官方更高精度** | `qwen_image_2.1_bf16.safetensors` 等 | 同族 `qwen3vl_8b_*` | 同上 VAE | 无 |

### Uncensored LoRA 怎么用

1. 工作流包选 **`qwen_image_21_uncensored`**（或对应的 `*_edit*_uncensored` / `*_inpaint_uncensored`），不要选无 `_uncensored` 后缀的官方包。
2. 页面出现与视频 Turbo **同一套**控件：**Uncensored LoRA** 开/关 → 开时可选 LoRA 文件与强度（默认开、推荐 `qwen-image-2.1-uncensored-lora.safetensors`、强度 1.0）。
3. **关**：图中摘掉 `LoraLoaderModelOnly`，只用 UC UNET（仍可能比官方更松）。
4. **开**：LoRA 挂在 Cache 之后、采样之前；强度过高可能过拟合，可从 0.7～1.0 试。
5. 文件放在 Comfy 的 `models/loras/`；下拉按文件名含 `uncensored` 过滤。UC UNET 放在 `diffusion_models/`。
6. 快速创作「生成插图」选越狱包时，同样会出 LoRA 开关。

官方包里即使手动把 UNET 改成 UC，也**不会**自动加载该 LoRA。

### 配对规则（必读）

1. **TE** 必须是 `qwen3vl_8b*`；**不要**选视频 H3 的 `qwen3vl_32b*` / `*_minimax_h3_*`。
2. **主模型** 必须是 `qwen_image_2.1*` / `qwen-image-2.1*`；**不要**选 `minimax_h3_*`、`wan_*`。
3. **VAE** 用 `qwen_image_2.1_vae*`；**不要**选视频 VAE。
4. **只选 `.safetensors`**，勿选 GGUF。
5. 越狱套餐：UNET 用 UC，TE/VAE 保持官方那两行；LoRA 用带 `uncensored` 的文件。
6. **CLIPLoader type** 保持 `qwen_image`。

下拉里认准 **`qwen_image` / `qwen-image` / `qwen3vl_8b` / `uncensored`**，避开 **`minimax` / `32b` / `h3` / `.gguf`**。

## 文生图

侧栏「图像 → 文生图」。选图像 Provider + `t2i` 工作流包。

- **`qwen_image_21`**：官方三件套。
- **`qwen_image_21_uncensored`**：UC + Uncensored LoRA 开关。
- **`flux3_klein`**：FLUX.3 Klein 蒸馏文生图。四件套、步数 16、扩展器不要换掉。详见上文「FLUX.3 Image Klein」。
- **`t2i_basic`**：`checkpoints/` 整包。

提示词可用右侧按钮经已配置的 LLM 改写。宽、高、步数、种子、张数按各包默认即可；`flux3_klein` 的步数改回 16。种子 `-1` 为随机，多张时从该种子逐张加 1。

## 图生图与编辑

侧栏「图像 → 图生图与编辑」。包能力一般为 `i2i`。官方 / 越狱成对出现；越狱包有 LoRA 开关。

- **整图编辑**：`qwen_image_21_edit` / `qwen_image_21_edit_uncensored`。只使用 **1 张**原图，接到 `TextEncodeQwenImage21` 的 `image_1`。上传框可以多选，但张数超过这个包的图像槽（这里是 1）时「开始」不可点。接口若仍传入多张，也只取第一张，其余不进工作流。提示词写要改什么、保留什么，例如「把背景换成海滩，人脸和姿势保持不变」。
- **多参考编辑（多人放进同一场景）**：`qwen_image_21_edit_multi` / `…_uncensored`。至少 2 张、最多 4 张，按上传顺序对应 `` `<image1>` `` … `` `<image4>` ``。第 1 张是主图，决定画布比例。把几张图里的人物放到同一场景就用这个包，例如「让 `<image1>` 的人物和 `<image2>` 的人物并排站在同一间室内，统一光照」。标记必须写成 `` `<image1>` `` 这种没有空格的形式；「image 1」或「图一」不会绑到对应参考图。两张都是人物照时，模型会把两个人都画进画面。只想保留其中一个人时，另一张用没有人的场景，或改回整图编辑、把背景直接写进提示词。
- **局部重绘**：`qwen_image_21_inpaint` / `…_uncensored`。先原图后蒙版；白=重画，黑=保留。`grow` 扩白区。
- **FLUX.3 单图编辑**：`flux3_klein_edit`。1 张原图，提示词写修改指令，步数 16。详见上文。
- **FLUX.3 多图编辑**：`flux3_klein_edit_multi`。2～4 张，也能把多张图里的人物放进同一场景。提示词用「第一张」「第二张」，不用 Qwen 的 `` `<image1>` ``。步数 16。详见上文。
- **跟参考图调色**：`qwen_edit_2511_color_grade`。第 1 张原图、第 2 张调色参考，提示词留空，步数 20、CFG 4。模型与节点要求见上文「参考图调色」。
- **深度图生人**：`qwen_image_21_union_depth`。只上传 1 张深度图，提示词写人物外观和场景，动作跟深度图。步数 40，CFG 固定 1。
- **人物照按深度图改动作**：`qwen_image_21_union_reference`。第 1 张人物照，第 2 张深度图。控制类型默认 Depth；若第 2 张是 OpenPose 骨架，改成 Pose。脸被带偏时把控制强度降到 0.7–0.8。两张图宽高比尽量一致。

这两个 Union 包需要 ComfyUI ≥ 0.37，并安装节点 [Qwen Image 2.1 Fun ControlNet Union (T8)](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8)。默认主模型是越狱 `qwen-image-2.1-UC-int8_convrot.safetensors`，文本编码器和 VAE 仍与 `qwen_image_21` 相同。另把 `Qwen-Image-2.1-Fun-Controlnet-Union-ComfyUI.safetensors` 放到 `controlnet/`，文件名必须以 `Qwen-Image-2.1-Fun-Controlnet-Union` 开头。权重：[t8star/Qwen-Image-2.1-Fun-Controlnet-Union-Comfy](https://huggingface.co/t8star/Qwen-Image-2.1-Fun-Controlnet-Union-Comfy)。

- **换衣**：`qwen_image_21_outfit_swap`。第 1 张人物照，第 2 张衣服（平铺或穿在别人身上，尽量裁到衣服本身）。提示词留空会用默认句：把 image 1 的人换成 image 2 的衣服，脸、头发、手、姿势和背景不变。想留鞋子时，把句尾改成 `Keep their own shoes and legwear.`。多人合影把 `the person` 改成位置或发型，不要用衣服来指人。分辨率默认 0，按人物照原尺寸出图。步数 25，CFG 固定 1，LoRA 强度 1.0。主模型默认官方 INT8（这条 LoRA 在官方 2.1 上测过）。把 `qwen-image-2.1-outfit-swap.safetensors` 放到 `loras/`，来源：[ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA](https://huggingface.co/ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA)。ComfyUI ≥ 0.38。

上传可以分多次添加，也能单独删掉某一张。能提交的张数等于当前包的图像槽数量：整图编辑 1 张，多参考 2～4 张，重绘是原图加蒙版。多参考和重绘的缩略图带角标。

## 修复与放大

侧栏「图像 → 修复与放大」，包 `upscale_basic`。走 Upscale 模型（约 4×），不是生图。权重放在 ComfyUI `upscale_models/`。提示词可留空。

## 深度图生成

侧栏「图像 → 深度图生成」。这里不跑 Comfy 工作流，而是把图片发给已启用的 **Liber Depth**（本机插件或局域网里的深度服务）。越亮表示离镜头越近。一次可以转多张；结果文件名是原名加 `_depth.png`，例如 `photo.jpg` 变成 `photo_depth.png`。

1. 先在「资源 → 插件」安装并启用本机深度插件，或在「服务提供方」里启用一份 Liber Depth 并填上地址（本机默认 `http://127.0.0.1:5556`）。
2. 页面上选深度服务、深度模型和硬件（`cuda` 或 `cpu`）。下拉里只出现该服务商已启用的模型。
3. 上传框可多选、可分多次添加，也可以拖拽。下方缩略图可单独删除。同一张图（文件名、大小、修改时间都相同）不会重复加入。
4. 点「开始转换」。本批结果显示在右侧，也可以从历史深度图里再打开或下载。

安装插件时只会下载 `dpt_swin2_large_384.pt`（SwinV2 Large，边长 384）。一次转换只用一个模型。其余 MiDaS 权重要自己放到模型目录，再在服务提供方里打开对应开关，这里才会出现：

| 模型 id | 作用 |
|---------|------|
| `dpt_swin2_large_384` | 默认。安装时自动下载 |
| `dpt_beit_large_512` | BEiT Large，边长 512，边缘更细，更慢 |
| `dpt_swin2_tiny_256` | SwinV2 Tiny，边长 256，更快，细节少 |
| `dpt_large_384` | 上一代 DPT Large |
| `dpt_hybrid_384` | DPT Hybrid，体积更小 |
| `midas_v21_small_256` | MiDaS v2.1 Small，最轻 |

目录里没有对应 `.pt` / `.pth` 时，选这项不会按该权重推理。生成出的深度图可以再拿到「图生图与编辑」的 Union 包里做深度图生人或改动作。

---
