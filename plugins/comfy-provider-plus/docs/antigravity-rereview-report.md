# Antigravity 复审报告 — `comfy-plus` Fix attempt 1（PR #5）

- **复审对象**：LiberAstra PR #5（commit `3172699`）
- **参照文档**：`plugins/comfy-provider-plus/docs/fix-attempt-1-report.md`、`plugins/comfy-provider-plus/docs/antigravity-final-review.md`
- **本地验证**：在独立 review worktree 检出 `3172699`（业务代码零改动、`git status` 全净），执行：
  - `npm ci`、`npm run typecheck`、`npm run build`、`npm test`（`32 passed | 2 skipped`）
  - 针对已编译 `dist/` 运行边界探针脚本（覆盖脱敏、URL、`loader.ts` ENOENT、`waitForHistory` `AbortSignal`、mock `fetch` 端到端 `generateComfyPlusImage`、`slot-normalizer` 边界及 `portrait-64x128.png` 魔数/宽高核验）

---

## 一、复审结论

- **结论**：**驳回（Request Changes）**
- **是否建议合并**：**暂不建议合并**。P0-2、P1-1、P1-2、P1-3、Phase 5 默认关闭及多项 P2 改进均已达标，但实测探针发现 **2 处 P0 残余阻断缺陷**（均在 3 个文件约 30 行内可修完并补单测），清零后即可同意合并。
- **Phase 5 状态**：**仍默认关闭**（`defaults.ts`、`schema.ts`、`openclaw.plugin.json`、`switch-to-comfy-plus.md` 均为 `false`，且 `operation-router.ts` 与 `provider-runtime.ts:169-171` 双层硬门禁有效）。

---

## 二、逐条复核矩阵

| 项 | 复核结果 | 核查证据 |
|---|---|---|
| **P0-1** `errors.ts` 脱敏 / `createComfyError` / 路径 / 归类 | **未通过（2 处残余）** | Bearer / `sk-` 脱敏、`createComfyError` 递归脱敏不崩溃、`uploadImages` 归类 `UPLOAD_FAILED`+`index` 已修；但实测发现：① `loader.ts:51`（以及 `provider-runtime.ts:128`、`client.ts:154/185/223/260`）用 `"code" in err` 误把 Node 系统错误（`ENOENT`/`EACCES`/`ECONNREFUSED` 等）当成 `ComfyPlusError` 直接原样抛出，导致 `loadWorkflowTemplate("D:/nonexistent/secret-dir/wf.json")` 仍返回裸 `ENOENT` 并**明文泄露本地绝对路径**；② `errors.ts:3-4` 的 `PATH_RE` 缺少边界与 `://` 排除，把所有 `http://`/`https://` URL 误脱敏成 `htt[REDACTED_PATH]` / `http[REDACTED_PATH]`（例如 `http://u:p@10.10.12.140:8188/prompt` 变成 `htt[REDACTED_PATH]]@10.10.12.140:8188/prompt`）。另 `Authorization: Basic <b64>` 漏脱敏凭据、`SENSITIVE_KEY_RE` 未命中 `access_token`/`x-api-key`。 |
| **P0-2** 未知 `operation` → `VALIDATION_FAILED`，无静默回退 | **通过** | `operation-router.ts:22-61` 与 `provider-runtime.ts:65` 保留原始 `po.operation` 并严格校验，实测 `"inpaint"`、`123`、`true`、`{}`、`[]` 均抛 `VALIDATION_FAILED`，无静默回退。 |
| **P0-3** `configSignals.required`、`isComfyPlusConfigured({})`、`model` 不双拼、`signal` 透传 | **未通过（`signal` 残余）** | `openclaw.plugin.json` `required: ["baseUrl", "workflows"]`（与 `switch-to-comfy-plus.md` 对齐）、`isComfyPlusConfigured({}) === false`、`normalizeProviderModel` 不双拼均**通过**；但 **`signal` 透传在 `ComfyClient.waitForHistory`（`client.ts:190-236`）中失效**：宿主触发 `AbortController.abort()` 后，`fetchImpl` 抛出的 `AbortError` 被 L222 `catch` 当作「瞬时网络/超时」静默吞掉，循环空转 **402 次 fetch / 400 次 sleep 直至 600s 满时**，且无 `signal` 取消单测。 |
| **P1-1** `applied.seed`；`edit.supportsSize` / metadata 一致 | **通过** | `injectWorkflowParams` 返回 `resolvedSeed`（负 seed 如 `-1` 转非负随机整数）；mock `fetch` 端到端实测 `generateComfyPlusImage` T2I/Edit 均回显有限非负 `metadata.applied.seed`；`index.ts:43` `edit.supportsSize: false` 且 Edit 模式 `metadata.applied` 仅保留 `resolution` 不回显 `width`/`height`。 |
| **P1-2** `slot-normalizer`（不吞词、第X张、图一百、保护模式） | **通过** | 实测 `"把第二张图的衣服换到第一张人物身上"` → `"把image_2的衣服换到image_1人物身上"`、`"把第二张衣服换到第一张人物身上"` → `"把image_2衣服换到image_1人物身上"`、`"把第一张和第二张合并"` → `image_1`/`image_2`、`"参考第二十张"` / `"用图一百的风格"` 均抛 `VALIDATION_FAILED` 越界拒绝；`applyProtect` 正确保护 `两个人`/`1024 宽`/`1024宽`/`25 步`/`25步`/`CFG 1`/`第一张桌子`。 |
| **P1-3** `integration-140` fixture 不再依赖 gitignored PNG | **通过** | `test/fixtures/portrait-64x128.png` 已入库（379 字节，合法 PNG 魔数 `89504e470d0a1a0a`，真实尺寸 `64×128` 竖图），未被 `.gitignore` 忽略；`integration-140.test.ts` 已切换使用该 fixture 并含常驻单测校验。 |
| **红线检查** `backend/` 零改动 + Phase 5 默认关闭 | **通过** | `git diff --stat 51d7b9f..3172699 -- backend/` 为空；Phase 5 调色/换姿全链路默认 `false` 且双层门禁拦截。另 `detectImageExt` 严格魔数校验、`extractImages` 支持 `outputKey`、`tryCleanup` 先查 `queue_running` 再 `/interrupt` 均已补齐。 |

---

## 三、未清项列表（Fix attempt 2 必改）

### 未清 P0-1：`isComfyPlusError` 误判系统错误导致路径泄露 + `PATH_RE` 误伤 URL

1. **新增精确判断 `isComfyPlusError(err)` 替代所有 `"code" in err`**
   - 涉及文件：`src/comfy/errors.ts`、`src/workflow/loader.ts:51`、`src/provider-runtime.ts:128`、`src/comfy/client.ts:154,185,223,260`
   - 复现：
     ```text
     loadWorkflowTemplate("D:/nonexistent/secret-dir/wf.json")
     => err.code = "ENOENT"
     => err.message = "ENOENT: no such file or directory, open 'D:\\nonexistent\\secret-dir\\wf.json'"
     ```
   - 修复：在 `errors.ts` 导出 `isComfyPlusError(err)`（仅当 `err.code` 属于 5 个 `ComfyErrorCode` 之一时返回 `true`），替换上述 6 处 `"code" in err`，确保 `ENOENT`/`EACCES`/`ECONNREFUSED` 等 Node 错误全部走 `createComfyError` / `classifyFetchFailure` 并经过 `redactSensitive`。
2. **修复 `PATH_RE` 不误伤 URL（并顺手补齐 `Basic` 与复合敏感键）**
   - 涉及文件：`src/comfy/errors.ts:3-12`
   - 复现：
     ```text
     redactSensitive("fetch failed http://10.10.12.140:8188/prompt")
     => "fetch failed htt[REDACTED_PATH]"
     redactSensitive("http://u:p@10.10.12.140:8188/prompt")
     => "htt[REDACTED_PATH]]@10.10.12.140:8188/prompt"
     ```
   - 修复：`PATH_RE` 的 Windows 盘符分支改为 `(?<![A-Za-z0-9_])[A-Za-z]:(?:\\|\/(?!\/))[^\s"'`,}\]]+`（保证 `http://`、`https://`、`ws://` 完整保留，而 `C:/...`、`D:/...`、`C:\...` 照常脱敏）；建议同步扩展 `AUTH_BEARER_RE` 覆盖 `(?:Bearer|Basic|Token)`，并将 `SENSITIVE_KEY_RE` 放宽以覆盖 `access_token`/`x-api-key`/`client_secret`。

### 未清 P0-3：`waitForHistory` 吞掉宿主 `AbortSignal`，取消后仍空转 600s

- 涉及文件：`src/comfy/client.ts:190-236, 320-322`
- 复现（探针实测）：第 2 次 poll 时宿主调用 `abortController.abort()`，结果 `waitForHistory` 执行了 **402 次 fetch、400 次 sleep、耗尽全部 600,000ms** 才退出。
- 修复：
  1. 在 `waitForHistory` 循环开头及 `catch` 块中优先判断 `if (this.signal?.aborted)`：立即调用 `await this.tryCleanup(promptId)` 并抛出 `createComfyError("EXECUTION_TIMEOUT", "请求已被取消（aborted）", { promptId })`；
  2. 将 `sleep` 改为支持 `AbortSignal`（监听 `abort` 事件提前 resolve/清理 timer），确保取消时零额外等待；
  3. 在单测中补充 `AbortController` 取消 `waitForHistory` 的断言（校验立即中止且 fetch/sleep 次数 ≤ 2）。

---

## 四、附带小建议（P2，不阻断但建议顺手修）

1. `slot-normalizer.ts`：`reCnPrefix` / `reOrdinal*` 的字符类补上 `千万`（目前 `parseChineseNumber` 写了 `/[百千万]/`，但正则未包含 `千`/`万`，导致 `"图一千"` 误匹配成 `"image_1千"`）；另删去 `PROTECT_PATTERNS` 第 105 行重复的 `个人|个人`。
2. `test/`：补充 `loadWorkflowTemplate` 不存在路径脱敏单测、`redactSensitive` 保留 `http://` URL 断言、`waitForHistory` 响应 `AbortSignal` 单测，以及 mock `fetch` 走通 `generateComfyPlusImage` 的端到端元数据单测。
3. 后续独立跟踪项不变：OpenClaw 实机切换、140 N=2/N=16 满载实跑、Phase 5 调色/换姿 140 实测归档（均不阻断本 PR 代码合入，但 Phase 5 必须保持默认关闭）。
