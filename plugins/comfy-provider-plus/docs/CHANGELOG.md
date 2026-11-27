# 变更清单（comfy-provider-plus）

## 新增

- 独立包 `@openclaw/comfy-provider-plus`（插件/provider id：`comfy-plus`，默认模型 `comfy-plus/workflow`）
- 标准工作流：`workflows/qwen-image-t2i.json`、`qwen-image-edit.json`
- Phase 5 评估草稿（默认关闭）：`qwen-image-color-grade.json`、`qwen-image-pose.json`
- 配置 schema / defaults：显式 `nodeBindings`（`nodeId + inputName`），拒绝官方单图旧键
- `slot-normalizer.ts`：确定性序号规范化、越界拒绝、非图数字保护、模糊指代不猜测、审计字段
- 事务性 1–16 图上传、动态 `LoadImage` 接线、LoRA 旁路
- 四类错误 + 脱敏；默认 `timeoutMs=600000`
- 上线切换说明：`scripts/switch-to-comfy-plus.md`、`scripts/sync-workflows.mjs`
- 单测：`test/*.test.ts`；Phase 0 / Phase 5 / 自测报告文档

## 未改动

- 官方 `~/.openclaw/extensions/comfy`（本机不存在；仅 npm/GitHub 只读取证）
- LiberAstra `backend/` 业务代码（仅参考 `backend/workflows/` 拓扑）

## 已知限制 / 遗留

- 扩展采样参数走 `providerOptions`（SDK 无一等字段）
- Phase 5 调色/换姿未做 140 完整实测归档，开关保持关闭
- 16 张满载 140 实跑未在本轮执行（有 N=1/2/16 接线单测 + 1 张实跑）
