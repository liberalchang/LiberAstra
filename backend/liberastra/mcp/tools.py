"""MCP 工具实现：与 fastmcp 解耦的纯函数（可直接测试）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    client: ApiClient,
    text: str,
    voice: str,
    *,
    fmt: str = "mp3",
    provider_id: int | None = None,
    options: dict[str, Any] | None = None,
    out_dir: Path | None = None,
) -> str:
    """文字转语音，返回保存路径。"""
    final = client.submit_and_wait(
        "POST",
        "/api/v1/tts",
        json={
            "text": text,
            "voice": voice,
            "format": fmt,
            "provider_id": provider_id,
            "options": options or {},
        },
    )
    saved = client.save_outputs(final, out_dir, default_name="speech", kind="audio")
    return str(saved[0])


def transcribe(
    client: ApiClient,
    file_path: str,
    *,
    language: str | None = None,
    model: str | None = None,
    formats: str = "txt",
) -> str:
    """语音转文字，返回文本。"""
    path = Path(file_path)
    data = {"formats": formats}
    if language:
        data["language"] = language
    if model:
        data["model"] = model
    with path.open("rb") as fh:
        final = client.submit_and_wait(
            "POST",
            "/api/v1/asr",
            files={"file": (path.name, fh)},
            data=data,
        )
    text_out = next((o for o in final["outputs"] if o.get("type") == "text"), None)
    return text_out["content"] if text_out else ""


def create_quick_video(
    client: ApiClient,
    topic: str | None,
    voice: str,
    *,
    script: str | None = None,
    aspect: str = "9:16",
    params: dict[str, Any] | None = None,
    out_dir: Path | None = None,
) -> str:
    """一句话出短视频，返回保存路径。"""
    payload = {
        "topic": topic,
        "script": script,
        "voice": voice,
        "aspect": aspect,
        **(params or {}),
    }
    final = client.submit_and_wait(
        "POST", "/api/v1/videos/quick", json=payload, timeout=7200
    )
    saved = client.save_outputs(final, out_dir, default_name="video", kind="video")
    return str(saved[0])


def get_job(client: ApiClient, job_id: str) -> dict:
    """查询任务状态。"""
    return client.request("GET", f"/api/v1/jobs/{job_id}")  # type: ignore[no-any-return]


# ---- 发现类 ----


def list_voices(client: ApiClient) -> list[dict]:
    return client.request("GET", "/api/v1/voices")  # type: ignore[no-any-return]


def list_workflows(client: ApiClient, *, capability: str | None = None) -> list[dict]:
    packs = client.request("GET", "/api/v1/workflows")
    if capability:
        return [pack for pack in packs if pack.get("capability") == capability]
    return packs  # type: ignore[no-any-return]


def list_providers(client: ApiClient) -> list[dict]:
    return client.request("GET", "/api/v1/providers")  # type: ignore[no-any-return]


def workflow_doctor(
    client: ApiClient, name: str, provider_id: int | None = None
) -> dict:
    params = {"provider_id": provider_id} if provider_id is not None else None
    return client.request(  # type: ignore[no-any-return]
        "GET", f"/api/v1/workflows/{name}/doctor", params=params
    )


def list_assets(
    client: ApiClient,
    *,
    kind: str | None = None,
    job_id: str | None = None,
    limit: int = 20,
    include_hidden: bool = False,
) -> list[dict]:
    params: dict[str, Any] = {"limit": limit}
    if kind:
        params["kind"] = kind
    if job_id:
        params["job_id"] = job_id
    if include_hidden:
        params["include_hidden"] = True
    return client.request("GET", "/api/v1/assets", params=params)  # type: ignore[no-any-return]


def get_asset(client: ApiClient, asset_id: int) -> dict:
    return client.request("GET", f"/api/v1/assets/{asset_id}")  # type: ignore[no-any-return]


# ---- 提交类：立即返回 job，由 wait_job 跟进 ----


def submit_image(
    client: ApiClient,
    prompt: str,
    *,
    width: int = 1024,
    height: int = 1024,
    workflow: str | None = None,
    provider_id: int | None = None,
) -> dict:
    return client.request(
        "POST",
        "/api/v1/images/generate",
        json={
            "prompt": prompt,
            "width": width,
            "height": height,
            "workflow": workflow,
            "provider_id": provider_id,
        },
    )  # type: ignore[no-any-return]


def submit_speech(
    client: ApiClient,
    text: str,
    voice: str,
    *,
    fmt: str = "mp3",
    provider_id: int | None = None,
    options: dict[str, Any] | None = None,
) -> dict:
    return client.request(
        "POST",
        "/api/v1/tts",
        json={
            "text": text,
            "voice": voice,
            "format": fmt,
            "provider_id": provider_id,
            "options": options or {},
        },
    )  # type: ignore[no-any-return]


def submit_transcription(
    client: ApiClient,
    file_path: str,
    *,
    language: str | None = None,
    model: str | None = None,
    formats: str = "txt",
) -> dict:
    path = Path(file_path)
    data = {"formats": formats}
    if language:
        data["language"] = language
    if model:
        data["model"] = model
    with path.open("rb") as fh:
        return client.request(
            "POST",
            "/api/v1/asr",
            files={"file": (path.name, fh)},
            data=data,
        )  # type: ignore[no-any-return]


def submit_video(
    client: ApiClient,
    *,
    voice: str,
    topic: str | None = None,
    script: str | None = None,
    aspect: str = "9:16",
    params: dict[str, Any] | None = None,
) -> dict:
    payload = {
        "topic": topic,
        "script": script,
        "voice": voice,
        "aspect": aspect,
        **(params or {}),
    }
    return client.request("POST", "/api/v1/videos/quick", json=payload)  # type: ignore[no-any-return]


def wait_job(client: ApiClient, job_id: str, timeout: float = 3600.0) -> dict:
    return client.wait_job(job_id, timeout=timeout)


def cancel_job(client: ApiClient, job_id: str) -> dict:
    return client.request("POST", f"/api/v1/jobs/{job_id}/cancel")  # type: ignore[no-any-return]


def retry_job(client: ApiClient, job_id: str) -> dict:
    return client.request("POST", f"/api/v1/jobs/{job_id}/retry")  # type: ignore[no-any-return]
