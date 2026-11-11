# 导演会话状态

每步确认后调用 `update_session_state`。状态用于刷新、切会话或重启后继续，不要重复已完成步骤。

## 字段

```json
{
  "step": 5,
  "topic": {
    "logline": "一句话主题",
    "platform": "短视频",
    "style": "写实电影感",
    "aspect": "16:9",
    "duration": "30 秒"
  },
  "characters": [
    {"name": "林夏", "source": "character_library", "character_id": 12, "note": "黑色短发，米色风衣"}
  ],
  "script": {
    "summary": "分场剧本摘要",
    "canvas_var": "input_text_script"
  },
  "shots": [
    {"id": 1, "summary": "雨夜街头停下", "prompt": "已确认的分镜提示词"}
  ],
  "route": "storyboard",
  "storyboard_mode": "shots",
  "audio_strategy": "native",
  "audio_ref_seconds": 5,
  "audio_bed": null,
  "seam_fade_ms": 60,
  "audio_nodes": [],
  "audio_context_length": 0,
  "audio_ref": null,
  "keyframe_count": 2,
  "keyframes": {
    "1": ["output_image_kf_1_1", "output_image_kf_1_2"]
  },
  "reference_images": {
    "1": "output_image_ref_1"
  },
  "segments": [
    {
      "id": 1,
      "shots": [1, 2, 3],
      "duration_s": 15,
      "composite_var": "output_image_ref_group_1"
    }
  ],
  "videos": [
    {"shot": 1, "video_var": "output_video_1"},
    {"shot": 2, "video_var": "output_video_2"}
  ],
  "single_video_var": null,
  "final_video_var": null,
  "confirmed": ["主题", "角色", "剧本", "分镜数量", "创作路线"]
}
```

## 更新规则

- 默认 `merge=true`，只传本步新增或修改的键。
- 整段替换时显式传 `merge=false`。
- `step` 用数字，表示下一次从哪里继续。
- `confirmed` 记录用户已经点头的步骤。
- `route`：`storyboard` = 分镜视频；`single_video` = 整段参考图视频。
- `storyboard_mode`：只在 `storyboard` 使用；`shots` = 逐镜拼接（默认），`continuous` = 连续时间线（A2）。
- `audio_strategy`：只在 A1 使用；`native` / `previous_tail` / `global_bed`。A2/B 为 `null`。
- `audio_ref_seconds`、`audio_bed`、`seam_fade_ms`：A1 的尾音/氛围底参数。`audio_bed` 存资产 ID、名称，不存绝对路径；`seam_fade_ms` 对应视频拼接节点的 `audioFadeMs`。
- `audio_nodes`：A1 建过的音频节点，记录 `kind`（`audio_extract` / `audio_input`）、`var`、`source_video` 和 `target_video`；模型原生时为空数组。
- `audio_context_length`：A2/B 长视频使用，默认 0；`audio_ref`：P1 的 Extender 参考音频，存资产 ID、名称，B 可带 `strategy`。
- 切换 `route` 或 `storyboard_mode` 时清空 `videos`、`final_video_var`、`single_video_var` 和新模式不适用的音频字段；旧状态缺字段按 `shots` / `native` / 0 处理。
- `keyframe_count`、`keyframes`：只在 `storyboard` 使用。每镜可以有 1～N 张关键帧，变量名按 `output_image_kf_<分镜>_<序号>` 记录。
- `reference_images`、`segments`：B 用 `reference_images` 记录每镜参考图，`segments` 记录参考图拼接段（`composite_var`）；A2 用 `segments` 记录时间线 clip（`clip_index`、`ref_vars`，用了拼接图时加 `composite_var`）。
- `videos`：只在 A1 使用，记录分镜号和视频节点变量名。
- `single_video_var`：B 且总时长不超过单段上限时使用。
- `final_video_var`：最终成片变量；A1 是拼接节点产物，A2/B 是 Extender 或单段视频产物。
- 具体工作流/目标按画布菜单当前配置解析，不要写进状态。
- 用户改路线、模式、关键帧数量或分镜后，清空后续视频状态，避免沿用旧的参考图或视频节点。
- 不要把完整剧本、完整提示词反复塞进状态；只存摘要和画布变量名，正文放画布文本节点。
- 安全策略由系统保存在 `safety`，`update_session_state` 会自动保留，不要覆盖。

## 恢复

1. 先读系统提示里的「当前会话状态」。
2. 从 `step` 继续，先复述已确认内容。
3. 如果画布变量在状态里有记录，先用 `canvas_get_graph` 确认节点仍存在。
4. 用户改了主题或角色时，回退到对应步骤并清空后续 `confirmed`。
