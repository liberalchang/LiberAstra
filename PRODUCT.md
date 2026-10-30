# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

四类确认的首要用户，界面需要同时服务好他们：

- **开源社区自托管者**：从 GitHub 拉取部署，重视文档与易上手。
- **中文内容工作室 / 小团队**：批量生产口播视频与图文内容。
- **个人创作者**：在本机或局域网自托管，日常出图、出视频、配音。
- **开发者 / 二次集成者**：通过 `astra` CLI、MCP Server、OpenAI 兼容 `/v1` 接口调用，几乎不碰 Web UI。

主要使用场景为桌面端浏览器访问自托管实例。

## Product Purpose

LiberAstra 是自托管 AIGC 聚合编排平台：对接局域网或本地的 ComfyUI、Ollama、OpenAI 兼容服务以及云端模型 API，提供语音、图像、视频三大能力。**平台本身不做模型推理，只做编排**——出图、出声、出视频都交给已配置的外部服务。

成功意味着：用户填好服务提供方地址后，能在一个工作台里完成从提示词到成品的完整生产流（文生图、图生图/编辑、修复放大、快速创作分镜视频、数字人口播、图生视频、动作迁移、TTS、语音转文字、音色库、音乐库），并在「作品」「任务」页追踪结果与进度。

## Positioning

自托管 AIGC 聚合编排层：不做推理，把本地/局域网的 ComfyUI、Ollama、语音服务和云端 API 统一成一个工作台。单用户、Provider 密钥加密保存、中英双语。内置并支持导入工作流包（含官方与越狱成对的图像/视频包）、分镜模板流水线（`static_` / `image_` / `video_`）与 PromptField 全局提示词优化。

## Operating Context

- 部署：仓库根目录 `docker compose up -d --build`，默认 `http://<主机>:8000`；Ollama / ComfyUI / 语音插件为独立组件，可分置到另一台主机。
- 首次使用：创建管理员 → 设置 → 服务提供方填地址与密钥 → 导入工作流包。
- 接入方式：Web UI、`astra` CLI、MCP Server、OpenAI 兼容 `/v1`(chat / audio / images)。
- 单用户，API Token 鉴权。

## Capabilities and Constraints

- 前端：React 19 + Vite + Tailwind CSS 4,cva/clsx/tailwind-merge + lucide-react,i18next 中英文，zustand + react-query。
- 界面按侧栏分组：首页工作台（图像/视频/语音）、图像生成、视频生成、语音服务、作品、任务、设置。
- 提示词统一走 PromptField（原始稿/优化稿、场景模板、提交优化任务）。
- 视频快速创作支持 AI 创作/固定文案/批量三种模式与 Turbo 加速 LoRA 开关。

## Brand Commitments

- **明暗双主题必须同时维护**：深浅两套主题都是一等公民，任何设计改动必须在两个主题下同时成立。
- **中英双语 UI 必须同时维护**：所有界面文案与规范覆盖中英文（i18next)。
- 除上述两条外暂无其他硬性品牌约束，风格可自由探索。

## Evidence on Hand

- 产品文案与功能说明：`README.md`、`docs/使用文档.md`、`docs/providers.md`。
- 界面截图：`docs/images/`(home、image-generate、image-edit、video-quick、video-assets、video-i2v、speech-tts)。
- 规划文档：`LiberAstra规划书.md` 及 `docs/internal/` 下各开发计划。
- 不可虚构：用户证言、Benchmark、第三方评测均不存在，未来工作不得编造。

## Product Principles

1. **编排透明**：UI 永远让用户清楚当前任务由哪个外部服务执行、进度如何（SSE 任务页、可取消/重试）。
2. **工具效率优先**：这是 Operate 模式的工具台，可扫读性、一致性与密度优先于视觉表现欲。
3. **双主题双语言同等质量**：不做"暗色是附属皮肤""英文是机翻"式的二等公民。
4. **配置驱动的真实状态**：控件随所选服务/工作流包能力切换（如音色列表、Turbo 开关只跟所选包有关），不显示不可用的选项。
5. **自托管可信**：密钥加密、单用户、分置部署——界面语言保持务实，不做营销式夸张。
