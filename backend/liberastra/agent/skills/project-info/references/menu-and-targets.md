# 菜单与执行目标

## list_canvas_menu 返回什么

每个菜单项来自用户在「画布菜单设置」里的实际配置：

```json
{
  "id": "preset_i2v_first",
  "category": "video",
  "title": "首帧生视频",
  "sub_capability": "i2v_first",
  "bind_mode": "manual",
  "enabled": true,
  "media_slots": [
    {"key": "first_frame", "type": "image", "label": "首帧图片", "required": true}
  ],
  "available_targets": [
    {
      "target_type": "workflow",
      "target_id": "minimax_h3_i2v_uncensored",
      "display_name": "minimax_h3_i2v_uncensored",
      "provider_id": null,
      "provider_name": "",
      "media_slots": [{"key": "first_frame", "type": "image"}],
      "input_keys": ["prompt", "image", "width", "height", "length"]
    }
  ],
  "default_target": {"target_type": "workflow", "target_id": "minimax_h3_i2v_uncensored", "provider_id": null},
  "default_target_resolved": {"target_type": "workflow", "target_id": "minimax_h3_i2v_uncensored", "display_name": "minimax_h3_i2v_uncensored"},
  "default_target_missing": false
}
```

- `enabled=false`：菜单里不可用，不要选。
- `available_targets`：这个菜单项可用的工作流或模型；`bind_mode=manual` 时来自用户勾选，`auto` 时来自全部已启用目标。
- `default_target_resolved`：实际会用的默认目标；为 `null` 且 `default_target_missing=true` 时，默认目标已失效，需要用户重新配置或换一个目标。
- `media_slots`：菜单项声明的默认槽位；具体目标可能有不同槽位，以目标的 `media_slots` 为准。

## 选择目标的顺序

1. 找菜单项：按 `title` 或 `sub_capability`。
2. 确认 `enabled`。
3. 看 `default_target_resolved` 是否可用。
4. 需要参数细节时 `list_workflows(name=default_target_resolved.target_id)`；模型目标用 `list_execution_specs(sub_capability=...)`。
5. 节点上已经有目标时，用 `canvas_get_node_schema` 读它当前解析到的目标，不要假设等于菜单默认值。

## 常见能力

| sub_capability | 菜单标题 | 说明 |
|---|---|---|
| `t2i` | 文生图 | 无参考图出图 |
| `i2i_single` | 单图编辑 | 一张参考图 |
| `i2i_multi` | 多图编辑 | 两到三张参考图 |
| `i2v_first` | 图生视频 | 首帧必填，尾帧可选；只传首帧或锁首尾帧 |
| `i2v_flf` | 首尾帧视频 | 首尾帧都必填；当前菜单不一定配置 |
| `i2v_enhance` | 图生增强 | 工作流内部自己优化提示词，只接首帧 |
| `depth_pose` | 人物换姿势 | 人物照 + 姿势图/线稿，保留人物身份；两个图片槽 |
| `depth_gen` | 姿势生成人物 | 只有姿势图/线稿或深度图；Union Depth 需从 `available_targets` 选包 |
| `upscale` | 图片修复放大 | 单图放大/修复；默认 RealESRGAN，SeedVR2 会生成式改细节 |
| `v2v_ref` | 参考图生视频（单段） / 分镜视频路线 | 多张参考图，不作为首尾帧；分镜视频每镜一个节点 |
| `v2v_ref_long` | 连续生成（长） | Extender 时间线，多段连续视频，每段不超过 15 秒 |
| `video_upscale` | 视频增强 | SeedVR2 视频修复/放大，保留原 fps 和音频 |
| `concat` | 图片/视频/音频拼接；`toolId=audio_extract` 时是音频提取 | 画布内置工具节点，不走工作流菜单 |

## 注意

- 菜单是用户配置，不同机器不一样；不要写死 `preset_*` 一定存在。
- 图生视频的尾帧是可选槽；目标只有一个图片槽时只用首帧。槽位数量以目标 `media_slots` 为准。
- 参考图生视频（单段）的时长上限看目标工作流的 `inputs.length`（帧数 + fps）或 `inputs.duration`（秒），不要固定认为 15 秒或 30 秒。
- 连续生成（长）走 Extender，单段仍不超过 H3 的 15 秒上限；60 秒默认拆成 4 段。
