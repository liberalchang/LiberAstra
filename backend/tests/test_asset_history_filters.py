"""素材历史按功能过滤；图片编辑 function 与隐藏上传。"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Job, User
from liberastra.storage import save_bytes


def _create_image_job(kind: str, function: str) -> tuple[str, int]:
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        job = Job(
            kind=kind,
            function=function,
            status="succeeded",
            owner_id=user.id,
            params={},
            outputs=[],
        )
        db.add(job)
        db.flush()
        rel = f"outputs/{job.id}/{uuid.uuid4().hex}.png"
        save_bytes(b"pixel", rel)
        asset = Asset(
            kind="image",
            path=rel,
            owner_id=user.id,
            job_id=job.id,
            hidden=False,
            size=5,
            meta={"name": f"{function}-{uuid.uuid4().hex[:6]}"},
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return job.id, asset.id
    finally:
        db.close()


def _asset_ids(client: TestClient, auth_header: dict[str, str], **params) -> set[int]:
    response = client.get("/api/v1/assets", params=params, headers=auth_header)
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()}


def test_asset_history_filters_by_job_function(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    _, generated = _create_image_job("image.generate", "image.generate")
    _, i2i = _create_image_job("image.edit", "image.i2i")
    _, upscale = _create_image_job("image.edit", "image.upscale")
    _, legacy = _create_image_job("image.edit", "image.edit")

    generated_ids = _asset_ids(
        client, auth_header, kind="image", job_function="image.generate"
    )
    assert generated in generated_ids
    assert upscale not in generated_ids

    i2i_ids = _asset_ids(
        client, auth_header, kind="image", job_function="image.i2i,image.edit"
    )
    assert {i2i, legacy} <= i2i_ids
    assert upscale not in i2i_ids

    upscale_ids = _asset_ids(
        client, auth_header, kind="image", job_function="image.upscale"
    )
    assert upscale_ids == {upscale}

    edit_kind_ids = _asset_ids(client, auth_header, kind="image", job_kind="image.edit")
    assert {i2i, upscale, legacy} <= edit_kind_ids


def test_image_edit_stores_function(
    client: TestClient,
    auth_header: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.services import image as image_service

    class _FakeImageAdapter:
        async def edit(self, **kwargs) -> list[tuple[str, bytes]]:
            return [("edited.png", b"PNG-DATA")]

    monkeypatch.setattr(image_service, "build_image_adapter", lambda record: _FakeImageAdapter())
    provider = client.post(
        "/api/v1/providers",
        json={"name": f"mock-image-{uuid.uuid4().hex}", "type": "openai_images", "base_url": "http://mock/v1"},
        headers=auth_header,
    )
    assert provider.status_code == 201, provider.text

    response = client.post(
        "/api/v1/images/edit?wait=true",
        headers=auth_header,
        data={
            "provider_id": str(provider.json()["id"]),
            "prompt": "放大",
            "capability": "upscale",
        },
        files=[("images", ("in.png", b"input", "image/png"))],
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["kind"] == "image.edit"
    assert job["function"] == "image.upscale"
    assert job["status"] == "succeeded", job["error"]


def test_hidden_upload_and_publish(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    upload = client.post(
        "/api/v1/uploads?as_asset=true&kind=image&hidden=true",
        headers=auth_header,
        files={"file": ("hidden.png", b"hidden-bytes", "image/png")},
    )
    assert upload.status_code == 201, upload.text
    asset_id = upload.json()["asset_id"]

    detail = client.get(f"/api/v1/assets/{asset_id}", headers=auth_header)
    assert detail.status_code == 200
    assert detail.json()["hidden"] is True

    assert asset_id not in _asset_ids(client, auth_header, kind="image")
    assert asset_id in _asset_ids(client, auth_header, kind="image", include_hidden=True)

    published = client.post(f"/api/v1/assets/{asset_id}/publish", headers=auth_header)
    assert published.status_code == 200
    assert published.json()["hidden"] is False
    assert asset_id in _asset_ids(client, auth_header, kind="image")
