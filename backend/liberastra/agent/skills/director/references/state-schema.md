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
  "keyframe_mode": "first",
  "keyframes": {
    "1": ["首帧"]
  },
  "video": {
    "mode": "i2v",
    "stage": "mode",
    "shot_durations": {"1": 5, "2": 5},
    "videos": [
      {"shot": 1, "video_var": "output_video_1"},
      {"shot": 2, "video_var": "output_video_2"}
    ],
    "shots_per_composite": 3,
    "groups": [
      {
        "id": 1,
        "shots": [1, 2, 3],
        "duration_s": 15,
        "concat_var": "output_image_storyboard_group_1",
        "text_var": "input_text_group_1",
        "video_var": "output_video_group_1"
      }
    ],
    "final_video_var": null
  },
  "confirmed": ["主题", "角色", "剧本", "分镜数量", "关键帧方式"]
}
```

## 更新规则

- 默认 `merge=true`，只传本步新增或修改的键。
- 整段替换时显式传 `merge=false`。
- `step` 用数字，表示下一次从哪里继续。
- `confirmed` 记录用户已经点头的步骤。
- `keyframe_mode`：`first` = 每镜只生成首帧；`first_last` = 每镜生成首帧和尾帧。
- `video.mode`：`i2v` = 每个分镜各自一个图生视频节点；`reference` = 先把多个分镜合成参考图，再建参考视频节点。具体工作流/目标按画布菜单当前配置解析，不要写进状态。
- `video.stage`：`mode` 选方式、`plan` 算时长/分组、`concat` 跑合成图、`videos` 跑视频、`final` 收尾。
- `video.shot_durations` 用秒存；参考图分组的总时长用原始秒数相加，再按目标规格对齐一次。
- `video.videos` 只在 `i2v` 模式使用，记录分镜号和视频节点变量名。
- `video.groups` 只在 `reference` 模式使用，每项记录该组分镜号、总时长、合成图/文本/视频节点变量名。
- 用户改关键帧方式或分镜后，清空后续 `video` 状态，避免沿用旧的合成图或视频节点。
- 不要把完整剧本、完整提示词反复塞进状态；只存摘要和画布变量名，正文放画布文本节点。
- 安全策略由系统保存在 `safety`，`update_session_state` 会自动保留，不要覆盖。

## 恢复

1. 先读系统提示里的「当前会话状态」。
2. 从 `step` 继续，先复述已确认内容。
3. 如果画布变量在状态里有记录，先用 `canvas_get_graph` 确认节点仍存在。
4. 用户改了主题或角色时，回退到对应步骤并清空后续 `confirmed`。
