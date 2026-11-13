---
name: qwen-image-2-1-prompt-writing
description: 为 Qwen-Image-2.1 写文生图和图像编辑提示词。按官方 PE-T2I / PE-I2I 规则做主体前置、版面与文字渲染、属性解耦、多参考图标签和透明背景；支持精简与长观察式两种 T2I 写法。Use when writing or rewriting a Qwen Image 2.1 prompt, poster/infographic/UI prompt, image-edit instruction, multi-reference composition, or text-rendering prompt.
compatibility: Portable to any agent that can read local files. Prompt-only; no image generation API calls.
---

# Qwen Image 2.1 Prompt Writing

本 skill 只负责**写提示词**，不生成图片。导演台负责把提示词写入 Qwen Image 2.1 画布节点或工作流；参考图必须由用户提供，不能伪造输入。

## 先读规则

动笔前先按任务读取对应参考文件，不要凭记忆：

- 文生图：`read_skill_file(name="qwen-image-2-1-prompt-writing", path="references/t2i-rules.md")`
- 图像编辑/合成：`read_skill_file(name="qwen-image-2-1-prompt-writing", path="references/edit-rules.md")`
- 图像内可读文字：再读 `references/text-rendering.md`
- 需要词汇或画幅速查：读 `references/cheat-sheet.md`
- 需要示例：读 `references/examples.md`

## 核心规则

1. 用自然语言描述，不用 SD 标签列表或 `(term:1.5)` 权重语法。
2. 主体前置：主体 → 环境 → 风格 → 构图 → 光线。
3. 必须出现在画面里的文字用双引号原样保留，不改写、不翻译、不美化。用户给了具体文案时，必须把原文写进画面，不能用 “caption area”“reserved for text” 之类占位描述代替。
4. 编辑 = 变更 + 保持条款：只改用户点名的属性，其余内容明确保留。
5. 画幅只放在 `wh_ratio` 或 `ratio_follow`，不要写进提示词正文。
6. 不用空泛质量词（masterpiece、8K、highly detailed、award-winning）。
7. T2I 描述用英文；编辑散文语言按编辑规则判定，画面内文字保留原语言。

## 工作流

1. 判断轨道：没有输入图 → T2I；有一张或多张输入图 → Edit/合成。
2. 读对应 reference，按其中的输出契约、字段名、互斥规则和自检清单执行。
3. 有图像内文字时叠加 `text-rendering.md` 的引用纪律。
4. 如果当前 Agent 环境能看图，先检查输入图的文字、姿态、服饰和布局，再改写；纯文本环境只在关键不变量无法推断时提问。
5. 对照核心规则自检后交付。

## T2I 风格选择

- **精简**：单一明确主体（人像、静物、安静场景），1–3 句自然语言，约 30 词。主体 → 环境 → 风格 → 构图 → 光线。
- **长观察式**：海报、版式、UI、信息图、故事板、多元素或需要精确定位/多段文字，约 20 句 / 300–500 词，按官方八步规范写。
- 不确定时：布局和文字密集图走长式，简单主体走精简式。

## Edit 规则

- 输出三个字段：`rewritten_prompt`、`wh_ratio`、`ratio_follow`；`wh_ratio` 与 `ratio_follow` 互斥。
- 多图（N ≥ 2）必须用 `<image1>`、`<image2>`… 标注，并说明每张图的角色（canvas / 素材来源）。
- 身份是最难的不变量：面部、标志性配饰、产品设计、渲染介质未被点名时一律保留。
- 复杂编辑拆成 2–3 个小 pass，每轮后复核身份和标签保真度。
- 局部编辑用红框/选区/蒙版限定范围，并写 "Leave everything else unchanged."

## LiberAstra 本地约定

- 只输出提示词或约定的 JSON，不要调用生成工具；需要出图时交给导演台创建/执行 Qwen Image 2.1 节点。
- 本地工作流把提示词和画幅分开传：提示词正文不要写比例、像素或分辨率。
- 编辑任务必须已有用户提供的参考图；没有参考图时只能按 T2I 写，或向用户要图。
- 本地工作流如果有独立的 negative prompt 字段，才使用负向描述；没有该字段时，把所有要求改写成正向、可见的描述。
- 不承诺“官方 PE 模型”效果：本 skill 是按官方 PE-T2I/PE-I2I 规则写提示词，不替代官方增强模型。

## 输出

### 默认模式

1. 提示词优化解析：2–4 条关键决策（主体、画幅、构图/光线/材质、语言判定）。
2. 可直接复制的提示词：只放最终提示词字符串，不重复画幅或副标题。
3. 微调建议：2–3 条可操作变体。

用户说“只输出提示词/只要最终提示词”时，跳过解析和微调，只给最终提示词与画幅。

不要在最终回复里输出草稿、修改过程、自检清单、英文思考或 “regenerate…”“let me fix…” 之类中间句。

### JSON 模式

用户明确要求 API 格式、JSON only、脚本格式或自动化流程时，只输出单行 JSON：

- T2I：`{"rewritten_prompt": "...", "wh_ratio": "3:2"}`
- Edit：`{"rewritten_prompt": "...", "wh_ratio": "", "ratio_follow": "<image1>"}`
