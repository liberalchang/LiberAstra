"""fastmcp MCP Server：把 LiberAstra 能力暴露为 Agent 工具（stdio 传输）。

凭据读取顺序：环境变量 LIBERASTRA_SERVER / LIBERASTRA_TOKEN > ~/.liberastra/config.toml。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

INSTRUCTIONS = """LiberAstra is a self-hosted AIGC orchestration desk.

Generation is asynchronous. `submit_*` tools return a job object immediately; use
`wait_job` to follow it, or call the blocking convenience tools (`generate_image`,
`synthesize_speech`, `transcribe`, `create_video`) when a single call is acceptable.

Credentials come from LIBERASTRA_SERVER / LIBERASTRA_TOKEN, then
~/.liberastra/config.toml. Run `astra login` once if the server is not configured.

Use the `list_*` tools to discover voices, workflow packs, providers, and assets
instead of guessing names."""

_SKILL_FALLBACK = """# LiberAstra Skill

Use the `astra` CLI or the MCP tools to call a running LiberAstra server.
Generate commands submit asynchronous jobs. Use `--json` for machine-readable
output, and `--no-wait` plus `astra job wait` for long jobs.

See https://github.com/liberalchang/LiberAstra for the current CLI reference."""


def _call(fn: Callable[[], Any]) -> Any:
    """把 CLI 异常转成 Agent 可恢复的结构化错误。"""
    from liberastra.cli.client import CliError

    try:
        return fn()
    except CliError as exc:
        return {
            "ok": False,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "exit_code": exc.exit_code,
            },
        }


def create_mcp() -> Any:
    from fastmcp import FastMCP

    from liberastra.cli.client import ApiClient
    from liberastra.mcp import tools

    mcp = FastMCP("LiberAstra", instructions=INSTRUCTIONS)

    def _client() -> ApiClient:
        return ApiClient.from_config()

    # ---- 阻塞式便捷工具 ----

    @mcp.tool()
    def generate_image(
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        workflow: str | None = None,
    ) -> Any:
        """文生图。返回本地文件路径。"""

        def run() -> Any:
            with _client() as client:
                return tools.generate_image(
                    client, prompt, width=width, height=height, workflow=workflow
                )

        return _call(run)

    @mcp.tool()
    def synthesize_speech(
        text: str,
        voice: str,
        fmt: str = "mp3",
        provider_id: int | None = None,
    ) -> Any:
        """文字转语音。voice 为音色名（如 zh-CN-XiaoxiaoNeural）。返回本地文件路径。"""

        def run() -> Any:
            with _client() as client:
                return tools.synthesize_speech(
                    client, text, voice, fmt=fmt, provider_id=provider_id
                )

        return _call(run)

    @mcp.tool()
    def transcribe(
        file_path: str,
        language: str | None = None,
        model: str | None = None,
        formats: str = "txt",
    ) -> Any:
        """语音转文字。返回转写文本。"""

        def run() -> Any:
            with _client() as client:
                return tools.transcribe(
                    client,
                    file_path,
                    language=language,
                    model=model,
                    formats=formats,
                )

        return _call(run)

    @mcp.tool()
    def create_video(
        topic: str | None = None,
        script: str | None = None,
        voice: str = "",
        aspect: str = "9:16",
    ) -> Any:
        """一句话出短视频（LLM 脚本 → 分镜 → 合成）。返回本地文件路径。"""

        def run() -> Any:
            if not topic and not script:
                return {
                    "ok": False,
                    "error": {
                        "type": "CliError",
                        "message": "请提供 topic 或 script",
                        "exit_code": 1,
                    },
                }
            with _client() as client:
                return tools.create_quick_video(
                    client, topic, voice, script=script, aspect=aspect
                )

        return _call(run)

    @mcp.tool()
    def get_job(job_id: str) -> Any:
        """查询 LiberAstra 任务状态。"""

        def run() -> Any:
            with _client() as client:
                return tools.get_job(client, job_id)

        return _call(run)

    # ---- 异步提交：立即返回 job ----

    @mcp.tool()
    def submit_image(
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        workflow: str | None = None,
        provider_id: int | None = None,
    ) -> Any:
        """提交文生图任务，立即返回 job。用 wait_job 跟进。"""

        def run() -> Any:
            with _client() as client:
                return tools.submit_image(
                    client,
                    prompt,
                    width=width,
                    height=height,
                    workflow=workflow,
                    provider_id=provider_id,
                )

        return _call(run)

    @mcp.tool()
    def submit_speech(
        text: str,
        voice: str,
        fmt: str = "mp3",
        provider_id: int | None = None,
    ) -> Any:
        """提交文字转语音任务，立即返回 job。用 wait_job 跟进。"""

        def run() -> Any:
            with _client() as client:
                return tools.submit_speech(
                    client, text, voice, fmt=fmt, provider_id=provider_id
                )

        return _call(run)

    @mcp.tool()
    def submit_transcription(
        file_path: str,
        language: str | None = None,
        model: str | None = None,
        formats: str = "txt",
    ) -> Any:
        """提交语音转文字任务，立即返回 job。用 wait_job 跟进。"""

        def run() -> Any:
            with _client() as client:
                return tools.submit_transcription(
                    client,
                    file_path,
                    language=language,
                    model=model,
                    formats=formats,
                )

        return _call(run)

    @mcp.tool()
    def submit_video(
        voice: str,
        topic: str | None = None,
        script: str | None = None,
        aspect: str = "9:16",
    ) -> Any:
        """提交快速创作任务，立即返回 job。用 wait_job 跟进。"""

        def run() -> Any:
            if not topic and not script:
                return {
                    "ok": False,
                    "error": {
                        "type": "CliError",
                        "message": "请提供 topic 或 script",
                        "exit_code": 1,
                    },
                }
            with _client() as client:
                return tools.submit_video(
                    client,
                    voice=voice,
                    topic=topic,
                    script=script,
                    aspect=aspect,
                )

        return _call(run)

    # ---- 发现类 ----

    @mcp.tool()
    def list_voices() -> Any:
        """列出已保存的音色。"""

        def run() -> Any:
            with _client() as client:
                return tools.list_voices(client)

        return _call(run)

    @mcp.tool()
    def list_workflows(capability: str | None = None) -> Any:
        """列出工作流包；可按 t2i/i2i/i2v/t2v/avatar/motion/upscale/v2v 过滤。"""

        def run() -> Any:
            with _client() as client:
                return tools.list_workflows(client, capability=capability)

        return _call(run)

    @mcp.tool()
    def list_providers() -> Any:
        """列出服务提供方。"""

        def run() -> Any:
            with _client() as client:
                return tools.list_providers(client)

        return _call(run)

    @mcp.tool()
    def list_assets(
        kind: str | None = None,
        job_id: str | None = None,
        limit: int = 20,
        include_hidden: bool = False,
    ) -> Any:
        """列出资产。"""

        def run() -> Any:
            with _client() as client:
                return tools.list_assets(
                    client,
                    kind=kind,
                    job_id=job_id,
                    limit=limit,
                    include_hidden=include_hidden,
                )

        return _call(run)

    @mcp.tool()
    def get_asset(asset_id: int) -> Any:
        """读取单个资产。"""

        def run() -> Any:
            with _client() as client:
                return tools.get_asset(client, asset_id)

        return _call(run)

    # ---- 任务控制 ----

    @mcp.tool()
    def wait_job(job_id: str, timeout: float = 3600.0) -> Any:
        """等待任务结束并返回最终 job。"""

        def run() -> Any:
            with _client() as client:
                return tools.wait_job(client, job_id, timeout=timeout)

        return _call(run)

    @mcp.tool()
    def cancel_job(job_id: str) -> Any:
        """取消任务。"""

        def run() -> Any:
            with _client() as client:
                return tools.cancel_job(client, job_id)

        return _call(run)

    @mcp.tool()
    def retry_job(job_id: str) -> Any:
        """用原参数重试任务。"""

        def run() -> Any:
            with _client() as client:
                return tools.retry_job(client, job_id)

        return _call(run)

    @mcp.resource("liberastra://skill", name="LiberAstra skill", mime_type="text/markdown")
    def liberastra_skill() -> str:
        skill_path = (
            Path(__file__).resolve().parents[3] / "skills" / "liberastra" / "SKILL.md"
        )
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8")
        return _SKILL_FALLBACK

    @mcp.resource(
        "liberastra://workflows",
        name="Workflow packs",
        mime_type="application/json",
    )
    def workflow_catalog() -> str:
        with _client() as client:
            data = _call(lambda: tools.list_workflows(client))
        return json.dumps(data, ensure_ascii=False)

    return mcp


def run_mcp() -> None:
    create_mcp().run()
