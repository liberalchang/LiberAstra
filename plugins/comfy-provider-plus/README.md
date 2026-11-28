# `@openclaw/comfy-provider-plus`（`comfy-plus`）

基于官方 `@openclaw/comfy-provider@2026.11.10` 二次开发的独立 OpenClaw 图片插件：

- 文生图（0 参考图）→ `workflows/qwen-image-t2i.json`（无 `LoadImage`）
- 图生图（1–16 张）→ `workflows/qwen-image-edit.json`（动态 `LoadImage` + `images.image_N`）
- 提示词槽位规范化（纯规则，不调用 LLM）
- 显式 `nodeId + inputName` 参数映射；LoRA 可旁路
- 默认超时 `600000ms`
- 调色 / 换姿默认 `enabled: false`（见 `docs/phase5-evaluation.md`）

**不修改**官方 `~/.openclaw/extensions/comfy`。不保留官方单图旧配置键。

## 开发

```bash
npm install
npm test
npm run build
```

140 实机联调：

```bash
set RUN_COMFY_140=1
npm test -- test/integration-140.test.ts
```

## 上线切换

见 `scripts/switch-to-comfy-plus.md`。同步工作流：

```bash
node scripts/sync-workflows.mjs
```

## 扩展参数（`providerOptions`）

OpenClaw `ImageGenerationRequest` 无一等字段承载采样/LoRA/操作类型时，通过：

`operation`, `steps`, `cfg`, `negativePrompt`, `seed`, `loraEnabled`, `loraStrength`, `loraName`, `unetName`, `clipName`, `vaeName`, `width`, `height`, `resolution`, `imageRoles`, `imageCount`

宽高也可由请求 `size`（如 `1024x768`）解析。
