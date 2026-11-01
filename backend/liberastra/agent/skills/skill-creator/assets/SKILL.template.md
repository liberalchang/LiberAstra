---
name: my-skill
description: 一句话说明做什么，并写清什么时候使用；加入用户可能提到的中英文触发词。
license: MIT
compatibility: 运行环境或依赖要求（可选，最多 500 字）。
metadata:
  author: your-name
  version: "1.0"
allowed-tools: read_skill_file list_skill_files
---

# 技能标题

用一两句话说明这个技能解决什么问题，以及不适用的情况。

**按需读取：**

- 需要详细参数时，读 `references/REFERENCE.md`。
- 需要输出模板时，读 `assets/template.md`。

## 步骤

1. 先确认输入和用户意图。
2. 执行第一步，产出明确结果。
3. 在风险操作前停下来让用户确认。
4. 验证结果，再进入下一步。
5. 输出最终结果和后续建议。

## 确认点

- 删除、覆盖、提交生成、写文件、运行脚本前必须确认。
- 不确定用户意图时先问，不要猜。

## 示例

用户说：
> ...

期望行为：
> ...

## Gotchas

- 写项目特有的坑和反直觉约定，不要写通用常识。
- 如果某一步容易失败，写清失败后怎么恢复。
