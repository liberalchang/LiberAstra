# SeedVR2 / FlashVSR 对比与 3B FP16 部署指南（RTX 3090 24GB）

> 面向：MiniMax H3 / ComfyUI 成片交付清晰化  
> 硬件基准：NVIDIA RTX 3090 24GB  
> 文档日期：2026-11-02（Asia/Shanghai）  
> 主要依据：[numz/ComfyUI-SeedVR2_VideoUpscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler)、[ComfyUI SeedVR2 教程](https://docs.comfy.org/tutorials/utility/seedvr2)、[ComfyUI 视频放大选型](https://docs.comfy.org/tutorials/utility/video-upscale)、[OpenImagingLab/FlashVSR](https://github.com/OpenImagingLab/FlashVSR)、[numz/SeedVR2_comfyUI (HF)](https://huggingface.co/numz/SeedVR2_comfyUI)

---

## 第一部分：3B FP16 vs 7B FP16 vs FlashVSR

### 1.1 对比总表（开源本地）

| 维度 | SeedVR2 **3B FP16** | SeedVR2 **7B FP16** | **FlashVSR** |
|------|---------------------|---------------------|--------------|
| 定位 | 开源质量向默认；细节重建强 | 同系列更高容量；细节/锐度上限更高 | 速度向；保守、少幻觉 |
| 架构 | 一步扩散视频修复（ByteDance Seed） | 同左 | 一步流式扩散 VSR（OpenImagingLab） |
| Comfy 路径 | [numz 自定义节点](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler)（推荐）或 Comfy 原生节点 | 同左 | 社区包装（如 [FlashVSR_Ultra_Fast](https://github.com/lihaoyun6/ComfyUI-FlashVSR_Ultra_Fast)、[ComfyUI_FlashVSR](https://github.com/smthemex/ComfyUI_FlashVSR)） |
| 权重体积（numz HF） | DiT ≈ **6.32 GiB** + VAE ≈ **0.48 GiB** | DiT ≈ **15.35 GiB** + 同 VAE | 整夹 `FlashVSR/`（DiT + VAE + TCDecoder 等，多文件） |
| 官方硬件档（numz） | **High VRAM（24GB+）首选 FP16**，先不开 BlockSwap | 同档可用；更吃显存/更慢 | 论文标 A100 ≈17 FPS（768×1408）；消费级需包装 + tiling |
| 3090 24G 可行性 | **可行且推荐日常交付** | **可行**；大 batch / 高分辨率更容易 OOM | **可行**；Comfy 包装对 30 系更友好（Ultra_Fast 免编译稀疏核） |
| 质量观感 | 开源里偏「重建细节」；适合 AI 软糊、档案修复 | 细节/锐度通常优于 3B；`*_sharp_*` 更猛 | 更保守；运动模糊保留好、幻觉少；细节重建弱于 SeedVR2 |
| 时序一致性 | 有；`batch_size` 须 **4n+1**，视频交付 **≥5** | 同左 | 流式窗口；官方强调长片内存有界 |
| 速度（相对） | 慢（分钟级/十秒素材） | 更慢（约 3B 的 2×～3×+，视分辨率/batch） | **明显更快**（官方对比表里常快一个数量级量级） |
| 何时用 | **3090 交付默认**；H3 Extender 定稿后清晰化 | 短片/英雄镜头要再抠细节时 | 批量试片、长片赶进度、怕幻觉时 |

### 1.2 速度参考（注明来源；非 3090 原厂标称）

| 场景 | 方案 | 约耗时 | 来源 |
|------|------|--------|------|
| 10s、720p→1080p | FlashVSR（本地） | **~41s** | [ComfyUI 视频放大文档](https://docs.comfy.org/tutorials/utility/video-upscale) |
| 同上 | SeedVR2（本地，**RTX 5090**） | **~312s（约 5.2 min）** | 同上（未标明 3B/7B；作「SeedVR2 量级」） |
| 约 3s 素材拉到 2K | SeedVR2 **7B**（社区 **3090**） | **约 5 min** | 社区经验（粗估，非官方） |
| 4090、20 帧、512×768→约 1080、`batch_size=1` | 3B FP16 | ~91s（≈0.22 fps） | 早期 README 基准表（**batch=1 无视频时序收益**，仅作吞吐参考） |
| 论文标称 | FlashVSR | A100 上约 **17 FPS**（768×1408） | [FlashVSR README](https://github.com/OpenImagingLab/FlashVSR) |

**3090 粗估（务必用短片自测）：**

- 相对 5090 文档里的 SeedVR2 ~312s/10s@1080，3090 往往更慢一截 → **同条件 SeedVR2 可能到约 8～15+ 分钟 / 10 秒片** 量级（3B 偏下限，7B 偏上限）。
- FlashVSR 仍通常显著快于 SeedVR2；但社区实测显示消费卡很难摸到 A100 的「近实时」标称。
- **先短片 2～5 秒测通再整段**；内容定稿后再开 SeedVR2。

### 1.3 硬件 / 显存要点（3090）

| 方案 | 推荐起步 | OOM 时降级 |
|------|----------|------------|
| **3B FP16** | `device=cuda:0`，`offload_device=none`，`blocks_to_swap=0`，`batch_size=5`→试 `21`，`resolution=1080` | 降 `batch_size`（仍保持 4n+1）；VAE encode/decode tiling；再考虑 **3B FP8** 或 BlockSwap |
| **7B FP16** | 同上，但先 `batch_size=5`，分辨率/帧数保守 | FP8 / mixed FP8、BlockSwap、`swap_io_components`、tiling；短边先 720/900 |
| **FlashVSR** | Ultra_Fast：`tiny` 试片、`full` 交付；官方强烈建议 **×4** | `tiled_vae` / `tiled_dit`、`unload_dit`；降 scale=2（质量通常变差） |

numz 官方分档摘要：

- **8GB 及以下**：GGUF + BlockSwap + VAE tiling  
- **12–16GB**：FP8 ± BlockSwap/tiling  
- **24GB+（含 3090）**：优先 **FP16**，尽量不先上内存优化（更快）

### 1.4 选型一句话

- **交付清晰（3090）→ SeedVR2 3B FP16**  
- **英雄镜头再抠 → 7B FP16 / 7B Sharp**  
- **赶进度 / 长片试片 → FlashVSR**  
- **不要用逐帧 Real-ESRGAN 当 AI 片交付**（无时序，易闪）

---

## 第二部分：SeedVR2 3B FP16 部署文档（ComfyUI · 3090）

本部分以 **numz 自定义节点 v2.5+（四节点架构）** 为主。首次使用会自动从 Hugging Face 拉权重到 `ComfyUI/models/SEEDVR2`；也可手动下载。

### 2.1 前置条件

| 项 | 要求 |
|----|------|
| GPU | RTX 3090 24GB（本指南目标） |
| ComfyUI | **最新版**（Manager / Nightly 均可；旧版可能缺节点） |
| Python | 3.12+（官方测过 3.12 / 3.13） |
| PyTorch | 建议 2.0+（`torch.compile` 可选） |
| 磁盘 | 至少预留 **~8 GiB**（3B FP16 ≈6.32 GiB + VAE ≈0.48 GiB）；若以后下 7B 再加 ~15 GiB |
| 依赖 | 节点 `requirements.txt`；可选 Triton（compile）、Flash Attention 2（Ampere+，3090 可用） |
| 辅助节点 | [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)（`VHS_LoadVideo` / `VHS_VideoCombine`） |

### 2.2 安装自定义节点

#### 方式 A：ComfyUI Manager（推荐）

1. 打开 **ComfyUI Manager → Custom Nodes Manager**  
2. 搜索：`ComfyUI-SeedVR2_VideoUpscaler`  
3. Install → **重启 ComfyUI**  
4. Registry：[seedvr2_videoupscaler](https://registry.comfy.org/nodes/seedvr2_videoupscaler)

#### 方式 B：git clone

在 ComfyUI 根目录执行：

```bash
cd ComfyUI
git clone https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git custom_nodes/seedvr2_videoupscaler
```

安装依赖（使用 ComfyUI 自己的 Python）：

```bash
# Windows
.venv\Scripts\python.exe -m pip install -r custom_nodes\seedvr2_videoupscaler\requirements.txt

# Linux / macOS
.venv/bin/python -m pip install -r custom_nodes/seedvr2_videoupscaler/requirements.txt
```

然后重启 ComfyUI。

> 教程视频（v2.5 四节点）：[AInVFX · SeedVR2 v2.5 Deep Dive](https://youtu.be/MBtWYXq_r60)

### 2.3 模型文件（3B FP16）

**手动下载（可选；也可首次跑图时自动下载）：**

| 文件 | 作用 | 约大小 | Hugging Face |
|------|------|--------|--------------|
| `seedvr2_ema_3b_fp16.safetensors` | DiT 主模型 | ≈ 6.32 GiB | [numz/SeedVR2_comfyUI](https://huggingface.co/numz/SeedVR2_comfyUI/blob/main/seedvr2_ema_3b_fp16.safetensors) |
| `ema_vae_fp16.safetensors` | VAE（全系列共用） | ≈ 478 MiB | [同仓](https://huggingface.co/numz/SeedVR2_comfyUI/blob/main/ema_vae_fp16.safetensors) |

备用镜像仓：[AInVFX/SeedVR2_comfyUI](https://huggingface.co/AInVFX/SeedVR2_comfyUI)

**放置路径（numz 节点）：**

```text
ComfyUI/
└── models/
    └── SEEDVR2/
        ├── seedvr2_ema_3b_fp16.safetensors
        └── ema_vae_fp16.safetensors
```

国内可用 `HF_ENDPOINT=https://hf-mirror.com` 或 huggingface-cli / 浏览器从镜像站拉上述文件名。

> **注意两种生态文件名不同：**  
> - **numz 节点**：`seedvr2_ema_3b_fp16.safetensors` + `ema_vae_fp16.safetensors` → `models/SEEDVR2/`  
> - **Comfy 原生 / Comfy-Org 教程**：`seedvr2_3b_fp16.safetensors` + `seedvr2_ema_vae_fp16.safetensors` → `models/diffusion_models/` 与 `models/vae/`（见 [docs.comfy.org SeedVR2](https://docs.comfy.org/tutorials/utility/seedvr2)）  
> 本指南按 **numz** 写；不要把两套路径混放后指望节点自动找到。

### 2.4 最小工作流（视频 → 1080）

四节点 + 读写视频：

```text
VHS_LoadVideo（或 Load Video）
        │  IMAGE 帧序列
        ▼
SeedVR2 (Down)Load DiT Model
  • model: seedvr2_ema_3b_fp16.safetensors
  • device: cuda:0
  • offload_device: none
  • blocks_to_swap: 0
  • attention_mode: sdpa（稳）或 flash_attn_2（若已装）
        │
        ▼
SeedVR2 (Down)Load VAE Model
  • model: ema_vae_fp16.safetensors
  • device: cuda:0
  • offload_device: none
  • encode_tiled / decode_tiled: False（3090 先关）
        │
        ▼
SeedVR2 Video Upscaler
  • seed: 42（可复现）
  • resolution: 1080          ← 短边目标
  • max_resolution: 0         ← 0=不限制
  • batch_size: 5             ← 先 5；稳了再试 9/13/17/21
  • uniform_batch_size: True  ← 长片建议开
  • temporal_overlap: 0～3
  • color_correction: lab（保真）或 wavelet
  • enable_debug: True（首跑建议开，看哪一阶段 OOM）
        │
        ▼
VHS_VideoCombine → 输出 mp4
```

**操作顺序建议：**

1. 把短测片放进 `ComfyUI/input/`  
2. `batch_size=5`、`resolution=1080` 跑通  
3. 再把 `batch_size` 提到 **21**（或接近镜头帧数的 4n+1）  
4. 整段交付片再关 debug、考虑是否 compile

### 2.5 RTX 3090 推荐参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| DiT | `seedvr2_ema_3b_fp16.safetensors` | 交付默认 |
| VAE | `ema_vae_fp16.safetensors` | 必需 |
| `device` | `cuda:0` | |
| `offload_device`（DiT/VAE） | `none` | 24G High VRAM 档优先；最快 |
| `blocks_to_swap` | `0` | 有 OOM 再开 |
| `resolution` | `1080` | H3 常见源约 896×576 升 1080 |
| `batch_size` | **5 → 21** | **必须 4n+1**；视频不要用 1 |
| `color_correction` | `lab` | 官方推荐最高保真 |
| `torch.compile` | 短片关；长片/批量可开 | 编译开销大，短 clip 常亏时间 |
| 输入 | 先 2～5 秒试片 | 再整段 |

**`batch_size` 合法值：** `1, 5, 9, 13, 17, 21, 25, …`（公式 **4n+1**）。  
- `1`：仅静图或不要时序时  
- **≥5**：视频时序一致性门槛  
- 越大：质量/每帧吞吐通常更好，但 VRAM 更高  

### 2.6 OOM 降级顺序（保持尽量不砍时序）

按官方建议，**先优化内存手段，再降 batch / 分辨率**（后两者直接伤质量）：

1. Upscaler 开 `enable_debug`，看卡在 Encoding / Upscaling / Decoding  
2. **Encoding OOM** → VAE `encode_tiled=True`（tile 1024→768→512）  
3. **Decoding OOM** → `decode_tiled=True`  
4. **Upscaling OOM** → DiT `offload_device=cpu`，`blocks_to_swap=16`→`24`→`32`，必要时 `swap_io_components=True`  
5. 仍不够 → 换 **`seedvr2_ema_3b_fp8_e4m3fn.safetensors`**  
6. 最后才降 `batch_size`（仍 ≥5）或 `resolution`（如 900/720）  
7. 极糊源可考虑先略缩小再 SeedVR2 拉回，逼重建而非放大压缩块（实践技巧，非强制）

### 2.7 与 MiniMax H3 Extender 可选清晰通路

内容定稿后，把 Extender 输出接到 SeedVR2，再封装：

```text
H3 Extender 输出视频
    → GetVideoComponents / VHS_LoadVideo（拆帧）
    → SeedVR2（3B FP16，resolution=1080，batch_size=5～21）
    → VHS_VideoCombine（按原 fps / 音频回封）
```

建议：

- **调戏片段阶段不要开 SeedVR2**（太慢）  
- 只对最终 master 或选定镜头跑  
- 需要更快试看时并行准备 FlashVSR 工作流，交付仍回 SeedVR2

### 2.8 注意与坑

1. **`batch_size=1` 不要当视频交付** —— 几乎没有时序收益，还可能更慢/闪。  
2. **`torch.compile` 只适合长片/多 batch/多 tile**；短片首跑编译成本常超过收益。  
3. **INT8 工作流若出全黑图**：Comfy 文档建议先关 FlashAttention、改回 FP16/FP8、检查 VAE 是否下全（3090 上有过 INT8+FlashAttn 黑图案例）。本指南主推 **FP16**，一般可避开。  
4. **VAE 常常是瓶颈** —— 大 `batch_size` 有助于摊薄；tiling 省显存但更慢。  
5. **FlashVSR 社区包装质量不一** —— 官方警告部分实现缺 LCSA、密注意力回退会导致糊/伪影；要速度可用 Ultra_Fast，要贴近论文效果优先官方仓或标注含 LCSA 的包装。  
6. FlashVSR 官方 **强烈建议 ×4 SR**；乱设 ×2 可能明显变差。

### 2.9 可选：CLI（同仓库）

已装 numz 节点时：

```bash
# Windows
.venv\Scripts\python.exe custom_nodes\seedvr2_videoupscaler\inference_cli.py video.mp4 --resolution 1080 --batch_size 21 --dit_model seedvr2_ema_3b_fp16.safetensors

# Linux
.venv/bin/python custom_nodes/seedvr2_videoupscaler/inference_cli.py video.mp4 --resolution 1080 --batch_size 21 --dit_model seedvr2_ema_3b_fp16.safetensors
```

更多参数见仓库 README「Run as Standalone」。

### 2.10 快速检查清单

- [ ] ComfyUI 已更新；SeedVR2 节点可在节点列表搜到  
- [ ] `models/SEEDVR2/` 下有 `seedvr2_ema_3b_fp16.safetensors` 与 `ema_vae_fp16.safetensors`  
- [ ] 短测片 `batch_size=5`、`resolution=1080` 跑通  
- [ ] 再试 `batch_size=21`；OOM 按 §2.6 降级  
- [ ] H3 定稿片再接 GetVideoComponents → SeedVR2 → VHS_VideoCombine  

---

## 参考链接

- https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler  
- https://huggingface.co/numz/SeedVR2_comfyUI  
- https://docs.comfy.org/tutorials/utility/seedvr2  
- https://docs.comfy.org/tutorials/utility/video-upscale  
- https://github.com/OpenImagingLab/FlashVSR  
- https://github.com/lihaoyun6/ComfyUI-FlashVSR_Ultra_Fast  
- https://huggingface.co/JunhaoZhuang/FlashVSR / https://huggingface.co/JunhaoZhuang/FlashVSR-v1.1  

*速度与显存数字来自公开文档与社区报告，未在你的 3090 上实测；以本机短片计时为准。*
