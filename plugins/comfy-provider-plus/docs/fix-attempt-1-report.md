# Fix attempt 1 — Antigravity 驳回项修复报告

> PR #5 · 日期 2026-11-28

## 验证命令

```bash
cd plugins/comfy-provider-plus
npm test          # 32 passed | 2 skipped
npm run typecheck
npm run build
```

## 逐条证据

| 项 | 状态 | 证据 |
|---|---|---|
| **P0-1** 脱敏/details/归类/loader | **已修** | `test/upload-and-errors.test.ts` →「四类错误码与脱敏（Bearer/路径/JSON details）」断言 Bearer/sk-/`D:/`/`C:\`/`api_key` 键均脱敏且 `createComfyError` 不崩；`src/comfy/errors.ts` 递归脱敏；`loader.ts` 经 `createComfyError`；上传走 `UPLOAD_FAILED`+index |
| **P0-2** 未知 operation | **已修** | `test/upload-and-errors.test.ts` →「未知 operation inpaint/123」抛 `VALIDATION_FAILED`；`operation-router.ts` 显式非法值不回退 |
| **P0-3** configSignals/isConfigured/model/signal | **已修** | `openclaw.plugin.json` required=`["baseUrl","workflows"]`；`config-switch.test.ts` 断言 `isComfyPlusConfigured({})===false`、显式配置 true、`normalizeProviderModel` 不双拼；`ComfyClient`/`generateImage` 透传 `signal` |
| **P1-1** seed 元数据 / edit.supportsSize | **已修** | `workflow-injector.test.ts` →「负 seed…元数据含 seed；Edit 不上报 width/height」；`index.ts` `edit.supportsSize=false`；`injectWorkflowParams` 返回 `resolvedSeed` |
| **P1-2** slot-normalizer | **已修** | `slot-normalizer.test.ts`：保留「人物」；独立「第一张/第二张」；「第二十张」「图一百」越界；`applyProtect` 覆盖「两个人/1024 宽/25 步」 |
| **P1-3** integration fixture | **已修** | `test/fixtures/portrait-64x128.png` 入库；`integration-140.test.ts` 改用 fixture；「fixture PNG 存在于仓库」单测 |

## 未做（可另开）

- OpenClaw 实机切换
- 140 N=2/16 满载实跑
- Phase 5 保持关闭
