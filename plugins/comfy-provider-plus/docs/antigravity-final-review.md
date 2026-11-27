# Antigravity 终审报告：`@openclaw/comfy-provider-plus`（`comfy-plus`）

- **审核对象**：LiberAstra PR #5（commit `c1cda2e`，目录 `plugins/comfy-provider-plus/`）
- **审核依据**：`DEVELOPMENT_PLAN.md`、`REQUIREMENTS.md`、`docs/phase0-evidence.md`、`docs/phase5-evaluation.md`、`docs/self-test-report.md` 及全量源码/单测/工作流模板
- **本地验证**：在独立 review worktree 检出 `c1cda2e`，执行 `npm ci`、`npm run typecheck`、`npm run build`、`npm test`（`23 passed | 2 skipped`）及针对已编译 `dist/` 的边界探针脚本，业务代码零改动。

---

## 一、书面审核结论：**驳回（Request Changes）**

**总体评价**：整体包隔离、工作流拆分（T2I 无 `LoadImage`、Edit 动态 1–16 `LoadImage`）、显式 `nodeBindings` 架构、纯规则 `slot-normalizer` 方向、600s 短轮询超时设计以及 Phase 5 默认关闭门禁均符合规划；LiberAstra `backend/` 与官方 `~/.openclaw/extensions/comfy` 零修改。

**驳回原因**：实测源码存在 **3 项 P0 阻断缺陷**（错误脱敏漏泄 Bearer Token 且含引号时 `createComfyError` 抛 `SyntaxError` 崩溃、未知 `operation` 静默回退 `t2i`/`edit`、`openclaw.plugin.json` 激活信号与上线配置文档冲突且 `isComfyPlusConfigured({})` 恒为 `true`）和 **3 项 P1 功能/回归缺陷**（`metadata.applied.seed` 恒为 `undefined`、`slot-normalizer` 吞掉「人物」且漏掉独立「第X张」/「图一百」及坏正则、`integration-140.test.ts` 依赖被 `.gitignore` 忽略的 PNG 导致新检出必崩）。上述 P0/P1 项必须修复并补齐单测后方可合并上线。

---

## 二、6 条必须核对红线检查

| # | 红线要求 | 结果 | 核查证据 |
|---|---|---|---|
| 1 | `backend/workflows/` 仅参考；产出须为纯标准 ComfyUI API Prompt JSON | **基本通过（Phase 5 草稿有小瑕疵）** | `git diff 51d7b9f..c1cda2e -- backend/` 为空。`workflows/qwen-image-t2i.json` 与 `workflows/qwen-image-edit.json` 为纯标准 ComfyUI API Prompt JSON，模型文件名与 `docs/phase0-raw/models_*.json` 逐一匹配，无 `VHS_LoadImagePath`/`LazySwitchKJ`/占位符。Phase 5 两份草稿含顶层 `_meta` 键（提交原始 Comfy `/prompt` 前需剥离，`loader.ts` 已处理，但 `qwen-image-color-grade.json` 节点断链，见 P2-3）。 |
| 2 | 显式 `nodeId + inputName`，禁止模糊搜索 JSON 替换 | **通过（1 处配置未生效）** | `src/workflow/injector.ts` 全部写入均走显式 `setInput(wf, nodeId, inputName, ...)`，无全图模糊扫描。小缺口：`bindings.output.outputKey` 在 `client.extractImages` 中被硬编码为 `images`（见 P2-2）。 |
| 3 | 独立包 `@openclaw/comfy-provider-plus`（`comfy-plus`）；未改官方 `~/.openclaw/extensions/comfy` | **通过** | `package.json`、`openclaw.plugin.json`、`src/config/defaults.ts` 均为 `@openclaw/comfy-provider-plus` / `comfy-plus`；已校验本机无 `~/.openclaw/extensions/comfy` 且 `assertNoLegacyComfyKeys` 明确拒绝官方单图旧键。 |
| 4 | `slot-normalizer` 纯确定性（无 LLM）；模糊指代不猜；越界拒绝；审计字段齐全 | **不通过（存在 P1 缺陷）** | 纯确定性无 LLM、模糊指代不猜、审计结构齐全均达标；但存在验收 #4 吞词（「第一张人物」丢「人物」）、独立「第一张/第二十张」漏匹配、「图一百」绕过越界拒绝、`PROTECT_PATTERNS` 对 `1024 宽`/`25 步` 因 `\b` 失效（见 P1-2）。 |
| 5 | Phase 5 调色/换姿默认 `enabled: false`；高危依赖未实测不得建议开启 | **通过** | `defaults.ts`、`schema.ts`、`openclaw.plugin.json`、`switch-to-comfy-plus.md` 均默认 `false`，且 `provider-runtime.ts:136-139` 额外硬门禁拦截；`docs/phase5-evaluation.md` 明确未实测归档不得开启。 |
| 6 | 扩展参数经 `providerOptions` 透传完整、错误脱敏 | **不通过（存在 P0/P1 缺陷）** | `providerOptions` 映射存在未知 `operation` 静默回退（P0-2）、`metadata.applied.seed` 丢失与 Edit `width`/`height` 失真（P1-1）、`steps`/`width` 等非法值未本地校验（P2-1）；错误脱敏存在 **Bearer Token 明文泄露、`createComfyError` 崩溃、JSON 键未脱敏、本地路径泄露**（P0-1）。 |

---

## 三、10 条验收矩阵对照核查（`DEVELOPMENT_PLAN.md` 第四章 vs `docs/self-test-report.md`）

| # | 验收标准 | 自测报告声称 | 终审认定 | 差异与核查结论 |
|---|---|---|---|---|
| 1 | 无参考图生图，ComfyUI 历史无 `LoadImage` 执行 | 通过 | **通过** | `qwen-image-t2i.json` 无 `LoadImage`/`images.*`，`injector.ts` 有提交前断言；`integration-140` T2I 路径清晰。 |
| 2 | 1/2/16 张按序进入编码器；17 张本地拒绝 | 部分通过 | **部分通过（需补 2/16 实跑）** | 单测覆盖 N=1/2/16 接线与 N=17 本地拒绝；但 `integration-140.test.ts` 仅写 N=1 且引用了被 `.gitignore` 忽略的 `qwen-image-uc_00060_.png`（P1-3），未实跑 N=2/16 满载。 |
| 3 | 第一张参考图为非方形时，输出比例跟随首图 | 通过（结构） | **部分通过（需修 `edit.supportsSize`）** | `KSampler.latent_image = ["5", 2]` 接线正确；但 `index.ts` 声明 `edit.supportsSize: true` 且 `metadata.applied` 回显 `1024×1024` 与实际比例跟随行为矛盾（P1-1）；缺 140 非方形竖图端到端集成用例。 |
| 4 | 「把第二张图的衣服换到第一张人物身上」→ `image_2`/`image_1` 且与接线一致 | 通过 | **不通过（P1-2）** | 实测输出 `"把image_2的衣服换到image_1身上"`，**吞掉了「人物」二字**；且未在 140 双图实测中核对提交体 `prompt` 与 `images.image_1/2`。 |
| 5 | 「图3」仅传 2 张被拒绝；「两个人」「1024 宽」不被替换 | 通过 | **不通过（P1-2）** | 虽单测通过，但探针实测 `PROTECT_PATTERNS` 的 `1024 宽` 和 `25 步` 因 `\b` 跟在中文后完全未命中；且「第二十张」（不带「图」）与「图一百」均绕过越界拒绝。 |
| 6 | 宽高、步数、CFG、负面提示词、种子、LoRA 强度可在元数据或提交体核对 | 通过 | **不通过（P1-1）** | `provider-runtime.ts:221-226` 未传 `seed` 给 `buildAppliedParamsMetadata`，导致返回元数据 `applied.seed` **恒为 `undefined`**；`samplerName`/`scheduler` 声明未注入。 |
| 7 | 不可达、上传失败、执行失败、超时四类错误均返回明确原因且无密钥/本地敏感路径 | 通过 | **不通过（P0-1）** | `redactSensitive` 对 `Authorization: Bearer sk-...` **明文泄露 token**，对裸 `Bearer sk-...` 与 Windows 正斜杠路径 `D:/...` 未脱敏；`createComfyError` 在 `details` 含带引号密钥时直接 **JSON.parse 崩溃**且不脱敏 JSON 键；`loader.ts` 读文件/校验报错泄露未脱敏绝对路径；超时异常在上传/提交阶段误归类为 `EXECUTION_FAILED`。 |
| 8 | 600 秒超时测试使用真实配置值 `600000` | 通过 | **有条件通过（建议补端到端/慢代理）** | 默认 `timeoutMs=600000` 与短轮询（20s）防 undici 300s 截断设计正确，注入时钟单测通过；建议补充经过 `generateComfyPlusImage` 的真实默认超时与本地慢响应 HTTP mock 测试。 |
| 9 | 停用官方 `comfy` 后默认命中 `comfy-plus/workflow`，回退模型不丢失 | 通过（设计校验） | **不通过（P0-3 + 未实机切换）** | `openclaw.plugin.json` 的 `configSignals.required` 强制要求 `nodeBindings`，与 `scripts/switch-to-comfy-plus.md` 配置不一致，上线将导致未激活；`isComfyPlusConfigured({})` 误返回 `true`；`index.ts` 可能双拼 `comfy-plus/comfy-plus/workflow`；且未在 OpenClaw 实机切换验证。 |
| 10 | 调色和换姿关闭时不可调用；开启前各有成功样本和失败边界记录 | 通过 | **通过（门禁达标，待 Phase 5 归档）** | 开关默认关闭且双层门禁拦截有效；未建议开启。 |

---

## 四、问题清单（按严重度排序）

### P0（阻断合并，必须修复）

#### P0-1：错误脱敏漏泄 Token、`createComfyError` 崩溃、路径泄露与错误归类不准
- **涉及文件**：
  - `plugins/comfy-provider-plus/src/comfy/errors.ts`（L3-L28, L30-L44）
  - `plugins/comfy-provider-plus/src/workflow/loader.ts`（L35-L42）
  - `plugins/comfy-provider-plus/src/comfy/client.ts`（L137-L140）
- **复现证据（实测已编译 `dist/`）**：
  1. `redactSensitive("Authorization: Bearer sk-live-999999 and Bearer sk-raw-888888 and C:/Users/liber/secret.png")`
     输出：`"[REDACTED_SECRET] sk-live-999999 and Bearer sk-raw-888888 and C:[REDACTED_PATH]"`（两个 token 均明文泄露；`D:/...` 正斜杠路径完全不脱敏）。
  2. `createComfyError("EXECUTION_FAILED", "x", { msg: 'api_key="sk-123"' })`
     直接抛出 `SyntaxError: Expected ',' or '}' after property value in JSON`，因为 `SECRET_RE` 破坏了 JSON 转义引号。
  3. `createComfyError("EXECUTION_FAILED", "x", { api_key: "sk-secret-123" }).details`
     返回 `{"api_key":"sk-secret-123"}`，JSON 对象中的敏感键完全未被脱敏。
  4. `loadWorkflowTemplate` 抛出的 `ENOENT` 或非法 JSON 报错直接包含未脱敏的本机绝对路径 `${resolved}`。
  5. `ComfyClient.uploadImages` 网络超时/解析异常走 `classifyFetchFailure` 时，未归类为 `UPLOAD_FAILED`（或 `EXECUTION_TIMEOUT`），且丢失 `{ index }`。
- **修改建议**：
  1. 重写 `SECRET_RE`：分别匹配 `Authorization\s*:\s*Bearer\s+\S+`、`\bBearer\s+\S+`、URL 凭证 `://[^/\s:@]+:[^/\s@]+@`、以及 `(?:api[_-]?key|token|secret|password|authorization)\s*[:=]\s*["']?[^\s"',}]+`（注意 `Authorization: Bearer <token>` 整体消费）；扩展 `PATH_RE` 支持 Windows 正反斜杠 `[A-Za-z]:[\\/][^\s"'`,}]+` 及 Linux/macOS 常见根目录 `/Users/|/home/|/root/|/var/|/tmp/|/private/|/etc/|/opt/|/srv/|/mnt/|/Volumes/`。
  2. `createComfyError` 改为递归遍历 `details` 对象（对 key 命中敏感词的值直接置为 `"[REDACTED_SECRET]"`，对 string 值调用 `redactSensitive`），严禁对 `JSON.stringify` 字符串做正则替换再 `JSON.parse`。
  3. `classifyFetchFailure` 增加 `TimeoutError` / `AbortError` / `timeout` 分支归入 `EXECUTION_TIMEOUT`；`uploadImages` 捕获异常时保留 `UPLOAD_FAILED`（网络不可达保留 `COMFY_UNREACHABLE`）并附 `{ index }`。
  4. `loadWorkflowTemplate` 与 `provider-runtime.ts` 外层错误统一经 `createComfyError` / `redactSensitive` 出口，禁止裸路径透出。

#### P0-2：未识别的 `operation` 静默回退到 `t2i` / `edit`
- **涉及文件**：
  - `plugins/comfy-provider-plus/src/router/operation-router.ts`（L10-L18, L40-L70）
  - `plugins/comfy-provider-plus/src/provider-runtime.ts`（L63）
- **复现证据**：
  `routeOperation({ config: DEFAULT_COMFY_PLUS_CONFIG, imageCount: 0, requestedOperation: "inpaint" })` 返回 `{ operation: "t2i", workflowKey: "t2i", imageCount: 0 }`；L66 `if (requested && ...)` 为死代码，因为 `normalizeOperation` 对未知字符串返回 `undefined`。同时 `provider-runtime.ts:63` 用 `str(po.operation)` 把非字符串（如 `operation: 123`）静默吞成 `undefined`。
- **修改建议**：
  1. 在 `routeOperation` 中先判断 `params.requestedOperation !== undefined && params.requestedOperation !== null && params.requestedOperation !== ""`：若非字符串或 `normalizeOperation(...)` 为 `undefined`，立即抛 `VALIDATION_FAILED`（`"未识别的 operation: ..."`），禁止落入自动路由。
  2. `readOverrides` 保留原始 `po.operation`（仅 `undefined` 时省略），交由 `routeOperation` 严格校验。

#### P0-3：OpenClaw 宿主激活契约冲突、`isComfyPlusConfigured` 误判与 `model` 拼接风险
- **涉及文件**：
  - `plugins/comfy-provider-plus/openclaw.plugin.json`（L12-L21）
  - `plugins/comfy-provider-plus/src/provider-runtime.ts`（L215, L233-L239）
  - `plugins/comfy-provider-plus/index.ts`（L44-L59）
- **问题详情**：
  1. `openclaw.plugin.json` 声明 `configSignals[0].required: ["baseUrl", "workflows", "nodeBindings"]`，但 `scripts/switch-to-comfy-plus.md` 与 `REQUIREMENTS.md` 推荐配置均**未写 `nodeBindings`**（由插件提供默认绑定）。由于 `activation.onStartup: false`，OpenClaw 按 `configSignals` 判定插件未配置而拒绝激活！
  2. `isComfyPlusConfigured({})` 实测返回 `true`（`getComfyPlusPluginConfig({})` 返回 `undefined` → `parseComfyPlusConfig(undefined)` 填满默认 `baseUrl`/`workflows`），导致未配置该插件时 OpenClaw 仍以为已配置。
  3. `index.ts:56` 写死 ``model: `${PROVIDER_ID}/${result.model}` ``：若宿主传入 `req.model = "comfy-plus/workflow"`，将返回 `"comfy-plus/comfy-plus/workflow"`。
  4. `index.ts` / `GenerateImageRequestLike` 忽略了 Phase 0 已确认的一等字段 `signal?: AbortSignal`，宿主取消请求时无法中止上传与轮询。
- **修改建议**：
  1. 将 `openclaw.plugin.json` 中 `configSignals[0].required` 改为 `["baseUrl", "workflows"]`（与 `switch-to-comfy-plus.md` 对齐），并在 `config-switch.test.ts` 中断言推荐 YAML 满足 `openclaw.plugin.json` 的 `configSignals` 与 `configSchema`。
  2. `isComfyPlusConfigured(cfg)` 须先检查 `getComfyPlusPluginConfig(cfg)` 为非空对象且包含显式 `baseUrl`（且插件未被设为 `enabled: false`），再调用 `parseComfyPlusConfig` 校验无旧键。
  3. `index.ts` 规范化 `result.model`：若已带 `${PROVIDER_ID}/` 前缀则不重复拼接（同时核对官方 `@openclaw/comfy-provider` 返回格式是 `"workflow"` 还是 `"comfy/workflow"`）。
  4. 透传 `req.signal` 至 `ComfyClient`（用 `AbortSignal.any([req.signal, AbortSignal.timeout(...)])` 组合）。

---

### P1（影响验收项，必须修复）

#### P1-1：`metadata.applied.seed` 恒为 `undefined`，Edit 模式 `width`/`height` 与 `supportsSize` 矛盾
- **涉及文件**：
  - `plugins/comfy-provider-plus/src/provider-runtime.ts`（L175-L185, L221-L226）
  - `plugins/comfy-provider-plus/src/workflow/injector.ts`（L61-L65, L153-L177）
  - `plugins/comfy-provider-plus/index.ts`（L39）
- **问题详情**：
  1. `generateComfyPlusImage` 未将实际注入的 `seed`（包括显式传入或随机生成的整数）传给 `buildAppliedParamsMetadata`，导致 `metadata.applied.seed` 永远是 `undefined`，违反验收 #6。
  2. `index.ts:39` 声明 `capabilities.edit.supportsSize: true`，但 `injector.ts` 在 Edit 模式下完全忽略 `width`/`height`（仅用 `resolution` 并跟随首图比例），而 `buildAppliedParamsMetadata` 仍上报 `width: 1024, height: 1024`，既误导宿主又失真。
  3. 传入 `seed: -1` 时 `Math.trunc(-1)` 直接写入 `-1`，会被 ComfyUI `KSampler` 拒绝。
- **修改建议**：
  1. 在 `provider-runtime.ts` 或 `injectWorkflowParams` 返回 `{ promptGraph, resolvedSeed }`，并将 `resolvedSeed` 写入 `buildAppliedParamsMetadata`；对 `seed < 0` 约定为随机或校验报错。
  2. 将 `capabilities.edit.supportsSize` 改为 `false`（或在确认 Edit 支持显式覆写宽高后再开启），Edit 模式下 `metadata.applied` 仅回显 `resolution` 而不回显未生效的 `width`/`height`。

#### P1-2：`slot-normalizer.ts` 吞词、漏匹配独立「第X张」/「图一百」及保护正则失效
- **涉及文件**：
  - `plugins/comfy-provider-plus/src/prompt/slot-normalizer.ts`（L36-L47, L80-L89, L147-L153, L186-L198）
- **复现证据**：
  1. `"把第二张图的衣服换到第一张人物身上"` → `"把image_2的衣服换到image_1身上"`，**吞掉了「人物」**（若写成「把第二张衣服换到第一张人物身上」会同时吞掉「衣服」和「人物」）。
  2. `"把第一张和第二张合并，不要用第二十张"` → 原样未改、`referencedSlots: []`（既未规范化，也未拦截越界的「第二十张」）。
  3. `"用图一百的风格"` → `parseChineseNumber("一百")` 返回 `null`，绕过越界拒绝。
  4. `PROTECT_PATTERNS` 中 `/\b\d{3,5}\s*(?:px|宽|高|宽度|高度)\b/gi` 与 `/\b\d+\s*(?:步|steps?)\b/gi` 在中文字符 `宽`/`步` 后误用 ASCII `\b`，探针实测 `"1024 宽"` 与 `"25 步"` 均未进入保护区间。
- **修改建议**：
  1. `reOrdinalCn` 拆分两类处理：
     - 图片本体词（`图|图片|照片|图像|参考图`）可整体替换为 `image_N`；
     - 内容属性词（`人物|人像|主体|角色|衣服|服装|背景|姿态|姿势`）必须用**正向先行断言** `(?=...)`，仅替换 `第X张` 为 `image_N`（例如 `"第一张人物"` → `"image_1人物"`），保留语义名词！
     - 独立 `第X张`（不跟在非图量词如 `桌子|椅子|床|纸|票|嘴|脸|卡|钞票|画纸|沙发` 前）同样应被匹配为 `image_N`（配合负向先行断言 `(?!\s*(?:桌子|椅子|...))`），以覆盖「把第一张和第二张合并」「参考第二十张」。
  2. 修复 `parseChineseNumber`：支持 `一十`、`一百`、`一百零X`、`X百XX` 等，或对所有匹配到的中文数字超 99 返回 `> 16` 触发越界拒绝。
  3. 移除 `PROTECT_PATTERNS` 中中文字符后的 `\b`（改用 `(?:px\b|宽度?|高度?)` 与 `(?:steps?\b|步)`），并将 `[一二两...]+(?:个|只|位|人...)` 改为完整覆盖「两个人」（`[一二两三四五六七八九十百]+(?:个人|个|只|...)`）。
  4. `imageRoles` 应在保护之后或做边界保护，并当 `imageRoles.length > actualImageCount` 且命中超界角色时明确报越界错误（即使自定义 `slotTemplate`）。

#### P1-3：`integration-140.test.ts` 依赖被 `.gitignore` 忽略的 PNG 文件，新检出运行必崩
- **涉及文件**：
  - `plugins/comfy-provider-plus/test/integration-140.test.ts`（L47-L49）
  - `plugins/comfy-provider-plus/.gitignore`（L5）
- **问题详情**：`docs/phase0-raw/*.png` 已被 `.gitignore` 忽略，仓库中不存在 `docs/phase0-raw/qwen-image-uc_00060_.png`（已验证 `Test-Path` 为 `False`）。任何人在新工作区或 CI 运行 `RUN_COMFY_140=1 npm test -- test/integration-140.test.ts` 会直接 `ENOENT` 失败。
- **修改建议**：在测试中内置最小合法非方形 PNG Buffer（或提交小尺寸固定测试 fixture 如 `test/fixtures/portrait-64x128.png`），既消除 `ENOENT`，又可顺便实测验收 #3（非方形首图比例跟随）与 N=2/16！

---

### P2（体验与健壮性改进，建议一并修或记录）

#### P2-1：参数本地校验与静默降级问题
- **文件**：`src/provider-runtime.ts`（L49-L102）、`src/config/defaults.ts`（L78-L79）、`src/workflow/injector.ts`（L86-L117）
- **问题**：
  1. `readOverrides` 未校验 `steps > 0`、`width > 0`、`height > 0`、`resolution > 0`、`cfg >= 0`；非法正数会直接送进 ComfyUI 报错。
  2. `o.imageCount` 仅在 Edit 模式校验，T2I 传入 `imageCount: 2` 时未拒绝。
  3. `defaults.samplerName` / `defaults.scheduler` 已在 schema 解析但从未注入 `KSampler`（死配置字段）。
  4. `resolveExistingWorkflowPath` 当用户显式配置了自定义路径但文件不存在时，会静默回退到内置模板而非报错，容易掩盖路径配错。

#### P2-2：`ComfyClient` 细节改进（假图片魔数、`outputKey`、共享服务器 `/interrupt`）
- **文件**：`src/comfy/client.ts`（L27-L41, L246-L264, L266-L285）
- **问题**：
  1. `detectImageExt` 在魔数不匹配时仍按 `mimeType`/后缀放行（实测纯文本 `"THIS IS NOT A PNG"` 标 `image/png` 通过预检）；且 L35 `"webp"` 重复。建议要求魔数校验通过（支持 PNG/JPEG/WEBP(含 `RIFF`+`WEBP`)/GIF）。
  2. `extractImages` 硬编码读取 `outputs[nodeId]?.images`，忽略了 `bindings.output.outputKey`。
  3. 超时清理 `tryCleanup` 无条件调用 `POST /interrupt`，在共享 140 服务器上可能误中断 LiberAstra 或其他会话正在执行的任务；建议先查 `GET /queue` 确认 `promptId` 正在 `queue_running` 中再中断。

#### P2-3：Phase 5 调色草稿工作流节点断链与顶层 `_meta`
- **文件**：`workflows/qwen-image-color-grade.json`（L1-L59）、`workflows/qwen-image-pose.json`（L1-L10）
- **问题**：
  1. `qwen-image-color-grade.json` 中节点 `1/2/3/6`（UNET/CLIP/VAE/LoRA）未连接任何采样器或编码器，实际只有 `10/11 -> 20(ColorMatch) -> 99(SaveImage)`，无法验证 `QIE-2511-Color-Grade-Transfer-LoRA`。
  2. 两份 Phase 5 草稿含顶层 `_meta` 字段；后续正式评估前应确保提交给 ComfyUI 的 JSON 不含非节点顶层键（并将说明放进 `docs/phase5-evaluation.md`）。

---

## 五、补测命令与期望清单（修复后必跑）

```bash
cd plugins/comfy-provider-plus
npm run typecheck
npm run build
npm test
```

**新增单测必须覆盖并断言通过**：
1. `test/upload-and-errors.test.ts`：
   - `redactSensitive` 覆盖 `Authorization: Bearer sk-xxx`、裸 `Bearer sk-yyy`、`D:/foo/bar.png`、`C:\Users\...\x.png`、`http://u:p@host`，断言 **token 本体** (`sk-xxx`/`sk-yyy`) 不残留；
   - `createComfyError` 传入 `{ msg: 'api_key="sk-123"', api_key: "sk-456" }` 不崩溃且两者均被脱敏；
   - `preflightImages` 拒绝伪造 PNG（纯文本 + `image/png`）；
   - `routeOperation` 对 `requestedOperation: "inpaint"`、`123` 均抛 `VALIDATION_FAILED`，不回退 `t2i`/`edit`。
2. `test/slot-normalizer.test.ts`：
   - 精确断言 `"把第二张图的衣服换到第一张人物身上"` 保留「人物」（如 `"把image_2的衣服换到image_1人物身上"`）；
   - 覆盖 `"把第一张和第二张合并"` → `image_1`/`image_2`、`"参考第二十张"` 越界抛错、`"用图一百的风格"` 越界抛错；
   - 直接断言 `__testables.applyProtect("两个人站在一起，1024 宽，CFG 1，25 步").masked` 中 `两个人`/`1024 宽`/`CFG 1`/`25 步` 全部被替换成 `__OCP_PROTECT_*__`。
3. `test/workflow-injector.test.ts` / 新增 `test/provider-runtime.test.ts`：
   - Mock `fetch` 走完整 `generateComfyPlusImage`，断言 `metadata.applied.seed` 为有限非负整数（显式与随机均非 `undefined`）；
   - `isComfyPlusConfigured({}) === false`，显式配置后 `=== true`；
   - `index.ts` 对 `req.model = "comfy-plus/workflow"` 不产生 `"comfy-plus/comfy-plus/workflow"`；
   - `config-switch.test.ts` 校验 `switch-to-comfy-plus.md` 的配置字段满足 `openclaw.plugin.json` 的 `configSignals.required`。

---

## 六、对 3 项遗留项的专项建议

### 1. OpenClaw 实机上线切换实测（验收 #9）
- **前置**：先修完 P0-3（尤其是 `openclaw.plugin.json` 的 `configSignals.required` 去掉 `nodeBindings` 与 `isComfyPlusConfigured` 修复），并在真实 OpenClaw 环境核对 `src/shims/plugin-entry.ts` 与 `openclaw/plugin-sdk` 入口兼容性。
- **操作步骤**：
  1. 执行 `node plugins/comfy-provider-plus/scripts/sync-workflows.mjs` 同步 `qwen-image-t2i.json` / `qwen-image-edit.json` 到 `~/.openclaw/workspace/workflows/comfy-plus/`；
  2. 安装/链接 `@openclaw/comfy-provider-plus`（先 `npm run build` 确保 `dist/index.js` 存在），确认官方 `~/.openclaw/extensions/comfy` 文件未改动；
  3. 通过 OpenClaw 配置命令设置：`plugins.entries.comfy.enabled=false`、`plugins.entries.comfy-plus.enabled=true`（按推荐 config）、`agents.defaults.imageGenerationModel.primary=comfy-plus/workflow`，并核对 `fallbacks` 仍包含 `google/gemini-3.1-flash-image`；
  4. 重启 OpenClaw，发一次无图生成与一次 2 图编辑，验证响应命中 `comfy-plus/workflow`、元数据 `promptAudit` 与 `applied.seed` 完整；再临时配置错误地址验证可正确回退至 `google/gemini-3.1-flash-image` 且错误信息无路径/密钥泄露。

### 2. 140 实机 `N=2` 与 `N=16` 满载实测（验收 #2、#3、#4）
- **前置**：先修完 P1-2（槽位不吞词）和 P1-3（内置 fixture 不依赖 gitignored PNG）。
- **建议补齐 3 个实机用例**（写入 `test/integration-140.test.ts` 在 `RUN_COMFY_140=1` 下执行）：
  1. **非方形竖图单图 Edit（验收 #3）**：传 `512×1024` 竖图，下载输出 PNG 读宽高比，断言输出仍为竖图（`height > width` 且比例接近 1:2，非 1024×1024）；
  2. **N=2 双图换衣语义联调（验收 #2 + #4）**：走完整 `generateComfyPlusImage`，提示词 `"把第二张图的衣服换到第一张人物身上"`，核对 `/history/{promptId}` 中 `5.inputs.prompt` 含 `image_2`、`image_1` 且保留「人物」，且 `images.image_1 -> ["101", 0]`、`images.image_2 -> ["102", 0]`；
  3. **N=16 满载压测（验收 #2）**：传 16 张小尺寸合法 PNG（`steps: 4`），核对 `/history/{promptId}` 中 `101..116` 全部执行且 `images.image_1..16` 顺序严格一致，记录 140 显存峰值与总耗时（确认在 600s 内且不 OOM；若 16 张高分辨率触发 OOM，应在文档标明推荐分辨率上限或安全建议）。
- **执行命令**：
  ```powershell
  $env:RUN_COMFY_140="1"
  cd plugins/comfy-provider-plus
  npm test -- test/integration-140.test.ts
  ```

### 3. Phase 5 调色与换姿 140 实测归档（验收 #10）
- **保持关闭**：在归档完成并复审前，严禁将 `operations.colorGrade.enabled` 或 `operations.pose.enabled` 改为 `true`。
- **调色（`color-grade`）**：
  - 先基于 LiberAstra `backend/workflows/qwen_edit_2511_color_grade/` 补全 `workflows/qwen-image-color-grade.json` 的真实 Edit-2511 采样链路（目前草稿 UNET/CLIP/VAE/LoRA 完全断链，只跑了 `ColorMatch`）；
  - 在 140 使用「同一人物原图 + 两张风格差异明显的色彩参考图（如暖调日落 vs 冷调赛博）」跑两组实测，验证色彩迁移显著且人物身份/构图未漂移；记录显存峰值（注意 2511 与 2.1 切换显存释放耗时）。
- **换姿（`pose-transfer`）**：
  - 实测前明确透明底姿态图压白底的归属方案（在插件内做纯 JS 预处理或验证 140 现有节点，遵循「不在 140 新增自定义节点」红线）及长边 ≤ 2048 尺寸防护；
  - 在 140 实测 UC 底模 + `VNCCS_QI2_PoseStudioV1.1.safetensors`（槽位反序 `image_1=姿态图`、`image_2=人物原图`），覆盖**线稿/深度姿态图（成功样本）**与**真人姿态照/透明底图（失败边界）**，重点核验 UC 底模身份保持是否退化。
- **归档格式**：两项均须在 `docs/phase5-evaluation.md` 补齐「工作流路径、输入/输出文件路径、成功/失败判定、显存峰值、耗时、失败边界与不可用原因」，经终审确认后方可开放对应开关。
