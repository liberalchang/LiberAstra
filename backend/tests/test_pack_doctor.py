"""工作流包体检测试：远程查询全部走 MockTransport。"""

from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx
from fastapi.testclient import TestClient

from liberastra.models import Provider
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.services.pack_doctor import (
    _alignment_check,
    _fps_check,
    _outputs_local_check,
    diagnose_pack,
    offline_pack_warnings,
)
from liberastra.services.workflows import WorkflowPack, load_pack_raw


def _provider() -> Provider:
    return Provider(
        id=1,
        name="mock-comfy",
        type="comfyui",
        base_url="http://mock:8188",
        extra={},
    )


def _files_by_folder(pack: WorkflowPack) -> dict[str, list[str]]:
    files: dict[str, list[str]] = {}
    for entry in (pack.requirements or {}).get("models") or []:
        folder, sep, relative = str(entry).partition("/")
        if sep and relative:
            files.setdefault(folder, []).append(relative)
    return files


def _client(
    pack: WorkflowPack,
    *,
    missing: set[tuple[str, str]] | None = None,
    missing_nodes: set[str] | None = None,
    missing_folders: set[str] | None = None,
) -> ComfyClient:
    files = _files_by_folder(pack)
    for folder, relative in missing or set():
        files[folder] = [item for item in files.get(folder, []) if item != relative]
    classes = {
        str(node.get("class_type"))
        for node in pack.workflow.values()
        if isinstance(node, dict) and node.get("class_type")
    }
    info = {
        name: {"input": {"required": {}}, "output": ["IMAGE"]}
        for name in classes
        if name not in (missing_nodes or set())
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/object_info":
            return httpx.Response(200, json=info)
        if request.url.path.startswith("/models/"):
            folder = request.url.path.split("/models/", 1)[1]
            if folder in (missing_folders or set()):
                return httpx.Response(404, text="not found")
            return httpx.Response(200, json=files.get(folder, []))
        return httpx.Response(404)

    return ComfyClient(
        "http://mock:8188",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _check(result: dict, check_id: str) -> dict:
    return next(check for check in result["checks"] if check["id"] == check_id)


def test_doctor_passes_for_builtin_pack() -> None:
    pack = load_pack_raw("minimax_h3_i2v")

    async def run() -> None:
        result = await diagnose_pack(pack, _provider(), client=_client(pack))
        assert result["status"] == "pass"
        assert _check(result, "nodes")["status"] == "pass"
        assert _check(result, "models")["status"] == "pass"
        assert _check(result, "alignment")["status"] == "pass"

    asyncio.run(run())


def test_doctor_reports_missing_required_model() -> None:
    pack = load_pack_raw("minimax_h3_i2v")
    missing = {("vae", "minimax_h3_video_vae_fp16.safetensors")}

    async def run() -> None:
        result = await diagnose_pack(
            pack, _provider(), client=_client(pack, missing=missing)
        )
        models = _check(result, "models")
        assert result["status"] == "fail"
        assert models["status"] == "fail"
        assert any("minimax_h3_video_vae_fp16" in item["name"] for item in models["items"])

    asyncio.run(run())


def test_doctor_treats_accel_lora_as_optional() -> None:
    pack = load_pack_raw("minimax_h3_i2v")
    missing = {("loras", "minimax_h3_turbo_v4_step600_ema.safetensors")}

    async def run() -> None:
        result = await diagnose_pack(
            pack, _provider(), client=_client(pack, missing=missing)
        )
        models = _check(result, "models")
        assert models["status"] == "warn"
        assert all(item["status"] != "fail" for item in models["items"])

    asyncio.run(run())


def test_doctor_reports_missing_node_type() -> None:
    pack = load_pack_raw("minimax_h3_i2v")

    async def run() -> None:
        result = await diagnose_pack(
            pack, _provider(), client=_client(pack, missing_nodes={"SamplerCustomAdvanced"})
        )
        nodes = _check(result, "nodes")
        assert nodes["status"] == "fail"
        assert any(item["name"] == "SamplerCustomAdvanced" for item in nodes["items"])

    asyncio.run(run())


def test_doctor_skips_unknown_model_folder() -> None:
    pack = load_pack_raw("seedvr2_3b_image_restore")

    async def run() -> None:
        result = await diagnose_pack(
            pack, _provider(), client=_client(pack, missing_folders={"seedvr2"})
        )
        models = _check(result, "models")
        assert models["status"] != "fail"
        assert any(item["status"] == "skip" for item in models["items"])

    asyncio.run(run())


def test_alignment_check_rejects_invalid_offset() -> None:
    pack = load_pack_raw("minimax_h3_i2v")
    length = dict(pack.inputs["length"])
    length["align_offset"] = 20
    broken = replace(pack, inputs={**pack.inputs, "length": length})
    check = _alignment_check(broken)
    assert check["status"] == "fail"


def test_fps_check_warns_on_mismatch() -> None:
    pack = WorkflowPack(
        name="fps-test",
        capability="t2v",
        description="",
        inputs={},
        outputs={},
        workflow={"1": {"class_type": "CreateVideo", "inputs": {"fps": 30}}},
        source="user",
        fps=24,
    )
    assert _fps_check(pack)["status"] == "warn"


def test_outputs_local_check_rejects_missing_node() -> None:
    pack = WorkflowPack(
        name="output-test",
        capability="t2v",
        description="",
        inputs={},
        outputs={"node": "9", "key": "videos"},
        workflow={"1": {"class_type": "CreateVideo", "inputs": {}}},
        source="user",
    )
    assert _outputs_local_check(pack)["status"] == "fail"


def test_offline_warnings_include_alignment_issue() -> None:
    pack = load_pack_raw("minimax_h3_i2v")
    length = dict(pack.inputs["length"])
    length["align_offset"] = 20
    broken = replace(pack, inputs={**pack.inputs, "length": length})
    warnings = offline_pack_warnings(broken)
    assert any("对齐" in warning for warning in warnings)


def test_doctor_api(
    client: TestClient, auth_header: dict[str, str], monkeypatch
) -> None:
    created = client.post(
        "/api/v1/providers",
        json={
            "name": "体检用 ComfyUI",
            "type": "comfyui",
            "base_url": "http://127.0.0.1:8188",
        },
        headers=auth_header,
    )
    assert created.status_code == 201
    provider_id = created.json()["id"]

    async def fake_diagnose(pack, provider):  # noqa: ANN001, ANN202
        return {
            "pack": pack.name,
            "provider": {
                "id": provider.id,
                "name": provider.name,
                "base_url": provider.base_url,
            },
            "status": "pass",
            "checked_at": "2026-11-10T00:00:00Z",
            "summary": {"pass": 1, "warn": 0, "fail": 0, "skip": 0},
            "checks": [
                {"id": "structure", "label": "结构", "status": "pass", "detail": "ok", "items": []}
            ],
        }

    monkeypatch.setattr("liberastra.api.routes.workflows.diagnose_pack", fake_diagnose)
    try:
        resp = client.get(
            f"/api/v1/workflows/minimax_h3_i2v/doctor?provider_id={provider_id}",
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pass"
        assert resp.json()["pack"] == "minimax_h3_i2v"

        missing = client.get(
            f"/api/v1/workflows/no-such-pack/doctor?provider_id={provider_id}",
            headers=auth_header,
        )
        assert missing.status_code == 404
    finally:
        client.delete(f"/api/v1/providers/{provider_id}", headers=auth_header)
