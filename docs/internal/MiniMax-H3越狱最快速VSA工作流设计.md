# MiniMax H3：越狱最快速工作流（8 步 + VSA）设计

> 状态（2026-10-27）：**只定设计，不改代码、不改现有工作流包。** 出片机上的画布对照还没做。对照通过之前，不要新建 `minimax_h3_i2v_uncensored_vsa`。
>
> 对照基线是现有越狱图生视频包 `minimax_h3_i2v_uncensored`：FL2VA 剪枝 INT8、越狱 NVFP4 文本编码器、Larry EMA Turbo、开加速后 8 步 `euler`。本设计只在这条链路上加稀疏注意力。
>
> 注意力方案来自 [ComfyUI-Ref2VA-VSA](https://github.com/Kablex/ComfyUI-Ref2VA-VSA) 的 `Ref2VAVSAGatePatch`。本地文章归档：`D:\BaiduSyncdisk\mydir\Comfy\docs\MiniMax H3参考生视频提速：ComfyUI插件，4090出片72秒-2026-10-27 17_38_51.md`。模型清单与远程环境沿用 [MiniMax-H3加速与越狱工作流开发计划.md](./MiniMax-H3加速与越狱工作流开发计划.md)。

## 1. 决定

新建一个 `capability: i2v` 的工作流包，名称 `minimax_h3_i2v_uncensored_vsa`。它是越狱图生视频的最快速档，和现有 `minimax_h3_i2v_uncensored` 并列。现有包继续当稠密对照，图和 manifest 都不改。

固定配方：

| 项 | 取值 |
|----|------|
| 主模型 | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` |
| 文本编码器 | `qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors`（`CLIPLoader.type = minimax`） |
| VAE | 现有视频 VAE + 音频 VAE |
| 条件节点 | `MiniMaxH3ImageToVideo`（首帧） |
| Turbo | `MiniMaxH3TurboLoRA` + `minimax_h3_turbo_v4_step600_ema.safetensors`，强度 1.0，`low_vram: false` |
| 注意力 | `Ref2VAVSAGatePatch`，gate 文件写死为 `fasth3_vsa_gate.safetensors`，稀疏度默认 0.70 |
| 采样 | 8 步、`euler`、调度器 `simple`、`denoise` 1.0 |
| 默认分辨率 / 帧数 | 1344×768、124 帧、24fps（与现有图生视频包相同，约 5.16 秒） |

采样步数以图内默认值为准，就是 8 步 `euler`。`accel.preset` 同样写成 8 / `euler`，避免开 Turbo 时被盖成别的值。关掉 Turbo 只摘 LoRA，步数停在用户当前值，不会回到现有越狱包的 20 步 `res_multistep`。要跑 20 步稠密质量档，用原来的 `minimax_h3_i2v_uncensored`。

Turbo 默认开启（`accel.default_enabled: true`）。

### 1.1 这次不纳入的内容

- 不换 `minimax_h3_ref2va_*` 底模。那个底模和 FL2VA 不能混用，动作迁移包另案。
- 不挂 LightX2V 的 `minimax_h3_ref2v_turbo_4step_*`。文章里的 4 步是另一套蒸馏，本包保持 8 步 EMA。
- 不直接用 `FastH3VSAPatch`。那个节点要求 checkpoint 自己带 `to_gate_compress`。本包用 `Ref2VAVSAGatePatch` 把外部 gate 接到现有 FL2VA 上。
- 不加 `MiniMaxH3SigmaShift`。现有图生视频图里没有这个节点，加它会改采样，不再是「只优化注意力」。
- 不走 Guide / 越狱 INT8 + tail。增强包多一次文本编码，不是最快速档。
- 文生视频、口播、动作迁移先不复制。图生视频对照通过后再决定要不要照同一张图复制。

## 2. 注意力在这条图上做什么

`Ref2VAVSAGatePatch` 从 gate 文件读出 50 个 `to_gate_compress` 矩阵，挂到 `MiniMaxH3Model` 的 50 个 DiT block 上，再用 comfy-kitchen 的 CUDA `sol_attn` 做 tile-64 稀疏注意力。

序列里种类不是 `video` 的段（文本、音频、首帧 keyframe）整段保持稠密。top-k 只作用在最后那段生成视频的 key tile 上。稀疏度 0.70 表示视频 key tile 剪掉约 70%，保留约 30%（节点参数 `topk_ratio = 1 - sparsity`）。

作者给这条移植路径的试用区间是 0.50–0.70。0.90 是 FastH3 原 checkpoint 的默认值，不作为本包默认。页面上的稀疏度限制在 0.50–0.90；节点本身接受 `[0, 0.98]`。

这组「FL2VA + 8 步 EMA + 从 FastH3 移植的 gate」没有公开基准。gate 形状和 FL2VA block 对不上时，节点会在加载时抛 shape 错误。出现这个错误就停，不要改底模去迁就 gate。

文章里的 72 秒 / 13.5GB 是 RTX 4090、4 步、Ref2VA、热启动的作者自测。本包的对照对象是同一台 3090 上的 8 步稠密越狱图生视频，不拿 72 秒当验收线。远程启动参数仍是 `--lowvram --reserve-vram 8`。

## 3. 计算图

在 `minimax_h3_i2v_uncensored` 的 API Format 上插入一个节点，并改两条 MODEL 连线。其余节点编号保持不动，方便和现有单测对照。

```
105:6   UNETLoader (FL2VA pruned INT8)
        │
        ▼
105:200 MiniMaxH3TurboLoRA (EMA, strength 1.0, low_vram false)
        │
        ▼
105:201 Ref2VAVSAGatePatch (fasth3_vsa_gate.safetensors, sparsity 0.70)
        │
        ├──► 105:9  BasicScheduler (simple, steps 8)
        └──► 105:16 BasicGuider
                │
                ▼
             105:14 SamplerCustomAdvanced (105:17 = euler)
```

`105:201` 的输入：

| 字段 | 值 |
|------|----|
| `model` | `["105:200", 0]` |
| `gate_file` | `fasth3_vsa_gate.safetensors` |
| `sparsity` | `0.70` |

`105:9` 和 `105:16` 的 `model` 从 `["105:200", 0]` 改到 `["105:201", 0]`。`105:17` 的 `sampler_name` 改为 `euler`，`105:9` 的 `steps` 改为 `8`。调度器保持 `simple`。

首帧、提示词、宽高、帧数、种子、TE、两个 VAE、解码和 `SaveVideo` 与现有越狱图生视频包相同。`filename_prefix` 改为 `video/MiniMax_H3_i2v_uncensored_vsa`。

### 3.1 关掉 Turbo 时连线怎么走

现有 `apply_accel` 只认识一个加速节点：关闭时删除该节点，并把所有指向它输出 0 的下游改接到 `bypass_input` 的来源。

因此：

- `accel.node` 仍然是 `105:200`，`bypass_input` 仍然是 `model`（来源是 `105:6`）。
- VSA 必须放在 Turbo **下游**，不能和 Turbo 并列，也不能放到 Turbo 上游。
- 关闭加速后，`105:201.inputs.model` 从 `["105:200", 0]` 改写成 `["105:6", 0]`。`105:9` 和 `105:16` 仍指向 `105:201`。VSA 留在图里。
- `105:201` 只有一路 MODEL 输出，下游只引用 slot 0。这和现有 accel 校验一致。

Turbo 和 VSA 用的不是同一种补丁，按上面的顺序可以叠在同一条 MODEL 上：

- Turbo 用权重旁路 / 合并，以及剪枝底模上的 adaln 运行时注入，另有一个 key 为 `h3turbo` 的 diffusion wrapper。
- VSA 用 key `fasth3_vsa_layout_v2` 的 diffusion wrapper，加上每个 DiT block 的 `patch_replace`。它拒绝图上已经存在的 `optimized_attention_override` 或别的 DiT `patch_replace`。
- VSA 重写 block 前向时仍调用 `adaln_proj` 和 `qkv_proj`，Turbo 挂在这两个模块上的补丁还会执行。

画布对照时要看 Turbo 日志里的 canary 仍是 LoRA 生效。如果 VSA 把 adaln 注入吃掉，8 步 EMA 会失效，这条包就不能按本设计上线。

这条工作流不要再加 SageAttention 或其它注意力补丁。

`low_vram` 先保持 `false`。只有对照时 OOM（显存溢出）才打开 Turbo 节点上的这个开关。量化底模上合并 LoRA 会让画面变软。它和 ComfyUI 进程的 `--lowvram` 是两回事，进程参数不动。

## 4. manifest 草案

实现时新增目录 `backend/workflows/minimax_h3_i2v_uncensored_vsa/`，内含 `manifest.yaml` 和 `workflow.json`。参数布局复制 `minimax_h3_i2v_uncensored`，只改下面这些字段。

```yaml
name: minimax_h3_i2v_uncensored_vsa
capability: i2v
description: 'MiniMax H3 图生视频（越狱最快速）

  首帧图加提示词，生成带同步音效的短视频。越狱 NVFP4 文本编码器，8 步 EMA Turbo，
  并对生成视频 token 做稀疏注意力。首帧、文本和音频保持稠密。'
fps: 24
# inputs 与 minimax_h3_i2v_uncensored 相同，除下列三项：
#   steps.default: 8
#   sampler_name.default: euler
#   新增 sparsity
inputs:
  sparsity:
    node: "105:201"
    field: inputs.sparsity
    type: float
    default: 0.70
    min: 0.50
    max: 0.90
    label: 视频稀疏度
    description: 只稀疏生成视频的 key tile。默认 0.70。脸或衣服漂移时降到 0.50
  # steps.default 改为 8，sampler_name.default 改为 euler
  # clip_name / unet_name 默认值与越狱图生视频包相同
outputs:
  node: "92"
  key: images
accel:
  label: Turbo 加速
  family: minimax_h3
  default_enabled: true
  node: "105:200"
  bypass_input: model
  lora:
    field: inputs.lora_name
    options_from: loras
    match: _ema
    recommended: minimax_h3_turbo_v4_step600_ema.safetensors
  strength:
    field: inputs.strength
    default: 1.0
    min: 0.5
    max: 1.5
  preset:
    steps: 8
    sampler_name: euler
requirements:
  nodes:
    - MiniMaxH3ImageToVideo
    - MiniMaxH3TurboLoRA
    - Ref2VAVSAGatePatch
    - SamplerCustomAdvanced
    - SaveVideo
    - CreateVideo
  models:
    - diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
    - text_encoders/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors
    - vae/minimax_h3_video_vae_fp16.safetensors
    - vae/minimax_h3_audio_vae_fp32.safetensors
    - loras/minimax_h3_turbo_v4_step600_ema.safetensors
    - loras/fasth3_vsa_gate.safetensors
```

`gate_file` 不做成下拉参数。普通 `options_from: loras` 会列出全部 LoRA，用户可能选到 EMA 文件，节点会在 shape 校验失败。gate 文件名写死在 `workflow.json`。换 gate 时改图，不改页面。

`sparsity` 走现有 float 输入，前端已有步进器，后端 `apply_inputs` 已按 float 写入。不新增参数类型。

`llm_note` 写明：越狱 NVFP4、无增强、8 步 EMA、视频 token 稀疏、首帧保持稠密。写作指导与现有越狱图生视频包相同。

## 5. 写包之前要备齐的运行环境

出片机仍是 `ps@10.10.12.140`，ComfyUI 在 `/home/ps/workspace/ComfyUI`。远程访问不了 huggingface.co，新文件先下到 `D:\BaiduSyncdisk\mydir\Comfy`，再 `scp`。

2026-10-20 的记录里，这台机器还没有 Larry 的 `ComfyUI-MiniMax-H3-Turbo`，EMA 也还在本地待上传。画布对照前先确认这两样已经在远程，否则 8 步配方本身不成立。

### 5.1 节点加载时的硬条件

`Ref2VAVSAGatePatch` 失败会直接抛错，没有静默回退：

- 扩散模型类型是原生 `MiniMaxH3Model`，且正好 50 个 DiT block。
- `comfy-kitchen` 的 CUDA 后端可用，能力列表含 `sol_attn`。在远程 ComfyUI 环境里执行：

```bash
python -c "import comfy_kitchen as ck; print(ck.list_backends())"
```

- 注意力输入是 CUDA、BF16、`head_dim=128`。3090 支持 BF16。
- batch 为 1。快速创作和单张图生视频已经是一张图一次采样，满足这点。
- 打包序列里恰好一段目标视频，且这段视频在序列末尾。`MiniMaxH3ImageToVideo` 的首帧应落在非视频前缀里。若运行时报「video segment」或「final packed segment」，本设计的 FL2VA 图生视频假设不成立，停在画布阶段。

### 5.2 要新放上去的文件

| 文件 | 放置位置 | 来源 |
|------|----------|------|
| `fasth3_vsa_gate.safetensors` | 本地与远程的 `models/loras/` | https://huggingface.co/barelymining/ComfyUI-MiniMax-H3-FastVideo/resolve/main/fasth3_vsa_gate.safetensors |
| `ComfyUI-Ref2VA-VSA` | 远程 `custom_nodes/ComfyUI-Ref2VA-VSA` | https://github.com/Kablex/ComfyUI-Ref2VA-VSA ，克隆后固定到一个 commit |

重启 ComfyUI 后，`/object_info` 里要能看到 `Ref2VAVSAGatePatch`。仓库目前是实验节点（界面名带 EXPERIMENTAL），实现时把 commit 写进本节状态栏。

已有、本包继续用的文件：

- `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- `text_encoders/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors`
- `vae/minimax_h3_video_vae_fp16.safetensors`
- `vae/minimax_h3_audio_vae_fp32.safetensors`
- `loras/minimax_h3_turbo_v4_step600_ema.safetensors`

本包不下载 `minimax_h3_ref2va_*`、4 步 Ref2V Turbo LoRA，也不下载整份 FastH3 checkpoint。只有在官方 gate 文件下不到时，才用仓库里的 `tools/extract_vsa_gate.py` 从 `minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors` 抽 gate。抽出来的文件名仍保存为 `fasth3_vsa_gate.safetensors`。

## 6. 画布对照（写 LiberAstra 包之前）

在 ComfyUI 画布上跑，不经过 LiberAstra。同一张首帧、同一提示词、同一种子、1344×768、124 帧、8 步 `euler`、`simple`、EMA 强度 1.0：

| 跑次 | 图 | 看什么 |
|------|----|--------|
| A | 现有越狱图生视频，Turbo 开，无 VSA | 墙钟时间、峰值显存、画面 |
| B | A 的 Turbo 后面接 `Ref2VAVSAGatePatch`，稀疏度 0.70 | 同上，并和 A 比脸、衣服、动作 |
| C | 仅当 B 身份明显漂移 | 稀疏度 0.50，再和 A 比 |

通过才进入第 7 节：

- B 或 C 相对 A 没有明显的脸或衣服漂移。
- 日志里 Turbo canary 仍表示 LoRA 生效。
- 墙钟时间低于 A。3090 上不要求接近 72 秒。
- 无 shape 错误、无 `sol_attn` 缺失、无「视频段不在序列末尾」。

把 A/B 的分辨率、帧数、种子、步数、稀疏度、墙钟时间和峰值显存补进本文状态栏。C 若成为默认，把 manifest 草案里的 `sparsity.default` 改成 0.50，图里的初值一起改。

## 7. 对照通过后的代码落点

只加包和测试、补文档。`apply_accel` 的摘节点逻辑不用改，前提是第 3.1 节的连线成立。

| 路径 | 动作 |
|------|------|
| `backend/workflows/minimax_h3_i2v_uncensored_vsa/workflow.json` | 按第 3 节新建 |
| `backend/workflows/minimax_h3_i2v_uncensored_vsa/manifest.yaml` | 按第 4 节新建；稀疏度默认值以第 6 节结论为准 |
| `backend/tests/test_workflows.py` | 加本包用例。现有越狱包用例保持绿色，用来保证旧包没被改到 |
| `docs/使用文档.md` | 在 MiniMax H3 图生视频表加一行最快速包，并写明 gate 文件与 `Ref2VAVSAGatePatch` |
| `docs/Liberastra部署相关资源下载.md` | 视频包表加本包一行，链到 gate 与节点仓库 |

单测要锁住的行为：

- 包能加载；`requirements.nodes` 含 `Ref2VAVSAGatePatch`；`requirements.models` 含 `loras/fasth3_vsa_gate.safetensors`。
- `105:201` 存在，`gate_file` 为 `fasth3_vsa_gate.safetensors`，`sparsity` 为选定默认值。
- 开 Turbo：`105:6 → 105:200 → 105:201 → 105:9 / 105:16`，LoRA 为 EMA，步数 8，采样器 `euler`。
- 关 Turbo：`105:200` 被删除；`105:201.inputs.model` 为 `["105:6", 0]`；`105:9` 和 `105:16` 仍指向 `105:201`；步数保持 8，不回到 20。
- `minimax_h3_i2v_uncensored` 的图里仍然没有 `105:201`。

前端不用新控件。`capability: i2v` 的页面会列出这个包；`sparsity` 用现有 float 步进器；Turbo 开关用现有 `AccelControl`。默认开加速后，页面初次渲染应显示 8 步和 `euler`。

## 8. 里程碑

| 阶段 | 内容 | 状态 |
|------|------|------|
| M0 | 远程确认 Larry Turbo 节点与 EMA；安装 `ComfyUI-Ref2VA-VSA` 并固定 commit；上传 `fasth3_vsa_gate.safetensors`；确认 `sol_attn` | 未做 |
| M1 | 第 6 节画布对照，把时间和显存写回本文 | 未做 |
| M2 | 对照通过后新增工作流包与单测 | 未做 |
| M3 | 补使用文档和部署下载表 | 未做 |

M1 判定为停（shape 不符、视频段不在末尾、8 步 EMA 被 VSA 吃掉、身份相对 A 不可用）时，不进入 M2。不把底模换成 Ref2VA 来让这个图生视频包通过。
