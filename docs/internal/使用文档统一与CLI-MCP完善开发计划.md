# 使用文档统一与 CLI/MCP 完善开发计划

状态：当前计划（2026-11-05）

范围：应用内使用文档、站点文档、Docker 构建、CLI/MCP、两个外部 skill。

不在本轮范围：Canvas / Character / VC 等 CLI 的全量能力；`site/docs` 生成物是否继续入库；`DirectorPanel` 的 `MarkdownView` 改造。

---

## 1. 已确认的决策

- `site/docs-src` 是文档唯一真源，同时供 GitHub Pages 和应用内 `/guide` 使用。
- `site/docs` 只是 VitePress 构建产物，继续入库，GitHub Pages 流程不改；应用运行时不依赖它。
- 应用内统一为一个文档页：左侧板块/章节树，中间正文，右侧页内目录；中英跟随界面语言。
- 英文文档全量对齐中文，不做“缺英文时回退中文”的默认行为。
- 删除独立 CLI 页面和导航入口；CLI 文档只作为统一文档页里的「集成 → CLI」章节存在。
- `/dev/cli` 不保留重定向，旧地址直接移除。
- 根 `.dockerignore` 全量添加，实际不存在的条目也写入，作为保险。
- `docs/internal` 历史计划统一标记为“已归档”。
- CLI/MCP 本轮先做 Agent 关键能力；两个 skill 允许调整脚本接口和退出码。

---

## 2. 文档内容迁移

### 2.1 唯一真源与目录约定

- 中文源：`site/docs-src/*.md`、`guides/*.md`、`integration/*.md`。
- 英文源：`site/docs-src/en/` 下的同名文件。
- 侧栏/章节清单：新增 `site/docs-src/nav.json`，VitePress 配置与前端共用。
- 迁移完成后删除：
  - `docs/使用文档.md`
  - `docs/cli.md`
  - `docs/cli.en.md`

### 2.2 中文迁移对照

| 旧 `docs/使用文档.md` 章节 | 迁入位置 |
|---|---|
| 开篇、打开方式、从资源库选择 | `quickstart.md` |
| 先搞清三层：服务提供方 → 工作流包 → 模型文件 | `quickstart.md`，保留原表格与解释 |
| 总览、从资源库选择 | `quickstart.md` + 各功能页对应章节 |
| 画布、画布菜单、节点、导演台、变量与提示词、执行与结果 | `guides/canvas.md` |
| 图像（FLUX.3、Qwen-Image 2.1、参考图调色、文生图、图生图、图片增强、深度图） | `guides/image.md` |
| 语音（TTS、ASR、换音、音色库、音乐库） | `guides/speech.md` |
| 视频（选包、MiniMax H3、自定义素材、数字人、i2v、动作迁移、快速创作、角色库、分镜模板、模型目录） | `guides/video.md` |
| 工具（图片/视频/音频拼接、图片/视频增强） | 新增 `guides/tools.md` |
| 资源（资产、插件）、任务 | `guides/works.md` |
| 设置（服务提供方、工作流包、提示词模板、系统设置） | `guides/settings.md` |
| 阅读 | `quickstart.md`；删除 CLI 页面说明 |
| 文件放在哪 | `install.md` |

迁移原则：保留旧文通俗、细致的解释、例子、表格和注意事项；只调整标题层级与分页，不做摘要化改写。

### 2.3 必须合并的冲突点

- 画布：站点有「分组：功能节点里的『所属』」，旧文有「画布菜单」；按当前 UI 确认后两者都保留。
- 图像：站点有「修复与放大」，旧文有「图片增强（已移到工具）」；以当前实现为准统一表述。
- 资源/作品：站点是「作品与任务」，旧文是「资源 + 任务」；合并成一份。
- 视频：站点与旧文详略不同，旧文的模型配对表、注意事项优先保留。

### 2.4 英文全量对齐

现状：英文页不是只缺 `guides/tools.md`，多数页面是精简版。

| 页面 | 中文行数 | 英文行数（当前） |
|---|---:|---:|
| `guides/canvas` | 180 | 26 |
| `guides/video` | 305 | 41 |
| `guides/image` | 192 | 51 |
| `guides/settings` | 107 | 27 |
| `guides/speech` | 48 | 25 |
| `guides/works` | 42 | 21 |

要求：

- 新建 `site/docs-src/en/guides/tools.md`。
- 所有 `en/` 页面按中文逐节扩写，做到内容同级，而不是只保证文件存在。
- 顺序：先定稿中文迁移，再逐页翻译，避免中文改动导致英文返工。
- 代码块、表格、模型名、文件名、工作流包名保持原样；标题文字可意译，但 H1/H2/H3 层级和大节一一对应。
- 应用内不再默认“英文缺失回退中文”；只在文件加载失败时做兜底提示。
- 加机械检查 `scripts/check_docs_parity.py`：
  - 每个中文页存在英文同名页；
  - H1/H2/H3 数量一致；
  - `nav.json` 里的 slug 都能找到对应文件。
- 该脚本在本地验收运行；是否加入 CI 可后续决定。

### 2.5 nav.json

结构示例：

```json
{
  "zh": {
    "sections": [
      {
        "title": "介绍",
        "items": [
          { "title": "项目目的与非目标", "slug": "index" },
          { "title": "快速开始", "slug": "quickstart" }
        ]
      }
    ]
  },
  "en": {
    "sections": []
  }
}
```

VitePress `config.ts` 用它生成中英侧栏；前端用它生成左侧章节树。新增 `guides/tools.md` 时同时补中英条目。

---

## 3. 应用内统一文档页

- 路由：`/guide/*`，默认显示 `index`（介绍页）；`/guide/integration/cli` 直达 CLI 章节。
- 布局：左侧板块/章节树，中间正文，右侧 H2/H3 页内目录；移动端侧栏折叠。
- 中英：跟随 `i18n.language`，英文读 `en/` 同名页；全量对齐后不依赖回退。
- 渲染：
  - 新增依赖 `react-markdown`、`remark-gfm`、`rehype-slug`、`github-slugger`。
  - 新增 `frontend/src/docs/`：
    - `content.ts`：显式 `import.meta.glob`，只匹配 `docs-src/*.md`、`docs-src/guides/*.md`、`docs-src/integration/*.md` 及 `en/` 对应目录，禁止 `**/*.md`。
    - `manifest.ts`：读取 `site/docs-src/nav.json`。
    - `slug.ts`、`links.ts`：frontmatter 剥离、标题 slug、站内链接映射。
  - `GuidePage.tsx` 重写为文档布局；`DocsMarkdown` 负责正文。
  - 跨页锚点（如 `/guide/guides/image#文生图`）在渲染后滚动到目标位置。
  - `MarkdownView` 保留不动：`DirectorPanel` 仍用它渲染技能正文和 LLM 文本。
- 链接映射：
  - `/guides/image` → `/guide/guides/image`
  - `/integration/cli` → `/guide/integration/cli`
  - `/en/...` 按当前语言归一化
  - 外部链接新窗口打开，站内链接走 React Router。
- `tsconfig.app.json` 增加 `resolveJsonModule`。
- 单测 `frontend/src/docs/docs.test.ts`：frontmatter 剥离、slug、链接映射、TOC 提取；加入 `package.json` 的 `test` 脚本。

---

## 4. 移除独立 CLI 页面

- 删除 `frontend/src/pages/CliPage.tsx`。
- 删除 `frontend/src/App.tsx` 里的 `CliPage` lazy import 和 `/dev/cli` 路由。
- 删除 `frontend/src/nav/model.ts` 里的 `nav.cliDocs` 入口，并把 `match: ["/guide", "/dev"]` 改为 `["/guide"]`。
- 删除 `frontend/src/i18n/index.ts` 的中英 `cliDocs` 文案。
- 删除 `frontend/src/nav/icons.tsx` 的 `cliDocs` 图标映射；确认 `Terminal` 是否仍被其他项使用。
- 更新 `frontend/src/nav/model.test.ts` 的期望项，去掉 `nav.cliDocs`。
- **不保留 `/dev/cli` 重定向**；旧地址直接移除。CLI 文档只通过 `/guide/integration/cli` 访问。

---

## 5. 构建与清理

### 5.1 Dockerfile

`docker/Dockerfile` 前端阶段：

```dockerfile
COPY frontend/ ./
COPY site/docs-src /site/docs-src
RUN npm run build
```

删除原来的：

```dockerfile
COPY docs/使用文档.md docs/cli.md docs/cli.en.md /docs/
```

运行阶段不动：Markdown 已被 Vite 打进 `dist`，不需要 Node、VitePress 或 `site/docs`。

### 5.2 根 `.dockerignore`

```dockerignore
.git
.github
.cursor
.impeccable
参考项目
docs
data
backend/data
services/*/models
packaging
*.exe
*.zip
**/node_modules
**/dist
frontend/dist
frontend/.vite
**/*.tsbuildinfo
site/docs
site/docs-src/.vitepress
**/__pycache__
**/*.py[cod]
**/.venv
**/venv
**/.pytest_cache
**/.mypy_cache
**/.ruff_cache
**/*.egg-info
**/.env
**/.env.*
!**/.env.example
*.pem
*.key
```

注意：不要排除 `site/docs-src/*.md`、`site/docs-src/nav.json`、`backend/workflows`、`backend/templates`、`backend/prompts`。

### 5.3 删除旧文件

- `docs/使用文档.md`
- `docs/cli.md`
- `docs/cli.en.md`

### 5.4 引用更新

- `README.md:162/232/395`
- `docs/README.md:13/18/40`
- `docs/agents.md:61/69`
- `docs/deployment.en.md:86`
- `PRODUCT.md:52`
- `docs/LiberAstra-公众号.md:174`
- `docker/Dockerfile:10`
- `frontend/src/pages/GuidePage.tsx`
- `frontend/src/pages/CliPage.tsx`（删除）
- `docs/internal` 内引用旧文档的段落：只改链接，不改历史内容

### 5.5 历史计划横幅

给 `docs/internal/*.md` 的历史计划/设计文档，在标题下第一行加：

```markdown
> **历史方案（已归档）**：本文记录当时的开发计划与决策，不代表当前实现。当前功能与文档以 `site/docs-src/` 和代码为准；请勿直接按本文实施。
```

范围：`docs/internal` 下除 `README.md` 和本计划以外的计划/设计文档；`docs/导演skill流程优化.md` 同样处理。

`docs/internal/README.md` 顶部增加说明，区分“当前计划”和“历史方案”。

`docs/LiberAstra-曝光优化建议-2026-10-30.md` 是分析快照，不改内容；只更新其中指向旧文档的链接。

---

## 6. CLI/MCP Agent 关键能力

### 6.1 CLI P0

- 全局参数 `--json/--server/--token` 支持放在子命令前后；在 `main()` 预处理 argv。
- `--json` 下统一结构化错误：`{ok:false,error:{type,message,exit_code}}` 输出到 stderr，退出码保持 0/2/3/4。
- `doctor --json` 输出结构化检查项。
- `job list --status --kind`（API 参数名 `status_filter`）、`job wait --timeout`、`job retry`。
- `image edit`（按 `/api/v1/images/edit` 现有表单字段封装）。
- `video i2v`（按 `/api/v1/videos/i2v`）；其余视频模式留 P1。
- `asset list`、`asset download`、`asset delete --yes`。
- `voices list`、`workflow list --capability`。
- `logout`、顶层 `--version`。
- `save_outputs` 用 `Path(name).name` 消毒服务端文件名。

### 6.2 MCP P0

- 发现类工具：`list_voices`、`list_workflows`、`list_providers`、`list_assets`、`get_asset`。
- 异步工具：`submit_image`、`submit_speech`、`submit_transcription`、`submit_video` 返回 `job_id`；`wait_job`、`cancel_job`、`retry_job`。
- 现有 5 个工具保留，新增 `wait: bool = True`；补齐 `workflow`、`provider_id`、`model`、`format`、`script` 等参数。
- 错误返回结构化 dict，401 提示 `astra login`。
- `FastMCP("LiberAstra", instructions=...)`；增加 `liberastra://skill`、`liberastra://workflows` 等 resources。
- CLI 与 MCP 共用提交参数构造和结果整形，避免参数漂移。

### 6.3 测试

- 扩展 `backend/tests/test_cli.py`：全局参数位置、JSON 错误、job 过滤/重试、image edit、asset、voices。
- 新增 `backend/tests/test_mcp.py`：`tools.py` 用 fake client；`create_mcp()` 校验工具名和必填参数。
- `skills/liberastra` 增加命令存在性测试：解析 SKILL 里的 `astra ...` 命令，校验 Typer app 中存在。

---

## 7. Skills

### 7.1 `skills/liberastra`

- `SKILL.md` 精简为触发条件 + 最短工作流。
- 新增 `references/cli.md`、`references/api.md`、`references/mcp.md`、`references/troubleshooting.md`。
- 补安装方式、Windows 安装包路径、异步 `--no-wait` + `job wait`、错误码处理、完整示例。

### 7.2 `skills/speechapi`

- 新增 `models` 子命令（`GET /api/v1/models`）。
- 增加 `--base-url/--api-key/--timeout/--retries`。
- 批量 ASR（多文件/目录）；自动创建输出目录；统一退出码。
- 加 mock 测试，覆盖配置优先级、参数构造、错误分支。
- README 同步；`data.json` 若为真实密钥，删除并轮换（`.gitignore` 已忽略，不在 git 历史里）。

### 7.3 `skills/README.md`

说明两个 skill 的边界：`liberastra` 是 `:8000` 异步编排平台，`speechapi` 是 `:5555` 同步语音服务。

### 7.4 集成文档

更新 `site/docs-src/integration/cli.md`、`site/docs-src/integration/mcp.md`、`docs/agents.md`，与新的 CLI/MCP 行为一致。

---

## 8. 验收

1. 前端单测 + `npm run build` + `tsc`。
2. 后端 `pytest` + `ruff check backend`。
3. 站点 `cd site/docs-src && npm run build`。
4. `scripts/check_docs_parity.py` 通过：中英页面一一对应，H1/H2/H3 数量一致。
5. Docker 从仓库根构建：
   - 构建上下文不含 `site/docs-src/node_modules`；
   - 镜像内 `/app/static` 有文档内容；
   - 容器启动后 `/guide` 正常。
6. 浏览器验收（临时环境 8001，不动 8000 和生产库）：
   - `/guide` 侧栏、章节切换、页内锚点、刷新、深链、后退。
   - `/guide/integration/cli` 可直达。
   - 导航不再有「CLI 文档」入口；`/dev/cli` 不再可用。
   - 中英切换显示完整英文内容，不出现默认中文回退。
   - 移动端侧栏折叠。
7. Skill 冒烟：`--help`、`models`（mock）、命令存在性测试。
8. 全量后端测试 + 静态检查通过后再提交。

---

## 9. 提交拆分

- **PR1 文档内容**：中文迁移定稿 + 英文全量对齐 + `nav.json` + VitePress 构建通过。
- **PR2 文档页与构建**：统一 `/guide` 文档页、删除 CLI 页面/导航、Dockerfile 与 `.dockerignore`、删除旧文件、更新引用、历史计划横幅。
- **PR3 CLI/MCP 与 skills**：Agent 关键能力 + 两个 skill + 集成文档。
- 可以压成两个 PR：文档一个，CLI/MCP + skills 一个。

---

## 10. 风险与对策

- **内容丢失**：迁移对照表 + 逐段核对；保留口语化解释和例子。
- **英文扩写量大**：中文定稿后再翻译；用 parity 脚本保证页面和标题结构一致。
- **路径/构建错误**：本地和 Docker 双构建验证；`import.meta.glob` 不用 `**/*.md`。
- **锚点和外链**：slug 映射做单测；跨页锚点在渲染后滚动。
- **导航/测试残留**：删除 `nav.cliDocs` 后跑 `nav/model.test.ts` 和前端 build。
- **历史计划误用**：统一横幅 + `docs/internal/README.md` 区分当前/历史。
