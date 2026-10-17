# MiniMax H3：模型清单、Turbo 加速与越狱增强工作流开发计划

> 状态：计划文档，未改动代码。编写日期 2026-10-18。
>
> 参考：[零度博客 25046：MiniMax H3 Turbo LoRA + 越狱模型](https://www.freedidi.com/25046.html)（本地归档 `D:\BaiduSyncdisk\mydir\Comfy\docs\25046-minimax-h3-turbo-uncensored.md`、`25046.html`）

## 0. 环境约定

| 项 | 值 |
|----|----|
| 本地 Comfy 资源目录 | `D:\BaiduSyncdisk\mydir\Comfy`：模型在 `models\`，自定义节点在 `custom_nodes\`，工作流在 `工作流\`，相关说明在 `docs\` |
| 部署主机 | `ps@10.10.12.140`（SSH 凭据见本地运维备忘，勿写入仓库） |
| ComfyUI 工作目录 | `/home/ps/workspace/ComfyUI`，模型目录 `/home/ps/workspace/ComfyUI/models/` |
| 远程硬件 | 2 × RTX 3090 24GB，内存 62GB，磁盘剩余约 126GB |
| 远程 ComfyUI 启动参数 | `python main.py --listen 0.0.0.0 --port 8188 --enable-manager --lowvram --reserve-vram 8` |
| 远程网络 | **访问不到 huggingface.co**，模型要先下到本地，再用 `scp` 传过去 |

远程 ComfyUI 已有的原生 H3 支持（通过 `/object_info` 实测）：`MiniMaxH3ImageToVideo`、`ResolutionSelector`、`ComfyMathExpression`、`CreateVideo`、`SaveVideo`、`LoraLoaderModelOnly`、`PreviewAny`、`PrimitiveFloat`；`comfy/model_sampling.py` 里有 `ModelSamplingAV`（音视频双调度原生支持）。

远程**缺少**：`MiniMaxH3PromptEnhancer`、`MiniMaxH3GenerationTailLoader`（需安装 Guide 节点包）。

---

## 1. 两个版本 MiniMax H3 的文件清单

两个版本**共用同一个视频扩散主模型（DiT, Diffusion Transformer）和两个 VAE（变分自编码器）**，区别只在文本编码器（TE, Text Encoder，即 `CLIPLoader` 加载的 Qwen3-VL-32B）：

- **官方版**：Comfy-Org 发布的 Qwen3-VL-32B，会拒绝部分敏感提示词。
- **越狱版（Uncensored / Heretic）**：ethanfel 基于 `Qwen3-VL-32B-Instruct-ultra-uncensored-heretic` 打包，用消融（abliteration）去掉拒答行为，在 `CLIPLoader` 里直接替换官方 TE 即可。

### 1.1 共用文件

| 文件 | 目录 | 大小 | 本地 | 远程 | 说明 |
|------|------|------|------|------|------|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `diffusion_models` | 19.5 GiB | 有 | 有 | FL2VA（首尾帧 → 视频 + 音频）主模型，剪枝（pruned）+ INT8 ConvRot 量化 |
| `minimax_h3_video_vae_fp16.safetensors` | `vae` | 4.85 GiB | 有 | 有 | 视频 VAE |
| `minimax_h3_audio_vae_fp32.safetensors` | `vae` | 0.56 GiB | 有 | 有 | 音频 VAE（H3 同时输出 32kHz 立体声） |

主模型的其他可选规格（[Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/diffusion_models)，目前都没下载）：

| 文件 | 大小 | 适用场景 |
|------|------|----------|
| `minimax_h3_fl2va_int8_convrot.safetensors` | 31.7 GiB | 未剪枝 INT8；T8 转换版 Turbo LoRA 用标准 LoRA 加载器时需要它，见第 2 节 |
| `minimax_h3_fl2va_pruned_fp8_scaled.safetensors` | 19.5 GiB | 剪枝 FP8 |
| `minimax_h3_fl2va_pruned_w6a8.safetensors` | 14.9 GiB | 最小量化规格，显存最紧张时用 |
| `minimax_h3_ref2va_*` | 同上 | Ref2VA（多参考图/视频/音频 → 视频）主模型，和 FL2VA 不能混用 |

### 1.2 官方版专用

| 文件 | 目录 | 大小 | 本地 | 远程 | 说明 |
|------|------|------|------|------|------|
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `text_encoders` | 14.6 GiB | 有 | 有 | 官方 TE（NVFP4/AWQ 量化）。3090 不是 Blackwell 架构，NVFP4 走回退路径，能用但不是最快 |
| `qwen3vl_32b_h3_instruct_generation_tail_50_63_nvfp4_awq.safetensors` | `text_encoders` | 5.0 GiB | 无 | 无 | **可选**：官方版要用提示词增强时配这个 tail（和 nvfp4 TE 同族） |

官方 TE 的其他规格：`qwen3vl_32b_minimax_h3_int8_convrot`（25.3 GiB）、`bf16`（48 GiB）。

### 1.3 越狱版专用

| 文件 | 目录 | 大小 | 本地 | 远程 | 说明 |
|------|------|------|------|------|------|
| `qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors` | `text_encoders` | 24.55 GiB | 下载中（约 4.5/24.55 GiB） | 无 | 越狱 TE（第 0–49 层 + 视觉塔），替换官方 TE |
| `qwen3vl_32b_h3_generation_tail_50_63_int8_convrot.safetensors` | `text_encoders` | 7.09 GiB | 下载中（约 4.0/7.09 GiB） | 无 | 越狱族生成尾（第 50–63 层 + LM head），**只有增强工作流需要** |

来源：[ethanfel/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot](https://huggingface.co/ethanfel/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot)。BF16 满血版 TE 有 47.97 GiB，24GB 显卡不建议用。

**配对规则**：tail 要和 TE 同族。越狱 TE 配 `qwen3vl_32b_h3_generation_tail_50_63_*`，官方 Instruct TE 配 `qwen3vl_32b_h3_instruct_generation_tail_50_63_*`。tail 不是独立模型，它复用所连 TE 的 embedding、视觉塔和 0–49 层。

### 1.4 两个版本对照

| 项 | 官方版 | 越狱版 |
|----|--------|--------|
| TE 文件 | `qwen3vl_32b_minimax_h3_nvfp4_awq` | `qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot` |
| `CLIPLoader.type` | `minimax` | `minimax` |
| 敏感提示词 | 可能被弱化或改写 | 拒答率约 4/100（原版 99/100），不保证完全无限制 |
| 内存/显存 | 较小 | TE 大约 10 GiB 更多；作者在 5090 上实测编码时显存约 24.7 GiB |
| 远程就绪 | 已就绪 | 需上传 TE（+ tail） |

**内存风险**：远程只有 62GB 内存，ComfyUI 常驻已占约 37GB。越狱 TE 24.5 GiB + 主模型 19.5 GiB + tail 7.1 GiB 已经接近上限。上线前要实测一次，确认没有内存换页抖动或 OOM（内存溢出），必要时用单独的 Comfy 实例只跑 H3。

### 1.5 部署到远程（越狱版）

```bash
# 在本地 PowerShell 执行（本地下载完成并校验 SHA-256 之后）
scp "D:\BaiduSyncdisk\mydir\Comfy\models\text_encoders\qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors" ps@10.10.12.140:/home/ps/workspace/ComfyUI/models/text_encoders/
scp "D:\BaiduSyncdisk\mydir\Comfy\models\text_encoders\qwen3vl_32b_h3_generation_tail_50_63_int8_convrot.safetensors" ps@10.10.12.140:/home/ps/workspace/ComfyUI/models/text_encoders/
```

SHA-256 校验值：

- 越狱 TE：`d84547412144b7c50a6ec77437a889b869d3ace88da77ef1775d3d2a4901c192`
- 越狱 tail：`b5bb9bb8dc87cf11cbee241a2d95d6d42fe52cf695ed26c093ac321f31160b20`

---

## 2. Turbo 加速模型

### 2.1 原理

Turbo LoRA（低秩适配权重）是针对 MiniMax H3 DiT 蒸馏训练的少步数 LoRA。挂到主模型上后，采样步数从约 20 步降到 4–8 步，采样阶段提速约 3–5 倍。文本编码、VAE 解码这些步骤的耗时不受影响。

### 2.2 文件

| 文件 | 来源 | 本地 | 远程 | 说明 |
|------|------|------|------|------|
| `minimax_h3_turbo_4step_comfyui.safetensors`（本地改名） | [t8star 转换版](https://huggingface.co/t8star/minimax-h3-4step-turbo-loras-comfyui-exp)：`minimax_h3_turbo_4步加速_comfyui.safetensors` | 已下载 0.73 GiB | 无 | v1 系列初版，T8 转换为 ComfyUI 标准 LoRA 格式 |
| `minimax_h3_turbo_v4_step600_comfyui_T8-convert.safetensors` | t8star 转换版 | 已下载 0.73 GiB | 无 | v4-600（非 EMA）转换版 |
| `minimax_h3_turbo_v4_step600_ema.safetensors` | [larryvrh 原版](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora) | 无 | 无 | **原作者推荐的当前最佳版本**，配 Turbo 节点包使用 |

### 2.3 两种接法（关键差异）

**方案 A：原作者节点包（推荐）**

- 节点包：[Larryvrh/ComfyUI-MiniMax-H3-Turbo](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo)，提供两个节点：`MiniMax-H3 Turbo LoRA`（MODEL → MODEL）和 `MiniMax-H3 Turbo Sampler`（→ SAMPLER）。
- **兼容剪枝主模型**：节点会自动检测 pruned 主模型并补回时间条件，所以现有的 `minimax_h3_fl2va_pruned_int8_convrot` 可以直接用，不用再下 31.7 GiB 的未剪枝主模型。
- 接法：`UNETLoader → MiniMax-H3 Turbo LoRA → BasicGuider`；`BasicScheduler` 设为 `simple`、6–8 步；采样器用 `MiniMax-H3 Turbo Sampler`。远程 ComfyUI 已原生支持 `ModelSamplingAV`，这时用自带的 `KSamplerSelect(euler)` 也能得到相同结果。
- 强度保持 1.0；有拖影就上调到 1.05–1.2，画面过锐就下调到 0.8–0.95。
- `low_vram` 开关：关（默认，最清晰）；开（把 LoRA 合并进权重，峰值显存最低，但在量化主模型上画面偏软）。3090 爆显存时再打开。

**方案 B：T8 转换版 + 标准 LoRA 加载器**

- 节点：ComfyUI 自带的 `LoraLoaderModelOnly`（远程已有）。
- T8 作者注明：**必须用未剪枝的 `minimax_h3_fl2va_int8_convrot.safetensors`，不能用 pruned 版**；采样器 `euler`、调度器 `beta`；4 步会爆音，要提高到 8–10 步，或者用他的双时钟采样器（[comfyui-minimax-h3-audio-T8](https://github.com/T8mars/comfyui-minimax-h3-audio-T8)）。
- 代价：要多下载 31.7 GiB 主模型，远程磁盘和内存压力更大。

**结论**：本地已下载的两个 T8 文件在现有 pruned 主模型 + 标准加载器下**不保证能正常出片**。建议远程走方案 A：装 Turbo 节点包，并补下 `minimax_h3_turbo_v4_step600_ema.safetensors`（744 MB）。

### 2.4 加速模型是否只支持 MiniMax

**是。** LoRA 权重和 H3 DiT 的层结构一一对应，只能加速 MiniMax H3（FL2VA 和 Ref2VA 主模型都可以），挂到 Wan、Qwen-Image 等模型上会因为键名或形状不匹配而报错或失效。

不过「加速开关」这个机制本身是通用的：

| 模型族 | 加速方式 | 现状 |
|--------|----------|------|
| MiniMax H3 | Turbo LoRA（本节） | 待接入 |
| Wan 2.2 | lightx2v / FusionX 类少步 LoRA（本地有 `wan-fusionx` 目录） | 待接入，同一套机制 |
| Qwen-Image 2.1 | 直接换 turbo 主模型（`qwen_image_2.1_turbo_*`），不是 LoRA | 现有包可通过换模型实现 |

所以开发上要做成**通用的「工作流包加速开关」**，再由每个包声明自己的 LoRA 节点和可选 LoRA 文件过滤规则，避免用户把 MiniMax 的 LoRA 挂到 Wan 上。

### 2.5 当前项目支持情况

- 视频生成（图生视频、快速创作·生成视频、自定义素材·素材动画）全部由工作流包驱动，见 `backend/liberastra/services/workflows.py`。
- **没有加速开关**：manifest 的每个参数只能映射到一个节点字段（`node` + `field`），不能做「开启时改 LoRA、步数、采样器多个字段，关闭时把 LoRA 节点从图里摘掉」这种联动。
- **现在就能用的折中做法**：把 LoRA 节点直接写进包的 `workflow.json`，用 `options_from: loras` 暴露 `lora_name` 下拉框，再把 `steps` 默认值设为 8。缺点是这个包永远开着加速，要关掉只能再做一个不带 LoRA 的包。

### 2.6 开发计划：用户可开关加速、可选择加速模型

#### 目标

1. 视频类页面中，如果所选工作流包声明了加速能力，就显示「Turbo 加速」开关和「加速模型」下拉框。
2. 开启时：注入所选 LoRA，步数、采样器、调度器切换到加速预设。
3. 关闭时：从提交给 ComfyUI 的图里摘掉 LoRA 节点，把下游连线改接回 LoRA 的输入源，恢复原始步数。
4. 下拉框只列出与包同族的 LoRA（按文件名规则过滤），并标出推荐项。

#### manifest 扩展（草案）

```yaml
name: minimax_h3_i2v
capability: i2v
fps: 24
inputs:
  steps:
    node: "105:9"
    field: inputs.steps
    type: int
    default: 20
  sampler_name:
    node: "105:17"
    field: inputs.sampler_name
    type: str
    default: res_multistep
  # ……其他参数
accel:
  label: Turbo 加速
  family: minimax_h3          # 用于和 LoRA 文件做兼容性提示
  default_enabled: false
  node: "105:200"             # 加速 LoRA 节点（Turbo LoRA 或 LoraLoaderModelOnly）
  bypass_input: model         # 关闭时：下游对 ["105:200", 0] 的引用改接到该节点 model 输入的来源
  lora:
    field: inputs.lora_name
    options_from: loras
    match: "minimax_h3_turbo" # 下拉框过滤规则（子串或正则）
    recommended: minimax_h3_turbo_v4_step600_ema.safetensors
  strength:
    field: inputs.strength
    default: 1.0
    min: 0.5
    max: 1.5
  preset:                     # 开启时覆盖的 inputs；用户手动改过的值优先
    steps: 8
    sampler_name: euler
```

#### 后端改动

| 文件 | 改动 |
|------|------|
| `backend/liberastra/services/workflows.py` | `WorkflowPack` 增加 `accel` 字段；`_load_pack` / `import_pack` 读取；`validate_pack` 校验 `accel.node` 存在、`bypass_input` 是连线类型；新增 `apply_accel(workflow, pack, enabled, lora, strength)`：开启时注入 LoRA 文件名和强度并应用 preset，关闭时删除节点并改写所有引用 `[node, 0]` 的下游输入 |
| `backend/liberastra/providers/comfyui/workflow.py` | `run_workflow_pack` 在 `apply_inputs` 之后调用 `apply_accel` |
| `backend/liberastra/schemas/workflow.py` | `WorkflowPackOut` 增加 `accel` |
| `backend/liberastra/api/routes/workflows.py` | `_to_out` 透出 `accel` |
| `backend/liberastra/api/routes/videos.py` | `i2v` / `quick` / `assets` 表单增加 `accel_enabled`、`accel_lora`、`accel_strength`（也可以统一放进现有 `inputs` JSON 的保留键 `__accel`） |
| `backend/liberastra/pipelines/simple.py`、`quick.py` | 把 accel 参数透传给 `_run_video_pack` 和逐镜 t2v 调用 |
| 提交前检查 | 开启加速时调用 `client.list_model_folder("loras")`，所选文件不存在就直接报中文错误（「ComfyUI 的 loras 目录里没有 xxx，请先上传」），不让任务跑到 ComfyUI 才失败 |

#### 前端改动

| 文件 | 改动 |
|------|------|
| `frontend/src/api/client.ts` | `WorkflowPackOut` 增加 `accel` 类型 |
| `frontend/src/components/WorkflowInputs.tsx` 或新建 `AccelControl.tsx` | 开关 + LoRA 下拉框（复用现有 `options_from` 拉取逻辑，再按 `match` 过滤，推荐项置顶）+ 强度步进器（复用 `number-stepper`）；开启时把 preset 的步数/采样器显示为默认值，并提示「推荐 6–8 步」 |
| `frontend/src/pages/VideoPackPage.tsx`、`VideoQuickPage.tsx`、自定义素材页 | 所选包有 `accel` 时渲染控件，随表单一起提交 |
| `frontend/src/pages/SystemSettingsPage.tsx`（可选） | 「默认开启视频加速」偏好，存入 `app_settings` |

#### 测试

- `backend/tests/test_workflows.py`：开启时 LoRA 字段和 preset 生效；关闭时 LoRA 节点被删除、下游连线改接正确、图里没有悬空引用；未声明 `accel` 的包行为完全不变。
- `backend/tests/test_video.py`：i2v 带 `accel_enabled=true/false` 两种提交，校验提交给假 ComfyClient 的图。
- 手工验收：远程同一张图、同一 seed，分别跑「20 步无加速」和「8 步 Turbo」，记录耗时和画质。

#### 里程碑

| 阶段 | 内容 | 产出 |
|------|------|------|
| M1 | 远程装 Turbo 节点包，上传 `v4_step600_ema`，在 Comfy 网页手工跑通 8 步 i2v | 可用的 API Format 工作流 |
| M2 | 后端 `accel` 机制 + 单测 | manifest 支持加速声明 |
| M3 | 前端开关、模型下拉框、偏好设置 | 用户可开关、可选模型 |
| M4 | 内置 `minimax_h3_i2v` 包（官方版 TE，带 accel）；文档 `使用文档.md` 补充 | 开箱可用 |
| M5（可选） | Wan 2.2 包接入 lightx2v 加速 LoRA，验证机制通用 | 多模型族加速 |

---

## 3. 越狱增强工作流 `video_minimax_h3_i2v_uncensored_enhancer.json`

文件位置：`D:\BaiduSyncdisk\mydir\Comfy\工作流\video_minimax_h3_i2v_uncensored_enhancer.json`（ComfyUI 画布格式，frontend 1.47.11）。

### 3.1 用途

**单张首帧图 + 简短提示词 → 用越狱版 Qwen3-VL-32B 先看图、再把提示词改写成符合 H3 规范的详细提示词 → MiniMax H3 生成带同步音效的视频。**

适合「提示词写得简单，或者内容会被官方 TE 弱化」的场景。注意：这个工作流**不包含 Turbo LoRA**，默认 20 步。

### 3.2 结构

顶层 7 个节点，核心是一个子图（subgraph）「Image to Video (MiniMax H3)」，里面有 19 个节点。

**顶层**

| 节点 | 作用 |
|------|------|
| `LoadImage` | 加载首帧图 |
| `ImageScaleToTotalPixels` | 按总像素缩放（宽高对齐到 32 的倍数） |
| `GetImageSize` | 读取缩放后的宽高（「Use Image Size」分组，用图片尺寸决定输出尺寸） |
| `ResolutionSelector` | 另一种方式：按宽高比和百万像素选尺寸（默认 16:9、0.4MP） |
| 子图 `Image to Video (MiniMax H3)` | 见下表；对外暴露 `first_frame`、`last_frame`、`prompt`、`width`、`height`、`duration`、`noise_seed`、`unet_name`、`clip_name`、两个 `vae_name` |
| `SaveVideo` | 保存到 `video/MiniMax_H3`，格式和编码为 `auto` |
| `MarkdownNote` | 尺寸参考表 |

**子图内部**

| 节点 | 来源 | 作用 | 关键参数 |
|------|------|------|----------|
| `UNETLoader` | 原生 | 加载 FL2VA 主模型 | `minimax_h3_fl2va_pruned_int8_convrot` |
| `CLIPLoader` | 原生 | 加载**越狱 TE** | `qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot`，`type=minimax` |
| `VAELoader` ×2 | 原生 | 视频 VAE、音频 VAE | |
| `MiniMaxH3GenerationTailLoader` | **Guide 节点包** | 选择生成尾文件。只是一个描述符，本身不占显存；增强时才临时加载第 50–63 层和 LM head | `qwen3vl_32b_h3_generation_tail_50_63_int8_convrot` |
| `MiniMaxH3PromptEnhancer` | **Guide 节点包** | 把 TE + tail 拼成可生成文本的完整 Qwen3-VL，看首帧图，把 `prompt` 改写成 H3 格式的详细提示词（镜头、运动、声音等段落） | `manual_prompt` ← 子图 `prompt`；`image` ← 首帧；`max_new_tokens=1400`；`sampling=sample`；`temperature=0.7`；`top_k=64`；`top_p=0.95`；`thinking=false`；`offload_after_generation=true` |
| `PreviewAny` ×2 | 原生 | 显示「增强后提示词」和「增强报告」 | |
| `PrimitiveFloat` + `ComfyMathExpression` | 原生 | 时长（秒）换算成帧数并吸附到 17k+5：`max(5, round(a*24)) + (5 - (max(5, round(a*24)) % 17)) % 17` | |
| `MiniMaxH3ImageToVideo` | 原生 | 用增强后的提示词、首帧（可选尾帧）、宽高、帧数生成条件和空 latent | |
| `RandomNoise` / `KSamplerSelect` / `BasicScheduler` / `BasicGuider` / `SamplerCustomAdvanced` | 原生 | 自定义采样 | `res_multistep`，`simple`，20 步，denoise 1 |
| `VAEDecode` / `VAEDecodeAudio` / `CreateVideo` | 原生 | 解码画面和音频，按 24fps 合成视频 | |

**注意**：`MiniMaxH3PromptEnhancer` 在 Guide 节点包里显示为「MiniMax H3 Prompt Enhancer (Legacy Qwen LLM)」，属于旧版节点，仍然注册可用。Guide 新版推荐 Plan v2 流程（`Project Setup → Shot → Prompt Merge → Structured Prompt Enhancer → Apply Reference Plan`），这份工作流没有用。

### 3.3 当前项目能否调用

| 层面 | 现状 |
|------|------|
| 直接导入这个 JSON | **不能**。它是画布格式（含 `nodes` / `links` / `definitions.subgraphs`），LiberAstra 只接受 API Format（`{节点id: {class_type, inputs}}`），见 `使用文档.md`「工作流包」一节 |
| 远程 ComfyUI | **缺 Guide 节点包**，缺越狱 TE 和 tail；原生 H3 节点齐全 |
| LiberAstra 后端 | **转成 API Format 包之后可以直接用**，不需要为 MiniMax 写专用代码：<br>• 图片输入走现有的 `type: image` 上传回填<br>• 宽高走 `multiple: 32`<br>• 帧数走 `align_base: 17` / `align_offset: 5` + 包顶层 `fps: 24`（页面按秒设置，提交时自动换算）<br>• TE 用 `options_from: text_encoders` 下拉框，**同一个包就能在官方版和越狱版之间切换**<br>• 输出走 `SaveVideo` |
| 展示增强后的提示词 | 后端已有 `extract_texts`，但 i2v 管线目前只取视频文件。展示增强结果属于增量功能（见 3.5 阶段 E3） |
| 开关增强 | 现在做不到（理由和加速开关相同）。可以复用 2.6 节的节点摘除机制：关闭时摘掉增强器，把 `prompt` 直接接到 `MiniMaxH3ImageToVideo.prompt` |

### 3.4 添加方法（不改代码即可完成的部分）

**第 1 步：远程装 Guide 节点包**（远程访问不到 GitHub 时，从本地已 clone 的目录打包上传）

```bash
# 本地 PowerShell：本地已有 D:\BaiduSyncdisk\mydir\Comfy\custom_nodes\ComfyUI-MiniMax-H3-Guide（commit 054ccb8）
scp -r "D:\BaiduSyncdisk\mydir\Comfy\custom_nodes\ComfyUI-MiniMax-H3-Guide" ps@10.10.12.140:/home/ps/workspace/ComfyUI/custom_nodes/
# 或者在远程上直接 clone（远程能访问 GitHub 时）
ssh ps@10.10.12.140
cd /home/ps/workspace/ComfyUI/custom_nodes && git clone https://github.com/ethanfel/ComfyUI-MiniMax-H3-Guide
```

Guide 节点包没有额外的 Python 依赖，装完重启 ComfyUI 即可。

**第 2 步：上传越狱 TE 和 tail**（见 1.5 节）

**第 3 步：在远程 Comfy 网页手工跑通**

1. 打开 `http://10.10.12.140:8188`，把工作流 JSON 拖进去，确认没有红色节点。
2. 跑一次，确认能出片，并记录耗时、显存、内存峰值。32B 提示词增强 + 20 步采样耗时很长，LiberAstra 的「ComfyUI 等待超时」要调到 3600 秒以上（「设置 → 运行参数」）。

**第 4 步：整理图再导出 API Format**

1. 去掉自动尺寸链路：删除 `ResolutionSelector`、`ImageScaleToTotalPixels`、`GetImageSize`，宽高由 LiberAstra 传入。
2. 去掉时长换算：删除 `PrimitiveFloat` 和 `ComfyMathExpression`，`MiniMaxH3ImageToVideo.length` 改成控件，由 LiberAstra 按 17k+5 吸附后传入。
3. `last_frame` 保持断开（LiberAstra 图生视频只上传一张图）。
4. 可选：子图右键「Unpack Subgraph（展开子图）」后再导出，节点 id 会更简洁。不展开的话，导出的 id 形如 `105:122`，manifest 照写就行。
5. 菜单「Export (API)」导出 `workflow_api.json`。

**第 5 步：编写 manifest**（节点 id 以实际导出为准，下面是示意）

```yaml
name: minimax_h3_i2v_enhancer
capability: i2v
description: MiniMax H3 图生视频 + Qwen3-VL 提示词增强（TE 可选官方版/越狱版；增强需要同族 tail）
fps: 24
inputs:
  image:
    node: "114"
    field: inputs.image
    type: image
    required: true
  prompt:
    node: "105:122"
    field: inputs.manual_prompt
    type: str
    required: true
  width:
    node: "105:104"
    field: inputs.width
    type: int
    default: 1344
    multiple: 32
  height:
    node: "105:104"
    field: inputs.height
    type: int
    default: 768
    multiple: 32
  length:
    node: "105:104"
    field: inputs.length
    type: int
    default: 124          # 约 5 秒
    min: 73
    max: 362
    align_base: 17
    align_offset: 5
  seed:
    node: "105:15"
    field: inputs.noise_seed
    type: int
    default: -1
  steps:
    node: "105:9"
    field: inputs.steps
    type: int
    default: 20
    min: 4
    max: 50
  clip_name:
    node: "105:13"
    field: inputs.clip_name
    type: str
    default: qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors
    options_from: text_encoders
    label: 文本编码器（官方/越狱）
  tail_file:
    node: "105:121"
    field: inputs.tail_file
    type: str
    default: qwen3vl_32b_h3_generation_tail_50_63_int8_convrot.safetensors
    options_from: text_encoders
    label: 生成尾（须与编码器同族）
  enhance_temperature:
    node: "105:122"
    field: inputs.temperature
    type: float
    default: 0.7
    label: 增强温度
outputs:
  node: "92"
  key: images
requirements:
  nodes: [MiniMaxH3ImageToVideo, MiniMaxH3PromptEnhancer, MiniMaxH3GenerationTailLoader, SamplerCustomAdvanced, SaveVideo]
  models:
    - diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
    - text_encoders/qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors
    - text_encoders/qwen3vl_32b_h3_generation_tail_50_63_int8_convrot.safetensors
    - vae/minimax_h3_video_vae_fp16.safetensors
    - vae/minimax_h3_audio_vae_fp32.safetensors
```

**第 6 步：导入 LiberAstra**

- 网页：「设置 → 工作流包 → 导入」，粘贴 API JSON 和 manifest。
- 或者放进用户包目录：`backend/data/workflows/minimax_h3_i2v_enhancer/{workflow.json, manifest.yaml}`。

**第 7 步：使用**

「视频 → 图生视频」：选择 Provider（远程 ComfyUI）→ 工作流包 `minimax_h3_i2v_enhancer` → 上传首帧 → 写简短提示词 → 设置时长和宽高比 → 提交。任务中心可以查看进度和结果。

### 3.5 开发计划（增强工作流相关）

| 阶段 | 内容 | 是否改代码 |
|------|------|------------|
| E1 | 远程装 Guide、上传模型，按 3.4 节导出并导入用户包，跑通端到端 | 否 |
| E2 | 做成内置包 `backend/workflows/minimax_h3_i2v_enhancer/`，补 `test_maintenance` 的包加载断言 | 是（只加数据文件和测试） |
| E3 | i2v 结果页额外展示「增强后提示词」和「增强报告」：manifest 增加 `texts` 输出声明（指向两个 `PreviewAny`），`run_i2v_job` 用 `extract_texts` 取出后写入任务结果，`ResultPanel` 展示 | 是 |
| E4 | 「提示词增强」开关：复用 2.6 节的节点摘除机制（manifest 增加通用 `toggles` 声明，`accel` 是其中一种） | 是 |
| E5 | 增强 + Turbo 合并包：在 `UNETLoader` 和 `BasicGuider` 之间插入 Turbo LoRA 节点，声明 `accel` | 是（依赖 M2） |
| E6（可选） | 评估 Guide 的 Plan v2 流程（结构化增强、提示词审阅），对应多参考图和多镜头的高级页面 | 待评估 |

---

## 4. 风险与待确认事项

| 项 | 说明 | 处理 |
|----|------|------|
| 远程内存 | 62GB 内存同时承载越狱 TE、主模型和 tail，之前出现过 Comfy OOM | E1 阶段实测峰值；增强器保持 `offload_after_generation=true`；必要时远程只跑 H3 |
| Turbo 与 pruned 主模型 | T8 转换版要求未剪枝主模型；原作者节点包支持 pruned | 优先走方案 A，不额外下载 31.7 GiB 主模型 |
| 4 步音频爆音 | 少步数时音频比画面更容易劣化 | 默认 preset 用 8 步 |
| NVFP4 在 3090 上的速度 | 官方 TE 在非 Blackwell 显卡上走回退路径 | 如果太慢，可换官方 `int8_convrot` TE（25.3 GiB） |
| 远程无法访问 HuggingFace | 只能本地下载后 `scp` 上传 | 上传前校验 SHA-256 |
| 合规 | 越狱 TE 去掉了拒答行为，生成内容由使用者负责；模型受 MiniMax H3 Community License 约束 | 在页面或文档中提示 |
| 节点版本漂移 | Guide 和 Turbo 节点包仍在快速迭代，节点名或参数可能变化 | 远程固定 commit；manifest 的 `requirements.nodes` 用来提前检查 |
