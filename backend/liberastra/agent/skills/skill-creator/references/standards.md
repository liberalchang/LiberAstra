# Agent Skills 标准速查

来源：https://agentskills.io/specification

## 目录

```text
my-skill/
├── SKILL.md          # 必需：frontmatter + 指令
├── scripts/          # 可选：可执行脚本
├── references/       # 可选：按需读取的文档
├── assets/           # 可选：模板、图片、数据
└── ...               # 其他文件
```

## frontmatter

| 字段 | 必需 | 规则 |
|------|------|------|
| `name` | 是 | 1–64 字，小写字母、数字、连字符；不以连字符开头/结尾；不能连续连字符；与目录名一致 |
| `description` | 是 | 1–1024 字，写清做什么和什么时候用 |
| `license` | 否 | 许可证名称或指向 LICENSE 文件 |
| `compatibility` | 否 | 1–500 字，环境要求 |
| `metadata` | 否 | 字符串键值对 |
| `allowed-tools` | 否 | 空格分隔的预授权工具；实验性 |

## 渐进披露

1. 启动时只加载所有技能的 `name` 和 `description`。
2. 任务匹配后加载完整 `SKILL.md`。
3. 需要细节时再读取 `references/`、`assets/`、`scripts/`。

`SKILL.md` 建议 500 行 / 5000 token 以内。长内容拆到 references，并写清“什么时候读哪个文件”。

## 脚本

- 脚本放 `scripts/`，从技能根目录用相对路径引用。
- 非交互：所有输入用命令行参数、环境变量或 stdin。
- 支持 `--help`，错误信息说明怎么修。
- 输出优先 JSON/CSV；诊断写 stderr。
- 破坏性操作提供 `--dry-run` 或显式 `--confirm`。

## 安全

技能内容可以描述风险操作，但执行由 agent 的安全路由决定。删除、生成、写文件、运行脚本默认需要用户确认；不要在技能里要求 agent 绕过确认。
