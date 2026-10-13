"""MCP 工具实现：与 fastmcp 解耦的纯函数（可直接测试）。"""

from __future__ import annotations

from pathlib import Path

from liberastra.cli.client import ApiClient


def generate_image(
    client: ApiClient,
    prompt: str,
    *,
    width: int = 1024,
    height: int = 1024,
    workflow: str | None = None,
    out_dir: Path | None = None,
) -> str:
    """文生图，返回保存路径。"""
    final = client.submit_and_wait(
        "POST",
        "/api/v1/images/generate",
        json={"prompt": prompt, "width": width, "height": height, "workflow": workflow},
    )
    saved = client.save_outputs(final, out_dir, default_name="image", kind="image")
    return str(saved[0])


def synthesize_speech(
    client: ApiClient, text: str, voice: str, *, fmt: str = "mp3", out_dir: Path | None = None
) -> str:
    """文字转语音，返回保存路径。"""
    final = client.submit_and_wait(
        "POST", "/api/v1/tts", json={"text": text, "voice": voice, "format": fmt}
    )
    saved = client.save_outputs(final, out_dir, default_name="speech", kind="audio")
    return str(saved[0])


def transcribe(client: ApiClient, file_path: str, *, language: str | None = None) -> str:
    """语音转文字，返回文本。"""
    path = Path(file_path)
    with path.open("rb") as fh:
        final = client.submit_and_wait(
            "POST",
            "/api/v1/asr",
            files={"file": (path.name, fh)},
            data={"formats": "txt", **({"language": language} if language else {})},
        )
    text_out = next((o for o in final["outputs"] if o.get("type") == "text"), None)
    return text_out["content"] if text_out else ""


def create_quick_video(
    client: ApiClient,
    topic: str,
    voice: str,
    *,
    aspect: str = "9:16",
    out_dir: Path | None = None,
) -> str:
    """一句话出短视频，返回保存路径。"""
    final = client.submit_and_wait(
        "POST", "/api/v1/videos/quick", json={"topic": topic, "voice": voice, "aspect": aspect},
        timeout=7200,
    )
    saved = client.save_outputs(final, out_dir, default_name="video", kind="video")
    return str(saved[0])


def get_job(client: ApiClient, job_id: str) -> dict:
    """查询任务状态。"""
    return client.request("GET", f"/api/v1/jobs/{job_id}")  # type: ignore[no-any-return]
