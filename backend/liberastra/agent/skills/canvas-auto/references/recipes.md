# 常用画布结构

## 文生图

```text
文本输入 input_text_prompt
  → 功能节点（pack=文生图包，prompt={{input_text_prompt}}）
  → 图片拼接（可选，多张时）
```

## 图生图 / 风格转换

```text
图片输入 input_image_1
  → 功能节点（pack=图生图包，bindings.image=input_image_1）
```

需要参考图时先建图片输入节点，把资产 id 写入节点，再连线到功能节点。

## 姿势 / 深度控制

```text
人物照 input_image_person + 姿势图/线稿 input_image_pose
  → 姿势换姿 preset_depth_pose（两个图片槽，保留人物身份）

姿势图/线稿 input_image_pose
  → 姿势生图 preset_depth_gen

深度图 input_image_depth
  → 姿势生图 preset_depth_gen + Union Depth 目标
```

- 姿势换姿：PoseStudio 线稿保持原始画幅，不裁白边；输出画幅取姿势参考图比例，分辨率取两图较大者，长边上限 2048。
- 姿势生图：线稿保持原始画幅，不裁白边；输出画幅跟随姿势参考图。
- `preset_depth_gen` 可能默认到姿势生图；需要 Union Depth 时从 `available_targets` 确认目标，再用 `canvas_apply_pack` 绑定具体包。
- 控制图是构图/动作参考，不是普通首帧；不要接到视频节点的首帧槽。

## 角色一致性

```text
角色输入 input_character_hero (front/side/back)
  → 图生图功能节点（多图参考）
  → 关键帧图片拼接
  → 图生视频
```

提示词里写「保持同一人物，五官、发型、服装一致」，不要只写角色名。

## 配音口播

```text
文本输入 input_text_script
  → 文字转语音 speech(mode=tts, text={{input_text_script}})
  → 图生视频或数字人节点
```

tts 节点也可以直接把文本写在节点里；被上游引用时用 `{{变量名}}`。需要语速、语气或节奏时写 `ttsTuning`；Turbo/Nano 只支持 `speed`。

## 语音转文字

```text
音频或视频输入（或上游视频节点）
  → speech(mode=asr, format=srt, asrTuning={timestamps:"word"})
```

ASR 高级参数写在 `asrTuning`；Qwen3-ASR 不支持 VAD、beam、热词、初始提示词和翻译。

## 分镜 → 视频

```text
每个分镜：3 个关键帧功能节点
  → 图片拼接（横排，gap=16）
  → 图生视频（首帧=拼接图）
```

视频提示词只写运动、节奏和约束，重复人物外观会浪费上下文。

## 批量搭建

1. 先 `canvas_get_graph` 拿现有变量名，避免重名。
2. 一次建一个分支：输入 → 功能 → 拼接/视频。
3. 每建完一个分支就检查连线和绑定。
4. 全部搭好后 `canvas_layout` 整理布局。
5. 执行前保存并预检；生成走安全确认。
