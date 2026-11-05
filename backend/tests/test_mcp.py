"""MCP 工具实现的纯函数测试（不依赖 fastmcp 运行时）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from liberastra.mcp import tools


class FakeClient:
    def __init__(self, responses: dict | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple] = []

    def request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        return self.responses.get((method, path), {"id": "job-1", "status": "queued"})

    def wait_job(self, job_id: str, timeout: float = 3600.0):
        self.calls.append(("WAIT", job_id, {"timeout": timeout}))
        return {"id": job_id, "status": "succeeded", "outputs": []}

    def save_outputs(self, job: dict, out: Path | None, **kwargs):
        return [Path("out.png")]


def test_list_workflows_filters_capability() -> None:
    client = FakeClient(
        {
            ("GET", "/api/v1/workflows"): [
                {"name": "a", "capability": "t2i"},
                {"name": "b", "capability": "i2v"},
            ]
        }
    )
    assert [pack["name"] for pack in tools.list_workflows(client, capability="i2v")] == [
        "b"
    ]


def test_list_assets_passes_filters() -> None:
    client = FakeClient({("GET", "/api/v1/assets"): []})
    tools.list_assets(client, kind="image", limit=5, include_hidden=True)
    method, path, kwargs = client.calls[-1]
    assert (method, path) == ("GET", "/api/v1/assets")
    assert kwargs["params"] == {"limit": 5, "kind": "image", "include_hidden": True}


def test_submit_image_returns_job() -> None:
    client = FakeClient()
    job = tools.submit_image(client, "cat", workflow="qwen_image_21")
    assert job["id"] == "job-1"
    method, path, kwargs = client.calls[-1]
    assert (method, path) == ("POST", "/api/v1/images/generate")
    assert kwargs["json"]["workflow"] == "qwen_image_21"


def test_submit_transcription_uses_file(tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x")
    client = FakeClient()
    tools.submit_transcription(client, str(audio), model="large-v3", formats="json")
    method, path, kwargs = client.calls[-1]
    assert (method, path) == ("POST", "/api/v1/asr")
    assert kwargs["data"]["model"] == "large-v3"
    assert kwargs["data"]["formats"] == "json"
    assert "file" in kwargs["files"]


def test_submit_video_merges_params() -> None:
    client = FakeClient()
    tools.submit_video(
        client, voice="v", script="s", params={"storyboard_count": 2}
    )
    _, path, kwargs = client.calls[-1]
    assert path == "/api/v1/videos/quick"
    assert kwargs["json"]["storyboard_count"] == 2
    assert kwargs["json"]["script"] == "s"


def test_wait_and_job_control_paths() -> None:
    client = FakeClient()
    tools.wait_job(client, "job-1", timeout=5)
    assert client.calls[-1][0] == "WAIT"
    tools.cancel_job(client, "job-1")
    assert client.calls[-1][:2] == ("POST", "/api/v1/jobs/job-1/cancel")
    tools.retry_job(client, "job-1")
    assert client.calls[-1][:2] == ("POST", "/api/v1/jobs/job-1/retry")


def test_create_mcp_builds() -> None:
    pytest.importorskip("fastmcp")
    from liberastra.mcp.server import create_mcp

    mcp = create_mcp()
    assert mcp.name == "LiberAstra"
