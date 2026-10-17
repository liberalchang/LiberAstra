"""Job 队列与 LLM 聊天任务测试：提交、wait、取消、重试、SSE。"""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def llm_provider(client: TestClient, auth_header: dict[str, str]) -> int:
    resp = client.post(
        "/api/v1/providers",
        json={"name": "mock-llm", "type": "openai_compatible", "base_url": "http://mock/v1"},
        headers=auth_header,
    )
    assert resp.status_code == 201
    return resp.json()["id"]  # noqa: RET504


class _FakeAdapter:
    def __init__(self, text: str = "你好", delay: float = 0.0) -> None:
        self._text = text
        self._delay = delay

    async def chat(self, *, model: str, messages: list, **params) -> str:
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._text


def _patch_adapter(monkeypatch: pytest.MonkeyPatch, adapter: _FakeAdapter) -> None:
    from liberastra.services import llm as llm_service

    monkeypatch.setattr(llm_service, "build_llm_adapter", lambda record, **_kw: adapter)


def _wait_status(client: TestClient, job_id: str, headers: dict[str, str], timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        time.sleep(0.1)
    raise AssertionError("任务未在超时内结束")


def test_chat_job_wait(
    client: TestClient,
    auth_header: dict[str, str],
    llm_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_adapter(monkeypatch, _FakeAdapter("你好，世界"))
    resp = client.post(
        "/api/v1/llm/chat?wait=true",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth_header,
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "succeeded"
    assert job["progress"] == 1.0
    assert job["outputs"][0]["content"] == "你好，世界"


def test_chat_job_cancel_and_retry(
    client: TestClient,
    auth_header: dict[str, str],
    llm_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_adapter(monkeypatch, _FakeAdapter(delay=0.5))
    job = client.post(
        "/api/v1/llm/chat",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth_header,
    ).json()

    cancel = client.post(f"/api/v1/jobs/{job['id']}/cancel", headers=auth_header)
    assert cancel.status_code == 200
    final = _wait_status(client, job["id"], auth_header)
    assert final["status"] == "canceled"

    retry = client.post(f"/api/v1/jobs/{job['id']}/retry", headers=auth_header)
    assert retry.status_code == 202
    assert _wait_status(client, retry.json()["id"], auth_header)["status"] == "succeeded"


def test_job_events_sse(
    client: TestClient,
    auth_header: dict[str, str],
    llm_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_adapter(monkeypatch, _FakeAdapter("流式"))
    job = client.post(
        "/api/v1/llm/chat",
        json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth_header,
    ).json()

    statuses: list[str] = []
    with client.stream(
        "GET", f"/api/v1/jobs/{job['id']}/events", headers=auth_header
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        for line in resp.iter_lines():
            if line.startswith("data:"):
                statuses.append(json.loads(line.removeprefix("data:").strip())["status"])
                if statuses[-1] in ("succeeded", "failed", "canceled"):
                    break

    # 快照可能在连接前已进入 running/succeeded（快任务），只断言终态正确送达
    assert statuses[-1] == "succeeded"


def test_job_ownership_isolation(client: TestClient, auth_header: dict[str, str]) -> None:
    assert client.get("/api/v1/jobs/nonexistent", headers=auth_header).status_code == 404
    assert client.get("/api/v1/jobs", headers=auth_header).status_code == 200
