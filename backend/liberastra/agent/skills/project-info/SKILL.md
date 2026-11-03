---
name: project-info
description: 只读查看 LiberAstra 项目资源与节点参数：资产、角色、音色、音乐、画布菜单、可用和默认工作流、当前节点属性。Use when the user asks what resources or workflows exist, or before changing node parameters.
license: MIT
compatibility: 需要 LiberAstra 导演台；只读，不修改画布或提交任务。
metadata:
  author: LiberAstra
  version: "1.1"
allowed-tools: list_assets get_asset read_asset_text list_characters list_voices list_music list_canvas_menu list_workflows list_execution_specs canvas_get_graph canvas_get_node canvas_get_node_schema
---

# 项目信息

只读技能。先读项目里的真实资源、菜单和执行目标，再让导演技能或自动画布技能去改节点。不要凭记忆猜节点 id、工作流名或参数名。

**按需读取：**

- 资产、角色、音色、音乐字段：`references/resources.md`。
- 菜单项、可用工作流、默认工作流：`references/menu-and-targets.md`。
- 节点属性字段和修改配方：`references/node-parameters.md`。

## 修改节点参数前的顺序

1. `list_canvas_menu` 找到对应菜单项，确认 `enabled`、`media_slots`、`available_targets`、`default_target_resolved`。
2. 需要工作流细节时 `list_workflows(name=...)`；需要云端模型时 `list_execution_specs(sub_capability=...)`。
3. `canvas_get_node_schema(node_id=...)` 读取当前节点的执行目标、输入槽、参数规格和当前 `values`。
4. 根据用户要求提出 patch；真正修改由导演技能或自动画布技能执行。
5. 改完后再读一次，确认字段和值。

## 资源读取

- 资产：`list_assets(kind, include_hidden, limit)`；单个详情用 `get_asset(asset_id, probe_media=true)`。图片看宽高，视频/音频看媒体时长。
- 文本资产：`read_asset_text(asset_id)`。
- 角色：`list_characters`，返回各视角图片和绑定音色。
- 音色：`list_voices`，TTS / 数字人节点用 `voiceRecordId` 或 `voice`。
- 音乐：`list_music`，节点的 `bgmPath` 写成 `bgm/<文件名>`。
- 菜单：`list_canvas_menu` 返回的是用户在「画布菜单设置」里的实际配置，不是出厂默认。默认目标失效时会有 `default_target_missing=true`。

## 参数规则

- 功能节点的包参数在 `data.values`，值都是字符串。`canvas_update_node` 的 `values` 是整份替换，先读完整值再改。
- 本地工作流视频包常按帧数 `length`，用包声明 `fps`、`min`、`max`、`align_base`、`align_offset` 对齐；云端模型常用秒数 `duration`。
- 媒体输入用 `bindings` 绑定到槽位，例如 `first_frame`、`last_frame`、`reference_image`、`prompt`。
- 输入节点用 `assetId`、`text`、`varName`；拼接工具节点（内部 `kind=concat`）用 `layout`、`columns`、`gap`、`gapColor`、`order`；语音节点用 `mode`、`text`、`providerId`、`voiceRecordId`、`voice`、`model`、`workflow`。
- `varName` 是全画布命名空间，写入前先看是否重名。

## Gotchas

- 不要用出厂菜单替代用户菜单；用户可能删过或改过节点。
- `default_target_missing=true` 时先让用户在设置里选目标，或从 `available_targets` 里挑一个可用目标。
- 菜单项 `enabled=false` 时不使用。
- 资产列表默认不含画布中间结果；需要时传 `include_hidden=true`。
- `meta.duration_s` 可能是任务处理耗时，不一定是媒体时长；媒体时长用 `get_asset(probe_media=true)`。
- 只读技能不提交生成、不改画布；用户要求修改时交给导演技能或自动画布技能。
