# 参与贡献

[English](#english)

改动通过 Pull Request 进入 `main`。行为问题用 [Bug 模板](https://github.com/liberalchang/LiberAstra/issues/new?template=bug_report.yml)，新能力用 [Feature 模板](https://github.com/liberalchang/LiberAstra/issues/new?template=feature_request.yml)。安全问题不要开公开 Issue，见 [SECURITY.md](SECURITY.md)。

## 本地跑起来

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node.js 20+。Ollama、ComfyUI、语音插件不是贡献本仓库的前置条件；只改界面或 API 时可以不装。

```bash
# 后端
cd backend
uv venv .venv && uv pip install -e ".[dev]"
uv run pytest
uv run ruff check .
uv run astra serve --reload
```

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

API 在 `http://localhost:8000`（交互文档 `/docs`）。前端开发服务器在 `http://localhost:5173`，把 `/api` 代理到 8000。提交前对前端跑一次 `npm run build`。

Docker 路径见 [docs/deployment.md](docs/deployment.md)。

## Pull Request

- 一个 PR 做一件事，说明用户能看到的变化。
- 不要提交 `.env`、`data/`、安装包、模型权重或 API Token。
- 界面文案同时改中文和英文（`frontend/src/i18n`）。明暗主题一起看。
- 后端改动带测试。前端改动至少保证 `npm run build` 通过。
- CI 会跑 Ruff、pytest 和前端构建，见 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)。

## English

Open a pull request against `main`. Use the bug or feature issue forms. Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.

```bash
cd backend && uv venv .venv && uv pip install -e ".[dev]"
uv run pytest && uv run ruff check .
uv run astra serve --reload
```

In another terminal: `cd frontend && npm install && npm run dev`. API: `http://localhost:8000`. UI dev server: `http://localhost:5173`.

Do not commit secrets, `data/`, installers, or model weights. Keep Chinese and English UI strings together. Backend changes need tests. CI runs Ruff, pytest, and the frontend build.
