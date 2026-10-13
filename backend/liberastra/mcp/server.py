"""fastmcp MCP Server：把 LiberAstra 能力暴露为 Agent 工具（stdio 传输）。

凭据读取顺序：环境变量 LIBERASTRA_SERVER / LIBERASTRA_TOKEN > ~/.liberastra/config.toml。
"""

from __future__ import annotations

from typing import Any


def create_mcp() -> Any:
    from fastmcp import FastMCP

    from liberastra.cli.client import ApiClient
    from liberastra.mcp import tools

    mcp = FastMCP("LiberAstra")

    def _client() -> ApiClient:
        return ApiClient.from_config()

    @mcp.tool()
    def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> str:
        """文生图。返回本地文件路径。"""
        with _client() as client:
            return tools.generate_image(client, prompt, width=width, height=height)

    @mcp.tool()
    def synthesize_speech(text: str, voice: str, fmt: str = "mp3") -> str:
        """文字转语音。voice 为音色名（如 zh-CN-XiaoxiaoNeural）。返回本地文件路径。"""
        with _client() as client:
            return tools.synthesize_speech(client, text, voice, fmt=fmt)

    @mcp.tool()
    def transcribe(file_path: str, language: str | None = None) -> str:
        """语音转文字。返回转写文本。"""
        with _client() as client:
            return tools.transcribe(client, file_path, language=language)

    @mcp.tool()
    def create_video(topic: str, voice: str, aspect: str = "9:16") -> str:
        """一句话出短视频（LLM 脚本 → 分镜 → 合成）。返回本地文件路径。"""
        with _client() as client:
            return tools.create_quick_video(client, topic, voice, aspect=aspect)

    @mcp.tool()
    def get_job(job_id: str) -> dict:
        """查询 LiberAstra 任务状态。"""
        with _client() as client:
            return tools.get_job(client, job_id)

    return mcp


def run_mcp() -> None:
    create_mcp().run()
