# LiberAstra 曝光优化建议

- **仓库**：https://github.com/liberalchang/LiberAstra
- **核对基准**：GitHub API + 本地 clone `/workspace/LiberAstra` @ `ef55430`（`v1.0.3`）
- **核对时间**：2026-10-30 11:14 Asia/Shanghai（UTC+8）
- **分析范围**：discovery / stars / forks / 社区传播 / SEO / 开源营销；顺带少数影响可信度与留存的工程质量项
- **不做**：未改用户仓库；未部署实测；未编造用户证言或 Benchmark
- **参考**：`/workspace/research/LiberAstra-功能与质量分析-2026-10-27.md`（功能/质量，非曝光主轴）；`/workspace/docs/LiberAstra-公众号.md`（已有传播文稿）

---

## 1. 结论摘要

产品本身已经具备「可被看见」的素材：MIT、中英 README、截图、Docker + Windows 安装包、Releases、使用文档、参考项目致谢。**曝光短板不在功能缺失，而在发现链路几乎断开。**

当前最致命的三点：

1. **GitHub 发现面几乎空白**：Topics 为空、Homepage 为空、About 描述偏短且几乎只有中文关键词；Community health 约 42%（缺 CONTRIBUTING / Issue 模板等）。
2. **站外 SEO 为零**：用「LiberAstra」「liberastra」检索时，顶到的是巴西商业导师站 [liberastra.com.br](https://liberastra.com.br/)，**本仓库几乎搜不到**；作者 GitHub 主页无 bio / blog / Twitter，项目也未在个人置顶中露出（星数低时默认不突出）。
3. **首屏转化弱**：README 前半是长功能说明书，缺少「30 秒看懂 + 一条命令跑起来 + 30 秒 Demo」；无徽章、无 GIF/视频、无对比表；Release 下载次数合计个位数，`v1.0.3` 还缺 LiberSpeech 安装包资源。

优先做 **仓库可发现性 + README 首屏 + 一条成片 Demo + 定向投稿/交叉引用**，比继续堆功能更能换星与传播。

---

## 2. 现状快照（2026-10-30 核对）

| 项 | 现状 | 说明 |
| --- | --- | --- |
| Stars / Forks / Watchers | **3 / 0 / 3** | API 字段；创建于 2026-10-13 |
| 最近推送 | 2026-10-27 19:26 UTC+8 | 近两周提交很密（画布等），活跃度本身是加分项 |
| Language | TypeScript | 前端主导；后端 Python 也大量存在 |
| Description（About） | `自托管 AIGC 聚合编排平台` | 仅中文短句；缺 ComfyUI / Ollama / self-hosted 等英文检索词 |
| Homepage | **null** | 无官网 / Demo / Docs 站点链接 |
| Topics | **[] 空** | Dreamifly 同类有 `comfyui` `ai` 等，本仓库完全未填 |
| LICENSE | MIT | 已有，利于二次传播 |
| Releases | v1.0.0～v1.0.3 | 有 Windows 安装包；累计下载约个位数；**v1.0.3 仅有 `LiberAstra-Setup.exe`，未见 `LiberSpeech-Setup.exe`** |
| Discussions | **关闭** | `has_discussions: false` |
| GitHub Pages / Wiki | Pages 关；Wiki 开但未见用作产品文档门户 | docs 在仓库内 |
| Community health | **约 42%** | 有 README + LICENSE；缺 CONTRIBUTING、CoC、Issue/PR 模板、SECURITY |
| README | ~308 行，中英双语；16 张静态 PNG；**无 shields 徽章、无 GIF、无 Demo 视频、无「为什么选它」对比** | 功能段在安装段之前，首屏偏「说明书」 |
| 截图 | `docs/images/` 8 张，最大约 396KB | 有产品感；缺动效与「成品样片」 |
| 文档 | `docs/使用文档.md` 等较全；夹杂多份「开发计划」 | 对新访客像内部 wiki |
| 站外检索 | 「LiberAstra」几乎不指向本项目 | 名称与巴西站撞车；仓库外几乎无索引页 |
| 作者画像 | bio/blog/twitter 均为空；followers 约 6 | 个人品牌未给仓库导流 |
| 已有传播资产 | `/workspace/docs/LiberAstra-公众号.md` | 文稿已备；**是否已发布未在本任务中核实** |
| 参考上游 | Pixelle-Video、Dreamifly、Liber_SpeechAPI | 致谢规范；Dreamifly ~207★ 且有 homepage |

---

## 3. 按优先级的可执行清单

### P0（1～3 天内做完，曝光杠杆最大）

#### P0-1 填满 GitHub About：Topics + 英文描述 + Homepage

- **现状**：Topics 空；description 仅中文；homepage 空。
- **为何影响曝光**：GitHub Explore / Topic 页 / 站内搜索主要吃这些字段；空 topics = 几乎不进「comfyui」「ollama」「aigc」相关浏览流。
- **怎么改**：
  - Description 建议双语关键词一句话，例如：`Self-hosted AIGC orchestration for ComfyUI / Ollama / OpenAI-compatible APIs (image, video, speech). MIT.`（可保留中文前缀）。
  - Topics 建议（可按实际再裁）：`aigc` `comfyui` `ollama` `self-hosted` `fastapi` `react` `mcp` `text-to-image` `text-to-video` `tts` `openai-compatible` `local-ai`。
  - Homepage：短期可填 Releases 或后续的 Demo/Docs URL；有 GitHub Pages / 录屏页后立刻换。
- **工作量**：15～30 分钟。

#### P0-2 重写 README「首屏 40 行」：一句话价值 → 卖点 4～6 条 → Quick Start → Demo

- **现状**：标题后直接进入长「功能」分节与多图；安装从约第 71 行才出现；英文段更像压缩说明书。
- **为何影响曝光**：访客平均停留极短；首屏看不懂「和直接用 ComfyUI 有何不同」就会关掉。星标决策通常发生在前 30 秒。
- **怎么改**：
  1. 徽章行：Release、License MIT、Docker、Stars（shields.io）。
  2. 一句话：`只编排、不推理：把 ComfyUI + Ollama + 语音接到同一个工作台（Web / CLI / MCP / OpenAI /v1）。`
  3. 4～6 条卖点（对齐 PRODUCT.md）：多模态一体、LAN 分置、工作流包、画布、MCP/`/v1`、Windows 一键包。
  4. **Quick Start** 提到功能长文之前：`docker compose up -d --build` + 浏览器 `http://localhost:8000` + 「首次创建管理员 → 设置 Provider」。
  5. Demo：GIF 或 30～90 秒视频（Bilibili / YouTube）嵌入或链接；至少一张「成品短视频截帧」。
  6. 功能细节、模型下载表折叠进链接或 `<details>`，避免首屏被 HF 链接墙淹没。
- **工作量**：0.5～1 天（不含拍片）。

#### P0-3 补一条「可分享」Demo（GIF 或短视频）

- **现状**：仅有静态 UI 截图；无 GIF / 无 Bilibili / YouTube。
- **为何影响曝光**：AIGC 项目在 Reddit / 即刻 / 视频号 / X 上，**动图/成片**的转发率远高于界面截图；当前素材不适合跨站传播。
- **怎么改**：拍 45～90 秒：`一句话主题 → 快速创作出片` 或 `画布：文生图 → TTS → 拼接`。导出 GIF（README）+ 横版视频（投稿）。片尾固定仓库 URL 与 `docker compose` 一行。
- **工作量**：0.5～1 天（有现成环境）；若环境未齐，先做「UI 走查 + 假数据预览」并在片中注明「需自备 Comfy/Ollama」。

#### P0-4 处理品牌检索冲突：LiberAstra vs liberastra.com.br

- **现状**：公开网页搜索「LiberAstra」优先命中巴西导师项目，本仓库几乎不出现。
- **为何影响曝光**：口碑传播时别人搜名字找不到 GitHub；也影响未来域名/商标清晰度。
- **怎么改**（选一或组合）：
  - 对外统一副标题关键词：`LiberAstra — self-hosted AIGC orchestration` / `LiberAstra 编排台`；
  - 文案与 README 首行加 `github.com/liberalchang/LiberAstra` 规范链接；
  - 中长期评估是否启用更可检索的英文副名（如 LiberAstra Studio / LiberAstra Hub），**不要求立刻改仓库名**；
  - 若有自有域名，做一页落地（GitHub Pages 即可）写清「这是开源 AIGC 编排，不是巴西 mentorship」。
- **工作量**：文案统一 1 小时；落地页 0.5 天。

#### P0-5 修 Release 转化漏洞

- **现状**：各版本安装包下载次数合计约个位数；`v1.0.3` 资源列表仅有主程序 exe，**LiberSpeech-Setup.exe 未随最新版发布**（v1.0.0～1.0.2 曾有）。
- **为何影响曝光**：Windows 用户按 README「最新 Release」找不到语音包 → 体验失败 → 不 Star、不转发；下载数为社会证明，长期为 0 会显得「没人用」。
- **怎么改**：每个 tag 固定附带主程序 + LiberSpeech（或在 Release 正文明确「语音包见某 tag / 某构建说明」）；Release 正文中英各半页，置顶 Quick Start 与 Demo 链接；可考虑附 `checksum`。
- **工作量**：半天（含重打包若需要）。

#### P0-6 作者主页与仓库互导

- **现状**：`liberalchang` bio/blog/twitter 空；followers 很少；个人 Top 列表看不到 LiberAstra 叙事。
- **为何影响曝光**：星少时 Topic 流量有限，**个人主页与社交签名**是冷启动主通道。
- **怎么改**：GitHub Profile README 置顶 LiberAstra；bio 写一句产品定位 + 仓库链接；把已写好的公众号文（`LiberAstra-公众号.md`）发出并回链仓库；X / 即刻 / V2EX / LinuxDo 发同一条「自托管编排」帖。
- **工作量**：2～4 小时（不含养号）。

---

### P1（1～2 周，提升可信度与留存 → 间接涨星）

#### P1-1 补齐社区「门面文件」

- **现状**：无 `CONTRIBUTING.md`、Issue/PR 模板、`SECURITY.md`；Discussions 关闭；health ~42%。
- **为何影响曝光**：贡献者与评测者会扫这些文件；也影响 GitHub 仓库「健康度」展示与「Good first issue」叙事。
- **怎么改**：最小集：Bug / Feature Issue 模板各一；CONTRIBUTING 写清「如何跑前端+后端、如何提 PR」；打开 Discussions（Q&A + Show and tell）；SECURITY 邮箱或 GitHub private advisory。
- **工作量**：0.5～1 天。

#### P1-2 README 增加「和谁不同」半页对比（事实表，不贬损）

- **现状**：有「参考项目」致谢表，但没有面向访客的定位对比；PRODUCT.md 明确禁止虚构 Benchmark——应遵守。
- **为何影响曝光**：用户脑中默认对照物是 ComfyUI 本体、Dreamifly、Pixelle 系、各种「一键短视频」。说不清差异就不会收藏。
- **怎么改**：用**职责边界**对比即可，例如：

  | | LiberAstra | ComfyUI | 典型聊天 UI |
  | --- | --- | --- | --- |
  | 角色 | 编排工作台 | 推理/工作流引擎 | 对话 |
  | 模态 | 图+视频流水线+语音 | 偏图/视频图 | 偏文本 |
  | 接入 | Web+CLI+MCP+/v1 | 插件生态 | API/插件 |

  明确写：需要自备 Comfy/Ollama；本项目不替代它们。
- **工作量**：2～4 小时。

#### P1-3 文档门户化：对外「使用」与对内「研发计划」拆开

- **现状**：`docs/` 混有 `*开发计划.md` 与用户文档；主使用文档文件名为中文；community profile 曾指向 `.../tree/master/docs`（默认分支实为 `main`，易造成死链观感）。
- **为何影响曝光**：访客打开 docs 像进入内部迭代板；英文用户难找入口；搜索引擎难抓中文文件名。
- **怎么改**：`docs/user/` 与 `docs/dev/`（或把计划移到 `docs/internal/` 并 README 不链出）；提供 `docs/README.md` 索引（中英）；中长期用 GitHub Pages / VitePress 做 `liberastra` 文档站并填进 Homepage。
- **工作量**：1～2 天（纯整理）；Pages 站点另加 1～2 天。

#### P1-4 压缩/优化 README 配图 + 增加「成果」图

- **现状**：单张 PNG 最高约 396KB；全是 UI，缺少「生成结果」拼图。
- **为何影响曝光**：README 加载慢、信息重复；AIGC 访客更想看**产出质量**而非设置页。
- **怎么改**：UI 图压到约 100～150KB（webp/png）；另做 1 张结果拼图（文生图/口播封面/分镜）；动效用短 GIF。
- **工作量**：半天。

#### P1-5 定向「可索引」外链 5～8 处（合规投稿）

- **现状**：站外几乎无反向链接；公众号文稿已存在但检索侧未见项目页。
- **为何影响曝光**：Google/Bing/中文搜索靠外链与文章标题关键词（`ComfyUI Ollama 编排` `自托管 AIGC`）。
- **怎么改**（每条带仓库 URL + Demo）：
  - 中文：V2EX、LinuxDo、即刻、小红书/视频号（短视频）、微信公众号（已有稿）；
  - 英文：r/LocalLLaMA、r/comfyui、Hacker News Show HN（产品更完整后再发）、相关 Discord；
  - 主动 PR 到 awesome-comfyui / awesome-local-ai / awesome-selfhosted（**先确认列表收录标准，按格式提交，勿刷**）；
  - 在 Dreamifly / Pixelle 系 Issues 或 Discussions 用「参考实现了上层编排」做**礼貌交叉引用**（勿广告刷屏）。
- **工作量**：持续 1～2 周，每天 30～60 分钟。

#### P1-6 英语 README 独立成章，而不是中文附录缩写

- **现状**：`## English` 段明显短于中文；安装细节大量「见中文节」。
- **为何影响曝光**：国际 LocalAI / Comfy 用户是主要星标池之一；英文用户看到「see Chinese section」会流失。
- **怎么改**：英文同样具备 Quick Start、卖点、Demo、对比；模型表可链到英文 `docs/deployment.en.md`（可先从中文节翻译最小集）。
- **工作量**：1 天。

---

### P2（有余力再做）

#### P2-1 「一键体验」叙事（哪怕是录屏替代）

- 真·在线 Demo 成本高（GPU）。可用：HuggingFace Space 放「只读 UI 演示」、或「脚本化 docker compose 演示环境」文档 + 录屏。避免承诺免费 GPU。

#### P2-2 Star History / 贡献者墙 / 路线图公开板

- 星少时 star-history 意义有限；可先公开 Roadmap Discussion，收集「你卡在哪」——内容反过来喂 README FAQ。

#### P2-3 技能包与 MCP 的独立曝光页

- 仓库已有 `skills/liberastra`；可单独写「在 Claude / Cursor 里用 LiberAstra」短文，吃 Agent 生态流量（与当前 MCP 热度对齐）。

#### P2-4 社交预览图（Open Graph）

- 自定义 GitHub Social Preview 图：Logo + 一句定位 + 三图标（Comfy / Ollama / Speech）。链接被贴到即刻/X/微信时卡片更专业。

#### P2-5 间接工程质量（留存 → 口碑）

- 保持 CI 绿、`astra doctor` 对新人友好、首次引导 Wizard（若尚未足够明显）；失败时 README 链到「常见坑：host.docker.internal / 模型目录 / 8000 端口」。
- **这些不直接涨星，但能减少「装完即弃」**，避免差评帖。

---

## 4. 「不要做」或低 ROI

| 项 | 原因 |
| --- | --- |
| 为了曝光大规模改架构 / 重写前端 | 当前瓶颈是发现与首屏，不是技术栈名声 |
| 虚构用户数、Benchmark、媒体引用 | PRODUCT.md 已禁止；一旦被拆穿伤害更大 |
| 仓库更名炒作（短期） | 成本高；先用副标题与落地页解决检索冲突更便宜 |
| 同时运营 5 个文档站 | 先把 README + 一页 Docs 索引做透 |
| 买星 / 互刷星 | 平台打击且损害信任 |
| 在上游项目 Issue 里硬广 | 易被关；改为高质量对比文 + 正规 awesome PR |
| 把「越狱包」当英文社区主卖点 | 部分国际社区敏感；对外主叙事用「official + optional packs」更稳 |
| 等功能「完美」再宣传 | v1.0.3 已有安装包与画布；冷启动靠传播节奏，不是靠再做三个模块 |

---

## 5. 建议 1～2 周行动路线

### 第 1 周（发现面 + 首屏）

| 日 | 动作 |
| --- | --- |
| D1 | 填 Topics / Description / Homepage；Profile 置顶；Release 补 LiberSpeech 或改文案 |
| D2 | README 首屏重排 + 徽章 + Quick Start 上移；功能长文折叠 |
| D3 | 拍 60 秒 Demo（快速创作或画布）；出 GIF |
| D4 | 发公众号稿（已有 `LiberAstra-公众号.md`）+ 同步即刻/视频号；英文短帖草稿 |
| D5 | 对比表 + FAQ「需要自备什么硬件/模型」；Issue 模板 + CONTRIBUTING 最小集 |
| D6–D7 | V2EX / LinuxDo / r/comfyui 或 r/LocalLLaMA 各一帖；收集反馈改 README 措辞 |

### 第 2 周（外链 + 可信度）

| 日 | 动作 |
| --- | --- |
| D8–D9 | docs 索引页；开发计划移出用户路径；考虑 GitHub Pages 一页落地 |
| D10 | 英文 Quick Start 补全；Social Preview 图 |
| D11–D12 | awesome 列表按规范提 PR；礼貌交叉引用参考项目生态 |
| D13–D14 | 根据提问补「常见失败」；打开 Discussions；复盘星/流量（GitHub Insights，需登录可见） |

成功信号（务实）：2 周内 Topics 流量可见、Release 下载从个位到两位数、出现首条外部文章索引「LiberAstra ComfyUI」、Issues/Discussions 开始有陌生人提问——比盯着「冲到 100 星」更可操作。

---

## 6. 附录：与曝光相关的已具备优势（保持）

- MIT + 规范 `THIRD_PARTY_NOTICES.md`（移植边界清晰，利于被引用）。
- 中英 UI / README 基础在（补齐英文安装即可）。
- Docker Compose profiles + Windows 安装包双路径（叙事完整）。
- 定位句清晰：**平台不做推理，只做编排**——适合做传播钩子。
- 产品截图与长篇 `使用文档` 已存在，改造成本低于从零写文档的项目。

---

*报告结束。*
