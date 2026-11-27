# 上线切换：`comfy` → `comfy-plus`

目标：停用官方 `comfy`，启用 `comfy-plus`，默认图片模型改为 `comfy-plus/workflow`，并保留回退 `google/gemini-3.1-flash-image`。

## 推荐配置片段

```yaml
plugins:
  entries:
    comfy:
      enabled: false
    comfy-plus:
      enabled: true
      config:
        mode: local
        baseUrl: http://10.10.12.140:8188
        timeoutMs: 600000
        workflows:
          t2i: ~/.openclaw/workspace/workflows/comfy-plus/qwen-image-t2i.json
          edit: ~/.openclaw/workspace/workflows/comfy-plus/qwen-image-edit.json
          colorGrade: ~/.openclaw/workspace/workflows/comfy-plus/qwen-image-color-grade.json
          pose: ~/.openclaw/workspace/workflows/comfy-plus/qwen-image-pose.json
        operations:
          colorGrade:
            enabled: false
          pose:
            enabled: false

agents:
  defaults:
    imageGenerationModel:
      primary: comfy-plus/workflow
      fallbacks:
        - google/gemini-3.1-flash-image
```

## 步骤

1. 将本包 `workflows/*.json` 同步到 `~/.openclaw/workspace/workflows/comfy-plus/`。
2. 安装/链接插件包 `@openclaw/comfy-provider-plus` 到 OpenClaw extensions。
3. 用 OpenClaw 配置命令（勿手改未校验副本）设置：
   - `plugins.entries.comfy.enabled=false`
   - `plugins.entries.comfy-plus.enabled=true` + 上列 config
   - `agents.defaults.imageGenerationModel.primary=comfy-plus/workflow`
   - 确认 `fallbacks` 仍含 `google/gemini-3.1-flash-image`
4. 重启 OpenClaw 后验证：一次无图请求命中 `comfy-plus/workflow`；回退列表未丢。

## 辅助脚本

见同目录 `sync-workflows.mjs`（仅复制工作流文件，不改 OpenClaw 主配置）。
