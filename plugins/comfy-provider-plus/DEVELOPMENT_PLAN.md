# `@openclaw/comfy-provider-plus`（`comfy-plus`）开发计划

> **需求来源**：[`REQUIREMENTS.md`](./REQUIREMENTS.md)  
> **插件目录**：`plugins/comfy-provider-plus/`  
> **角色分工**：
> - **开发调度**：Bot 长官（负责任务拆解、进度统筹、卡点跟进与验收把关）
> - **代码编写**：Cursor
> - **最终代码审核**：Antigravity

---

## 一、LiberAstra 现有工作流参考边界（只能参考，不能直接使用）

本仓库 `backend/workflows/` 中的工作流属于**“manifest.yaml + Python 运行时图改写”的 Comfy 变体**，开发时只可参考其节点拓扑、模型配对与避坑经验，**不可直接拷贝给 OpenClaw / 原生 ComfyUI 使用**：

| 维度 | LiberAstra 现有实现（仅参考） | 不可直接复用的原因 | `comfy-plus` 改造策略 |
|---|---|---|---|
| **工作流形态** | `manifest.yaml` + 带占位符 `workflow.json`（如 `backend/workflows/qwen_image_21_uncensored/workflow.json`） | 依赖 `backend/liberastra/services/workflows.py` 做类型转换、默认值、`seed=-1` 随机化 | 产出纯标准 ComfyUI API Prompt JSON，由插件配置 schema 显式声明 `nodeId + inputName` 写入 |
| **LoRA 开关** | `manifest.accel` + 运行时摘节点重连（见 `workflows.py` `apply_accel`） | `workflow.json` 硬编码节点 `200`，直接提交无法关闭 LoRA | 在插件内实现**显式配置驱动的 LoRA 旁路**：`loraEnabled=false` 时摘除 LoRA 节点并将下游 `model` 重连回上游 `QwenImage21Cache` |
| **多图输入** | 预置 4 个 `LoadImage`（10–13），未传图靠 `workflow.py` `_detach_unused_media_links` 断边 | 仅支持 4 槽；孤立 `LoadImage` 仍残留在 JSON 中 | `qwen-image-edit.json` 模板不预置占位 `LoadImage`，提交前按实际数量 `N (1..16)` 动态生成 `LoadImage` 并只接 `images.image_1..N`；0 张图走独立 `qwen-image-t2i.json` |
| **节点 ID 规范** | `t2i` 的 KSampler 为 `7`，`edit` 为 `6`，`posestudio` 为 `11` | 各包节点 ID 不一致，且 140 已验证工作流（前缀 `qwen-image-uc`）与 LiberAstra 存在差异 | Phase 0 以 140 已跑通工作流与 `/object_info` 为真值，重构并统一 4 套新工作流的节点编号 |
| **提示词槽位格式** | `qwen_image_21_edit_multi_uncensored/manifest.yaml` 写 `image 1`，`site/docs-src/guides/image.md` 与 `edit-rules.md` 写 `<image1>`；`canvas_graph.py` 仅做静态替换 | 与本次验收 #4（`image_1` / `image_2`）不一致，且缺少自然语言序号解析与越界拒绝 | 插件内置独立提示词规范化器，默认目标格式为 `image_N`（可配置模板），带严格非图数字保护与越界拒绝 |
| **调色工作流** | `backend/workflows/qwen_edit_2511_color_grade/` | **高危架构差异**：`QIE-2511-Color-Grade-Transfer-LoRA` 属于 **Qwen-Image-Edit-2511** 系列（需 `qwen_image_edit_2511_*` + `qwen_2.5_vl_7b_*` + `qwen_image_vae` + KJNodes `ColorMatch`/`color-matcher`），与 Qwen-Image 2.1 三件套不兼容 | 第一版保持 `enabled: false`；Phase 5 先核查 140 资产与节点，缺件直接记录结论，不硬塞进 2.1 |
| **换姿工作流** | `backend/workflows/qwen_image_21_posestudio/` + `backend/liberastra/services/pose_image.py` | ① 内部槽位反序（`image_1=姿态图`，`image_2=人物照`）；② 依赖 Python 透明底压白底预处理；③ 依赖 `manifest.size` 覆写 `EmptyLatentImage` 控长边 ≤ 2048；④ 在官方 2.1 底模上验证而非 UC 底模；⑤ 要求姿态图为线稿/深度图 | 第一版保持 `enabled: false`；Phase 5 专项评估槽位映射、透明底处理、UC 底模身份保持及是否缺姿态预处理节点 |

---

## 二、目标架构与核心模块设计

### 2.1 包与目录结构

独立 OpenClaw 插件包，以 `~/.openclaw/extensions/comfy`（`2026.11.10`）为上游基线，**严禁修改官方 `extensions/comfy`**：

```text
plugins/comfy-provider-plus/
├── package.json                      # "@openclaw/comfy-provider-plus"
├── openclaw.plugin.json              # id: "comfy-plus", contracts.imageGenerationProviders: ["comfy-plus"]
├── index.ts                          # register(api) -> api.registerImageGenerationProvider(...)
├── src/
│   ├── config/
│   │   ├── schema.ts                 # 严格配置 Schema（不保留官方单图旧键）
│   │   └── defaults.ts               # UC 默认模型、25步、CFG 1、600000ms 超时、默认节点映射
│   ├── router/
│   │   └── operation-router.ts       # 路由：0图->t2i, 1..16图->edit, color-grade/pose 强门禁校验
│   ├── prompt/
│   │   └── slot-normalizer.ts        # 纯确定性规则/正则：图片指代规范化 -> image_N、角色映射、越界拒绝、审计记录
│   ├── workflow/
│   │   ├── loader.ts                 # 模板加载、深拷贝、启动/提交前节点存在性校验
│   │   ├── injector.ts               # 显式 nodeId+inputName 参数写入、LoRA 节点旁路、1..16 动态 LoadImage 接线
│   │   └── presets.ts                # 节点映射契约定义（T2I / Edit / 预留 ColorGrade & Pose）
│   ├── comfy/
│   │   ├── client.ts                 # 继承官方提交/轮询/下载行为 + 事务性多图上传 + 600s 超时 & 瞬时重试
│   │   └── errors.ts                 # 四类错误归类 + 密钥与本地敏感路径脱敏
│   └── types.ts
├── workflows/                        # 随包分发/同步到 ~/.openclaw/workspace/workflows/comfy-plus/
│   ├── qwen-image-t2i.json
│   ├── qwen-image-edit.json
│   ├── qwen-image-color-grade.json   # Phase 5 评估产物
│   └── qwen-image-pose.json          # Phase 5 评估产物
└── test/
    ├── slot-normalizer.test.ts
    ├── workflow-injector.test.ts
    ├── upload-and-errors.test.ts
    ├── timeout-600s.test.ts
    └── integration-140.test.ts
```

### 2.2 关键技术设计决策

#### 1. 工作流拓扑与节点契约
- **`qwen-image-t2i.json`（0 张参考图）**：
  - 拓扑：`UNETLoader` → `QwenImage21Cache` → `LoraLoaderModelOnly` → `KSampler` ← `TextEncodeQwenImage21`（**无 `vae`、无 `images.*`、整图零 `LoadImage` 节点**） + `EmptyLatentImage`（默认 `1024×1024`，支持 `width`/`height` 覆盖）→ `VAEDecode` → `SaveImage`。
  - 默认参数：`qwen-image-2.1-UC-int8_convrot.safetensors`、`qwen3vl_8b_int8_convrot.safetensors`、`qwen_image_2.1_vae_bf16.safetensors`、`qwen-image-2.1-uncensored-lora.safetensors`（`loraEnabled=true`, `loraStrength=1.0`）、`steps=25`、`cfg=1`、`euler/simple`。
- **`qwen-image-edit.json`（1–16 张参考图）**：
  - `TextEncodeQwenImage21` 连接 `clip`、`vae`、`prompt`、`negative_prompt`、`resolution`（默认 `1024`）。
  - `KSampler.latent_image` 默认连接 `["<textEncodeNodeId>", 2]`，确保非方形首图自动跟随 `image_1` 比例（满足验收 #3）。
  - **动态接线**：模板不预置占位 `LoadImage`。运行时按实际上传数 `N ∈ [1, 16]` 分配确定性节点 ID（如 `101..100+N`）创建 `LoadImage`，并将 `images.image_1..images.image_N` 写入 `TextEncodeQwenImage21.inputs`；严格校验 `imageCount === N` 且不存在空路径。
  - **图生图 `width`/`height` 覆盖核验**：Phase 0 需核验 140 上 `TextEncodeQwenImage21` 输出槽 `2` (`LATENT`) 是否含参考像素 latent；若为空画布 latent，可在显式传宽高时切 `EmptyLatentImage`；否则通过 `resolution` 控制并明确记录元数据。

#### 2. 显式配置 Schema（禁止全图模糊搜索）
- 按新 schema 设计，**不保留**官方 `inputImageNodeId` / `inputImageInputName` 兼容层。
- 顶层配置：`mode`（`local`）、`baseUrl`、`timeoutMs`（默认 `600000`）、`maxUploadBytes`、`workflows`（`t2i`/`edit`/`colorGrade`/`pose` 路径）、`defaults`（`unetName`/`clipName`/`vaeName`/`loraName`/`loraStrength`/`loraEnabled`/`steps`/`cfg`/`width`/`height`/`resolution`/`negativePrompt`）、`operations`（`colorGrade.enabled=false`、`pose.enabled=false`）、`nodeBindings`。
- `nodeBindings` 为每个工作流显式声明 `prompt`、`negativePrompt`、`seed`、`steps`、`cfg`、`width`、`height`、`resolution`、`unetName`、`clipName`、`vaeName`、`lora`（含 `nodeId`/`nameInputName`/`strengthInputName`/`bypassInputName`）、`imageEncoder`（含 `nodeId`/`inputPrefix` 或显式槽位数组）、`output`（`nodeId`/`outputKey`）。
- 加载与提交前校验所有配置的 `nodeId` 在工作流 JSON 中存在，不存在即直接报错，禁止模糊扫描替换。

#### 3. 提示词槽位规范化器（`src/prompt/slot-normalizer.ts`）
> **实现方式明确：纯确定性词法规则 / 正则（不调用 LLM）**。自然语言会话理解与传图顺序编排由上游 OpenClaw 主 Agent 负责；插件内只做确定性规整、强约束守门与审计记录，保证零额外模型依赖、不猜测模糊指代、100% 可单测回归。

- **前置门禁**：
  - 无图模式下若提示词包含明确图片序号（如 `图1`、`第一张图`），提交前拒绝，不静默退回文生图。
  - `operation` 未识别或对应开关为 `false` 时直接报错（`"调色工作流未验证"` / `"换姿工作流未验证"`），不退回通用编辑或文生图。
- **保护区间与明确序号规则**：
  - 先保护普通数量词与尺寸/采样词：`两个人`、`三只猫`、`1024 宽`、`1920x1080`、`16:9`、`25 步`、`CFG 1`、`第一天`。
  - 匹配明确图片指代：`图1`/`图一`/`图片2`/`照片3`/`参考图4`/`第一张`/`第二张图`/`第3张参考图`/`image 1`/`image_1`/`<image1>`/`first image`/`2nd reference image`。
  - 中文数字解析覆盖 `一`–`九十九` 及 `两`→2，确保超界序号（如 `图17`、`第二十张`）被准确捕获并拒绝。
  - 对 `第X张` 增加后置词守卫：命中 `第二张图`、`第一张人物`、`第3张参考图`，避开 `第一张桌子`、`第二张椅子` 等非图片物体量词。
- **角色映射与模糊指代**：
  - 调用方提供 `imageRoles` 时按显式角色表映射；未提供角色时，对 `"左边那张"`、`"衣服那张"` 等模糊描述**不做猜测**，原样保留并记录提示，要求调用方改用明确序号。
- **越界拒绝与审计记录**：
  - 任意提取序号 `< 1` 或 `> actualImageCount` 时，提交前直接拒绝并指出缺失槽位。
  - 每次提交保留 `{ originalPrompt, normalizedPrompt, slotMap: [{ slot, sourceName, comfyFilename, role? }], warnings }`。

#### 4. 多图事务性上传、错误分类与 600s 超时
- **本地全量预检**：上传前遍历 `1..N`，校验文件非空、未超配置大小上限、魔数/MIME 符合 ComfyUI 支持格式；任一张失败直接返回 1-based 序号和原因，不发网络请求。
- **顺序上传与原子失败**：按调用方顺序上传，文件名唯一且可追溯（`ocp_<reqId>_img<01..16>_<safeName>.<ext>`）；第 `k` 张上传失败时中止整次请求，不提交不完整工作流。
- **四类错误分类 + 严格脱敏**：
  1. `COMFY_UNREACHABLE`
  2. `UPLOAD_FAILED`（含序号和原因）
  3. `EXECUTION_FAILED`（提取 `node_type`/`node_id`/精简异常消息）
  4. `EXECUTION_TIMEOUT`（超时后尽力调用 `/queue` delete + `/interrupt` 清理孤儿任务）
  - 所有对外错误信息剥离密钥、Token、本机绝对路径（`/Users/...`、`/home/ps/...`、`C:\...`）及原始堆栈。
- **600s 超时实现细节**：
  - 总 deadline 默认 `600000ms`；单次 `/history/{id}` 轮询超时设为短超时（如 `15–30s`）并对瞬时网络/读超时重试至总 deadline，避免 ComfyUI 忙时单次轮询失败中断任务，同时规避 Node `fetch`/undici 默认 300s `headersTimeout` 提前截断。

---

## 三、分阶段实施顺序

### Phase 0：上游基线与 140 环境取证（编码前置门禁）
1. 只读检视 `~/.openclaw/extensions/comfy`（`v2026.11.10`）源码与 `openclaw/plugin-sdk` 的 `ImageGenerationProvider` / `ImageGenerationRequest` 类型定义，确认 `operation`、`steps`、`cfg`、`negativePrompt`、`seed`、`loraEnabled`、`loraStrength`、`imageRoles` 的实际透传入口。
2. 拉取 `http://10.10.12.140:8188/object_info` 与 `/models/*`，导出并核对 140 已验证 `qwen-image-uc_00060_.png`（T2I）和 `qwen-image-uc_00061_.png`（单图 704×1504）真实工作流 JSON。
3. 核验 `TextEncodeQwenImage21` 对 `image_1` 槽位语法及 output 2 (`LATENT`) 的行为，并预检 140 是否具备调色（Edit-2511 三件套 + `ColorMatch`）与换姿相关节点。

### Phase 1：独立插件脚手架与 Schema 建立
- 复制官方插件代码到 `plugins/comfy-provider-plus/`（不动 `~/.openclaw/extensions/comfy`）。
- 改为 `@openclaw/comfy-provider-plus`、插件 id `comfy-plus`、provider id `comfy-plus`、模型 `comfy-plus/workflow`，声明 `capabilities.edit.maxInputImages = 16`。
- 移除官方单图配置键，落地新 config schema 与校验测试。

### Phase 2：标准 T2I 与单图工作流迁移（无功能倒退）
- 基于 Phase 0 140 真值工作流并参考 LiberAstra 拓扑，落地标准 `qwen-image-t2i.json` 与 `qwen-image-edit.json`。
- 跑通文生图与单图编辑，验证与 `qwen-image-uc_00060_.png` / `00061_.png` 等价无倒退，且文生图历史无 `LoadImage` 节点执行。

### Phase 3：真实多图上传、按数量动态接线与提示词规范化
- 实现 `1..16` 张预检、顺序上传、原子失败与动态 `LoadImage` + `images.image_1..N` 接线（`>16` 本地拒绝）。
- 实现 `src/prompt/slot-normalizer.ts` 及全量正反单测（覆盖验收 #4、#5）。
- 140 实跑 `1 / 2 / 16` 张参考图并核对编码器接线顺序与显存/耗时表现。

### Phase 4：全参数映射、错误分类、600s 超时与上线切换
- 完成全部通用/模型/图生图显式参数映射、`loraEnabled=false` 旁路、元数据回显。
- 完成四类错误分类、敏感信息脱敏、使用真实配置 `600000ms` 的超时测试（fake timer + 慢响应代理实测）。
- 通过 OpenClaw 配置命令切换：停用 `comfy` → 启用 `comfy-plus` → 默认图片模型改为 `comfy-plus/workflow` → 核对回退模型 `google/gemini-3.1-flash-image` 未丢失。

### Phase 5：调色与换姿独立可行性评估（门禁后置）
- 两项操作默认 `enabled: false`。
- **调色**：先核查 140 是否具备 Edit-2511 三件套与 KJNodes `ColorMatch`；若缺件直接定论并保持关闭；若齐备，用同一原图 + 两组差异明显的色彩参考图验证色彩变化与身份/构图保真度。
- **换姿**：参考 `qwen_image_21_posestudio` 构建 `qwen-image-pose.json`（注意 `image_1=姿态图` / `image_2=人物原图` 反序映射、透明底线稿压白底、输出尺寸防护），实测 UC 底模 + `VNCCS_QI2_PoseStudioV1.1.safetensors` 在线稿/深度图与真人姿态照下的边界。
- 产出完整评估记录（工作流路径、输入输出路径、成功/失败、显存峰值、耗时、不可用原因）；仅达标且有成功样本与失败边界记录后才开启对应开关。

---

## 四、验收对照矩阵（10 条验收项）

| # | 验收标准 | 自动化单测 / Mock | 140 实机联调 |
|---|---|---|---|
| 1 | 无参考图生图，ComfyUI 历史无 `LoadImage` 执行 | 断言 T2I 提交 JSON 无 `LoadImage` 与 `images.*` | 检查 `/history/{id}` 执行节点列表 |
| 2 | 1 / 2 / 16 张按序进入编码器；17 张本地拒绝 | 测试 `N=1,2,16` 接线正确；`N=17` 0 网络请求直接拒 | 140 实跑 1/2/16 张并核对 `/history` |
| 3 | 第一张参考图为非方形时，输出比例跟随首图 | 断言 Edit `KSampler.latent_image` 接 `[textEncodeId, 2]` | 竖图实测验证输出比例与首图一致 |
| 4 | “把第二张图的衣服换到第一张人物身上”规范化为 `image_2`/`image_1` 且与接线一致 | `slot-normalizer.test.ts` 断言规范化文与 `slotMap` | 140 双图实测核对提交体 `prompt` 与 `images.image_1/2` |
| 5 | “图3”仅传 2 张被拒绝；“两个人”“1024 宽”不被替换 | 边界单测覆盖越界、`两个人`、`1024 宽`、`第一张桌子`、`左边那张` | 端到端校验越界直接拒绝不上传 |
| 6 | 宽高、步数、CFG、负面提示词、种子、LoRA 强度可在元数据或提交体核对 | `workflow-injector.test.ts` 断言各显式绑定与 LoRA 旁路 | 140 覆盖参数实测并核对返回元数据与 `/history` |
| 7 | 不可达、上传失败、执行失败、超时四类错误均返回明确原因且无密钥/本地敏感路径 | Mock 四类异常并正则校验脱敏 | 实测错误地址、非法文件、错误模型名、超时文案 |
| 8 | 600 秒超时测试使用真实配置值 `600000` | fake timers + 真实 `timeoutMs: 600000` 验证 | 延迟代理验证默认 `600000` 不被底层 300s 截断 |
| 9 | 停用官方 `comfy` 后默认命中 `comfy-plus/workflow`，回退模型不丢失 | 配置校验单测 | OpenClaw 配置切换后核验默认命中与回退配置 |
| 10 | 调色和换姿关闭时不可调用；开启前各有成功样本和失败边界记录 | 断言 `enabled: false` 返回未验证错误且不退回通用编辑 | 归档 Phase 5 评估报告后再决定开启 |

---

## 五、协作与审核门禁

1. **调度（长官）**：按 Phase 0 → Phase 5 顺序派发任务给 **Cursor**；Phase 0 取证结果确认后再进入 Phase 1–4 编码；Phase 4 测试全绿后再执行上线切换与 Phase 5 评估。
2. **实现（Cursor）**：所有插件源码与测试落在 `plugins/comfy-provider-plus/`，工作流模板同步产出标准 ComfyUI API JSON，提交自测报告（单测 + 140 联调证据）。
3. **代码审核（Antigravity）**：Cursor 完成开发与自测后，交由 **Antigravity** 进行最终代码审核，重点审查：
   - 官方 `extensions/comfy` 零改动与旧单图配置键零残留；
   - 参数写入 100% 走显式 `nodeId + inputName`（无模糊 JSON 搜索）；
   - `slot-normalizer.ts` 纯规则边界、越界拒绝、非图数字保护与模糊指代不猜测；
   - 多图事务性上传、错误四分类脱敏与 600s 真实配置超时实现；
   - 调色/换姿门禁锁定与评估证据完整性。
