# Phase 0 取证证据

> 日期：2026-11-28  
> 取证机：办公室主机（本机 Orca worker）  
> ComfyUI：`http://10.10.12.140:8188`（可达）

## 1. 官方 `@openclaw/comfy-provider@2026.11.10` 基线

本机无 `~/.openclaw/extensions/comfy`。改从 npm 拉取官方包并对照 GitHub `main` 源码：

| 来源 | 路径 / 产物 |
|---|---|
| npm pack | `.tmp-comfy-upstream/openclaw-comfy-provider-2026.11.10.tgz` |
| 解包 | `.tmp-comfy-upstream/package/`（仅 `dist/*.js` + `openclaw.plugin.json`） |
| 上游 TS | `docs/phase0-raw/extensions_comfy_*.ts`（raw.githubusercontent.com） |

关键事实：

- 插件 id / provider id：`comfy`；默认模型：`workflow`（即 `comfy/workflow`）。
- `capabilities.edit.maxInputImages = 1`；`>1` 直接抛错。
- 配置保留单图键：`inputImageNodeId` / `inputImageInputName`。
- 默认 `timeoutMs` 回退为 `300000`（源码 `DEFAULT_TIMEOUT_MS = 3e5`），与需求 600s 不一致，需由 `comfy-plus` 默认 `600000`。
- **禁止修改**官方扩展；本任务仅只读取证。

## 2. `ImageGenerationRequest` 透传面（plugin-sdk）

来源：`openclaw` npm `2026.11.10` + GitHub `src/image-generation/provider-types.ts`（见 `docs/phase0-raw/src_image-generation_provider-types.ts`）。

一等字段：

`provider`, `model`, `prompt`, `cfg`（**OpenClaw 配置对象，非采样 CFG**）, `agentDir`, `authStore`, `timeoutMs`, `signal`, `count`, `size`, `aspectRatio`, `resolution`（仅 `1K|2K|4K`）, `quality`, `outputFormat`, `background`, `inputImages`, `providerOptions`, `ssrfPolicy`。

**缺口（无一等字段）**：`operation`、`steps`、采样 `cfg`、`negativePrompt`、`seed`、`loraEnabled`、`loraStrength`、`imageRoles`、`width`/`height`（需从 `size` 解析或 `providerOptions`）。

**开工结论**：扩展参数一律从 `providerOptions`（及 `size`）读取；插件内定义明确约定键，禁止假设宿主已一等透传。

## 3. 140 `/object_info` 与 `/models/*`

| 端点 | 结果 | 产物 |
|---|---|---|
| `GET /object_info` | 200，约 3.0 MB | `docs/phase0-raw/object_info.json` |
| `GET /models/diffusion_models` | 含 UC / 2511 等 | `docs/phase0-raw/models_diffusion_models.json` |
| `GET /models/text_encoders` | 含 `qwen3vl_8b_int8_convrot`、`qwen_2.5_vl_7b_fp8_scaled` | `docs/phase0-raw/models_text_encoders.json` |
| `GET /models/vae` | 含 `qwen_image_2.1_vae_bf16`、`qwen_image_vae` | `docs/phase0-raw/models_vae.json` |
| `GET /models/loras` | 含 UC LoRA、Color-Grade、PoseStudio | `docs/phase0-raw/models_loras.json` |
| `GET /models/unet`、`/models/clip` | **404**（此版 ComfyUI 无此别名） | 记入缺口 |

### `TextEncodeQwenImage21`

- required：`clip`, `prompt`, `negative_prompt`, `resolution`, `images`（`COMFY_AUTOGROW_V3`，`image_1`…`image_16`，`min: 0`）
- optional：`vae`
- outputs：`positive`, `negative`, **`latent`（index 2）**
- 结论：Edit 工作流 `KSampler.latent_image = [textEncodeId, 2]` 可跟随首图比例（验收 #3）。无图时应走独立 T2I（`EmptyLatentImage`），不要把空 `images` 硬塞进同一套 LazySwitch 图。

### Phase 5 相关节点预检

| 能力 | 资产 / 节点 | 140 状态 |
|---|---|---|
| 调色 | `QIE-2511-Color-Grade-Transfer-LoRA` + `qwen_image_edit_2511_fp8mixed` + `qwen_2.5_vl_7b_fp8_scaled` + `qwen_image_vae` + `ColorMatch` | **资产与 ColorMatch 均存在**；属 Edit-2511 家族，与 2.1 UC 三件套不兼容 |
| 换姿 | `VNCCS_QI2_PoseStudioV1.1` LoRA；节点名无独立 `VNCCS*` class | LoRA 存在；拓扑需参考 LiberAstra `qwen_image_21_posestudio`（槽位反序、透明底压白） |

**门禁**：`operations.colorGrade.enabled` / `pose.enabled` 默认 `false`，未经 140 实测归档不得开启。

## 4. 已验证真值工作流（PNG 内嵌 prompt）

| 产物 | 尺寸 | 内嵌 API Prompt |
|---|---|---|
| `qwen-image-uc_00060_.png`（T2I） | 1024×1024 | `docs/phase0-raw/qwen-image-uc_00060_.png.prompt.json` |
| `qwen-image-uc_00061_.png`（单图编辑） | 704×1504 | `docs/phase0-raw/qwen-image-uc_00061_.png.prompt.json` |

观察：

- 140 当前真值图是 **T2I/Edit 合一** 的 LazySwitch 图（`VHS_LoadImagePath` + 本地绝对路径拼接 + `LazySwitchKJ`），**不可**作为 OpenClaw 运行时模板直接分发。
- 模型配对已验证：UC UNET + `qwen3vl_8b_int8_convrot` + `qwen_image_2.1_vae_bf16` + UC LoRA；`steps=25`，`cfg=1`，`euler/simple`。
- 单图编辑走 `TextEncodeQwenImage21` 的 `images.image_1`，latent 来自编码器 output 2（经 switch）。
- `comfy-plus` 策略：拆成纯标准 API Prompt 的 `qwen-image-t2i.json` / `qwen-image-edit.json`；Edit 不预置 `LoadImage`，按 N 动态接线。

## 5. 缺口与是否可开工

| 缺口 | 影响 | 处理 |
|---|---|---|
| 本机无 `~/.openclaw/extensions/comfy` | 无法就地 diff 安装树 | 已用 npm `2026.11.10` + GitHub 源码替代，足够做独立包 |
| SDK 无一等扩展采样字段 | 参数需约定 `providerOptions` | 文档化 + schema/defaults 承接 |
| 140 真值图含绝对路径 / LazySwitch / VHS | 不能直接当分发模板 | 重构为标准 LoadImage + 分工作流 |
| `/models/unet|clip` 404 | 无 | 改用 `diffusion_models` / `text_encoders` |
| Phase 5 未实测 | 不得开启开关 | 仅评估材料，`enabled: false` |

**结论：Phase 0 门禁通过，可进入 Phase 1–4 编码。** Phase 5 仅评估、默认关闭。
