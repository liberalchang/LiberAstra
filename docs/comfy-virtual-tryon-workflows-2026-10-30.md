# ComfyUI / Qwen 生态：虚拟换装（Virtual Try-On / Outfit Transfer）调研

- 调研日期：2026-10-30（Asia/Shanghai）
- 目标需求：**第一张 = 人物图**，**参考图 = 衣物**，输出给人物换装，**尽量保持肖像（脸）与背景不变**
- 偏好：本地 ComfyUI、可下载权重、不必走在线审核 API；优先贴合用户近期栈（Qwen-Image-2.1 / Fun ControlNet Union / T8）；显存约 24GB；无审查本地优先
- 方法：公开网页 / GitHub / Hugging Face / Comfy 文档 / Civitai；**本调研未在本机出图实测**

---

## 1. 一句话结论

**有，且与需求高度对口。**  
当前最贴用户栈的是社区 **Qwen-Image-2.1 Outfit Swap Consistency LoRA + 现成 Comfy 工作流**（人物=image1、衣物=image2，作者自测显著抑制脸软化与背景重绘）。  
另有一批专用 VTON 本地栈（CatVTON / FitDiT / IDM-VTON / Leffa），靠**衣服区域蒙版**硬保脸与背景，衣物保真往往更好，但依赖 DensePose/解析等额外权重，且与 Qwen-2.1 栈无关。  
Fun ControlNet Union **没有**「换装专用」现成 JSON，可用 inpaint + 衣物参考**自拼近似**，不保证蒙版外像素不变。

---

## 2. 需求对照表

| 条件 | 含义 |
| --- | --- |
| 输入 A | 人物照片（要换装的人） |
| 输入 B | 衣物参考（上衣/裙子/整套；平铺、挂拍、模特图均可，视方案而定） |
| 硬约束 | 脸（肖像）尽量不变；背景尽量不变 |
| 部署 | 优先本地权重；API 仅降级列出 |

---

## 3. 分类总览

### 3.1 明确支持「人物图 + 衣物图、保脸保背景」的现成 Comfy 工作流 JSON

| 方案 | 本地 | 保脸/保背景机制 | 备注 |
| --- | --- | --- | --- |
| **Qwen 2.1 Outfit Swap + Consistency LoRA**（AusBoss） | ✅ | LoRA 把换装钉在原图画框上；作者测脸像素变化 14.1%→1.7%，背景 10.8%→0.9% | **最贴用户栈**；无蒙版；衣物细节仍靠基模 |
| **CatVTON Comfy 工作流** | ✅ | 自动/手动衣服 mask；非蒙版区保留 | 专用 VTON；需 DensePose 等 |
| **FitDiT Comfy 示例** `fitdit_workflow.json` | ✅ | Mask + pose；主要重绘服装区 | 高保真衣物；可 offload |
| **IDM-VTON Comfy** | ✅ | SAM mask + DensePose | ≥16GB VRAM 声明 |
| **Leffa Comfy 节点**（StartHua / Bionic） | ✅ | 解析 mask；非衣物区保留 | 权重包很大（~34GB 量级） |
| **Bria / Kling Virtual Try-On**（Comfy Partner） | ❌ 云 API | 文档写明保脸/姿势/背景 | 见 §3.4 |

### 3.2 有模型/论文、Comfy 工作流不完整或较弱

| 方案 | 说明 |
| --- | --- |
| **OOTDiffusion** | 官方以独立 `run_ootd.py` 为主；社区偶有 workflow 图，非一等公民 Comfy 包 |
| **CatV2TON / CatV2TON-V2** | 2025 DiT 图+视频 try-on；公开推理脚本与 HF 权重；**未见**成熟官方 Comfy JSON |
| **CatVTON-FLUX** | FLUX.1-Fill LoRA；偏 Gradio/代码，非完整 Comfy 产品流 |
| **Kolors Virtual Try-On** | 多见 API/托管封装，非用户要的本地无审查主路径 |

### 3.3 会改背景或脸不稳定（或需额外手段）

| 方案 | 问题 |
| --- | --- |
| **裸跑 Qwen-Image-2.1 双图 Edit 换装**（无 Consistency LoRA） | 作者同设定测：结果相对原图漂移约 3.6px；脸约 14% 像素明显变化；背景约 11% 被重绘；还可能拉远镜头塞进全身衣服 |
| **T8 Fun ControlNet Union 参考编辑 / 纯 prompt 换装** | 参考槽语义是「编辑画布 + 附加外观」；**无**换装专用模板；蒙版「不保证」蒙版外像素不变 |
| **通用 Image Edit / IP-Adapter 风格换衣** | 身份与背景常漂移；不如专用 VTON 或 Consistency LoRA |

### 3.4 必须在线 API（降级列出）

| 方案 | 链接 | 说明 |
| --- | --- | --- |
| **Bria Virtual Try-On** | [Comfy 教程](https://docs.comfy.org/tutorials/partner-nodes/bria/product-compositing) · [工作流](https://comfy.org/workflows/c5e28a935db5-c5e28a935db5/) | `person_image` + 1～3 `garment_images`；文档明确保脸、姿势、背景；需 Comfy 积分/云 |
| **Kling Virtual Try-On** | [Comfy 教程](https://docs.comfy.org/tutorials/partner-nodes/kling/kling-virtual-try-on) · [工作流](https://comfy.org/workflows/9038d2d953b6-9038d2d953b6/) | 人物 + 衣物两图；默认 `keep_pose`；保脸与姿势；云 API |

---

## 4. 推荐方案详表（均未本机实测）

### 4.1 【最推荐 · 贴 Qwen-2.1】AusBoss Outfit Swap Consistency LoRA + 工作流

| 项 | 内容 |
| --- | --- |
| 名称 | Qwen-Image-2.1 Outfit Swap Consistency LoRA / Civitai「Outfit Swap \| Virtual Try-On」 |
| 链接 | [HF LoRA](https://huggingface.co/ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA) · [HF 工作流 JSON](https://huggingface.co/ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA/blob/main/workflows/qwen-image-2.1-outfit-swap.json) · [Civitai 工作流](https://civitai.com/models/2983126/qwen-image-21-outfit-swap-or-virtual-try-on) · [ComfyUI Wiki 说明](https://comfyui-wiki.com/en/news/2026-10-07-qwen-image-2-1-outfit-swap-lora) |
| 输入怎么接 | **Image 1 = 人物**；**Image 2 = 衣物/穿戴参考**（可裁剪到目标衣物）；可选视觉模型自动写 prompt |
| 提示词范式 | `Dress the person in image 1 in the <outfit> shown in image 2. Keep their face, hair, hands, pose and the background exactly the same.` + 默认追加 `Replace everything they wear.` |
| 保脸/保背景 | **设计目标就是这两项**。作者 16 次未见过训练对的对比：对齐后脸变化 1.7% vs 无 LoRA 14.1%；背景 0.9% vs 10.8%；画框漂移 0.1px vs 3.6px |
| 本地 | ✅ 权重进 `models/loras/`；叠在 Comfy-Org Qwen Image 2.1 上；需 AusBoss nodes ≥2.5.1、ComfyUI ≥0.38 |
| 显存粗估 | 与 Qwen-Image-2.1 Edit 同级；作者示例用 int8 权重（扩散 ~7.3GB + TE ~9.4GB + VAE）；**24GB 通常够用**（未实测） |
| 许可 | Qwen Research License：**默认非商用**（工作流页写明）；LoRA 本身以适配器形式发布，使用仍受基模许可约束 |
| 缺口 | 不提升纽扣/花纹等衣物细节（有时不如裸模抄得全）；旧衣/鞋可能残留；姿势锁死（需要换姿的衣服不会自动改姿）；需额外装 AusBoss 节点 |
| 实测 | **未实测** |

**最小自拼步骤（无完整 JSON 时）：**

1. `LoraLoaderModelOnly` 加载 `qwen-image-2.1-outfit-swap.safetensors`，强度 **1.0**（推荐 step 1000 主文件）  
2. `TextEncodeQwenImage21`：`image_1`=人物，`image_2`=衣物，`resolution`=0  
3. KSampler：25 steps，CFG 1，euler/simple，denoise 1，接 encoder 的 **latent**  
4. VAE Decode → Split Image with Alpha（2.1 VAE 出 RGBA）

### 4.2 【专用 VTON · 蒙版硬保】CatVTON（Comfy）

| 项 | 内容 |
| --- | --- |
| 名称 | CatVTON / Comfyui-CatVTON |
| 链接 | [官方仓库](https://github.com/Zheng-Chong/CatVTON) · [Comfy 发布包](https://github.com/Zheng-Chong/CatVTON/releases/tag/ComfyUI)（`ComfyUI-CatVTON.zip` + `catvton_workflow.json`） · [社区节点](https://github.com/pzc163/Comfyui-CatVTON) · [HF](https://huggingface.co/zhengchong/CatVTON) |
| 输入 | 左/人物图；右/衣物参考；`cloth_type` 匹配 upper/lower/overall；自动 mask（需 DensePose） |
| 保脸/保背景 | 靠衣服区域 mask；非白区保留；典型 VTON 行为 |
| 本地 | ✅；首次运行自动下权重 |
| 显存 | 官方称 1024×768 bf16 **< 8GB** |
| 许可 | 见仓库 / HF 模型卡（科研向居多，商用需自核） |
| 缺口 | Detectron2/DensePose 安装痛（尤其 Windows）；与 Qwen-2.1 无关；偏电商半身试衣数据集气质 |
| 实测 | **未实测** |

### 4.3 【专用 VTON · 高保真衣物】FitDiT（Comfy）

| 项 | 内容 |
| --- | --- |
| 名称 | FitDiT ComfyUI |
| 链接 | [FitDiT 主仓](https://github.com/BoyuanJiang/FitDiT) · 分支说明见搜索结果中的 `FitDiT-ComfyUI` / `fitdit_workflow.json` · [节点说明（comfy.icu）](https://comfy.icu/node/FitDiTTryOn) |
| 输入 | `model_image`（人物）+ `garment_image`（衣物）；Mask Generator 产出 mask / pose |
| 保脸/保背景 | 蒙版+姿态；管线 pad/resize 后还原原尺寸；主要改服装区 |
| 本地 | ✅；权重放 `models/FitDiT_models`，CLIP 放 `models/clip`；支持 `with_offload` / `with_aggressive_offload` |
| 显存 | 24GB 通常可跑中等分辨率；更低可用 offload（更慢） |
| 缺口 | 依赖官方/Manager 安装路径；非 Qwen 栈；衣物平铺图效果更好 |
| 实测 | **未实测** |

### 4.4 【专用 VTON】IDM-VTON / Leffa

| 方案 | 链接 | 输入 | 保脸/背景 | 本地 / 显存 | 缺口 |
| --- | --- | --- | --- | --- | --- |
| **IDM-VTON** | [TemryL/ComfyUI-IDM-VTON](https://github.com/TemryL/ComfyUI-IDM-VTON/) | 人物 + 衣物；SAM mask；DensePose | 蒙版外保留 | ✅；声明 **≥16GB** | 依赖多；安装重 |
| **Leffa（全管线）** | [Bionic ComfyUI-Leffa](https://github.com/Bionic-AI-Solutions/ComfyUI-Leffa) · [StartHua/Comfyui_leffa](https://github.com/StartHua/Comfyui_leffa) · 权重 [franciszzj/Leffa](https://huggingface.co/franciszzj/Leffa) | 人物 + 衣物（全管线版自动解析）；`garment_type` | 蒙版/解析区外保留 | ✅；整包约 **~34GB** | 磁盘大；StartHua 版常要自备 DensePose/mask |

### 4.5 【降级 · 云】Bria / Kling

见 §3.4。输入形态与需求几乎一致（人物 + 衣物，文档写保脸背景），但**非本地、非无审查优先路径**。

### 4.6 其它可参考（非首选）

| 方案 | 链接 | 说明 |
| --- | --- | --- |
| RunComfy「Qwen 2.1 Outfit Change」 | [工作流页](https://www.runcomfy.com/comfyui-workflows/qwen-image-2-1-outfit-change-in-comfyui-reference-try-on) | 双图 Edit 换装模板；**未**捆绑 Consistency LoRA 时，脸/背景稳定性弱于 4.1 |
| Qwen Image Edit 换衣教程 | [MyAIForce Clothes Swap](https://myaiforce.com/qwen-image-edit-clothes-swap/) · [Edit 2511 outfit](https://www.nextdiffusion.ai/tutorials/consistent-outfit-changes-with-multi-qwen-image-edit-2511-in-comfyui) | 旧/Edit 线；可用蒙版限制区域；保一致性不如 2.1+Consistency LoRA 专精 |
| OOTDiffusion | [levihsu/OOTDiffusion](https://github.com/levihsu/ootdiffusion) | 独立推理为主 |
| CatV2TON | [Zheng-Chong/CatV2TON](https://github.com/zheng-chong/catv2ton) | 图+视频；缺成熟 Comfy JSON |

---

## 5. Qwen-Image-2.1 / Edit / Fun ControlNet Union 专项核对

### 5.1 官方 / 原生 Image Edit（无 LoRA）

- **能做**：双图（人物 + 衣物）+ 自然语言「把 image1 换成 image2 的衣服，保持脸和背景」。  
- **不够稳**：AusBoss 公开测量——画框漂移、脸软化、背景重绘、全身衣塞进半身照导致拉远。  
- **结论**：作为基线可行；要「尽量保脸保背景」应加 **Outfit Swap Consistency LoRA**（§4.1）。

### 5.2 Outfit Swap Consistency LoRA（推荐路径）

- 明确为 **virtual try-on / outfit swap** 训练；输入语义就是人物图 + 衣物图。  
- **现成 JSON**：HF `workflows/qwen-image-2.1-outfit-swap.json`；Civitai 同源 v1.1（含衣物裁剪控件、自动描述衣物、旧衣替换句）。  
- 与用户需求：**匹配度最高**。

### 5.3 Fun ControlNet Union / T8（换装能力）

| 问题 | 答案 |
| --- | --- |
| 有无「换装」专用现成 JSON？ | **无**。T8 `workflows/` 是 Canny/Depth/Pose/…、pose_reference_edit、pose_reference_inpaint 等，**无** try-on / outfit / clothes 命名模板 |
| 能否自拼？ | **可以近似**：`reference_image`=人物；`reference_image_2`=衣物；prompt 写换装并保脸背景；或再加 **衣服白蒙版** → `inpaint_image` + `mask`，衣物参考进 `_2` |
| 蒙版是否硬保背景？ | README：**mask 条件化模型，不保证蒙版外像素不变** |
| 与 Consistency LoRA 关系 | Union 是结构/局部重绘分支；Consistency LoRA 挂在 **原生 2.1 Edit 双图编码** 路径。二者可概念上组合，但**无**公开「Union+OutfitSwapLoRA」现成 JSON |
| 许可 | [alibaba-pai Fun ControlNet Union](https://huggingface.co/alibaba-pai/Qwen-Image-2.1-Fun-Controlnet-Union) 随 Qwen 研究许可，**默认非商用** |

**建议**：若目标是「人物+衣物、保脸保背景」——优先 §4.1，不必先绕 Union。若还要**同时**锁姿势/深度，再考虑 Union inpaint + 衣物参考，或先换装再 pose_reference_edit。

### 5.4 官方 Inpaint 类模板

- 存在「局部重绘 + 参考」类云/托管模板（如 RunComfy inpainting），可把衣服区域蒙住再参考新衣。  
- 仍属通用 inpaint，**不是**专用 try-on；保背景弱于专用 mask-VTON 与 Consistency LoRA 的定位。

---

## 6. 按用户场景的选用建议

| 优先级 | 选什么 | 何时 |
| --- | --- | --- |
| 1 | **Qwen 2.1 + Outfit Swap Consistency LoRA + Civitai/HF JSON** | 已在用 2.1；要人物+衣物两图；要保脸保背景；本地 |
| 2 | **CatVTON 或 FitDiT** | 更在意衣物褶皱/图案保真；接受独立 VTON 栈与 DensePose/解析 |
| 3 | **自拼 T8 Union inpaint** | 已装 Union；要蒙版局部换 + 可选姿态/深度；接受无现成 try-on JSON |
| 4 | **Bria / Kling Partner** | 可接受云 API、要少踩坑 |

**24GB 显存**：上述本地方案粗看均可尝试；CatVTON 最省；Qwen-2.1 int8 Edit + LoRA 与用户现有 2.1 预算一致；Leffa 更吃磁盘与加载策略。

---

## 7. 主要缺口与注意

1. **旧衣残留**：鞋、牛仔裤、腰带可能留在新装下；用 `Replace everything they wear.` 或换种子；step 1000 LoRA 相对更爱脱掉旧装。  
2. **衣物细节**：Consistency LoRA **不**负责抄纽扣/花纹；要极致衣物保真看 FitDiT/CatVTON/Leffa。  
3. **半身 vs 全身**：全身衣参考塞进半身人物易导致拉远——工作流用裁剪/「只穿上半」逻辑缓解。  
4. **姿势锁死**：保背景/保构图的代价是姿势基本不变；要改动作需另接 Pose 控制（此前调研的 Fun Union）。  
5. **许可**：Qwen-Image-2.1 / Fun Union / 多数量化权重默认 **研究/非商用**；上线商用前核许可证。  
6. **API 审查**：Bria/Kling 等有 moderation；与「无审查本地」偏好冲突。  
7. **本调研未出图实测**；数值与「保脸保背景」百分比来自作者公开测评页面，非本机复现。

---

## 8. 关键链接速查

- [AusBoss Consistency LoRA (HF)](https://huggingface.co/ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA)  
- [Outfit Swap 工作流 JSON (HF)](https://huggingface.co/ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA/blob/main/workflows/qwen-image-2.1-outfit-swap.json)  
- [Civitai Outfit Swap \| Virtual Try-On](https://civitai.com/models/2983126/qwen-image-21-outfit-swap-or-virtual-try-on)  
- [CatVTON](https://github.com/Zheng-Chong/CatVTON) · [Comfy Release](https://github.com/Zheng-Chong/CatVTON/releases/tag/ComfyUI)  
- [FitDiT](https://github.com/BoyuanJiang/FitDiT)  
- [ComfyUI-IDM-VTON](https://github.com/TemryL/ComfyUI-IDM-VTON/)  
- [ComfyUI-Leffa (Bionic)](https://github.com/Bionic-AI-Solutions/ComfyUI-Leffa) · [StartHua Leffa](https://github.com/StartHua/Comfyui_leffa)  
- [T8 Fun ControlNet Union](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8)  
- [Fun ControlNet Union 权重](https://huggingface.co/alibaba-pai/Qwen-Image-2.1-Fun-Controlnet-Union)  
- [Bria VTON 教程](https://docs.comfy.org/tutorials/partner-nodes/bria/product-compositing)  
- [Kling VTON 教程](https://docs.comfy.org/tutorials/partner-nodes/kling/kling-virtual-try-on)  
- 相关前序调研：[qwen-image-2.1-pose-depth-workflows-2026-10-30.md](./qwen-image-2.1-pose-depth-workflows-2026-10-30.md)

---

*报告结束。所有「保脸/保背景」效果声明均来自公开文档或作者测评；本调研未本机跑通出图。*
