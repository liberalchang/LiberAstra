---
name: skill-creator
description: 引导用户把真实流程写成 Agent Skills 标准技能：用途、触发条件、步骤、资源、脚本、示例和验证。Use when the user wants to create, improve, or package a skill, including SKILL.md, references, assets, or scripts.
license: MIT
compatibility: 需要 LiberAstra 技能管理与安全确认；写入技能文件时会暂停等待用户同意。
metadata:
  author: LiberAstra
  version: "2.0"
allowed-tools: ask_user read_skill_file list_skill_files save_skill save_skill_file run_skill_script
---

# 技能生成

帮用户创建一个符合 Agent Skills 标准的技能包。技能可以是单个 `SKILL.md`，也可以带 `references/`、`assets/`、`scripts/`。

**按需读取：**

- 开始设计前，读 `references/standards.md` 了解 frontmatter、渐进披露和目录约定。
- 需要骨架时，读 `assets/SKILL.template.md`。

## 要问清的信息

1. **用途**：这个技能解决什么问题？用户为什么会需要它？
2. **触发条件**：用户说什么、做什么时应该激活？description 里要有中英文触发词。
3. **输入与输出**：开始前需要什么，结束时产出什么格式？
4. **步骤**：按顺序列出，每步做什么、用哪些工具、在哪里停。
5. **确认点**：删除、生成、写文件、跑脚本等风险操作必须停下来。
6. **资源**：是否需要参考文档、模板、图片或脚本？
7. **示例与边界**：给一个真实请求和期望结果；什么情况不该用这个技能。

一次问 2–3 个问题，不要一口气全问。

## 设计结构

- `SKILL.md` 只放核心流程和触发后必读内容，控制在 500 行以内。
- 长参考放到 `references/`，并在 SKILL.md 里写清“什么时候读哪个文件”。
- 输出模板、示例数据放 `assets/`。
- 可复用逻辑放 `scripts/`；脚本必须非交互、支持 `--help`、错误信息可操作、优先输出 JSON/CSV。
- 不要为了显得完整而堆砌通用知识；只写 agent 不知道的项目事实、坑和约定。

## 写 frontmatter

```yaml
---
name: my-skill
description: 做什么 + 什么时候用 + 中英文触发词，最多 1024 字。
license: MIT
compatibility: 运行环境要求（可选，最多 500 字）。
metadata:
  author: your-name
  version: "1.0"
allowed-tools: read_skill_file list_skill_files
---
```

`name` 只能用小写字母、数字和连字符，不能以连字符开头/结尾或连续出现连字符。

## 保存

1. 把 SKILL.md 完整正文给用户过目。
2. 用户确认后调用 `save_skill` 保存 SKILL.md。
3. 需要额外文件时，逐个调用 `save_skill_file` 写入 `references/`、`assets/` 或 `scripts/`。写文件会经过安全确认。
4. 用户已有完整目录时，告诉用户把目录打成 zip，在「技能」菜单上传。

## 验证

- 用 2–3 个真实用户请求测试技能，检查是否在正确时机激活。
- 检查 description 是否包含“做什么”和“什么时候用”。
- 检查所有引用的文件路径是否存在。
- 检查脚本能否在无交互环境下运行。
- 检查风险操作是否交给安全路由确认，而不是在技能里自行绕过。

## Gotchas

- 不要写“你可以考虑……”这种空话；步骤要能直接执行。
- 不要把全部参考资料塞进 SKILL.md；拆分并用触发条件说明何时读取。
- 不要在脚本里等待交互输入；agent 环境是非交互的。
- 不要伪造测试结果；跑不了子 agent 或脚本时标注 dry_run，并说明原因。
- 内置技能不能被覆盖；同名会被拒绝，换一个名字。
