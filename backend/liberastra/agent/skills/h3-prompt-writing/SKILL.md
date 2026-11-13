---
name: h3-prompt-writing
description: 为 MiniMax H3 视频生成写 T2VA、I2VA、FL2VA、L2VA、Ref2VA 提示词。把多模态需求改写成官方字段结构，处理镜头时间轴、关键帧路径、参考图/视频/音频标签、对白与声音分层。Use when writing or rewriting an H3 video prompt, storyboard shot prompt, keyframe prompt, or full-reference Ref2VA prompt.
compatibility: Portable to any agent that can read local files. No external API calls or MiniMax Hub runtime required.
---

# H3 Prompt Writing

本 skill 只负责**写提示词**，不创建画布节点、不调用生成工具。节点、分段、执行由导演台按画布工具和项目时长规则处理。

## 先读规则

写提示词前，先按模式读取对应参考文件，不要凭记忆：

- 基础模式（T2VA / I2VA / FL2VA / L2VA）：
  `read_skill_file(name="h3-prompt-writing", path="references/base-en.txt")`
- 全参考模式（Ref2VA）：
  `read_skill_file(name="h3-prompt-writing", path="references/ref-en.txt")`

参考文件里的字段名、段落顺序、标签和时间格式是权威契约，不要改名、不要重排。

## 工作流

1. 判断输入模式：T2VA、I2VA、FL2VA、L2VA 或 full-reference Ref2VA。
2. 基础模式按 `references/base-en.txt` 的最终提示词结构写；Ref2VA 按 `references/ref-en.txt` 的六段结构写。
3. 先建立参考素材角色表、说话人表和时间轴，再写镜头正文。
4. 严格保持字段名、标签、时间码和保留标记；参考标签一经定义，全篇编号不变。
5. 输出前按参考文件做一次自检：字段齐全、时间轴匹配、参考标签一致、无未定义标签。

## 基础模式

- T2VA：从文本构建完整视听时间线。
- I2VA：从首帧开始向后发展。
- FL2VA：描述首帧与末帧之间的连续路径。
- L2VA：推断合理开头，收束到给定末帧。

按 `references/base-en.txt` 的顺序使用：

- `integrated_multimodal_description`
- `overall_soundscape`
- `non_diegetic_music`

## 全参考模式（Ref2VA）

按顺序写六段：

1. `subject_definitions`
2. `summary`
3. `retention_analysis`
4. `detailed_description`
5. `overall_soundscape`
6. `non_diegetic_music`

参考图统一用 `<Picture N>`，参考视频用 `<Video N>`，参考音频用 `<Audio N>`；标签在各段之间保持一致。

## LiberAstra 本地约定

- **正文语言**：默认跟随用户语言；字段名、`[Shot N]`、`At MM:SS.mmm`、`<Picture N>/<Video N>/<Audio N>/<Subject N>`、保留标记和固定对齐句保持英文。用户明确要求纯英文时，按官方全英文输出。
- 对白、歌词和画面内可见文字保留原语言；画面文字用引号原样引用。
- 每个 H3 单段建议 4–15 秒，24fps；本地 H3 单段上限 362 帧（17n+5 对齐，约 15.08 秒）。需要更长时由导演台拆段或使用连续生成，不把总时长写进单个节点。
- 口播/动作迁移的成片时长由音频或参考视频决定；这里只写单段视频提示词，不要要求用户压缩文案或裁短参考视频。
- 没有配乐时写 `N/A`；没有环境声时也要写 `N/A`，不要省略字段。
- 不写空泛质量词（cinematic、beautiful、masterpiece）；用可见的构图、动作、光线、材质和声音细节表达。
- 不伪造参考素材。用户没提供的图片、视频或音频，不要写进 `<Picture N>/<Video N>/<Audio N>`。

## 输出

直接输出最终提示词，字段结构按所选模式。不要附加生成参数 JSON、节点操作说明或未经用户要求的多版本；需要多版本时明确标注每版差异。不要在最终回复里输出草稿、修改过程、自检清单或 “let me rewrite…” 之类中间句。
